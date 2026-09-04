from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from .database import add_audit, connection, fetch_all, fetch_one, json_text, new_id, now_iso
from .events import get_event


ALLOWED_EVENT_OUTCOMES = {"relevant_event_clue", "brand_content_opportunity"}
TASK_GENERATING_OUTCOMES = {"relevant_event_clue", "brand_content_opportunity"}
ALLOWED_ACTION_PATHS = {"original_growth", "source_content_boost"}
ALLOWED_DRAFT_PURPOSES = {"original_growth", "source_content_boost", "original_post_boost"}
ALLOWED_TASK_TYPES = {"original_comment", "original_content", "source_content_boost", "original_post_boost"}
ALLOWED_DRAFT_STATUSES = {"draft_pending_review", "approved", "rejected"}
PLATFORM_LABELS = {
    "weibo": "微博能力",
    "douyin": "抖音能力",
    "wechat_official_account": "公众号能力",
    "wechat_channels": "视频号能力",
    "toutiao": "头条能力",
    "xiaohongshu": "小红书能力",
    "bilibili": "B站能力",
    "autohome": "汽车之家能力",
    "dongchedi": "懂车帝能力",
}

BOOST_ACTIONS_BY_PLATFORM = {
    "weibo": ["like", "positive_comment", "repost"],
    "douyin": ["like", "positive_comment"],
    "wechat_official_account": ["like", "positive_comment"],
    "wechat_channels": ["like", "positive_comment"],
    "toutiao": ["like", "positive_comment"],
    "xiaohongshu": ["like", "favorite", "positive_comment"],
    "bilibili": ["like", "positive_comment"],
    "autohome": ["like", "positive_comment"],
    "dongchedi": ["like", "positive_comment"],
}


def _recommend_platforms(event: dict[str, Any]) -> list[str]:
    title = event.get("event_title") or ""
    source_platforms = set(event.get("source_platforms") or [])
    recommendations: list[str] = []
    if "weibo" in source_platforms:
        recommendations.append("weibo")
    if any(term in title for term in ("视频", "车展", "直播", "亮相", "实车")):
        recommendations.extend(["douyin", "xiaohongshu"])
    if any(term in title for term in ("上市", "配置", "价格", "选车", "体验")):
        recommendations.extend(["xiaohongshu", "toutiao"])
    if not recommendations or any(term in title for term in ("发布", "交付", "技术", "质量", "市场", "规划")):
        recommendations.extend(["toutiao", "wechat_official_account"])
    return list(dict.fromkeys(recommendations))[:2]


PLATFORM_GUIDANCE = {
    "douyin": "内容形态：30—90秒口播、实拍混剪或图文轮播；开头3秒呈现经证据核验的核心看点，字幕突出事实，不虚构体验。",
    "xiaohongshu": "内容形态：图文笔记或短视频；标题明确主体与信息点，正文分段表达，可从真实使用场景或同价位选择角度展开。",
    "weibo": "内容形态：短评、多图或短视频博文；文案简洁，使用运营确认的话题，配图或视频并保留个人观点。",
    "toutiao": "内容形态：短图文、中短评或视频；标题点明核心事实，正文先结论后依据，适合较完整的行业解读。",
    "wechat_official_account": "内容形态：公众号图文；按事件背景、已核验事实、产品或行业价值、个人观点组织，不使用未核验数据。",
    "wechat_channels": "内容形态：短视频或直播切片；使用可授权素材，口播仅引用事件证据，避免实时数据和效果承诺。",
}


