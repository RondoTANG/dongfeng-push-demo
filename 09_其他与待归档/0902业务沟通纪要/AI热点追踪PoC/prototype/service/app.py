from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import json

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .database import add_audit, init_database
from .config_loader import business_config_summary, query_catalog, reload_configs
from .config_admin import (
    delete_brand, delete_domain, delete_platform, delete_query,
    upsert_brand, upsert_domain, upsert_platform, upsert_query,
)
from .automation import automation_status_payload, scheduler_loop, update_automation_config
from .drafts import count_drafts, get_draft, list_drafts, review_draft, review_event, update_draft
from .evidence_requests import (
    confirm_evidence_request, create_evidence_plan, execute_evidence_request,
    get_evidence_request, list_evidence_requests,
)
from .effects import add_snapshot, count_publications, create_publication, evaluate_publication, get_publication, list_publications
from .events import aggregate_run, count_events, get_event, list_events, merge_events, split_event
from .pipeline import execute_collection, import_real_sample, reserve_collection_run, run_cooldown
from .repositories import (
    count_audit, count_invalid, count_runs, count_sources, get_run,
    list_audit, list_invalid, list_runs, list_sources,
)
from .settings import AUTH_COOKIE_SECURE, AUTH_SESSION_HOURS, DATABASE_PATH, PROJECT_ROOT
from .work_items import claim_work_item, complete_work_item, fail_work_item, get_work_item, list_work_items
from .access_control import (
    authenticate_key, create_session, create_viewer_key, delete_session, get_session,
    init_access_control, list_access_keys, reveal_viewer_key, revoke_access_key,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    init_access_control()
    stop_event = asyncio.Event()
    scheduler_task = asyncio.create_task(scheduler_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await scheduler_task


app = FastAPI(
    title="东风护卫军 AI 热点线索 PoC",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def access_control(request: Request, call_next):
    path = request.url.path
    public_api = {"/api/health", "/api/auth/login", "/api/auth/status"}
    protected_documents = path.startswith(("/docs/", "/flowcharts/"))
    if protected_documents and not get_session(request.cookies.get("ai_hotspot_session")):
        return RedirectResponse(url="/", status_code=303)
    if path.startswith("/api/") and path not in public_api:
        session = get_session(request.cookies.get("ai_hotspot_session"))
        if not session:
            return JSONResponse(status_code=401, content={"detail": "请先输入有效访问密钥"})
        request.state.identity = session
        if path.startswith("/api/access-keys") and session["role"] != "admin":
            return JSONResponse(status_code=403, content={"detail": "当前访问密钥无权管理其他密钥"})
        if request.method not in {"GET", "HEAD", "OPTIONS"} and session["role"] != "admin" and path != "/api/auth/logout":
            return JSONResponse(status_code=403, content={"detail": "当前为只读访问，不能执行采集、审核或修改操作"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class LoginRequest(BaseModel):
    access_key: str = Field(min_length=8, max_length=200)


class AccessKeyCreateRequest(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    expires_in_days: int | None = Field(default=30, ge=1, le=365)


class AccessKeyRevealRequest(BaseModel):
    admin_key: str = Field(min_length=8, max_length=200)


@app.get("/api/auth/status")
def auth_status(request: Request) -> dict[str, object]:
    session = get_session(request.cookies.get("ai_hotspot_session"))
    if not session:
        return {"authenticated": False, "auth_required": True}
    return {
        "authenticated": True,
        "role": session["role"],
        "display_name": session["display_name"],
        "permissions": {"can_write": session["role"] == "admin", "can_manage_keys": session["role"] == "admin"},
        "expires_at": session["expires_at"],
    }


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    identity = authenticate_key(payload.access_key)
    if not identity:
        raise HTTPException(status_code=401, detail="访问密钥无效、已停用或已过期")
    token, session = create_session(identity)
    response.set_cookie(
        "ai_hotspot_session", token, max_age=AUTH_SESSION_HOURS * 60 * 60, httponly=True,
        secure=AUTH_COOKIE_SECURE or request.url.scheme == "https", samesite="strict", path="/",
    )
    return {"authenticated": True, "role": session["role"], "display_name": session["display_name"],
            "permissions": {"can_write": session["role"] == "admin", "can_manage_keys": session["role"] == "admin"}}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, object]:
    delete_session(request.cookies.get("ai_hotspot_session"))
    response.delete_cookie("ai_hotspot_session", path="/")
    return {"logged_out": True}


@app.get("/api/access-keys")
def access_keys() -> dict[str, object]:
    return {"items": list_access_keys()}


@app.post("/api/access-keys", status_code=201)
def create_access_key(payload: AccessKeyCreateRequest, request: Request) -> dict[str, object]:
    identity = request.state.identity
    result = create_viewer_key(payload.label, payload.expires_in_days, identity["display_name"])
    add_audit("create_access_key", "access_key", result["access_key_id"], actor_type="admin", actor_id=identity["display_name"], after={"label": payload.label, "expires_at": result["expires_at"]})
    return result


@app.post("/api/access-keys/{access_key_id}/revoke")
def revoke_key(access_key_id: str, request: Request) -> dict[str, object]:
    if not revoke_access_key(access_key_id):
        raise HTTPException(status_code=404, detail="访问密钥不存在")
    identity = request.state.identity
    add_audit("revoke_access_key", "access_key", access_key_id, actor_type="admin", actor_id=identity["display_name"])
    return {"revoked": True, "access_key_id": access_key_id}


@app.post("/api/access-keys/{access_key_id}/reveal")
def reveal_access_key(access_key_id: str, payload: AccessKeyRevealRequest, request: Request) -> dict[str, object]:
    identity = request.state.identity
    try:
        result = reveal_viewer_key(access_key_id, payload.admin_key)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    add_audit(
        "reveal_access_key", "access_key", access_key_id,
        actor_type="admin", actor_id=identity["display_name"],
        after={"label": result["label"], "reason": "管理员二次验证后查看"},
    )
    return result


class RunRequest(BaseModel):
    mode: str = Field(default="quick", pattern="^(quick|full)$")
    trigger_type: str = Field(default="manual", pattern="^manual$")
    idempotency_key: str | None = Field(default=None, max_length=120)
    timeout: int = Field(default=30, ge=5, le=120)


class AutomationConfigRequest(BaseModel):
    enabled: bool
    interval_hours: int = Field(ge=1, le=168)


class BrandConfigRequest(BaseModel):
    brand_id: str = Field(min_length=2, max_length=80)
    canonical_name: str = Field(min_length=1, max_length=80)
    entity_type: str = Field(default="brand", max_length=40)
    status: str = Field(default="active", pattern="^(active|inactive)$")
    exact_aliases: list[str] = Field(default_factory=list, max_length=30)
    weak_aliases: list[str] = Field(default_factory=list, max_length=30)
    weak_alias_context_terms: list[str] = Field(default_factory=list, max_length=30)
    official_domains: list[str] = Field(default_factory=list, max_length=30)
    official_accounts: list[str] = Field(default_factory=list, max_length=50)


class QueryConfigRequest(BaseModel):
    query_id: str = Field(min_length=2, max_length=80)
    query_group: str = Field(pattern="^(brand|topic)$")
    query: str = Field(min_length=2, max_length=100)
    brand_id: str | None = Field(default=None, max_length=80)
    topic_id: str | None = Field(default=None, max_length=80)
    enabled: bool = True


class PlatformConfigRequest(BaseModel):
    platform_id: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=1, max_length=80)
    account_fields_supported: bool = False
    poc_coverage: str = Field(default="public_web", max_length=80)


class DomainConfigRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=200)
    source_platform: str = Field(min_length=2, max_length=80)
    source_site_name: str = Field(min_length=1, max_length=100)
    publisher_type: str = Field(default="media", max_length=80)
    related_brand_ids: list[str] = Field(default_factory=list, max_length=30)
    status: str = Field(default="active", pattern="^(active|inactive)$")


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
    review_result: str = Field(pattern="^(approved|rejected)$")
    event_status: str | None = None
    reviewer: str = Field(default="local-operator", min_length=2, max_length=80)
    review_note: str | None = Field(default=None, max_length=1000)
    evidence_summary: str = Field(min_length=5, max_length=3000)
    risk_summary: str = Field(default="未发现需要阻断草案生成的明确风险", max_length=2000)
    recommended_action: str = Field(default="由运营先判断是否形成原创增长草案；如事件存在可执行关联内容，可同时评估是否直接加热", max_length=1000)
    action_paths: list[str] = Field(default_factory=lambda: ["original_growth"], max_length=2)
    boost_source_ids: list[str] = Field(default_factory=list, max_length=3)


class EvidencePlanRequest(BaseModel):
    question: str | None = Field(default=None, max_length=500)
    unresolved_items: list[str] = Field(default_factory=list, max_length=8)
    search_queries: list[str] = Field(default_factory=list, max_length=3)
    lookback_hours: int = Field(default=72, ge=1, le=720)


class EvidenceConfirmRequest(BaseModel):
    methods: list[str] = Field(min_length=1, max_length=4)
    confirmed_by: str = Field(default="本地运营", min_length=2, max_length=80)


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


class PublicationCreateRequest(BaseModel):
    original_draft_id: str = Field(min_length=4, max_length=80)
    platform: str = Field(min_length=2, max_length=50)
    content_url: str = Field(min_length=10, max_length=2000)
    content_title: str | None = Field(default=None, max_length=300)
    platform_content_id: str | None = Field(default=None, max_length=200)
    published_at: str = Field(min_length=10, max_length=40)
    submitted_by: str = Field(default="local-operator", min_length=2, max_length=80)


class PublicationSnapshotRequest(BaseModel):
    captured_at: str = Field(min_length=10, max_length=40)
    data_source: str = Field(default="manual_evidence", min_length=2, max_length=50)
    metrics: dict[str, int] = Field(default_factory=dict)
    unavailable_reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1000)
    actor_id: str = Field(default="local-operator", min_length=2, max_length=80)


class PublicationEvaluationRequest(BaseModel):
    decision: str = Field(pattern="^(create_followup_boost|watch|no_boost|manual_review)$")
    decision_reason: str = Field(min_length=5, max_length=2000)
    evaluated_by: str = Field(default="local-operator", min_length=2, max_length=80)


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
        "scope": "collection-to-draft-approval-and-original-effect-loop",
    }


@app.get("/api/runs")
def runs(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    total = count_runs()
    return {"items": list_runs(page_size, (page - 1) * page_size), "page": page, "page_size": page_size, "total": total}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, object]:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行批次不存在")
    return run


@app.post("/api/runs", status_code=202)
def create_run(payload: RunRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
    cooldown = run_cooldown(payload.mode)
    if not cooldown["allowed"]:
        raise HTTPException(status_code=429, detail={"message": "运行仍在冷却期，请勿重复产生搜索调用", **cooldown})
    run_id = reserve_collection_run(
        mode=payload.mode,
        trigger_type=payload.trigger_type,
        idempotency_key=payload.idempotency_key,
    )
    background_tasks.add_task(
        execute_and_aggregate,
        run_id=run_id,
        mode=payload.mode,
        trigger_type=payload.trigger_type,
        idempotency_key=payload.idempotency_key,
        timeout=payload.timeout,
    )
    planned_query_count = len(query_catalog()) if payload.mode == "full" else 1
    return {
        "accepted": True,
        "run_id": run_id,
        "planned_query_count": planned_query_count,
        "planned_job_count": planned_query_count * 2,
        "providers": ["doubao_global_search", "codex_web_search"],
        "message": "双路运行已进入本地执行队列",
    }


@app.get("/api/runs/cooldown/{mode}")
def run_cooldown_status(mode: str) -> dict[str, object]:
    if mode not in {"quick", "full"}:
        raise HTTPException(status_code=400, detail="mode必须为quick或full")
    return run_cooldown(mode)


@app.post("/api/runs/import-real-sample")
def import_sample() -> dict[str, object]:
    raise HTTPException(status_code=410, detail="历史样本导入已停用，请使用完整搜索或快速验证获取当前数据")


@app.get("/api/sources")
def sources(
    run_id: str | None = None,
    status: str | None = "valid",
    platform: str | None = None,
    keyword: str | None = None,
    fetched_from: str | None = None,
    fetched_to: str | None = None,
    published_from: str | None = None,
    published_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    filters = dict(run_id=run_id, status=status, platform=platform, keyword=keyword, fetched_from=fetched_from, fetched_to=fetched_to, published_from=published_from, published_to=published_to)
    total = count_sources(**filters)
    items = list_sources(**filters, limit=page_size, offset=(page - 1) * page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@app.get("/api/invalid-records")
def invalid_records(
    run_id: str | None = None,
    rule_id: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    total = count_invalid(run_id, rule_id, keyword)
    items = list_invalid(run_id, rule_id, keyword, page_size, (page - 1) * page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@app.get("/api/audit")
def audit(
    object_type: str | None = None,
    action: str | None = None,
    actor_id: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    total = count_audit(object_type=object_type, action=action, actor_id=actor_id, keyword=keyword)
    items = list_audit(object_type=object_type, action=action, actor_id=actor_id, keyword=keyword, limit=page_size, offset=(page - 1) * page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


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
    runtime = automation_status_payload()
    config = runtime["config"]
    manual_runs = [item for item in list_runs(200) if item.get("trigger_type") == "manual"]
    pending = list_work_items("pending", 500)
    in_progress = list_work_items("in_progress", 500)
    return {
        "config": config,
        "last_manual_run": manual_runs[0] if manual_runs else None,
        "last_scheduled_run": runtime["last_scheduled_run"],
        "pending_work_item_count": len(pending),
        "in_progress_work_item_count": len(in_progress),
        "runner_command": "python3 scripts/run_collection.py --mode full --trigger-type manual",
        "trigger_policy": "admin_configurable_schedule",
        "work_item_command": "python3 scripts/process_codex_work_items.py --claim-next --actor-id codex-local-automation",
        "mcp_required": False,
        "enabled_query_count": len(query_catalog()),
    }


@app.patch("/api/automation/config")
def automation_config_update(payload: AutomationConfigRequest, request: Request) -> dict[str, object]:
    identity = request.state.identity
    config = update_automation_config(enabled=payload.enabled, interval_hours=payload.interval_hours, actor_id=identity["display_name"])
    return {"ok": True, "config": config, "message": "自动采集已开启" if config["enabled"] else "自动采集已停止"}


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


def _config_result(action: str, object_type: str, object_id: str, actor: str, result: object | None = None) -> dict[str, object]:
    add_audit(action, object_type, object_id, actor_type="admin", actor_id=actor, after=result)
    return {"ok": True, "item": result, "config": config_summary()}


@app.post("/api/config/brands")
def config_brand_create(payload: BrandConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_brand(payload.model_dump(), create_only=True)
        return _config_result("create", "brand_config", result["brand_id"], request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/config/brands/{brand_id}")
def config_brand_update(brand_id: str, payload: BrandConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_brand(payload.model_dump(), original_id=brand_id)
        return _config_result("update", "brand_config", brand_id, request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/config/brands/{brand_id}")
def config_brand_delete(brand_id: str, request: Request) -> dict[str, object]:
    try:
        delete_brand(brand_id)
        return _config_result("delete", "brand_config", brand_id, request.state.identity["display_name"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/config/queries")
def config_query_create(payload: QueryConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_query(payload.model_dump(), create_only=True)
        return _config_result("create", "query_config", result["query_id"], request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/config/queries/{query_id}")
def config_query_update(query_id: str, payload: QueryConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_query(payload.model_dump(), original_id=query_id)
        return _config_result("update", "query_config", query_id, request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/config/queries/{query_id}")
def config_query_delete(query_id: str, request: Request) -> dict[str, object]:
    try:
        delete_query(query_id)
        return _config_result("delete", "query_config", query_id, request.state.identity["display_name"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/config/platforms")
def config_platform_create(payload: PlatformConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_platform(payload.model_dump(), create_only=True)
        return _config_result("create", "platform_config", result["platform_id"], request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/config/platforms/{platform_id}")
def config_platform_update(platform_id: str, payload: PlatformConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_platform(payload.model_dump(), original_id=platform_id)
        return _config_result("update", "platform_config", platform_id, request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/config/platforms/{platform_id}")
def config_platform_delete(platform_id: str, request: Request) -> dict[str, object]:
    try:
        delete_platform(platform_id)
        return _config_result("delete", "platform_config", platform_id, request.state.identity["display_name"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/config/domains")
def config_domain_create(payload: DomainConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_domain(payload.model_dump(), create_only=True)
        return _config_result("create", "domain_config", result["domain"], request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/config/domains/{domain:path}")
def config_domain_update(domain: str, payload: DomainConfigRequest, request: Request) -> dict[str, object]:
    try:
        result = upsert_domain(payload.model_dump(), original_domain=domain)
        return _config_result("update", "domain_config", domain, request.state.identity["display_name"], result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/config/domains/{domain:path}")
def config_domain_delete(domain: str, request: Request) -> dict[str, object]:
    try:
        delete_domain(domain)
        return _config_result("delete", "domain_config", domain, request.state.identity["display_name"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/runs/{run_id}/aggregate")
def aggregate(run_id: str) -> dict[str, int]:
    if not get_run(run_id):
        raise HTTPException(status_code=404, detail="运行批次不存在")
    return aggregate_run(run_id)


@app.get("/api/events")
def events(status: str | None = None, run_id: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    total = count_events(status, run_id)
    items = list_events(status=status, run_id=run_id, limit=page_size, offset=(page - 1) * page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


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


@app.post("/api/events/{event_id}/evidence-plan")
def evidence_plan(event_id: str, payload: EvidencePlanRequest) -> dict[str, object]:
    try:
        return create_evidence_plan(
            event_id,
            question=payload.question,
            unresolved_items=payload.unresolved_items or None,
            search_queries=payload.search_queries or None,
            lookback_hours=payload.lookback_hours,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/evidence-requests")
def evidence_requests(event_id: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> dict[str, object]:
    items = list_evidence_requests(event_id, limit)
    return {"items": items, "count": len(items)}


@app.get("/api/evidence-requests/{request_id}")
def evidence_request_detail(request_id: str) -> dict[str, object]:
    item = get_evidence_request(request_id)
    if not item:
        raise HTTPException(status_code=404, detail="补证申请不存在")
    return item


@app.post("/api/evidence-requests/{request_id}/confirm", status_code=202)
def evidence_request_confirm(request_id: str, payload: EvidenceConfirmRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
    try:
        item = confirm_evidence_request(request_id, methods=payload.methods, confirmed_by=payload.confirmed_by)
        background_tasks.add_task(execute_evidence_request, request_id)
        return {"accepted": True, "evidence_request": item, "message": "补证已确认并进入执行队列"}
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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    total = count_drafts(status, purpose)
    items = list_drafts(status, purpose, page_size, (page - 1) * page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


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


@app.get("/api/publications")
def publications(status: str | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    total = count_publications(status)
    items = list_publications(status, page_size, (page - 1) * page_size)
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@app.get("/api/publications/{publication_id}")
def publication_detail(publication_id: str) -> dict[str, object]:
    publication = get_publication(publication_id)
    if not publication:
        raise HTTPException(status_code=404, detail="原创发布记录不存在")
    return publication


@app.post("/api/publications")
def publication_create(payload: PublicationCreateRequest) -> dict[str, object]:
    try:
        return create_publication(**payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/publications/{publication_id}/snapshots")
def publication_snapshot(publication_id: str, payload: PublicationSnapshotRequest) -> dict[str, object]:
    try:
        return add_snapshot(publication_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/publications/{publication_id}/evaluate")
def publication_evaluate(publication_id: str, payload: PublicationEvaluationRequest) -> dict[str, object]:
    try:
        return evaluate_publication(publication_id, **payload.model_dump())
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
