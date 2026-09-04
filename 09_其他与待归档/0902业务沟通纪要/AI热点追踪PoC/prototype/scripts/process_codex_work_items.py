#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.work_items import (  # noqa: E402
    claim_work_item,
    complete_work_item,
    fail_work_item,
    get_work_item,
    list_work_items,
)


ALLOWED_OUTPUT_FIELDS = {
    "summary", "decision_reason", "evidence", "risk_tags",
    "entity_mentions", "entity_uncertainties", "brand_relations",
}


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("回传内容必须是 JSON 对象")
    unknown = sorted(set(payload) - ALLOWED_OUTPUT_FIELDS)
    if unknown:
        raise ValueError(f"存在契约外字段：{', '.join(unknown)}")
    if not str(payload.get("summary") or payload.get("decision_reason") or "").strip():
        raise ValueError("必须填写 summary 或 decision_reason")
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("evidence 必须是数组")
    for item in evidence:
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            raise ValueError("每条 evidence 必须包含 text")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex 事件补证与分析工作项接口")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--claim-next", action="store_true", help="领取最早的待处理工作项")
    action.add_argument("--claim", metavar="WORK_ITEM_ID", help="领取指定工作项")
    action.add_argument("--complete", metavar="WORK_ITEM_ID", help="使用 --payload 完成指定工作项")
    action.add_argument("--fail", metavar="WORK_ITEM_ID", help="将指定工作项记为失败")
    parser.add_argument("--payload", type=Path, help="Codex 结构化回传 JSON 文件")
    parser.add_argument("--message", help="失败原因")
    parser.add_argument("--actor-id", default="codex-local-automation")
    parser.add_argument("--status", default="pending", choices=["pending", "in_progress", "completed", "failed", "cancelled"])
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    try:
        if args.claim_next:
            items = list_work_items("pending", 1)
            if not items:
                emit({"ok": True, "status": "empty", "message": "当前没有待 Codex 处理的工作项"})
                return 0
            item = claim_work_item(items[0]["work_item_id"], args.actor_id)
            emit({"ok": True, "status": "claimed", "work_item": item})
            return 0
        if args.claim:
            emit({"ok": True, "status": "claimed", "work_item": claim_work_item(args.claim, args.actor_id)})
            return 0
        if args.complete:
            if not args.payload:
                raise ValueError("--complete 必须同时提供 --payload")
            payload = validate_payload(json.loads(args.payload.read_text(encoding="utf-8")))
            emit({"ok": True, "status": "completed", "work_item": complete_work_item(args.complete, args.actor_id, payload)})
            return 0
        if args.fail:
            if not args.message:
                raise ValueError("--fail 必须同时提供 --message")
            emit({"ok": True, "status": "failed", "work_item": fail_work_item(args.fail, args.actor_id, args.message)})
            return 0

        items = list_work_items(args.status, args.limit)
        emit({
            "ok": True,
            "status": args.status,
            "count": len(items),
            "items": items,
            "contract": {
                "allowed_output_fields": sorted(ALLOWED_OUTPUT_FIELDS),
                "hotspot_rule": "公开搜索只能补证事件事实，不得将搜索排名或结果数写成真实热度",
                "state_rule": "Codex 只能填写契约字段，事件状态由后端根据风险与存疑计算",
            },
        })
        return 0
    except (LookupError, ValueError, json.JSONDecodeError, OSError) as exc:
        emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