def _original_draft_brief(event: dict[str, Any], platforms: list[str], source_ids: list[str]) -> str:
    evidence_rows = fetch_all(
        "SELECT evidence_text FROM event_evidence WHERE event_id=? ORDER BY created_at LIMIT 3", (event["event_id"],)
    )
    evidence_text = "\n".join(str(item.get("evidence_text") or "") for item in evidence_rows)
    hashtags = list(dict.fromkeys(re.findall(r"#[^#\s，。；、]{2,30}#?", evidence_text)))[:4]
    topic_text = "、".join(hashtags) if hashtags else "待运营依据官方口径补充；系统不从搜索摘要臆造话题"
    platform_text = "\n".join(
        f"- {PLATFORM_LABELS.get(platform, platform).replace('能力', '')}：{PLATFORM_GUIDANCE.get(platform, '按平台内容规范形成原创表达，具体形式由运营确认。')}"
        for platform in platforms
    ) or "- 目标平台待运营确认。"
    evidence_summary = "；".join(
        str(item.get("evidence_text") or "").strip().replace("\n", " ")[:180] for item in evidence_rows if item.get("evidence_text")
    ) or event.get("event_title") or "当前未取得可展示的正文证据"
    return (
        "本任务基于公开信息线索形成，不代表真实热点结论。\n\n"
        "一、作业详情\n"
        f"1. 必带话题：{topic_text}\n"
        f"2. 核心命题：围绕“{event.get('event_title')}”开展原创创作，只使用已核验证据说明事件事实及其品牌或行业价值。\n"
        f"3. 已核验证据摘要：{evidence_summary}\n"
        f"4. 证据编号：{'、'.join(source_ids)}\n\n"
        "二、平台适配指引\n"
        f"{platform_text}\n\n"
        "三、创作方向参考\n"
        "1. 普通用户解读：用通俗语言解释事件对购车、用车或行业认知的影响。\n"
        "2. 真实场景视角：仅在有可靠素材时结合通勤、长途、家庭或户外等场景，不得模拟未发生的车主体验。\n"
        "3. 行业观察视角：结合已核验事实分析产品或行业价值，不扩大为销量、排名或全网口碑结论。\n\n"
        "四、作业规则\n"
        "1. 内容必须原创，不得照搬官方或他人账号内容，不得组织同质化复制评论。\n"
        "2. 不得添加证据未支持的价格、销量、配置、排名、互动量和用户评价。\n"
        "3. 不得使用“全网热议”“正在爆发”“冲上热搜”等未经平台原生数据证明的表述。\n"
        "4. 违规、申诉周期和积分处理沿用护卫军正式作业规则，发布前由运营补齐并确认。"
    )


def _create_or_get_original_draft(event: dict[str, Any]) -> dict[str, Any]:
    existing = fetch_one(
        "SELECT * FROM task_drafts WHERE event_id=? AND draft_purpose='original_growth' AND target_source_id=''",
        (event["event_id"],),
    )
    if existing:
        return existing
    evidence = fetch_all("SELECT source_id FROM event_evidence WHERE event_id=? AND source_id IS NOT NULL", (event["event_id"],))
    source_ids = list(dict.fromkeys(item["source_id"] for item in evidence if item.get("source_id")))
    if not source_ids:
        raise ValueError("事件没有可追溯来源，不能生成作业草案")
    platforms = _recommend_platforms(event)
    tags = [PLATFORM_LABELS[item] for item in platforms if item in PLATFORM_LABELS]
    risk_notes = [f"事件风险标签：{tag}" for tag in (event.get("risk_tags") or [])]
    risk_notes.extend(event.get("hotspot_unavailable_reason") or [])
    task_draft_id = new_id("DRF")
    timestamp = now_iso()
    deadline = (datetime.now().astimezone() + timedelta(hours=24)).isoformat(timespec="minutes")
    with connection() as db:
        db.execute(
            """
            INSERT INTO task_drafts (
                task_draft_id, event_id, draft_purpose, target_source_id,
                task_type, task_title, task_brief, recommended_platforms_json,
                target_member_tags_json, engagement_actions_json, response_deadline,
                evidence_source_ids_json, prohibited_claims_json, risk_notes_json,
                task_status, created_at, updated_at
            ) VALUES (?, ?, 'original_growth', '', 'original_content', ?, ?, ?, ?, '[]', ?, ?, ?, ?, 'draft_pending_review', ?, ?)
            """,
            (
                task_draft_id,
                event["event_id"],
                f"原创作业｜{event.get('event_title')}",
                _original_draft_brief(event, platforms, source_ids),
                json_text(platforms),
                json_text(tags),
                deadline,
                json_text(source_ids),
                json_text(
                    [
                        "不得把公开搜索线索表述为真实热点",
                        "没有平台原生数据时，不得使用“全网热议”“正在爆发”“冲上热搜”等表述",
                        "不得添加证据未支持的销量、排名、互动量或用户评价",
                    ]
                ),
                json_text(list(dict.fromkeys(risk_notes))),
                timestamp,
                timestamp,
            ),
        )
    draft = fetch_one("SELECT * FROM task_drafts WHERE task_draft_id=?", (task_draft_id,)) or {}
    add_audit("create", "task_draft", task_draft_id, actor_type="system", actor_id="draft-engine", after=draft)
    return draft


