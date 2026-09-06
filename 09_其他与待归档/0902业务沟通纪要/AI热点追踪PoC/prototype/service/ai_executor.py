from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from .config_loader import active_brands, risk_rules
from .database import add_audit, connection, fetch_all, json_text, now_iso
from .events import get_event
from .settings import CODEX_AI_BATCH_SIZE, CODEX_AI_MODEL, CODEX_AI_TIMEOUT_SECONDS, CODEX_CLI_PATH
from .work_items import claim_work_item, complete_work_item, fail_work_item, list_work_items


ACTOR_ID = "codex-ai-runner"
PLATFORM_IDS = [
    "weibo", "douyin", "xiaohongshu", "toutiao", "wechat_official_account",
    "wechat_channels", "bilibili", "autohome", "dongchedi",
]
ENGAGEMENT_ACTIONS = ["like", "positive_comment", "repost", "favorite"]


def _schema() -> dict[str, Any]:
    text_or_null = {"type": ["string", "null"]}
    evidence = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "source_id": {"type": "string"}, "text": {"type": "string"},
            "url": text_or_null, "type": {"type": "string"},
        },
        "required": ["source_id", "text", "url", "type"],
    }
    entity = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "entity_name": {"type": "string"},
            "entity_type": {"type": "string", "enum": ["model", "person", "campaign", "organization"]},
            "evidence_source_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["entity_name", "entity_type", "evidence_source_ids"],
    }
    uncertainty = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "entity_name_raw": {"type": "string"},
            "entity_type": {"type": "string", "enum": ["model", "person", "campaign", "organization", "fact"]},
            "uncertainty_reason": {"type": "string"}, "proposed_relation": {"type": "string"},
            "evidence_source_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["entity_name_raw", "entity_type", "uncertainty_reason", "proposed_relation", "evidence_source_ids"],
    }
    platform = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "platform_id": {"type": "string", "enum": PLATFORM_IDS},
            "reason": {"type": "string"}, "content_form": {"type": "string"}, "guidance": {"type": "string"},
        },
        "required": ["platform_id", "reason", "content_form", "guidance"],
    }
    original = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "recommended": {"type": "boolean"}, "reason": {"type": "string"},
            "task_title": {"type": "string"}, "mandatory_topics": {"type": "array", "items": {"type": "string"}},
            "core_proposition": {"type": "string"}, "evidence_summary": {"type": "string"},
            "platforms": {"type": "array", "items": platform, "maxItems": 4},
            "creative_directions": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "prohibited_claims": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "risk_notes": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        },
        "required": ["recommended", "reason", "task_title", "mandatory_topics", "core_proposition", "evidence_summary", "platforms", "creative_directions", "prohibited_claims", "risk_notes"],
    }
    boost = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "source_id": {"type": "string"}, "recommended": {"type": "boolean"}, "reason": {"type": "string"},
            "engagement_actions": {"type": "array", "items": {"type": "string", "enum": ENGAGEMENT_ACTIONS}},
            "comment_direction": {"type": "string"},
        },
        "required": ["source_id", "recommended", "reason", "engagement_actions", "comment_direction"],
    }
    result = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "work_item_id": {"type": "string"}, "summary": {"type": "string"},
            "decision_reason": {"type": "string"},
            "content_tone": {"type": "string", "enum": ["positive", "neutral", "negative", "mixed", "unknown"]},
            "tone_reason": {"type": "string"},
            "evidence": {"type": "array", "items": evidence, "maxItems": 8},
            "risk_tags": {"type": "array", "items": {"type": "string"}},
            "entity_mentions": {"type": "array", "items": entity, "maxItems": 12},
            "entity_uncertainties": {"type": "array", "items": uncertainty, "maxItems": 12},
            "original_growth_blueprint": original,
            "source_content_boost_blueprints": {"type": "array", "items": boost, "maxItems": 5},
            "evidence_resolution": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "resolved_items": {"type": "array", "items": {"type": "string"}},
                    "unresolved_items": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["resolved_items", "unresolved_items"],
            },
        },
        "required": ["work_item_id", "summary", "decision_reason", "content_tone", "tone_reason", "evidence", "risk_tags", "entity_mentions", "entity_uncertainties", "original_growth_blueprint", "source_content_boost_blueprints", "evidence_resolution"],
    }
    return {
        "type": "object", "additionalProperties": False,
        "properties": {"results": {"type": "array", "items": result}},
        "required": ["results"],
    }


