from __future__ import annotations

from typing import Any

from .database import add_audit, connection, fetch_all, fetch_one, json_text, now_iso


ALLOWED_WORK_TYPES = {"evidence_and_analysis", "evidence_only", "draft_analysis"}


def list_work_items(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if status:
        return fetch_all(
            "SELECT * FROM codex_work_items WHERE status=? ORDER BY created_at LIMIT ?",
            (status, limit),
        )
    return fetch_all("SELECT * FROM codex_work_items ORDER BY created_at DESC LIMIT ?", (limit,))


def get_work_item(work_item_id: str) -> dict[str, Any] | None:
    return fetch_one("SELECT * FROM codex_work_items WHERE work_item_id=?", (work_item_id,))


def claim_work_item(work_item_id: str, actor_id: str) -> dict[str, Any]:
    before = get_work_item(work_item_id)
    if not before:
        raise LookupError("工作项不存在")
    if before["status"] not in {"pending", "failed"}:
        raise ValueError(f"当前状态不可领取：{before['status']}")
    with connection() as db:
        db.execute(
            """
            UPDATE codex_work_items
            SET status='in_progress', locked_by=?, locked_at=?, attempts=attempts+1, error_message=NULL
            WHERE work_item_id=?
            """,
            (actor_id, now_iso(), work_item_id),
        )
    after = get_work_item(work_item_id) or {}
    add_audit(
        "claim",
        "codex_work_item",
        work_item_id,
        actor_type="codex",
        actor_id=actor_id,
        before=before,
        after=after,
    )
    return after


def complete_work_item(work_item_id: str, actor_id: str, output: dict[str, Any]) -> dict[str, Any]:
    before = get_work_item(work_item_id)
    if not before:
        raise LookupError("工作项不存在")
    if before["status"] != "in_progress":
        raise ValueError(f"当前状态不可完成：{before['status']}")
    if before.get("locked_by") != actor_id:
        raise ValueError("工作项已由其他执行者领取")
    event = fetch_one("SELECT * FROM events WHERE event_id=?", (before["event_id"],))
    if not event:
        raise LookupError("关联事件不存在")
    evidence_items = output.get("evidence") or []
    if not isinstance(evidence_items, list):
        raise ValueError("evidence 必须为数组")
    timestamp = now_iso()
    with connection() as db:
        for item in evidence_items:
            if not isinstance(item, dict) or not str(item.get("text", "")).strip():
                raise ValueError("每条 evidence 必须包含 text")
            db.execute(
                """
                INSERT INTO event_evidence (
                    evidence_id, event_id, source_id, evidence_type, evidence_text,
                    evidence_url, provided_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("evidence_id") or f"EVD-{work_item_id[-8:]}-{len(item.get('text', ''))}-{abs(hash(item.get('text'))) % 100000}",
                    before["event_id"],
                    item.get("source_id"),
                    item.get("type", "codex_web_evidence"),
                    str(item["text"]).strip(),
                    item.get("url"),
                    f"codex:{actor_id}",
                    timestamp,
                ),
            )
        risk_tags = sorted(set((event.get("risk_tags") or []) + (output.get("risk_tags") or [])))
        entity_mentions = output.get("entity_mentions") if output.get("entity_mentions") is not None else (event.get("entity_mentions") or [])
        entity_uncertainties = output.get("entity_uncertainties") if output.get("entity_uncertainties") is not None else (event.get("entity_uncertainties") or [])
        brand_relations = output.get("brand_relations") if output.get("brand_relations") is not None else (event.get("brand_relations") or [])
        decision_reason = str(output.get("decision_reason") or output.get("summary") or "").strip()
        if not decision_reason:
            raise ValueError("必须提供 summary 或 decision_reason")
        next_status = "pending_review"
        db.execute(
            """
            UPDATE events
            SET risk_tags_json=?, entity_mentions_json=?, entity_uncertainties_json=?,
                brand_relations_json=?, decision_reason=?, event_status=?, updated_at=?
            WHERE event_id=?
            """,
            (
                json_text(risk_tags),
                json_text(entity_mentions),
                json_text(entity_uncertainties),
                json_text(brand_relations),
                decision_reason,
                next_status,
                timestamp,
                before["event_id"],
            ),
        )
        db.execute(
            """
            UPDATE codex_work_items
            SET status='completed', output_json=?, completed_at=?, error_message=NULL
            WHERE work_item_id=?
            """,
            (json_text(output), timestamp, work_item_id),
        )
    after = get_work_item(work_item_id) or {}
    add_audit(
        "complete",
        "codex_work_item",
        work_item_id,
        actor_type="codex",
        actor_id=actor_id,
        before=before,
        after=after,
    )
    return after


def fail_work_item(work_item_id: str, actor_id: str, error_message: str) -> dict[str, Any]:
    before = get_work_item(work_item_id)
    if not before:
        raise LookupError("工作项不存在")
    with connection() as db:
        db.execute(
            "UPDATE codex_work_items SET status='failed', error_message=? WHERE work_item_id=?",
            (error_message[:500], work_item_id),
        )
    after = get_work_item(work_item_id) or {}
    add_audit("fail", "codex_work_item", work_item_id, actor_type="codex", actor_id=actor_id, before=before, after=after)
    return after
