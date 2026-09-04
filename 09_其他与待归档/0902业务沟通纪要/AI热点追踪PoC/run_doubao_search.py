#!/usr/bin/env python3
"""调用豆包Global Search，并复用现有结果拆包逻辑。

接口地址、方法和请求结构来自用户提供的Global版接口文档。
API Key不写入项目文件；运行时从环境变量或macOS Keychain读取。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ENDPOINT = "https://open.feedcoopapi.com/search_api/global_search"
KEYCHAIN_SERVICE = "guard-army-doubao-search"
KEYCHAIN_ACCOUNT = "api-key"
API_KEY_ENV = "DOUBAO_SEARCH_API_KEY"


def load_api_key() -> str:
    env_value = os.environ.get(API_KEY_ENV, "").strip()
    if env_value:
        return env_value

    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_ACCOUNT,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "未找到豆包搜索API Key；可通过环境变量或macOS Keychain提供，"
            f"service={KEYCHAIN_SERVICE}, account={KEYCHAIN_ACCOUNT}"
        )
    api_key = result.stdout.strip()
    if not api_key:
        raise RuntimeError("豆包搜索API Key为空")
    return api_key


def _load_processor():
    project_root = Path(__file__).resolve().parents[3]
    processor_path = (
        project_root
        / "03_审核与AI中台"
        / "AI评论与直播话术生成"
        / "code"
        / "doubao_search_result_processor.py"
    )
    spec = importlib.util.spec_from_file_location(
        "doubao_search_result_processor", processor_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载结果解析器：{processor_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_request_body(query: str) -> dict:
    query = query.strip()
    if not 1 <= len(query) <= 100:
        raise ValueError("Query长度必须为1～100个字符")
    return {
        "Query": query,
        "SearchType": "web",
        "DocCount": 3,
        "MaxSnippetLength": 1000,
        "MaxImageCountPerDoc": 1,
    }


def _request_once(api_key: str, query: str, timeout: int) -> dict:
    body = build_request_body(query)
    request = Request(
        ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return {
                "status_code": response.status,
                "body": json.loads(response_body),
            }
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"豆包搜索HTTP {exc.code}：{message}") from exc
    except URLError as exc:
        raise RuntimeError(f"豆包搜索网络错误：{exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("豆包搜索响应不是合法JSON") from exc


def search(api_key: str, query: str, timeout: int) -> dict:
    last_error: Exception | None = None
    for attempt, delay in enumerate((0, 2, 8), start=1):
        if delay:
            time.sleep(delay)
        try:
            return _request_once(api_key, query, timeout)
        except (RuntimeError, TimeoutError) as exc:
            last_error = exc
            if attempt == 3:
                break
    raise RuntimeError(str(last_error or "豆包搜索失败"))


def main() -> int:
    parser = argparse.ArgumentParser(description="豆包Global Search PoC调用器")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument(
        "--show-request",
        action="store_true",
        help="显示脱敏后的实际请求，不读取或输出API Key",
    )
    args = parser.parse_args()

    try:
        if args.show_request:
            if not args.query:
                parser.error("--show-request至少需要一个 --query")
            print(
                json.dumps(
                    {
                        "url": ENDPOINT,
                        "method": "POST",
                        "headers": {
                            "Authorization": "Bearer ***",
                            "Content-Type": "application/json; charset=utf-8",
                        },
                        "requests": [build_request_body(query) for query in args.query],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        api_key = load_api_key()
        if args.check_config:
            print("doubao_search_api_key_ok")
            return 0
        if not args.query:
            parser.error("至少提供一个 --query")

        responses = [search(api_key, query.strip(), args.timeout) for query in args.query]
        processor = _load_processor()
        result = processor.handler({"search_results": responses})
        payload = {
            "provider": "doubao_global_search",
            "queries": args.query,
            "result": result,
        }
        output_text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output_text + "\n", encoding="utf-8")
        print(output_text)
        return 0 if result.get("success") else 2
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