def _event_payload(work_item: dict[str, Any]) -> dict[str, Any]:
    event = get_event(work_item["event_id"])
    if not event:
        raise LookupError("关联事件不存在")
    sources = []
    for source in event.get("sources") or []:
        sources.append({
            "source_id": source["source_id"], "title": source.get("title"),
            "snippet": str(source.get("snippet") or "")[:3000],
            "published_at": source.get("published_at"), "source_platform": source.get("source_platform"),
            "source_site_name": source.get("source_site_name"),
            "url": source.get("canonical_url") or source.get("original_url"),
            "business_relation": source.get("business_relation"),
        })
    return {
        "work_item_id": work_item["work_item_id"], "work_type": work_item["work_type"],
        "event_id": event["event_id"], "event_title": event.get("event_title"),
        "event_date": event.get("event_date"), "rule_brand_relations": event.get("brand_relations") or [],
        "rule_risk_tags": event.get("risk_tags") or [], "existing_uncertainties": event.get("entity_uncertainties") or [],
        "hotspot_judgement_available": event.get("hotspot_judgement_available"),
        "hotspot_unavailable_reason": event.get("hotspot_unavailable_reason") or [],
        "request_context": work_item.get("input") or {}, "sources": sources,
    }


def _prompt(payloads: list[dict[str, Any]]) -> str:
    brand_scope = [{"brand_id": b.get("brand_id"), "name": b.get("canonical_name")} for b in active_brands()]
    risks = [{"tag": r.get("tag"), "display_name": r.get("display_name")} for r in risk_rules() if r.get("enabled", True)]
    return (
        "你是东风护卫军公开信息线索PoC的受控分析器。只分析输入JSON，不搜索互联网、不调用工具、不读取或修改文件。"
        "逐个work_item输出结构化研判和可供人工审核的作业草案蓝图。证据不足必须明确写入entity_uncertainties或evidence_resolution.unresolved_items。"
        "不得把搜索排名、搜索条数、媒体转载或主观感受写成真实热点；hotspot_judgement_available为false时只能写热点不可判定。"
        "品牌关系以rule_brand_relations为硬约束，不得新增品牌；风险标签只能使用允许标签。"
        "content_tone只是内容语气辅助标注，不生成舆情处置结论。"
        "原创蓝图必须结合事实写核心命题、创作方向与平台差异；话题标签只有在输入证据明确出现时才能填写，否则mandatory_topics为空。"
        "源内容加热只能绑定输入sources中的source_id；是否推荐只是AI建议，最终由运营审核。"
        "固定违规、申诉和权限规则由程序追加，不要自行发明。"
        f"允许品牌：{json.dumps(brand_scope, ensure_ascii=False)}。允许风险：{json.dumps(risks, ensure_ascii=False)}。"
        "待处理输入：" + json.dumps(payloads, ensure_ascii=False)
    )


