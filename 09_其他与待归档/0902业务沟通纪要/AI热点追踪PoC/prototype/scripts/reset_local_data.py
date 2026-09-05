"""经明确授权后备份并清理本地PoC业务数据；保留配置、凭证与代码。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.settings import DATABASE_PATH


def reset() -> dict:
    if not DATABASE_PATH.is_file():
        raise RuntimeError("本地数据库不存在，未执行清理")
    backup_dir = DATABASE_PATH.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"before-reset-{datetime.now():%Y%m%d-%H%M%S-%f}.db"
    with sqlite3.connect(DATABASE_PATH) as db:
        if db.execute("SELECT count(*) FROM collection_runs WHERE status='running'").fetchone()[0]:
            raise RuntimeError("存在运行中的采集批次，不能清理")
        with sqlite3.connect(backup) as target:
            db.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("备份完整性检查失败，未执行清理")
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        counts = {name: db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0] for name in tables}
        # 此脚本只对已验证的固定PoC数据库执行，不读取任意用户输入的表名或路径。
        db.execute("PRAGMA foreign_keys=OFF")
        with db:
            for name in tables:
                db.execute(f'DELETE FROM "{name}"')
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    return {"backup": str(backup), "removed_records": counts, "can_restore": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-reset", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(reset(), ensure_ascii=False, indent=2))
