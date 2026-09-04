from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .collector import load_existing_sample, search_one
from .config_loader import active_brands, config_versions, domain_rules, query_catalog
from .database import add_audit, connection, json_text, new_id, now_iso
from .settings import REAL_SAMPLE_PATH


TRACKING_PREFIXES = ("utm_", "from", "source", "share_token")
ADMIN_TERMS = ("招标", "采购", "招聘", "环评公示", "任免", "评标专家")
PROMOTION_TERMS = ("报价", "优惠", "到店", "联系电话", "促销", "团购")
NON_EVENT_TITLES = ("首页", "企业新闻", "品牌官网", "官方网站")


def _parse_time(value: str | None) -> tuple[str | None, str]:
    if not value:
        return None, "unknown"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat(), "high"
    except ValueError:
        return value, "low"


def _canonical_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    if not parts.scheme or not parts.netloc:
        return (url or "").strip()
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not any(key.lower().startswith(prefix) for prefix in TRACKING_PREFIXES)
    ]
    normalized_host = parts.netloc.lower()
    normalized_path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.lower(), normalized_host, normalized_path, urlencode(query), ""))


def _resolve_platform(domain: str | None, hostname: str | None) -> tuple[str, str | None]:
    normalized = (domain or "").lower().split(":", 1)[0]
    for rule in domain_rules():
        rule_domain = rule.get("domain", "").lower()
        if normalized == rule_domain or normalized.endswith(f".{rule_domain}"):
            return rule.get("source_platform", "unknown"), rule.get("source_site_name")
    return "unknown", hostname or normalized or None