def _run_codex(payloads: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    cli = Path(CODEX_CLI_PATH)
    if not cli.exists():
        raise RuntimeError(f"未找到Codex CLI：{CODEX_CLI_PATH}")
    started_at = now_iso()
    with tempfile.TemporaryDirectory(prefix="ai-hotspot-analysis-") as temp_dir:
        schema_path = Path(temp_dir) / "schema.json"
        output_path = Path(temp_dir) / "result.json"
        schema_path.write_text(json.dumps(_schema(), ensure_ascii=False), encoding="utf-8")
        command = [str(cli), "-a", "never", "-s", "read-only", "-C", temp_dir]
        if CODEX_AI_MODEL:
            command.extend(["-m", CODEX_AI_MODEL])
        command.extend(["exec", "--skip-git-repo-check", "--ephemeral", "--output-schema", str(schema_path), "--output-last-message", str(output_path), "-"])
        completed = subprocess.run(command, input=_prompt(payloads), capture_output=True, text=True, timeout=CODEX_AI_TIMEOUT_SECONDS, check=False)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Codex AI研判失败").strip()
            raise RuntimeError(detail[-1500:])
        if not output_path.exists():
            raise RuntimeError("Codex AI未生成结构化输出")
        result = json.loads(output_path.read_text(encoding="utf-8"))
    return result, {
        "executor": "codex_cli", "model": CODEX_AI_MODEL or "服务器Codex默认模型",
        "started_at": started_at, "completed_at": now_iso(), "prompt_contract_version": "event-analysis-v1",
    }


def generate_followup_boost_blueprint(publication: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    """为已发布原创的二次加热生成个性化要求；数值增量仍由程序计算。"""
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "task_title": {"type": "string"}, "recommendation_reason": {"type": "string"},
            "comment_direction": {"type": "string"},
            "engagement_actions": {"type": "array", "items": {"type": "string", "enum": ENGAGEMENT_ACTIONS}},
            "risk_notes": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "prohibited_claims": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        },
        "required": ["task_title", "recommendation_reason", "comment_direction", "engagement_actions", "risk_notes", "prohibited_claims"],
    }
    platform = publication.get("platform")
    allowed_actions = [item for item in ENGAGEMENT_ACTIONS if item in {
        "weibo": ["like", "positive_comment", "repost"], "douyin": ["like", "positive_comment"],
        "wechat_official_account": ["like", "positive_comment"], "wechat_channels": ["like", "positive_comment"],
        "toutiao": ["like", "positive_comment"], "xiaohongshu": ["like", "favorite", "positive_comment"],
        "bilibili": ["like", "positive_comment"], "autohome": ["like", "positive_comment"], "dongchedi": ["like", "positive_comment"],
    }.get(platform, [])]
    prompt = (
        "你是东风护卫军原创内容后效作业草拟助手。只分析输入JSON，不搜索、不调用工具、不修改文件。"
        "程序已计算同一原创内容的同口径指标增量，运营已决定生成二次加热草案。"
        "你只生成适合目标平台的任务标题、加热建议理由、正向评论方向、动作建议和风险边界；"
        "不得虚构正文内容、指标、热点等级、用户评价或统一复制话术。"
        f"只可使用这些互动动作：{json.dumps(allowed_actions, ensure_ascii=False)}。输入："
        + json.dumps({
            "publication_id": publication.get("publication_id"), "content_title": publication.get("content_title"),
            "content_url": publication.get("content_url"), "platform": platform,
            "original_task_title": (publication.get("original_draft") or {}).get("task_title"),
            "event_title": (publication.get("event") or {}).get("event_title"), "evaluation": evaluation,
        }, ensure_ascii=False)
    )
    cli = Path(CODEX_CLI_PATH)
    if not cli.exists():
        raise RuntimeError(f"未找到Codex CLI：{CODEX_CLI_PATH}")
    started_at = now_iso()
    with tempfile.TemporaryDirectory(prefix="ai-hotspot-followup-") as temp_dir:
        schema_path = Path(temp_dir) / "schema.json"
        output_path = Path(temp_dir) / "result.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
        command = [str(cli), "-a", "never", "-s", "read-only", "-C", temp_dir]
        if CODEX_AI_MODEL:
            command.extend(["-m", CODEX_AI_MODEL])
        command.extend(["exec", "--skip-git-repo-check", "--ephemeral", "--output-schema", str(schema_path), "--output-last-message", str(output_path), "-"])
        completed = subprocess.run(command, input=prompt, capture_output=True, text=True, timeout=CODEX_AI_TIMEOUT_SECONDS, check=False)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Codex AI二次加热草案生成失败").strip()
            raise RuntimeError(detail[-1500:])
        result = json.loads(output_path.read_text(encoding="utf-8"))
    result["engagement_actions"] = [item for item in result.get("engagement_actions", []) if item in allowed_actions]
    if not result["engagement_actions"]:
        result["engagement_actions"] = allowed_actions[:2]
    result["execution"] = {"executor": "codex_cli", "model": CODEX_AI_MODEL or "服务器Codex默认模型", "started_at": started_at, "completed_at": now_iso(), "prompt_contract_version": "followup-boost-v1"}
    return result


