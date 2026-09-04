from __future__ import annotations

from typing import Any

from .collector import search_codex_batch, search_doubao
from .database import add_audit, connection, fetch_all, fetch_one, json_text, new_id, now_iso
from .events import get_event


ALLOWED_METHODS = {"codex_web_search", "doubao_global_search", "existing_url_parse", "manual_link"}


def create_evidence_plan(
    event_id: str,
    *,
    question: str | None = None,
    unresolved_items: list[str] | None = None,
    search_queries: list[str] | None = None,
    lookback_hours: int = 72,
) -> dict[str, Any]:
    event = get_event(event_id)
    if not event:
        raise LookupError("事件不存在")
    unresolved = unresolved_items or [
        *(item.get("uncertainty_reason") for item in (event.get("entity_uncertainties") or []) if item.get("uncertainty_reason")),
        *(event.get("missing_evidence") or []),
    ]
    unresolved = list(dict.fromkeys(str(item) for item in unresolved if str(item).strip()))[:8]
    default_question = f"核验事件“{event.get('event_title')}”的发布时间、官方事实、品牌关系及风险边界"
    queries = search_queries or [f"{event.get('event_title')} 官方 最新"]
    request_id = new_id("EVR")
    timestamp = now_iso()
    estimated = {"codex_web_search": len(queries), "doubao_global_search": len(queries)}
    with connection() as db:
        db.execute(
            """
            INSERT INTO evidence_requests (
                evidence_request_id,event_id,status,question,unresolved_items_json,
                search_queries_json,selected_methods_json,lookback_hours,
                estimated_calls_json,created_at
            ) VALUES (?,?, 'pending_confirmation', ?,?,?, '[]',?,?,?)
            """,
            (request_id, event_id, question or default_question, json_text(unresolved), json_text(queries), lookback_hours, json_text(estimated), timestamp),
        )
    result = get_evidence_request(request_id) or {}
    add_audit("create_plan", "evidence_request", request_id, actor_type="operator", actor_id="本地运营", after=result)
    return result


def get_evidence_request(request_id: str) -> dict[str, Any] | None:
    item = fetch_one("SELECT * FROM evidence_requests WHERE evidence_request_id=?", (request_id,))
    if item:
        item["jobs"] = fetch_all("SELECT * FROM evidence_jobs WHERE evidence_request_id=? ORDER BY started_at, evidence_job_id", (request_id,))
    return item


