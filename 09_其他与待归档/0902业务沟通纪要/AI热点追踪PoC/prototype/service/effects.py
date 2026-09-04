from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from .database import add_audit, connection, fetch_all, fetch_one, json_text, new_id, now_iso
from .drafts import BOOST_ACTIONS_BY_PLATFORM, PLATFORM_LABELS, get_draft
from .events import get_event


ALLOWED_PLATFORMS = set(BOOST_ACTIONS_BY_PLATFORM)
ALLOWED_DATA_SOURCES = {"existing_collector", "business_push", "manual_evidence"}
ALLOWED_METRICS = {"view_count", "like_count", "comment_count", "share_count", "favorite_count"}
ALLOWED_DECISIONS = {"create_followup_boost", "watch", "no_boost", "manual_review"}


def _valid_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _publication_detail(publication: dict[str, Any]) -> dict[str, Any]:
    publication = dict(publication)
    publication["original_draft"] = get_draft(publication["original_draft_id"])
    publication["event"] = get_event(publication["event_id"])
    publication["snapshots"] = fetch_all(
        "SELECT * FROM publication_metric_snapshots WHERE publication_id=? ORDER BY captured_at ASC",
        (publication["publication_id"],),
    )
    publication["evaluations"] = fetch_all(
        "SELECT * FROM publication_evaluations WHERE publication_id=? ORDER BY evaluated_at DESC",
        (publication["publication_id"],),
    )
    publication["latest_evaluation"] = publication["evaluations"][0] if publication["evaluations"] else None
    return publication