def _validated_output(raw: dict[str, Any], item: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    event = get_event(item["event_id"])
    if not event:
        raise LookupError("关联事件不存在")
    allowed_source_ids = {s["source_id"] for s in event.get("sources") or []}
    allowed_risks = {r.get("tag") for r in risk_rules() if r.get("enabled", True)}
    evidence_text = "\n".join(f"{s.get('title') or ''}\n{s.get('snippet') or ''}" for s in event.get("sources") or [])
    evidence = [e for e in raw.get("evidence", []) if e.get("source_id") in allowed_source_ids and str(e.get("text") or "").strip()]
    mentions = []
    for entity in raw.get("entity_mentions", []):
        refs = [ref for ref in entity.get("evidence_source_ids", []) if ref in allowed_source_ids]
        if refs:
            mentions.append({**entity, "evidence_source_ids": refs})
    uncertainties = []
    for entity in raw.get("entity_uncertainties", []):
        refs = [ref for ref in entity.get("evidence_source_ids", []) if ref in allowed_source_ids]
        uncertainties.append({**entity, "evidence_source_ids": refs})
    original = dict(raw.get("original_growth_blueprint") or {})
    original["mandatory_topics"] = [topic for topic in original.get("mandatory_topics", []) if topic and topic in evidence_text]
    original["platforms"] = [p for p in original.get("platforms", []) if p.get("platform_id") in PLATFORM_IDS]
    boosts = []
    for boost in raw.get("source_content_boost_blueprints", []):
        if boost.get("source_id") in allowed_source_ids:
            boosts.append({**boost, "engagement_actions": [a for a in boost.get("engagement_actions", []) if a in ENGAGEMENT_ACTIONS]})
    return {
        "summary": str(raw.get("summary") or "").strip(),
        "decision_reason": str(raw.get("decision_reason") or "").strip(),
        "content_tone": raw.get("content_tone", "unknown"), "tone_reason": str(raw.get("tone_reason") or "").strip(),
        "evidence": evidence, "risk_tags": sorted(set(event.get("risk_tags") or []) | (set(raw.get("risk_tags") or []) & allowed_risks)),
        "entity_mentions": mentions, "entity_uncertainties": uncertainties,
        "brand_relations": event.get("brand_relations") or [],
        "original_growth_blueprint": original, "source_content_boost_blueprints": boosts,
        "evidence_resolution": raw.get("evidence_resolution") or {"resolved_items": [], "unresolved_items": []},
        "execution": execution,
    }


def process_work_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {"requested": 0, "completed": 0, "failed": 0, "work_item_ids": []}
    claimed = []
    for item in items[:CODEX_AI_BATCH_SIZE]:
        claimed.append(claim_work_item(item["work_item_id"], ACTOR_ID))
    try:
        raw_payload, execution = _run_codex([_event_payload(item) for item in claimed])
        mapped = {str(r.get("work_item_id")): r for r in raw_payload.get("results", []) if isinstance(r, dict)}
        completed_ids = []
        failed_ids = []
        for item in claimed:
            raw = mapped.get(item["work_item_id"])
            if not raw:
                fail_work_item(item["work_item_id"], ACTOR_ID, "Codex AI输出缺少对应工作项")
                failed_ids.append(item["work_item_id"])
                continue
            output = _validated_output(raw, item, execution)
            if not output["summary"] or not output["decision_reason"]:
                fail_work_item(item["work_item_id"], ACTOR_ID, "Codex AI输出缺少摘要或判断依据")
                failed_ids.append(item["work_item_id"])
                continue
            complete_work_item(item["work_item_id"], ACTOR_ID, output)
            completed_ids.append(item["work_item_id"])
        return {"requested": len(claimed), "completed": len(completed_ids), "failed": len(failed_ids), "work_item_ids": completed_ids, "failed_work_item_ids": failed_ids, "execution": execution}
    except Exception as exc:
        for item in claimed:
            try:
                fail_work_item(item["work_item_id"], ACTOR_ID, str(exc))
            except Exception:
                pass
        raise


def process_run_work_items(run_id: str) -> dict[str, Any]:
    rows = fetch_all(
        "SELECT w.* FROM codex_work_items w JOIN events e ON e.event_id=w.event_id WHERE e.run_id=? AND w.status='pending' ORDER BY w.created_at",
        (run_id,),
    )
    totals = {"requested": 0, "completed": 0, "failed": 0, "work_item_ids": [], "failed_work_item_ids": []}
    for start in range(0, len(rows), CODEX_AI_BATCH_SIZE):
        batch = rows[start:start + CODEX_AI_BATCH_SIZE]
        try:
            result = process_work_items(batch)
        except Exception as exc:
            result = {
                "requested": len(batch), "completed": 0, "failed": len(batch),
                "work_item_ids": [], "failed_work_item_ids": [item["work_item_id"] for item in batch],
                "error": str(exc)[:1000],
            }
        totals["requested"] += result["requested"]
        totals["completed"] += result["completed"]
        totals["failed"] += result["failed"]
        totals["work_item_ids"].extend(result.get("work_item_ids", []))
        totals["failed_work_item_ids"].extend(result.get("failed_work_item_ids", []))
    with connection() as db:
        row = db.execute("SELECT step_summary_json FROM collection_runs WHERE run_id=?", (run_id,)).fetchone()
        summary = json.loads(row[0] or "{}") if row else {}
        summary["codex_ai_analysis"] = totals
        db.execute("UPDATE collection_runs SET step_summary_json=? WHERE run_id=?", (json_text(summary), run_id))
    add_audit("process_run", "codex_ai_analysis", run_id, actor_type="codex", actor_id=ACTOR_ID, after=totals)
    return totals


def process_pending_work_items(limit: int = CODEX_AI_BATCH_SIZE) -> dict[str, Any]:
    return process_work_items(list_work_items("pending", min(limit, CODEX_AI_BATCH_SIZE)))
