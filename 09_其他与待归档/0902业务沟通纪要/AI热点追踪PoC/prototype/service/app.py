from __future__ import annotations

from contextlib import asynccontextmanager
import json

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .database import add_audit, init_database
from .config_loader import business_config_summary, reload_configs
from .drafts import get_draft, list_drafts, review_draft, review_event, update_draft
from .events import aggregate_run, get_event, list_events, merge_events, split_event
from .pipeline import execute_collection, import_real_sample
from .repositories import get_run, list_audit, list_invalid, list_runs, list_sources
from .settings import DATABASE_PATH, PROJECT_ROOT
from .work_items import claim_work_item, complete_work_item, fail_work_item, get_work_item, list_work_items


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="东风护卫军 AI 热点线索 PoC",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)


class RunRequest(BaseModel):
    mode: str = Field(default="quick", pattern="^(quick|full)$")
    trigger_type: str = Field(default="manual", pattern="^(manual|schedule)$")
    idempotency_key: str | None = Field(default=None, max_length=120)
    timeout: int = Field(default=30, ge=5, le=120)


class WorkItemActor(BaseModel):
    actor_id: str = Field(min_length=2, max_length=80)


class WorkItemComplete(BaseModel):
    actor_id: str = Field(min_length=2, max_length=80)
    summary: str = Field(min_length=5, max_length=3000)
    decision_reason: str | None = Field(default=None, max_length=3000)
    evidence: list[dict[str, object]] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)
    entity_mentions: list[dict[str, object]] | None = None
    entity_uncertainties: list[dict[str, object]] | None = None
    brand_relations: list[dict[str, object]] | None = None


class WorkItemFail(BaseModel):
    actor_id: str = Field(min_length=2, max_length=80)
    error_message: str = Field(min_length=2, max_length=500)


class MergeRequest(BaseModel):
    event_ids: list[str] = Field(min_length=2)
    event_title: str = Field(min_length=4, max_length=160)
    actor_id: str = Field(default="local-operator", min_length=2, max_length=80)


class SplitRequest(BaseModel):
    source_ids: list[str] = Field(min_length=1)
    new_title: str = Field(min_length=4, max_length=160)
    actor_id: str = Field(default="local-operator", min_length=2, max_length=80)


class EventReviewRequest(BaseModel):
    review_result: str = Field(pattern="^(approved|approved_after_edit|rejected)$")
    event_status: str | None = None
    reviewer: str = Field(default="local-operator", min_length=2, max_length=80)
    review_note: str | None = Field(default=None, max_length=1000)
    evidence_summary: str = Field(min_length=5, max_length=3000)
    risk_summary: str = Field(default="未发现需要阻断草案生成的明确风险", max_length=2000)
    recommended_action: str = Field(default="由运营分别判断是否形成原创增长草案或源内容加热草案", max_length=1000)
    action_paths: list[str] = Field(default_factory=lambda: ["original_growth"], max_length=2)
    boost_source_ids: list[str] = Field(default_factory=list, max_length=3)


class DraftUpdateRequest(BaseModel):
    actor_id: str = Field(default="local-operator", min_length=2, max_length=80)
    task_type: str | None = None
    task_title: str | None = Field(default=None, min_length=4, max_length=160)
    task_brief: str | None = Field(default=None, min_length=10, max_length=5000)
    recommended_platforms: list[str] | None = None
    target_member_tags: list[str] | None = None
    engagement_actions: list[str] | None = None
    response_deadline: str | None = None
    prohibited_claims: list[str] | None = None
    risk_notes: list[str] | None = None


class DraftReviewRequest(BaseModel):
    review_result: str = Field(pattern="^(approved|rejected)$")
    reviewer: str = Field(default="local-operator", min_length=2, max_length=80)
    review_note: str | None = Field(default=None, max_length=1000)


def execute_and_aggregate(**kwargs: object) -> None:
    run_id = execute_collection(**kwargs)
    run = get_run(run_id) or {}
    if run.get("status") in {"success", "partial_success"}:
        aggregate_run(run_id)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "ai-hotspot-clue-poc",
        "database": DATABASE_PATH.name,
        "scope": "collection-to-draft-approval",
    }


@app.get("/api/runs")
def runs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    return {"items": list_runs(limit), "limit": limit}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, object]:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行批次不存在")
    return run