def list_publications(status: str | None = None, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    where = "WHERE tracking_status=?" if status else ""
    params: tuple[Any, ...] = (status, limit, offset) if status else (limit, offset)
    rows = fetch_all(
        f"SELECT * FROM original_publications {where} ORDER BY submitted_at DESC LIMIT ? OFFSET ?",
        params,
    )
    return [_publication_detail(item) for item in rows]


def count_publications(status: str | None = None) -> int:
    where = "WHERE tracking_status=?" if status else ""
    params = (status,) if status else ()
    row = fetch_one(f"SELECT COUNT(*) total FROM original_publications {where}", params) or {}
    return int(row.get("total") or 0)


def get_publication(publication_id: str) -> dict[str, Any] | None:
    publication = fetch_one("SELECT * FROM original_publications WHERE publication_id=?", (publication_id,))
    return _publication_detail(publication) if publication else None


def create_publication(
    *,
    original_draft_id: str,
    platform: str,
    content_url: str,
    content_title: str | None,
    platform_content_id: str | None,
    published_at: str,
    submitted_by: str,
) -> dict[str, Any]:
    draft = get_draft(original_draft_id)
    if not draft:
        raise LookupError("原创增长草案不存在")
    if draft.get("draft_purpose") != "original_growth":
        raise ValueError("只有原创增长草案可以登记原创发布结果")
    if draft.get("task_status") != "approved":
        raise ValueError("原创增长草案审批通过后才能登记发布结果")
    if platform not in ALLOWED_PLATFORMS:
        raise ValueError("暂不支持该发布平台")
    if not _valid_http_url(content_url):
        raise ValueError("原创内容链接必须是可访问的 HTTP/HTTPS 地址")
    if fetch_one("SELECT publication_id FROM original_publications WHERE content_url=?", (content_url,)):
        raise ValueError("该原创内容链接已登记")
    publication_id = new_id("PUB")
    timestamp = now_iso()
    with connection() as db:
        db.execute(
            """
            INSERT INTO original_publications (
                publication_id, event_id, original_draft_id, platform, content_url,
                content_title, platform_content_id, published_at, submitted_by,
                submitted_at, tracking_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'tracking', ?)
            """,
            (
                publication_id,
                draft["event_id"],
                original_draft_id,
                platform,
                content_url,
                content_title,
                platform_content_id,
                published_at,
                submitted_by,
                timestamp,
                timestamp,
            ),
        )
    publication = get_publication(publication_id) or {}
    add_audit(
        "create",
        "original_publication",
        publication_id,
        actor_type="operator",
        actor_id=submitted_by,
        after=publication,
    )
    return publication


def add_snapshot(
    publication_id: str,
    *,
    captured_at: str,
    data_source: str,
    metrics: dict[str, int],
    unavailable_reason: str | None,
    note: str | None,
    actor_id: str,
) -> dict[str, Any]:
    publication = get_publication(publication_id)
    if not publication:
        raise LookupError("原创发布记录不存在")
    if data_source not in ALLOWED_DATA_SOURCES:
        raise ValueError("不支持的数据来源")
    unknown_fields = set(metrics) - ALLOWED_METRICS
    if unknown_fields:
        raise ValueError(f"包含不支持的指标：{', '.join(sorted(unknown_fields))}")
    normalized = {key: int(value) for key, value in metrics.items()}
    if any(value < 0 for value in normalized.values()):
        raise ValueError("指标值不能小于0")
    if not normalized and not (unavailable_reason or "").strip():
        raise ValueError("没有采集到指标时必须填写不可采原因")
    snapshot_id = new_id("SNP")
    timestamp = now_iso()
    with connection() as db:
        db.execute(
            """
            INSERT INTO publication_metric_snapshots (
                snapshot_id, publication_id, captured_at, data_source, metrics_json,
                unavailable_reason, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                publication_id,
                captured_at,
                data_source,
                json_text(normalized),
                unavailable_reason,
                note,
                timestamp,
            ),
        )
        db.execute(
            "UPDATE original_publications SET tracking_status='tracking', updated_at=? WHERE publication_id=?",
            (timestamp, publication_id),
        )
    snapshot = fetch_one("SELECT * FROM publication_metric_snapshots WHERE snapshot_id=?", (snapshot_id,)) or {}
    add_audit(
        "create",
        "publication_metric_snapshot",
        snapshot_id,
        actor_type="operator" if data_source == "manual_evidence" else "system",
        actor_id=actor_id,
        after=snapshot,
    )
    return get_publication(publication_id) or publication


def _metric_delta(baseline: dict[str, Any], latest: dict[str, Any]) -> tuple[dict[str, int], str]:
    baseline_metrics = baseline.get("metrics") or {}
    latest_metrics = latest.get("metrics") or {}
    keys = sorted(set(baseline_metrics) | set(latest_metrics))
    delta = {key: int(latest_metrics.get(key, 0)) - int(baseline_metrics.get(key, 0)) for key in keys}
    if any(value < 0 for value in delta.values()):
        return delta, "data_anomaly"
    if any(value > 0 for value in delta.values()):
        return delta, "growth_observed"
    return delta, "no_growth_observed"


def _create_followup_boost_draft(
    publication: dict[str, Any],
    evaluation_id: str,
    decision_reason: str,
) -> dict[str, Any]:
    existing = fetch_one(
        """
        SELECT * FROM task_drafts
        WHERE event_id=? AND draft_purpose='original_post_boost' AND target_submission_id=?
        """,
        (publication["event_id"], publication["publication_id"]),
    )
    if existing:
        return get_draft(existing["task_draft_id"]) or existing
    platform = publication["platform"]
    actions = BOOST_ACTIONS_BY_PLATFORM.get(platform, [])[:2]
    if not actions:
        raise ValueError("当前平台没有配置可用的加热动作")
    original_draft = publication.get("original_draft") or {}
    event = publication.get("event") or {}
    task_draft_id = new_id("DRF")
    timestamp = now_iso()
    deadline = (datetime.now().astimezone() + timedelta(hours=6)).isoformat(timespec="minutes")
    title = publication.get("content_title") or original_draft.get("task_title") or publication["publication_id"]
    brief = (
        "该草案作用于护卫军用户已经发布的原创内容，用于发布后效果追踪中的二次加热；"
        "它不同于直接加热外部热点源文章或视频。\n\n"
        f"原创内容：{title}\n目标链接：{publication['content_url']}\n"
        f"后效判断：{decision_reason}\n"
        "运营需复核指标来源、增量窗口、任务人数、频控和评论表达后再审批。"
    )
    evidence_source_ids = original_draft.get("evidence_source_ids") or []
    with connection() as db:
        db.execute(
            """
            INSERT INTO task_drafts (
                task_draft_id, event_id, draft_purpose, target_source_id,
                target_submission_id, trigger_evaluation_id, target_url,
                target_content_title, task_type, task_title, task_brief,
                recommended_platforms_json, target_member_tags_json,
                engagement_actions_json, response_deadline, evidence_source_ids_json,
                prohibited_claims_json, risk_notes_json, task_status, created_at, updated_at
            ) VALUES (?, ?, 'original_post_boost', '', ?, ?, ?, ?,
                'original_post_boost', ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'draft_pending_review', ?, ?)
            """,
            (
                task_draft_id,
                publication["event_id"],
                publication["publication_id"],
                evaluation_id,
                publication["content_url"],
                title,
                f"原创后二次加热｜{title}",
                brief,
                json_text([platform]),
                json_text([PLATFORM_LABELS.get(platform, f"{platform}能力")]),
                json_text(actions),
                deadline,
                json_text(evidence_source_ids),
                json_text([
                    "不得要求复制统一评论",
                    "不得把单次指标增量表述为全平台热点",
                    "不得补写采集指标之外的传播效果",
                ]),
                json_text([
                    f"由原创发布后效评估 {evaluation_id} 触发",
                    "加热决策由运营确认，系统仅计算同一内容在两个快照间的可核验增量",
                    "需遵守目标平台动作、人数和时间窗规则",
                ]),
                timestamp,
                timestamp,
            ),
        )
    draft = get_draft(task_draft_id) or {}
    add_audit("create", "task_draft", task_draft_id, actor_type="system", actor_id="effect-engine", after=draft)
    return draft


def evaluate_publication(
    publication_id: str,
    *,
    decision: str,
    decision_reason: str,
    evaluated_by: str,
) -> dict[str, Any]:
    publication = get_publication(publication_id)
    if not publication:
        raise LookupError("原创发布记录不存在")
    if decision not in ALLOWED_DECISIONS:
        raise ValueError("不支持的后效处理结论")
    snapshots = [item for item in publication.get("snapshots", []) if item.get("metrics")]
    if len(snapshots) < 2:
        raise ValueError("至少需要两个包含指标的时间快照，才能判断传播是否增长")
    baseline, latest = snapshots[0], snapshots[-1]
    if baseline["snapshot_id"] == latest["snapshot_id"]:
        raise ValueError("基准快照与最新快照不能相同")
    delta_metrics, growth_status = _metric_delta(baseline, latest)
    if growth_status == "data_anomaly" and decision == "create_followup_boost":
        raise ValueError("指标出现回退或口径变化，必须先人工核验，不能直接生成二次加热草案")
    evaluation_id = new_id("EVL")
    timestamp = now_iso()
    with connection() as db:
        db.execute(
            """
            INSERT INTO publication_evaluations (
                evaluation_id, publication_id, baseline_snapshot_id,
                latest_snapshot_id, delta_metrics_json, growth_status, decision,
                decision_reason, evaluated_by, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_id,
                publication_id,
                baseline["snapshot_id"],
                latest["snapshot_id"],
                json_text(delta_metrics),
                growth_status,
                decision,
                decision_reason,
                evaluated_by,
                timestamp,
            ),
        )
    draft = None
    if decision == "create_followup_boost":
        publication = get_publication(publication_id) or publication
        draft = _create_followup_boost_draft(publication, evaluation_id, decision_reason)
        with connection() as db:
            db.execute(
                "UPDATE publication_evaluations SET created_draft_id=? WHERE evaluation_id=?",
                (draft["task_draft_id"], evaluation_id),
            )
    tracking_status = {
        "create_followup_boost": "boost_draft_created",
        "watch": "tracking",
        "no_boost": "closed",
        "manual_review": "manual_review",
    }[decision]
    with connection() as db:
        db.execute(
            """
            UPDATE original_publications
            SET tracking_status=?, latest_evaluation_id=?, updated_at=?
            WHERE publication_id=?
            """,
            (tracking_status, evaluation_id, timestamp, publication_id),
        )
    evaluation = fetch_one("SELECT * FROM publication_evaluations WHERE evaluation_id=?", (evaluation_id,)) or {}
    add_audit(
        "evaluate",
        "original_publication",
        publication_id,
        actor_type="operator",
        actor_id=evaluated_by,
        before={"tracking_status": publication.get("tracking_status")},
        after={"evaluation": evaluation, "draft_id": draft.get("task_draft_id") if draft else None},
    )
    return {"publication": get_publication(publication_id), "evaluation": evaluation, "draft": draft}