def _source_platform(source: dict[str, Any]) -> str | None:
    platform = source.get("source_platform")
    if platform in BOOST_ACTIONS_BY_PLATFORM:
        return str(platform)
    site_name = source.get("source_site_name") or ""
    domain = source.get("domain") or ""
    if "今日头条" in site_name or "toutiao.com" in domain:
        return "toutiao"
    if "汽车之家" in site_name or "autohome.com" in domain:
        return "autohome"
    if "懂车帝" in site_name or "dongchedi.com" in domain:
        return "dongchedi"
    if "小红书" in site_name or "xiaohongshu.com" in domain:
        return "xiaohongshu"
    if "哔哩哔哩" in site_name or "bilibili.com" in domain:
        return "bilibili"
    return None


def _event_source(event_id: str, source_id: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT s.* FROM source_items s
        JOIN event_evidence e ON e.source_id=s.source_id
        WHERE e.event_id=? AND s.source_id=?
        """,
        (event_id, source_id),
    )


def _validate_boost_source(event_id: str, source_id: str) -> tuple[dict[str, Any], str, str]:
    source = _event_source(event_id, source_id)
    if not source:
        raise ValueError(f"目标来源不属于当前事件：{source_id}")
    platform = _source_platform(source)
    if not platform:
        raise ValueError(f"来源 {source_id} 未识别为可执行互动的平台内容，不能生成加热草案")
    target_url = source.get("canonical_url") or source.get("original_url")
    if not target_url:
        raise ValueError(f"来源 {source_id} 缺少可访问链接，不能生成加热草案")
    return source, platform, str(target_url)


def _create_or_get_boost_draft(event: dict[str, Any], source_id: str) -> dict[str, Any]:
    source, platform, target_url = _validate_boost_source(event["event_id"], source_id)
    existing = fetch_one(
        "SELECT * FROM task_drafts WHERE event_id=? AND draft_purpose='source_content_boost' AND target_source_id=?",
        (event["event_id"], source_id),
    )
    if existing:
        return existing

    actions = BOOST_ACTIONS_BY_PLATFORM[platform][:2]
    task_draft_id = new_id("DRF")
    timestamp = now_iso()
    deadline = (datetime.now().astimezone() + timedelta(hours=6)).isoformat(timespec="minutes")
    title = source.get("title") or event.get("event_title") or source_id
    brief = (
        "本草案用于加热热点事件中的目标文章或视频本身，不要求用户另行发布原创内容。\n\n"
        f"目标内容：{title}\n目标链接：{target_url}\n"
        "运营须确认目标内容值得放大、链接有效且互动动作符合平台规则，再决定点赞、正向评论等任务要求。"
    )
    risk_notes = list(dict.fromkeys([
        *(event.get("risk_tags") or []),
        *(event.get("hotspot_unavailable_reason") or []),
        "公开搜索只能证明发现该内容，不能证明其真实热度；是否值得加热由运营结合业务判断确认",
        "避免短时间集中操作、同质化评论和诱导性表达，任务人数与时间窗待运营配置",
    ]))
    with connection() as db:
        db.execute(
            """
            INSERT INTO task_drafts (
                task_draft_id, event_id, draft_purpose, target_source_id,
                target_url, target_content_title, task_type, task_title, task_brief,
                recommended_platforms_json, target_member_tags_json,
                engagement_actions_json, response_deadline, evidence_source_ids_json,
                prohibited_claims_json, risk_notes_json, task_status, created_at, updated_at
            ) VALUES (?, ?, 'source_content_boost', ?, ?, ?, 'source_content_boost', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft_pending_review', ?, ?)
            """,
            (
                task_draft_id,
                event["event_id"],
                source_id,
                target_url,
                title,
                f"热点源内容加热｜{title}",
                brief,
                json_text([platform]),
                json_text([PLATFORM_LABELS.get(platform, f"{platform}能力")]),
                json_text(actions),
                deadline,
                json_text([source_id]),
                json_text([
                    "不得要求复制粘贴统一评论",
                    "不得发布证据未支持的事实、销量、排名或用户评价",
                    "不得把公开线索表述为已确认的真实热点",
                ]),
                json_text(risk_notes),
                timestamp,
                timestamp,
            ),
        )
    draft = fetch_one("SELECT * FROM task_drafts WHERE task_draft_id=?", (task_draft_id,)) or {}
    add_audit("create", "task_draft", task_draft_id, actor_type="system", actor_id="draft-engine", after=draft)
    return draft


def review_event(
    event_id: str,
    *,
    review_result: str,
    event_status: str | None,
    reviewer: str,
    review_note: str | None,
    evidence_summary: str,
    risk_summary: str,
    recommended_action: str,
    action_paths: list[str],
    boost_source_ids: list[str],
) -> dict[str, Any]:
    event = get_event(event_id)
    if not event:
        raise LookupError("事件不存在")
    if review_result not in {"approved", "rejected"}:
        raise ValueError("不支持的事件审核结果")
    if review_result == "rejected":
        final_status = "rejected"
        if not (review_note or "").strip():
            raise ValueError("驳回事件必须填写原因")
    else:
        if event_status not in ALLOWED_EVENT_OUTCOMES:
            raise ValueError("通过事件时必须选择可用的事件结论")
        if not event.get("evidence"):
            raise ValueError("没有证据的事件不能通过")
        final_status = str(event_status)
        invalid_paths = set(action_paths) - ALLOWED_ACTION_PATHS
        if invalid_paths:
            raise ValueError(f"不支持的行动方向：{', '.join(sorted(invalid_paths))}")
        if final_status in TASK_GENERATING_OUTCOMES and not action_paths:
            raise ValueError("事件值得行动时，至少选择原创增长或源内容加热中的一项")
        if "source_content_boost" in action_paths and not boost_source_ids:
            raise ValueError("选择源内容加热时，必须指定至少一条目标文章或视频")
        if final_status in TASK_GENERATING_OUTCOMES and "source_content_boost" in action_paths:
            for source_id in list(dict.fromkeys(boost_source_ids))[:3]:
                _validate_boost_source(event_id, source_id)
    review_id = new_id("REV")
    timestamp = now_iso()
    with connection() as db:
        db.execute(
            """
            INSERT INTO candidate_reviews (
                candidate_id, event_id, event_status, evidence_summary, risk_summary,
                recommended_action, review_result, reviewer, review_note, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                event_id,
                final_status,
                evidence_summary,
                risk_summary,
                recommended_action,
                review_result,
                reviewer,
                review_note,
                timestamp,
            ),
        )
        db.execute(
            "UPDATE events SET event_status=?, decision_reason=?, updated_at=? WHERE event_id=?",
            (final_status, evidence_summary, timestamp, event_id),
        )
    drafts: list[dict[str, Any]] = []
    reviewed_event = get_event(event_id) or event
    if final_status in TASK_GENERATING_OUTCOMES:
        if "original_growth" in action_paths:
            drafts.append(_create_or_get_original_draft(reviewed_event))
        if "source_content_boost" in action_paths:
            for source_id in list(dict.fromkeys(boost_source_ids))[:3]:
                drafts.append(_create_or_get_boost_draft(reviewed_event, source_id))
    add_audit(
        "review",
        "event",
        event_id,
        actor_type="operator",
        actor_id=reviewer,
        before={"event_status": event.get("event_status")},
        after={
            "event_status": final_status,
            "review_result": review_result,
            "action_paths": action_paths,
            "boost_source_ids": boost_source_ids,
            "draft_ids": [item.get("task_draft_id") for item in drafts],
        },
    )
    return {"event": get_event(event_id), "drafts": drafts, "draft": drafts[0] if drafts else None}


def list_drafts(status: str | None = None, purpose: str | None = None, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if status:
        conditions.append("task_status=?")
        params.append(status)
    if purpose:
        if purpose not in ALLOWED_DRAFT_PURPOSES:
            raise ValueError("不支持的草案方向")
        conditions.append("draft_purpose=?")
        params.append(purpose)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])
    return fetch_all(f"SELECT * FROM task_drafts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", tuple(params))


