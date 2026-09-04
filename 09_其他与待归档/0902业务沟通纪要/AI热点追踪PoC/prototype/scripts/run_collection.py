#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.pipeline import execute_collection  # noqa: E402
from service.repositories import get_run  # noqa: E402
from service.events import aggregate_run  # noqa: E402


def default_idempotency_key(mode: str, trigger_type: str) -> str:
    now = datetime.now().astimezone()
    if trigger_type == "schedule":
        bucket_hour = now.hour - (now.hour % 3)
        return f"schedule-{mode}-{now:%Y%m%d}-{bucket_hour:02d}"
    return f"manual-{mode}-{now:%Y%m%d%H%M%S}"


def main() -> int:
    parser = argparse.ArgumentParser(description="东风护卫军公开信息线索采集")
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    parser.add_argument("--trigger-type", choices=["manual", "schedule"], default="manual")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--skip-aggregate", action="store_true", help="仅采集来源，不生成统一事件")
    args = parser.parse_args()
    try:
        idempotency_key = args.idempotency_key or default_idempotency_key(args.mode, args.trigger_type)
        run_id = execute_collection(
            mode=args.mode,
            trigger_type=args.trigger_type,
            idempotency_key=idempotency_key,
            timeout=args.timeout,
        )
        run = get_run(run_id) or {}
        aggregation = {"events_created": 0, "evidence_links": 0}
        if not args.skip_aggregate and run.get("status") in {"success", "partial_success"}:
            aggregation = aggregate_run(run_id)
        output = {
            "ok": run.get("status") in {"success", "partial_success"},
            "run_id": run_id,
            "idempotency_key": idempotency_key,
            "trigger_type": args.trigger_type,
            "mode": args.mode,
            "run_status": run.get("status"),
            "query_coverage": run.get("query_coverage"),
            "source_processing": (run.get("step_summary") or {}).get("source_processing"),
            "aggregation": aggregation,
            "exit_category": "success" if run.get("status") == "success" else "partial_success" if run.get("status") == "partial_success" else "failed",
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        if run.get("status") == "success":
            return 0
        if run.get("status") == "partial_success":
            return 2
        return 3
    except Exception as exc:
        print(json.dumps({"ok": False, "exit_category": "runtime_error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
