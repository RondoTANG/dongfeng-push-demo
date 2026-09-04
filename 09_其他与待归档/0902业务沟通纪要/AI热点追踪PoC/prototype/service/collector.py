from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from .settings import CODEX_CLI_PATH, DOUBAO_SCRIPT_PATH, PROJECT_ROOT


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


def search_doubao(query: str, *, timeout: int = 30) -> dict[str, Any]:
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


def _codex_schema() -> dict[str, Any]:
    item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "url": {"type": "string"},
            "snippet": {"type": "string"},
            "publish_time": {"type": ["string", "null"]},
            "domain": {"type": ["string", "null"]},
            "hostname": {"type": ["string", "null"]},
        },
        "required": ["title", "url", "snippet", "publish_time", "domain", "hostname"],
    }
    result = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "query_id": {"type": "string"},
            "query": {"type": "string"},
            "items": {"type": "array", "items": item, "maxItems": 5},
            "error": {"type": ["string", "null"]},
        },
        "required": ["query_id", "query", "items", "error"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"results": {"type": "array", "items": result}},
        "required": ["results"],
    }


def search_codex_batch(queries: list[dict[str, Any]], *, timeout: int = 240) -> dict[str, dict[str, Any]]:
    """通过本机已登录 Codex CLI 执行一组公开网页搜索。

    查询仍以独立 query_job 入库；批量调用只为减少本机进程和模型启动开销。
    可通过 CODEX_WEB_SEARCH_FIXTURE 指向测试 JSON，避免测试产生联网调用。
    """
    fixture = __import__("os").getenv("CODEX_WEB_SEARCH_FIXTURE")
    if fixture:
        payload = json.loads(Path(fixture).read_text(encoding="utf-8"))
    else:
        cli = Path(CODEX_CLI_PATH)
        if not cli.exists():
            raise RuntimeError("本机未找到 Codex CLI，请从 Codex 桌面应用启动或配置 CODEX_CLI_PATH")
        compact_queries = [{"query_id": item["query_id"], "query": item["query"]} for item in queries]
        prompt = (
            "你是公开信息检索执行器。必须逐条处理输入查询，使用公开网页搜索；"
            "只返回可访问页面的标题、URL、摘要、公开发布时间、domain 和 hostname。"
            "搜索排序和结果数不代表热点，不输出热点结论，不修改任何本地文件。"
            "每条查询最多返回5项；无法取得时填写error并返回空items。输入："
            + json.dumps(compact_queries, ensure_ascii=False)
        )
        with tempfile.TemporaryDirectory(prefix="ai-hotspot-codex-") as temp_dir:
            schema_path = Path(temp_dir) / "schema.json"
            output_path = Path(temp_dir) / "result.json"
            schema_path.write_text(json.dumps(_codex_schema(), ensure_ascii=False), encoding="utf-8")
            command = [
                str(cli), "--search", "-a", "never", "-s", "read-only", "-C", str(PROJECT_ROOT),
                "exec", "--ephemeral", "--output-schema", str(schema_path),
                "--output-last-message", str(output_path), prompt,
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "Codex公开搜索执行失败").strip()
                raise RuntimeError(detail[-1200:])
            payload = json.loads(output_path.read_text(encoding="utf-8"))
    mapped: dict[str, dict[str, Any]] = {}
    for result in payload.get("results", []):
        if not isinstance(result, dict) or not result.get("query_id"):
            continue
        items = [item for item in result.get("items", []) if isinstance(item, dict)]
        mapped[str(result["query_id"])] = {
            "provider": "codex_web_search",
            "query": result.get("query") or "",
            "items": items,
            "raw_response": result,
            "error": result.get("error"),
        }
    return mapped


# 保留旧调用名，避免已有脚本瞬间失效；新管线显式使用提供方函数。
search_one = search_doubao


def load_existing_sample(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("provider") != "doubao_global_search":
        raise ValueError("真实样本提供方不是 doubao_global_search")
    items = parse_processed_items(payload.get("result") or {})
    return {**payload, "items": items}