def count_drafts(status: str | None = None, purpose: str | None = None) -> int:
    conditions: list[str] = []; params: list[Any] = []
    if status: conditions.append("task_status=?"); params.append(status)
    if purpose: conditions.append("draft_purpose=?"); params.append(purpose)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    row = fetch_one(f"SELECT COUNT(*) total FROM task_drafts {where}", tuple(params)) or {}
    return int(row.get("total") or 0)


def get_draft(task_draft_id: str) -> dict[str, Any] | None:
    draft = fetch_one("SELECT * FROM task_drafts WHERE task_draft_id=?", (task_draft_id,))
    if not draft:
        return None
    draft["event"] = get_event(draft["event_id"])
    return draft


def update_draft(task_draft_id: str, changes: dict[str, Any], actor_id: str) -> dict[str, Any]:
    before = get_draft(task_draft_id)
    if not before:
        raise LookupError("作业草案不存在")
    if before["task_status"] != "draft_pending_review":
        raise ValueError("只有待审批草案可以修改")
    allowed = {
        "task_type",
        "task_title",
        "task_brief",
        "recommended_platforms",
        "target_member_tags",
        "engagement_actions",
        "response_deadline",
        "prohibited_claims",
        "risk_notes",
    }
    payload = {key: value for key, value in changes.items() if key in allowed and value is not None}
    if payload.get("task_type") and payload["task_type"] not in ALLOWED_TASK_TYPES:
        raise ValueError("只支持原创评论、原创内容、源内容加热或原创后二次加热草案")
    if before["draft_purpose"] in {"source_content_boost", "original_post_boost"}:
        expected_type = before["draft_purpose"]
        if payload.get("task_type") and payload["task_type"] != expected_type:
            raise ValueError("加热草案不能改为其他作业类型")
        if "engagement_actions" in payload:
            actions = payload["engagement_actions"]
            platforms = before.get("recommended_platforms") or []
            allowed_actions = {
                action
                for platform in platforms
                for action in BOOST_ACTIONS_BY_PLATFORM.get(platform, [])
            }
            if not actions:
                raise ValueError("源内容加热草案至少保留一项互动动作")
            invalid_actions = set(actions) - allowed_actions
            if invalid_actions:
                raise ValueError(f"目标平台不支持互动动作：{', '.join(sorted(invalid_actions))}")
    elif payload.get("task_type") in {"source_content_boost", "original_post_boost"}:
        raise ValueError("原创增长草案不能改为源内容加热类型，请回到事件选择目标来源")
    if not payload:
        return before
    field_map = {
        "recommended_platforms": "recommended_platforms_json",
        "target_member_tags": "target_member_tags_json",
        "engagement_actions": "engagement_actions_json",
        "prohibited_claims": "prohibited_claims_json",
        "risk_notes": "risk_notes_json",
    }
    assignments: list[str] = []
    values: list[Any] = []
    for key, value in payload.items():
        column = field_map.get(key, key)
        assignments.append(f"{column}=?")
        values.append(json_text(value) if key in field_map else value)
    assignments.append("updated_at=?")
    values.extend([now_iso(), task_draft_id])
    with connection() as db:
        db.execute(f"UPDATE task_drafts SET {', '.join(assignments)} WHERE task_draft_id=?", tuple(values))
    after = get_draft(task_draft_id) or {}
    add_audit("update", "task_draft", task_draft_id, actor_type="operator", actor_id=actor_id, before=before, after=after)
    return after


