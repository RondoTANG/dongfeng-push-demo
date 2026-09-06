from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .database import add_audit, connection, now_iso
from .events import aggregate_run
from .pipeline import execute_collection, reserve_collection_run, run_cooldown
from .settings import AUTOMATION_CONFIG_PATH, AUTOMATION_SEED_PATH


_LOCK = threading.RLock()
_DEFAULT = {
    "enabled": False,
    "interval_hours": 3,
    "mode": "full",
    "automation_id": "poc",
    "actor_id": "server-scheduler",
    "next_run_at": None,
    "updated_at": None,
    "updated_by": "system",
}


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _normalise(payload: dict[str, Any]) -> dict[str, Any]:
    result = {**_DEFAULT, **payload}
    result["enabled"] = bool(result.get("enabled"))
    result["interval_hours"] = max(1, min(168, int(result.get("interval_hours") or 3)))
    result["mode"] = "full"
    return result


def load_automation_config() -> dict[str, Any]:
    with _LOCK:
        if not AUTOMATION_CONFIG_PATH.exists():
            seed = {}
            if AUTOMATION_SEED_PATH.exists():
                seed = json.loads(AUTOMATION_SEED_PATH.read_text(encoding="utf-8"))
            _atomic_write(AUTOMATION_CONFIG_PATH, _normalise(seed))
        return _normalise(json.loads(AUTOMATION_CONFIG_PATH.read_text(encoding="utf-8")))


def update_automation_config(*, enabled: bool, interval_hours: int, actor_id: str) -> dict[str, Any]:
    with _LOCK:
        before = load_automation_config()
        now = datetime.now().astimezone()
        changed_schedule = (not before["enabled"] and enabled) or before["interval_hours"] != interval_hours
        after = _normalise({
            **before,
            "enabled": enabled,
            "interval_hours": interval_hours,
            "updated_at": now.isoformat(timespec="seconds"),
            "updated_by": actor_id,
        })
        if not enabled:
            after["next_run_at"] = None
        elif changed_schedule or not after.get("next_run_at"):
            after["next_run_at"] = (now + timedelta(hours=after["interval_hours"])).isoformat(timespec="seconds")
        _atomic_write(AUTOMATION_CONFIG_PATH, after)
    add_audit("update", "automation_config", "poc", actor_type="admin", actor_id=actor_id, before=before, after=after)
    return after


def _has_running_collection() -> bool:
    with connection() as db:
        row = db.execute("SELECT 1 FROM collection_runs WHERE status='running' LIMIT 1").fetchone()
    return bool(row)


def _claim_due_run() -> tuple[str, dict[str, Any]] | None:
    with _LOCK:
        config = load_automation_config()
        if not config["enabled"] or not config.get("next_run_at") or _has_running_collection():
            return None
        now = datetime.now().astimezone()
        due = datetime.fromisoformat(str(config["next_run_at"]))
        if due.tzinfo is None:
            due = due.replace(tzinfo=now.tzinfo)
        if now < due:
            return None
        cooldown = run_cooldown("full")
        if not cooldown["allowed"]:
            config["next_run_at"] = cooldown["next_allowed_at"]
            _atomic_write(AUTOMATION_CONFIG_PATH, config)
            return None
        run_id = reserve_collection_run(
            trigger_type="schedule",
            mode="full",
            idempotency_key=f"schedule-{due.isoformat(timespec='minutes')}",
        )
        config["last_triggered_at"] = now.isoformat(timespec="seconds")
        config["last_run_id"] = run_id
        config["next_run_at"] = (now + timedelta(hours=config["interval_hours"])).isoformat(timespec="seconds")
        _atomic_write(AUTOMATION_CONFIG_PATH, config)
        return run_id, config


def _execute_scheduled(run_id: str) -> None:
    completed_id = execute_collection(run_id=run_id, mode="full", trigger_type="schedule", idempotency_key=None)
    with connection() as db:
        row = db.execute("SELECT status FROM collection_runs WHERE run_id=?", (completed_id,)).fetchone()
    if row and row["status"] in {"success", "partial_success"}:
        aggregate_run(completed_id)


async def scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            claimed = await asyncio.to_thread(_claim_due_run)
            if claimed:
                run_id, _ = claimed
                await asyncio.to_thread(_execute_scheduled, run_id)
        except Exception as exc:
            add_audit(
                "scheduler_error",
                "automation_config",
                "poc",
                actor_type="system",
                actor_id="server-scheduler",
                after={"error": str(exc)},
            )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=20)
        except asyncio.TimeoutError:
            pass


def automation_status_payload() -> dict[str, Any]:
    config = load_automation_config()
    with connection() as db:
        last_scheduled = db.execute(
            "SELECT run_id,status,started_at,finished_at FROM collection_runs WHERE trigger_type='schedule' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    return {"config": config, "last_scheduled_run": dict(last_scheduled) if last_scheduled else None}
