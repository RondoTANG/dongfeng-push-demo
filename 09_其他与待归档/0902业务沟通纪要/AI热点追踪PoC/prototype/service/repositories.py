from __future__ import annotations

from typing import Any

from .database import fetch_all, fetch_one


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    return fetch_all("SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT ?", (limit,))


def get_run(run_id: str) -> dict[str, Any] | None:
    run = fetch_one("SELECT * FROM collection_runs WHERE run_id = ?", (run_id,))
    if not run:
        return None
    run["query_jobs"] = fetch_all("SELECT * FROM query_jobs WHERE run_id = ? ORDER BY query_id", (run_id,))
    return run


def list_sources(
    *,
    run_id: str | None = None,
    status: str | None = None,
    platform: str | None = None,
    keyword: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if run_id:
        conditions.append("run_id = ?")
        params.append(run_id)
    if status:
        conditions.append("source_status = ?")
        params.append(status)
    if platform:
        conditions.append("source_platform = ?")
        params.append(platform)
    if keyword:
        conditions.append("(title LIKE ? OR snippet LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    return fetch_all(f"SELECT * FROM source_items {where} ORDER BY fetched_at DESC LIMIT ?", tuple(params))


def list_invalid(
    run_id: str | None = None,
    rule_id: str | None = None,
    keyword: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if run_id:
        conditions.append("run_id = ?")
        params.append(run_id)
    if rule_id:
        conditions.append("invalid_rule_id = ?")
        params.append(rule_id)
    if keyword:
        conditions.append("(invalid_reason LIKE ? OR source_id_or_raw_result_id LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    return fetch_all(f"SELECT * FROM invalid_logs {where} ORDER BY discarded_at DESC LIMIT ?", tuple(params))


def list_audit(
    *,
    object_type: str | None = None,
    action: str | None = None,
    actor_id: str | None = None,
    keyword: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if object_type:
        conditions.append("object_type = ?")
        params.append(object_type)
    if action:
        conditions.append("action = ?")
        params.append(action)
    if actor_id:
        conditions.append("actor_id = ?")
        params.append(actor_id)
    if keyword:
        conditions.append("(object_id LIKE ? OR action LIKE ? OR actor_id LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    return fetch_all(f"SELECT * FROM audit_logs {where} ORDER BY created_at DESC LIMIT ?", tuple(params))