def review_draft(task_draft_id: str, *, review_result: str, reviewer: str, review_note: str | None) -> dict[str, Any]:
    before = get_draft(task_draft_id)
    if not before:
        raise LookupError("作业草案不存在")
    if before["task_status"] != "draft_pending_review":
        raise ValueError(f"当前草案状态不可审批：{before['task_status']}")
    if review_result not in {"approved", "rejected"}:
        raise ValueError("草案审批只支持通过或驳回")
    if review_result == "rejected" and not (review_note or "").strip():
        raise ValueError("驳回草案必须填写原因")
    if review_result == "approved" and before["draft_purpose"] in {"source_content_boost", "original_post_boost"}:
        if before["draft_purpose"] == "source_content_boost" and not before.get("target_source_id"):
            raise ValueError("源内容加热草案缺少目标来源，不能通过")
        if before["draft_purpose"] == "original_post_boost" and not before.get("target_submission_id"):
            raise ValueError("原创后二次加热草案缺少原创发布记录，不能通过")
        if not before.get("target_url"):
            raise ValueError("加热草案缺少目标链接，不能通过")
        if not (before.get("engagement_actions") or []):
            raise ValueError("加热草案至少需要一项互动动作才能通过")
    timestamp = now_iso()
    with connection() as db:
        db.execute(
            """
            UPDATE task_drafts SET task_status=?, reviewer=?, review_note=?, reviewed_at=?, updated_at=?
            WHERE task_draft_id=?
            """,
            (review_result, reviewer, review_note, timestamp, timestamp, task_draft_id),
        )
    after = get_draft(task_draft_id) or {}
    add_audit("review", "task_draft", task_draft_id, actor_type="operator", actor_id=reviewer, before=before, after=after)
    return after
