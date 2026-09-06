from __future__ import annotations

import json
from urllib.parse import urlsplit, urlunsplit


RESPONSE_WRAPPER_KEYS = ("output", "outputs", "items", "data", "results", "content")


def _parse_json_if_possible(value):
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _is_api_payload(value):
    return isinstance(value, dict) and ("ResponseMetadata" in value or "Result" in value)


def _iter_api_responses(value):
    value = _parse_json_if_possible(value)
    if isinstance(value, list):
        for item in value:
            yield from _iter_api_responses(item)
        return
    if not isinstance(value, dict):
        return
    if _is_api_payload(value):
        yield value, None
        return
    if "body" in value:
        body = _parse_json_if_possible(value.get("body"))
        if _is_api_payload(body):
            yield body, value.get("status_code")
            return
    for key in RESPONSE_WRAPPER_KEYS:
        if key in value:
            yield from _iter_api_responses(value.get(key))


def _canonical_url(value):
    text = str(value or "").strip()
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def _domain(url):
    try:
        return (urlsplit(url).hostname or "").lower().strip(".")
    except ValueError:
        return ""


def _text_snippet(value):
    if not isinstance(value, list):
        return ""
    parts, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or item.get("Type") != "text":
            continue
        text = str(item.get("Text", "")).strip()
        if text and text not in seen:
            seen.add(text)
            parts.append(text)
    return "\n".join(parts)


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _warning_text(index, payload, result):
    metadata = payload.get("ResponseMetadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    metadata_error = metadata.get("Error")
    if isinstance(metadata_error, dict):
        code = metadata_error.get("Code") or metadata_error.get("CodeN") or ""
        message = str(metadata_error.get("Message", "")).strip()
        return f"第{index}次搜索接口错误{f' {code}' if code else ''}：{message or '未知错误'}"
    if result is None:
        return f"第{index}次搜索Result为空"
    error_code = _integer(result.get("ErrorCode"), default=-1)
    if error_code != 0:
        error_message = str(result.get("ErrorMsg", "")).strip()
        return f"第{index}次搜索失败 {error_code}：{error_message or '未知错误'}"
    return ""


def handler(params):
    """把豆包 Global Search 原始信封转换为热点 PoC 的统一来源列表。"""
    try:
        responses = list(_iter_api_responses(params.get("search_results", [])))
        if not responses:
            raise ValueError("未识别到豆包搜索响应，请确认已引用HTTP节点的完整输出")
        unique, warnings = {}, []
        for response_index, (payload, status_code) in enumerate(responses, 1):
            status = _integer(status_code, default=200)
            if status < 200 or status >= 300:
                warnings.append(f"第{response_index}次搜索HTTP状态码为{status}，已跳过")
                continue
            result = payload.get("Result")
            result = result if isinstance(result, dict) else None
            error = _warning_text(response_index, payload, result)
            if error:
                warnings.append(error)
                continue
            documents = result.get("Documents")
            if not isinstance(documents, list):
                warnings.append(f"第{response_index}次搜索没有Documents数组")
                continue
            metadata = payload.get("ResponseMetadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            request_id = str(metadata.get("RequestId", "")).strip()
            for document in documents:
                if not isinstance(document, dict):
                    continue
                url = _canonical_url(document.get("Url"))
                if not url or url in unique:
                    continue
                document_info = document.get("DocumentInfo")
                document_info = document_info if isinstance(document_info, dict) else {}
                host_info = document.get("HostInfo")
                host_info = host_info if isinstance(host_info, dict) else {}
                unique[url] = {
                    "source_id": "",
                    "source_type": "web_search",
                    "rank": _integer(document.get("Rank"), default=0),
                    "title": str(document.get("Title", "")).strip(),
                    "url": url,
                    "domain": _domain(url),
                    "hostname": str(host_info.get("Hostname", "")).strip(),
                    "provider_authority_level": str(host_info.get("AuthorityLevel", "")).strip(),
                    "publish_time": str(document_info.get("PublishTime", "")).strip(),
                    "filetype": str(document_info.get("Filetype", "")).strip(),
                    "snippet": _text_snippet(document.get("Snippet")),
                    "provider_request_id": request_id,
                }
        web_search_items = list(unique.values())
        for index, item in enumerate(web_search_items, 1):
            item["source_id"] = f"W{index:02d}"
        if not web_search_items and not warnings:
            warnings.append("豆包搜索未返回可用URL")
        return {
            "success": bool(web_search_items),
            "web_search_items_json": json.dumps(web_search_items, ensure_ascii=False),
            "error_message": "" if web_search_items else "；".join(warnings),
        }
    except Exception as exc:
        return {"success": False, "web_search_items_json": "[]", "error_message": str(exc)}