def _match_brands(text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for brand in active_brands():
        exact_terms = [brand.get("canonical_name", ""), *brand.get("exact_aliases", [])]
        hit = next((term for term in exact_terms if term and term in text), None)
        if not hit:
            for weak in brand.get("weak_aliases", []):
                if weak and weak in text and any(ctx in text for ctx in brand.get("weak_alias_context_terms", [])):
                    hit = weak
                    break
        if hit:
            matches.append(
                {
                    "brand_id": brand.get("brand_id"),
                    "brand_name": brand.get("canonical_name"),
                    "relation_status": "direct_mention",
                    "matched_term": hit,
                }
            )
    return matches


def _invalid_reason(item: dict[str, Any], query_group: str, brand_matches: list[dict[str, Any]]) -> tuple[str, str] | None:
    url = (item.get("url") or "").strip()
    title = (item.get("title") or "").strip()
    snippet = (item.get("snippet") or "").strip()
    text = f"{title}\n{snippet}"
    if not url or not (title or snippet):
        return "INV001", "无法访问或无有效URL"
    if any(term in text for term in ADMIN_TERMS):
        return "INV003", "纯招投标采购招聘行政信息"
    if sum(term in text for term in PROMOTION_TERMS) >= 2:
        return "INV004", "纯促销引流"
    published, _ = _parse_time(item.get("publish_time"))
    if published:
        try:
            published_dt = datetime.fromisoformat(published)
            now = datetime.now().astimezone()
            if published_dt.tzinfo is None:
                published_dt = published_dt.replace(tzinfo=now.tzinfo)
            if published_dt < now - timedelta(hours=72):
                return "INV005", "旧闻重新索引：发布时间超过72小时且当前未识别新增事实"
        except ValueError:
            pass
    if any(term in title for term in NON_EVENT_TITLES) and len(snippet) < 160:
        return "INV006", "无实际事件：导航或常驻列表页"
    if query_group == "brand" and not brand_matches:
        return "INV002", "同名或弱关联结果：未匹配已登记品牌"
    return None


def _new_run(trigger_type: str, mode: str, idempotency_key: str | None) -> tuple[str, bool]:
    if idempotency_key:
        with connection() as db:
            row = db.execute(
                "SELECT run_id FROM collection_runs WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if row:
                return row["run_id"], False
    run_id = new_id("RUN")
    now = now_iso()
    with connection() as db:
        db.execute(
            """
            INSERT INTO collection_runs (
                run_id, idempotency_key, trigger_type, mode, status, started_at,
                config_versions_json, query_coverage_json, provider_summary_json, step_summary_json
            ) VALUES (?, ?, ?, ?, 'running', ?, ?, '{}', '{}', '{}')
            """,
            (run_id, idempotency_key, trigger_type, mode, now, json_text(config_versions())),
        )
    add_audit("create", "collection_run", run_id, actor_type="system", actor_id="pipeline")
    return run_id, True


def _query_lookup() -> dict[str, dict[str, Any]]:
    return {item["query"]: item for item in query_catalog()}


def _assign_sample_items(queries: list[str], items: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    lookup = _query_lookup()
    assignments: list[tuple[dict[str, Any], dict[str, Any]]] = []
    query_index = -1
    for index, item in enumerate(items):
        if item.get("rank") == 0 or query_index < 0:
            query_index += 1
        query_text = queries[min(query_index, max(len(queries) - 1, 0))] if queries else "样本导入"
        query = lookup.get(query_text, {"query_id": f"IMP{query_index + 1:02d}", "query": query_text, "query_group": "import"})
        assignments.append((query, item))
    return assignments


def _store_query_and_items(
    run_id: str,
    query: dict[str, Any],
    items: list[dict[str, Any]],
    raw_payload: dict[str, Any],
    *,
    status: str = "success",
    error_message: str | None = None,
) -> dict[str, int]:
    query_job_id = new_id("QRY")
    raw_result_id = new_id("RAW")
    timestamp = now_iso()
    counts = {"sources": 0, "valid": 0, "invalid": 0}
    with connection() as db:
        db.execute(
            """
            INSERT INTO query_jobs (
                query_job_id, run_id, query_id, query_text, query_group, status,
                provider_id, started_at, finished_at, result_count, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, 'doubao_global_search', ?, ?, ?, ?)
            """,
            (
                query_job_id,
                run_id,
                query.get("query_id", "UNKNOWN"),
                query.get("query", ""),
                query.get("query_group", "unknown"),
                "no_result" if status == "success" and not items else status,
                timestamp,
                timestamp,
                len(items),
                error_message,
            ),
        )
        db.execute(
            """
            INSERT INTO raw_provider_results (
                raw_result_id, run_id, provider_id, query_id, request_started_at,
                response_received_at, request_status, provider_request_id, raw_payload_json
            ) VALUES (?, ?, 'doubao_global_search', ?, ?, ?, ?, ?, ?)
            """,
            (
                raw_result_id,
                run_id,
                query.get("query_id", "UNKNOWN"),
                timestamp,
                timestamp,
                status,
                next((item.get("provider_request_id") for item in items if item.get("provider_request_id")), None),
                json_text(raw_payload),
            ),
        )
        for item in items:
            canonical_url = _canonical_url(item.get("url") or "")
            digest = hashlib.sha256(f"{run_id}|{canonical_url}".encode("utf-8")).hexdigest()[:14]
            source_id = f"SRC-{digest}"
            existing = db.execute("SELECT query_ids_json FROM source_items WHERE source_id = ?", (source_id,)).fetchone()
            if existing:
                query_ids = set(json.loads(existing["query_ids_json"] or "[]"))
                query_ids.add(query.get("query_id", "UNKNOWN"))
                db.execute("UPDATE source_items SET query_ids_json = ? WHERE source_id = ?", (json_text(sorted(query_ids)), source_id))
                continue
            text = f"{item.get('title') or ''}\n{item.get('snippet') or ''}"
            brand_matches = _match_brands(text)
            invalid = _invalid_reason(item, query.get("query_group", "unknown"), brand_matches)
            source_status = "invalid" if invalid else "valid"
            platform, site_name = _resolve_platform(item.get("domain"), item.get("hostname"))
            published_at, time_confidence = _parse_time(item.get("publish_time"))
            db.execute(
                """
                INSERT INTO source_items (
                    source_id, run_id, raw_result_id, retrieved_by, query_ids_json,
                    source_status, source_platform, source_site_name, source_account,
                    original_url, canonical_url, domain, title, snippet, published_at,
                    published_time_confidence, fetched_at, first_seen_at, provider_authority_level
                ) VALUES (?, ?, ?, 'doubao_global_search', ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    run_id,
                    raw_result_id,
                    json_text([query.get("query_id", "UNKNOWN")]),
                    source_status,
                    platform,
                    site_name,
                    item.get("url") or "",
                    canonical_url,
                    item.get("domain"),
                    item.get("title") or (item.get("snippet") or "")[:80] or "未命名线索",
                    item.get("snippet"),
                    published_at,
                    time_confidence,
                    timestamp,
                    timestamp,
                    item.get("provider_authority_level"),
                ),
            )
            counts["sources"] += 1
            counts[source_status] += 1
            if invalid:
                db.execute(
                    """
                    INSERT INTO invalid_logs (
                        invalid_id, run_id, source_id_or_raw_result_id,
                        invalid_rule_id, invalid_reason, discarded_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (new_id("INV"), run_id, source_id, invalid[0], invalid[1], timestamp),
                )
    return counts


def _finish_run(run_id: str, *, failed_queries: int = 0, error_message: str | None = None) -> None:
    with connection() as db:
        query_rows = db.execute("SELECT status, COUNT(*) count FROM query_jobs WHERE run_id=? GROUP BY status", (run_id,)).fetchall()
        source_rows = db.execute("SELECT source_status, COUNT(*) count FROM source_items WHERE run_id=? GROUP BY source_status", (run_id,)).fetchall()
        query_summary = {row["status"]: row["count"] for row in query_rows}
        source_summary = {row["source_status"]: row["count"] for row in source_rows}
        total_queries = sum(query_summary.values())
        succeeded = query_summary.get("success", 0) + query_summary.get("no_result", 0)
        if total_queries == 0 or succeeded == 0:
            status = "failed"
        elif failed_queries or query_summary.get("failed", 0):
            status = "partial_success"
        else:
            status = "success"
        db.execute(
            """
            UPDATE collection_runs
            SET status=?, finished_at=?, query_coverage_json=?, provider_summary_json=?,
                step_summary_json=?, error_message=?
            WHERE run_id=?
            """,
            (
                status,
                now_iso(),
                json_text({"planned": total_queries, "executed": total_queries, "by_status": query_summary}),
                json_text({"doubao_global_search": query_summary}),
                json_text({"source_processing": source_summary}),
                error_message,
                run_id,
            ),
        )
    add_audit("complete", "collection_run", run_id, actor_type="system", actor_id="pipeline", after={"status": status})


def import_real_sample(idempotency_key: str = "real-sample-20260903-v1") -> str:
    run_id, created = _new_run("import", "sample", idempotency_key)
    if not created:
        return run_id
    try:
        sample = load_existing_sample(REAL_SAMPLE_PATH)
        assignments = _assign_sample_items(sample.get("queries", []), sample["items"])
        grouped: dict[str, dict[str, Any]] = {}
        for query, item in assignments:
            entry = grouped.setdefault(query.get("query_id", "UNKNOWN"), {"query": query, "items": []})
            entry["items"].append(item)
        for entry in grouped.values():
            _store_query_and_items(run_id, entry["query"], entry["items"], sample.get("result") or {})
        _finish_run(run_id)
    except Exception as exc:
        _finish_run(run_id, failed_queries=1, error_message=str(exc))
        raise
    return run_id


def execute_collection(
    *,
    mode: str = "quick",
    trigger_type: str = "manual",
    idempotency_key: str | None = None,
    timeout: int = 30,
) -> str:
    run_id, created = _new_run(trigger_type, mode, idempotency_key)
    if not created:
        return run_id
    catalog = query_catalog()
    selected = catalog[:1] if mode == "quick" else catalog
    failed = 0
    last_error: str | None = None
    for query in selected:
        try:
            response = search_one(query["query"], timeout=timeout)
            _store_query_and_items(run_id, query, response["items"], response["processed"])
        except Exception as exc:
            failed += 1
            last_error = str(exc)
            _store_query_and_items(run_id, query, [], {"error": last_error}, status="failed", error_message=last_error)
    _finish_run(run_id, failed_queries=failed, error_message=last_error)
    return run_id