def list_evidence_requests(event_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if event_id:
        return fetch_all("SELECT * FROM evidence_requests WHERE event_id=? ORDER BY created_at DESC LIMIT ?", (event_id, limit))
    return fetch_all("SELECT * FROM evidence_requests ORDER BY created_at DESC LIMIT ?", (limit,))


def confirm_evidence_request(request_id: str, *, methods: list[str], confirmed_by: str) -> dict[str, Any]:
    item = get_evidence_request(request_id)
    if not item:
        raise LookupError("补证申请不存在")
    if item["status"] != "pending_confirmation":
        raise ValueError(f"当前补证状态不可确认：{item['status']}")
    selected = list(dict.fromkeys(methods))
    invalid = set(selected) - ALLOWED_METHODS
    if invalid:
        raise ValueError(f"不支持的补证方式：{', '.join(sorted(invalid))}")
    if not selected:
        raise ValueError("至少选择一种补证方式")
    timestamp = now_iso()
    with connection() as db:
        db.execute(
            "UPDATE evidence_requests SET status='confirmed',selected_methods_json=?,confirmed_by=?,confirmed_at=? WHERE evidence_request_id=?",
            (json_text(selected), confirmed_by, timestamp, request_id),
        )
    return get_evidence_request(request_id) or {}


def _add_job(request_id: str, provider: str, query: str | None) -> str:
    job_id = new_id("EVJ")
    with connection() as db:
        db.execute(
            "INSERT INTO evidence_jobs (evidence_job_id,evidence_request_id,provider_id,query_text,status,started_at) VALUES (?,?,?,?, 'running',?)",
            (job_id, request_id, provider, query, now_iso()),
        )
    return job_id


def _finish_job(job_id: str, *, items: list[dict[str, Any]] | None = None, error: str | None = None) -> None:
    with connection() as db:
        db.execute(
            "UPDATE evidence_jobs SET status=?,result_count=?,result_json=?,finished_at=?,error_message=? WHERE evidence_job_id=?",
            ("failed" if error else "success", len(items or []), json_text(items or []), now_iso(), error, job_id),
        )


def execute_evidence_request(request_id: str) -> dict[str, Any]:
    request = get_evidence_request(request_id)
    if not request:
        raise LookupError("补证申请不存在")
    if request["status"] not in {"confirmed", "failed"}:
        raise ValueError(f"当前补证状态不可执行：{request['status']}")
    methods = request.get("selected_methods") or []
    queries = request.get("search_queries") or []
    timestamp = now_iso()
    with connection() as db:
        db.execute("UPDATE evidence_requests SET status='running',error_message=NULL WHERE evidence_request_id=?", (request_id,))
    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    if "existing_url_parse" in methods:
        job_id = _add_job(request_id, "existing_url_parse", None)
        current = fetch_all("SELECT evidence_text text,evidence_url url FROM event_evidence WHERE event_id=?", (request["event_id"],))
        _finish_job(job_id, items=current)
        evidence.extend(current)
    if "codex_web_search" in methods and queries:
        query_defs = [{"query_id": f"E{index:02d}", "query": query} for index, query in enumerate(queries, 1)]
        jobs = {item["query_id"]: _add_job(request_id, "codex_web_search", item["query"]) for item in query_defs}
        try:
            results = search_codex_batch(query_defs)
            for item in query_defs:
                result = results.get(item["query_id"], {})
                error = result.get("error") or (None if result.get("items") is not None else "Codex未返回查询结果")
                _finish_job(jobs[item["query_id"]], items=result.get("items") or [], error=error)
                if error:
                    errors.append(str(error))
                evidence.extend(result.get("items") or [])
        except Exception as exc:
            for job_id in jobs.values():
                _finish_job(job_id, error=str(exc))
            errors.append(str(exc))
    if "doubao_global_search" in methods:
        for query in queries:
            job_id = _add_job(request_id, "doubao_global_search", query)
            try:
                result = search_doubao(query)
                _finish_job(job_id, items=result["items"])
                evidence.extend(result["items"])
            except Exception as exc:
                _finish_job(job_id, error=str(exc))
                errors.append(str(exc))
    with connection() as db:
        for item in evidence:
            text = str(item.get("snippet") or item.get("text") or item.get("title") or "").strip()
            if not text:
                continue
            db.execute(
                """
                INSERT INTO event_evidence (
                    evidence_id,event_id,source_id,evidence_type,evidence_text,evidence_url,provided_by,created_at
                ) VALUES (?,?,NULL,'targeted_supplement',?,?,?,?)
                """,
                (new_id("EVD"), request["event_id"], text[:1600], item.get("url"), "evidence-request", timestamp),
            )
        status = "failed" if errors and not evidence else "partial_success" if errors else "completed"
        summary = f"新增{len(evidence)}条补证结果；失败{len(errors)}项。请运营重新研判，系统不自动改变业务结论。"
        db.execute(
            "UPDATE evidence_requests SET status=?,result_summary=?,completed_at=?,error_message=? WHERE evidence_request_id=?",
            (status, summary, now_iso(), "；".join(errors)[:1000] if errors else None, request_id),
        )
        db.execute(
            "UPDATE events SET event_status='pending_review',decision_reason=?,updated_at=? WHERE event_id=?",
            (summary, now_iso(), request["event_id"]),
        )
    result = get_evidence_request(request_id) or {}
    add_audit("execute", "evidence_request", request_id, actor_type="system", actor_id="evidence-runner", after=result)
    return result
