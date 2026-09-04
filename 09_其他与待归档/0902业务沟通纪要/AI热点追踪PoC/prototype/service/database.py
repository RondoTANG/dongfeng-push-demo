from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from .models import JSON_FIELDS, SCHEMA_STATEMENTS
from .settings import DATABASE_PATH, ensure_runtime_dirs


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


@contextmanager
def connection() -> Iterable[sqlite3.Connection]:
    ensure_runtime_dirs()
    db = sqlite3.connect(DATABASE_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_database() -> None:
    with connection() as db:
        followup_markers = (
            "original_publications",
            "publication_metric_snapshots",
            "publication_evaluations",
            "idx_publications_status",
            "idx_snapshots_publication",
            "idx_evaluations_publication",
        )
        base_statements = [
            statement for statement in SCHEMA_STATEMENTS
            if not any(marker in statement for marker in followup_markers)
        ]
        followup_statements = [
            statement for statement in SCHEMA_STATEMENTS
            if any(marker in statement for marker in followup_markers)
        ]
        for statement in base_statements:
            db.execute(statement)
        _migrate_task_drafts(db)
        _migrate_task_drafts_followup(db)
        for statement in followup_statements:
            db.execute(statement)


def _migrate_task_drafts(db: sqlite3.Connection) -> None:
    """将早期“一事件一原创草案”结构迁移为“一事件多行动草案”。"""
    columns = {row[1] for row in db.execute("PRAGMA table_info(task_drafts)").fetchall()}
    if not columns or "draft_purpose" in columns:
        return
    db.execute("ALTER TABLE task_drafts RENAME TO task_drafts_legacy")
    db.execute(
        """
        CREATE TABLE task_drafts (
            task_draft_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            draft_purpose TEXT NOT NULL DEFAULT 'original_growth',
            target_source_id TEXT NOT NULL DEFAULT '',
            target_url TEXT,
            target_content_title TEXT,
            task_type TEXT NOT NULL,
            task_title TEXT NOT NULL,
            task_brief TEXT NOT NULL,
            recommended_platforms_json TEXT NOT NULL DEFAULT '[]',
            target_member_tags_json TEXT NOT NULL DEFAULT '[]',
            engagement_actions_json TEXT NOT NULL DEFAULT '[]',
            response_deadline TEXT,
            evidence_source_ids_json TEXT NOT NULL DEFAULT '[]',
            prohibited_claims_json TEXT NOT NULL DEFAULT '[]',
            risk_notes_json TEXT NOT NULL DEFAULT '[]',
            task_status TEXT NOT NULL DEFAULT 'draft_pending_review',
            reviewer TEXT,
            review_note TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (event_id, draft_purpose, target_source_id),
            FOREIGN KEY (event_id) REFERENCES events(event_id)
        )
        """
    )
    db.execute(
        """
        INSERT INTO task_drafts (
            task_draft_id, event_id, draft_purpose, target_source_id,
            task_type, task_title, task_brief, recommended_platforms_json,
            target_member_tags_json, engagement_actions_json, response_deadline,
            evidence_source_ids_json, prohibited_claims_json, risk_notes_json,
            task_status, reviewer, review_note, reviewed_at, created_at, updated_at
        )
        SELECT task_draft_id, event_id, 'original_growth', '',
            task_type, task_title, task_brief, recommended_platforms_json,
            target_member_tags_json, '[]', response_deadline,
            evidence_source_ids_json, prohibited_claims_json, risk_notes_json,
            task_status, reviewer, review_note, reviewed_at, created_at, updated_at
        FROM task_drafts_legacy
        """
    )
    db.execute("DROP TABLE task_drafts_legacy")


def _migrate_task_drafts_followup(db: sqlite3.Connection) -> None:
    """增加原创发布后效分支所需的投稿目标字段，并修正多目标唯一键。"""
    columns = {row[1] for row in db.execute("PRAGMA table_info(task_drafts)").fetchall()}
    if not columns or "target_submission_id" in columns:
        return
    db.execute("ALTER TABLE task_drafts RENAME TO task_drafts_before_followup")
    db.execute(
        """
        CREATE TABLE task_drafts (
            task_draft_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            draft_purpose TEXT NOT NULL DEFAULT 'original_growth',
            target_source_id TEXT NOT NULL DEFAULT '',
            target_submission_id TEXT NOT NULL DEFAULT '',
            trigger_evaluation_id TEXT,
            target_url TEXT,
            target_content_title TEXT,
            task_type TEXT NOT NULL,
            task_title TEXT NOT NULL,
            task_brief TEXT NOT NULL,
            recommended_platforms_json TEXT NOT NULL DEFAULT '[]',
            target_member_tags_json TEXT NOT NULL DEFAULT '[]',
            engagement_actions_json TEXT NOT NULL DEFAULT '[]',
            response_deadline TEXT,
            evidence_source_ids_json TEXT NOT NULL DEFAULT '[]',
            prohibited_claims_json TEXT NOT NULL DEFAULT '[]',
            risk_notes_json TEXT NOT NULL DEFAULT '[]',
            task_status TEXT NOT NULL DEFAULT 'draft_pending_review',
            reviewer TEXT,
            review_note TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (event_id, draft_purpose, target_source_id, target_submission_id),
            FOREIGN KEY (event_id) REFERENCES events(event_id)
        )
        """
    )
    db.execute(
        """
        INSERT INTO task_drafts (
            task_draft_id, event_id, draft_purpose, target_source_id,
            target_submission_id, trigger_evaluation_id, target_url,
            target_content_title, task_type, task_title, task_brief,
            recommended_platforms_json, target_member_tags_json,
            engagement_actions_json, response_deadline, evidence_source_ids_json,
            prohibited_claims_json, risk_notes_json, task_status, reviewer,
            review_note, reviewed_at, created_at, updated_at
        )
        SELECT task_draft_id, event_id, draft_purpose, target_source_id,
            '', NULL, target_url, target_content_title, task_type, task_title,
            task_brief, recommended_platforms_json, target_member_tags_json,
            engagement_actions_json, response_deadline, evidence_source_ids_json,
            prohibited_claims_json, risk_notes_json, task_status, reviewer,
            review_note, reviewed_at, created_at, updated_at
        FROM task_drafts_before_followup
        """
    )
    db.execute("DROP TABLE task_drafts_before_followup")


def decode_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for field in JSON_FIELDS:
        if field not in result:
            continue
        raw = result.pop(field)
        public_name = field.removesuffix("_json")
        if raw in (None, ""):
            result[public_name] = None if raw is None else {}
            continue
        try:
            result[public_name] = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            result[public_name] = raw
    if "hotspot_judgement_available" in result:
        result["hotspot_judgement_available"] = bool(result["hotspot_judgement_available"])
    return result


def fetch_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with connection() as db:
        return decode_row(db.execute(sql, params).fetchone())


def fetch_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connection() as db:
        return [decode_row(row) or {} for row in db.execute(sql, params).fetchall()]


def execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    with connection() as db:
        cursor = db.execute(sql, params)
        return cursor.rowcount


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def add_audit(
    action: str,
    object_type: str,
    object_id: str,
    *,
    actor_type: str = "system",
    actor_id: str = "local-service",
    before: Any = None,
    after: Any = None,
) -> str:
    audit_id = new_id("AUD")
    with connection() as db:
        db.execute(
            """
            INSERT INTO audit_logs (
                audit_id, actor_type, actor_id, action, object_type, object_id,
                before_json, after_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                actor_type,
                actor_id,
                action,
                object_type,
                object_id,
                json_text(before) if before is not None else None,
                json_text(after) if after is not None else None,
                now_iso(),
            ),
        )
    return audit_id
