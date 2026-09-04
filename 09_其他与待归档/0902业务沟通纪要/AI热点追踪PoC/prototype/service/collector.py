from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from .settings import DOUBAO_SCRIPT_PATH


def _load_doubao_module():
    spec = importlib.util.spec_from_file_location("guard_army_doubao_search", DOUBAO_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载豆包采集器：{DOUBAO_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_processed_items(result: dict[str, Any]) -> list[dict[str, Any]]:
    if not result.get("success"):
        raise RuntimeError(result.get("error_message") or "豆包结果处理失败")
    raw_items = result.get("web_search_items_json", "[]")
    if isinstance(raw_items, str):
        try:
            items = json.loads(raw_items)
        except json.JSONDecodeError as exc:
            raise RuntimeError("豆包 web_search_items_json 不是合法 JSON") from exc
    elif isinstance(raw_items, list):
        items = raw_items
    else:
        raise RuntimeError("豆包 web_search_items_json 类型异常")
    return [item for item in items if isinstance(item, dict)]


def search_one(query: str, *, timeout: int = 30) -> dict[str, Any]:
    module = _load_doubao_module()
    api_key = module.load_api_key()
    response = module.search(api_key, query, timeout)
    processor = module._load_processor()
    processed = processor.handler({"search_results": [response]})
    return {
        "provider": "doubao_global_search",
        "query": query,
        "raw_response": response,
        "processed": processed,
        "items": parse_processed_items(processed),
    }


def load_existing_sample(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("provider") != "doubao_global_search":
        raise ValueError("真实样本提供方不是 doubao_global_search")
    items = parse_processed_items(payload.get("result") or {})
    return {**payload, "items": items}