@app.post("/api/runs", status_code=202)
def create_run(payload: RunRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
    background_tasks.add_task(
        execute_and_aggregate,
        mode=payload.mode,
        trigger_type=payload.trigger_type,
        idempotency_key=payload.idempotency_key,
        timeout=payload.timeout,
    )
    return {"accepted": True, "message": "运行已进入本地执行队列"}


@app.post("/api/runs/import-real-sample")
def import_sample() -> dict[str, object]:
    run_id = import_real_sample()
    return get_run(run_id) or {"run_id": run_id}


@app.get("/api/sources")
def sources(
    run_id: str | None = None,
    status: str | None = None,
    platform: str | None = None,
    keyword: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    items = list_sources(run_id=run_id, status=status, platform=platform, keyword=keyword, limit=limit)
    return {"items": items, "count": len(items)}


@app.get("/api/invalid-records")
def invalid_records(
    run_id: str | None = None,
    rule_id: str | None = None,
    keyword: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    items = list_invalid(run_id, rule_id, keyword, limit)
    return {"items": items, "count": len(items)}


@app.get("/api/audit")
def audit(
    object_type: str | None = None,
    action: str | None = None,
    actor_id: str | None = None,
    keyword: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    items = list_audit(object_type=object_type, action=action, actor_id=actor_id, keyword=keyword, limit=limit)
    return {"items": items, "count": len(items)}


@app.get("/api/config/summary")
def config_summary() -> dict[str, object]:
    summary = business_config_summary()
    recent_runs = list_runs(200)
    for item in summary["meta"]:
        used_by = [
            run["run_id"] for run in recent_runs
            if (run.get("config_versions") or {}).get(item["config_key"]) == item["version"]
        ]
        item["used_by_run_count"] = len(used_by)
        item["latest_run_ids"] = used_by[:3]
    return summary


@app.get("/api/automation/status")
def automation_status() -> dict[str, object]:
    path = PROJECT_ROOT / "config" / "automation.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"enabled": False}
    scheduled_runs = [item for item in list_runs(200) if item.get("trigger_type") == "schedule"]
    pending = list_work_items("pending", 500)
    in_progress = list_work_items("in_progress", 500)
    return {
        "config": config,
        "last_scheduled_run": scheduled_runs[0] if scheduled_runs else None,
        "pending_work_item_count": len(pending),
        "in_progress_work_item_count": len(in_progress),
        "runner_command": "python3 scripts/run_collection.py --mode full --trigger-type schedule",
        "work_item_command": "python3 scripts/process_codex_work_items.py --claim-next --actor-id codex-local-automation",
        "mcp_required": False,
    }


@app.post("/api/config/reload")
def config_reload() -> dict[str, object]:
    before = business_config_summary().get("meta", [])
    reload_configs()
    after = config_summary()
    add_audit(
        "reload",
        "configuration",
        "local-yaml",
        actor_type="operator",
        actor_id="本地产品管理员",
        before=before,
        after=after.get("meta", []),
    )
    return {"ok": True, "message": "已重新读取本地 YAML 配置", "config": after}


@app.post("/api/runs/{run_id}/aggregate")
def aggregate(run_id: str) -> dict[str, int]:
    if not get_run(run_id):
        raise HTTPException(status_code=404, detail="运行批次不存在")
    return aggregate_run(run_id)


@app.get("/api/events")
def events(status: str | None = None, run_id: str | None = None, limit: int = Query(default=200, ge=1, le=500)) -> dict[str, object]:
    items = list_events(status=status, run_id=run_id, limit=limit)
    return {"items": items, "count": len(items)}


@app.get("/api/events/{event_id}")
def event_detail(event_id: str) -> dict[str, object]:
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    return event


@app.post("/api/events/merge")
def event_merge(payload: MergeRequest) -> dict[str, object]:
    try:
        return merge_events(payload.event_ids, payload.event_title, payload.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/events/{event_id}/split")
def event_split(event_id: str, payload: SplitRequest) -> dict[str, object]:
    try:
        return split_event(event_id, payload.source_ids, payload.new_title, payload.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/events/{event_id}/review")
def event_review(event_id: str, payload: EventReviewRequest) -> dict[str, object]:
    try:
        return review_event(event_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/codex/work-items")
def work_items(status: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> dict[str, object]:
    items = list_work_items(status, limit)
    return {"items": items, "count": len(items)}


@app.get("/api/codex/work-items/{work_item_id}")
def work_item_detail(work_item_id: str) -> dict[str, object]:
    item = get_work_item(work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="工作项不存在")
    return item


@app.post("/api/codex/work-items/{work_item_id}/claim")
def work_item_claim(work_item_id: str, payload: WorkItemActor) -> dict[str, object]:
    try:
        return claim_work_item(work_item_id, payload.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/codex/work-items/{work_item_id}/complete")
def work_item_complete(work_item_id: str, payload: WorkItemComplete) -> dict[str, object]:
    try:
        return complete_work_item(
            work_item_id,
            payload.actor_id,
            payload.model_dump(exclude={"actor_id"}, exclude_none=True),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/codex/work-items/{work_item_id}/fail")
def work_item_fail(work_item_id: str, payload: WorkItemFail) -> dict[str, object]:
    try:
        return fail_work_item(work_item_id, payload.actor_id, payload.error_message)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/drafts")
def drafts(
    status: str | None = None,
    purpose: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    items = list_drafts(status, purpose, limit)
    return {"items": items, "count": len(items)}


@app.get("/api/drafts/{task_draft_id}")
def draft_detail(task_draft_id: str) -> dict[str, object]:
    draft = get_draft(task_draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="作业草案不存在")
    return draft


@app.patch("/api/drafts/{task_draft_id}")
def draft_update(task_draft_id: str, payload: DraftUpdateRequest) -> dict[str, object]:
    try:
        changes = payload.model_dump(exclude={"actor_id"}, exclude_none=True)
        return update_draft(task_draft_id, changes, payload.actor_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/drafts/{task_draft_id}/review")
def draft_review(task_draft_id: str, payload: DraftReviewRequest) -> dict[str, object]:
    try:
        return review_draft(task_draft_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html")


for mount_path, directory in (
    ("/assets", "assets"),
    ("/js", "js"),
    ("/mock", "mock"),
    ("/config", "config"),
    ("/annotations", "annotations"),
    ("/docs", "docs"),
    ("/flowcharts", "flowcharts"),
):
    app.mount(mount_path, StaticFiles(directory=PROJECT_ROOT / directory, html=True), name=directory)
