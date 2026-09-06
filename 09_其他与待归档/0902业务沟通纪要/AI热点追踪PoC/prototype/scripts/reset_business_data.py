#!/usr/bin/env python3
"""备份后清理PoC业务运行数据；保留访问密钥、登录会话、配置与Codex授权。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.settings import DATABASE_PATH  # noqa: E402


BUSINESS_TABLES = [
    "publication_evaluations", "publication_metric_snapshots", "original_publications",
    "task_drafts", "candidate_reviews", "evidence_jobs", "evidence_requests",
    "codex_work_items", "event_evidence", "events", "invalid_logs",
    "source_discoveries", "source_items", "raw_provider_results", "query_jobs", "collection_runs",
]
PRESERVED_AUDIT_TYPES = {
    "access_key", "automation_config", "configuration", "brand_config",
    "query_config", "platform_config", "domain_config",
}


def reset_business_data() -> dict[str, object]:
    if not DATABASE_PATH.is_file():
        raise RuntimeError("数据库不存在，未执行清理")
    backup_dir = DATABASE_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"before-business-reset-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
    with sqlite3.connect(DATABASE_PATH) as db:
        db.row_factory = sqlite3.Row
        running = db.execute("SELECT COUNT(*) FROM collection_runs WHERE status='running'").fetchone()[0]
        if running:
            raise RuntimeError("存在运行中的采集批次，不能清理")
        existing_tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [table for table in BUSINESS_TABLES if table not in existing_tables]
        if missing:
            raise RuntimeError(f"数据库结构不完整，未执行清理：{', '.join(missing)}")
        counts = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in BUSINESS_TABLES}
        counts["audit_logs"] = db.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
        with sqlite3.connect(backup) as target:
            db.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("备份完整性检查失败，未执行清理")
        backup.chmod(0o600)
        db.execute("PRAGMA foreign_keys=OFF")
        with db:
            for table in BUSINESS_TABLES:
                db.execute(f'DELETE FROM "{table}"')
            placeholders = ",".join("?" for _ in PRESERVED_AUDIT_TYPES)
            db.execute(f"DELETE FROM audit_logs WHERE object_type NOT IN ({placeholders})", tuple(sorted(PRESERVED_AUDIT_TYPES)))
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError("清理后外键检查失败；请从备份恢复")
        remaining = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in BUSINESS_TABLES}
        preserved = {
            "access_keys": db.execute("SELECT COUNT(*) FROM access_keys").fetchone()[0] if "access_keys" in existing_tables else 0,
            "access_sessions": db.execute("SELECT COUNT(*) FROM access_sessions").fetchone()[0] if "access_sessions" in existing_tables else 0,
            "audit_logs": db.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0],
        }
    return {
        "backup": str(backup), "removed_before": counts, "remaining_business_records": remaining,
        "preserved": preserved, "can_restore": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-business-reset", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(reset_business_data(), ensure_ascii=False, indent=2))
