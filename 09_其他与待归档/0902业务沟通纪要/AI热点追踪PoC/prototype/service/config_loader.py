from __future__ import annotations

import hashlib
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .settings import HOTSPOT_RULE_PATH, SOURCE_CONFIG_DIR


CONFIG_FILES = {
    "brands": "品牌实体字典_v0.1.yaml",
    "sources": "来源平台字典_v0.1.yaml",
    "queries": "查询目录_v0.1.yaml",
    "processing": "清洗聚合与判定规则_v0.1.yaml",
    "drafts": "作业生成与分发规则_v0.1.yaml",
    "contract": "输出数据契约_v0.1.yaml",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"配置文件不是对象：{path.name}")
    return payload


@lru_cache(maxsize=1)
def load_configs() -> dict[str, dict[str, Any]]:
    result = {key: _load_yaml(SOURCE_CONFIG_DIR / filename) for key, filename in CONFIG_FILES.items()}
    result["hotspot"] = _load_yaml(HOTSPOT_RULE_PATH)
    return result


def reload_configs() -> dict[str, dict[str, Any]]:
    load_configs.cache_clear()
    return load_configs()


def config_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    paths = {key: SOURCE_CONFIG_DIR / filename for key, filename in CONFIG_FILES.items()}
    paths["hotspot"] = HOTSPOT_RULE_PATH
    for key, path in paths.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        version = str(_load_yaml(path).get("version", "unversioned"))
        versions[key] = f"{version}-{digest}"
    return versions


def query_catalog() -> list[dict[str, Any]]:
    query_config = load_configs()["queries"]
    catalog: list[dict[str, Any]] = []
    for group_name, key in (("brand", "brand_queries"), ("topic", "topic_queries")):
        for item in query_config.get(key, []):
            if item.get("enabled", True):
                catalog.append({**item, "query_group": group_name})
    return catalog


def active_brands() -> list[dict[str, Any]]:
    return [item for item in load_configs()["brands"].get("brands", []) if item.get("status") == "active"]


def domain_rules() -> list[dict[str, Any]]:
    rules = [item for item in load_configs()["sources"].get("domain_rules", []) if item.get("status") == "active"]
    return sorted(rules, key=lambda item: len(item.get("domain", "")), reverse=True)


CONFIG_NAMES = {
    "brands": "品牌与实体",
    "sources": "来源平台与站点",
    "queries": "基础查询目录",
    "processing": "清洗、聚合与判定",
    "drafts": "双路作业草案",
    "contract": "输出数据契约",
    "hotspot": "热点数据准入",
}


def _credential_configured() -> bool:
    if os.getenv("DOUBAO_SEARCH_API_KEY", "").strip():
        return True
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "guard-army-doubao-search", "-a", "api-key", "-w"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def business_config_summary() -> dict[str, Any]:
    configs = load_configs()
    versions = config_versions()
    brands = active_brands()
    brand_names = {item.get("brand_id"): item.get("canonical_name") for item in brands}
    queries = configs["queries"]
    source_config = configs["sources"]
    processing = configs["processing"]
    draft_config = configs["drafts"]
    hotspot = configs["hotspot"]

    meta = []
    for key, payload in configs.items():
        meta.append({
            "config_key": key,
            "display_name": CONFIG_NAMES[key],
            "version": versions[key],
            "updated_at": payload.get("updated_at"),
            "owner": payload.get("owner", "产品"),
            "reviewer": payload.get("reviewer", "运营／业务"),
        })

    query_items = []
    for group_key, group_name in (("brand_queries", "品牌查询"), ("topic_queries", "行业主题查询")):
        for item in queries.get(group_key, []):
            query_items.append({
                "query_id": item.get("query_id"),
                "group_name": group_name,
                "query": item.get("query"),
                "brand_name": brand_names.get(item.get("brand_id")),
                "enabled": item.get("enabled", True),
            })

    providers = []
    provider_names = {
        "doubao_global_search": "豆包全网搜索",
        "codex_web_search": "Codex 公开网页搜索",
        "existing_engagement_collector": "现有链接效果采集",
        "professional_sentiment_provider": "待选生产级舆情数据源",
    }
    for item in source_config.get("provider_registry", []):
        caps = item.get("data_capabilities", {})
        providers.append({
            "provider_id": item.get("provider_id"),
            "display_name": provider_names.get(item.get("provider_id"), item.get("provider_id")),
            "status": item.get("status"),
            "role": item.get("role"),
            "can_discover": bool(caps.get("content_discovery")),
            "has_native_metrics": caps.get("native_engagement_metrics"),
            "has_timeseries": caps.get("metric_timeseries"),
            "can_judge_hotspot": bool(caps.get("hotspot_judgement")),
        })

    platforms = [
        {
            "platform_id": item.get("platform_id"),
            "display_name": item.get("display_name"),
            "account_supported": item.get("account_fields_supported", False),
            "poc_coverage": item.get("poc_coverage"),
        }
        for item in source_config.get("platform_registry", [])
    ]
    domains = [
        {
            "domain": item.get("domain"),
            "site_name": item.get("source_site_name"),
            "platform": item.get("source_platform"),
            "related_brands": [brand_names.get(brand_id, brand_id) for brand_id in item.get("related_brand_ids", [])],
            "status": item.get("status"),
        }
        for item in source_config.get("domain_rules", [])
    ]

    stage = draft_config.get("stage_control", {})
    allowed_event_status = processing.get("task_generation", {}).get("allowed_event_status", [])
    current_statuses = ["draft_pending_review", "approved", "rejected"]
    return {
        "meta": meta,
        "summary": {
            "active_brand_count": len(brands),
            "brand_query_count": len(queries.get("brand_queries", [])),
            "topic_query_count": len(queries.get("topic_queries", [])),
            "provider_count": len(providers),
            "platform_count": len(platforms),
            "domain_rule_count": len(domains),
            "invalid_rule_count": len(processing.get("source_validation", {}).get("invalid_rules", [])),
            "credential_configured": _credential_configured(),
        },
        "stage": {
            "scope": "公开信息采集→事件研判→原创增长／源内容加热草案→分别审批",
            "manual_approval_required": stage.get("manual_approval_required", True),
            "auto_publish_enabled": False,
            "allowed_event_status": allowed_event_status,
            "draft_statuses": current_statuses,
            "deferred": ["正式下发", "任务执行", "结果回流与效果评估"],
        },
        "brands": {
            "items": brands,
            "rules": [
                "只有 active 品牌和别名参与确定性匹配",
                "新车型、人物、活动和机构在事件内动态识别，不要求先建完整主数据",
                "证据不足时记录不确定原因，与事件一起交给人工判断",
            ],
        },
        "queries": {
            "items": query_items,
            "execution": {
                "full_coverage_each_run": queries.get("execution", {}).get("full_coverage_each_run"),
                "lookback_hours": queries.get("execution", {}).get("lookback_hours"),
                "late_signal_hours": queries.get("execution", {}).get("late_signal_hours"),
                "provider_failure_policy": queries.get("execution", {}).get("provider_failure_policy"),
                "industry_brand_relation": "行业结果通过来源有效性检查后，对9个启用品牌全量验证，不轮换、不抽样",
            },
        },
        "sources": {"providers": providers, "platforms": platforms, "domains": domains},
        "processing": {
            "invalid_rules": processing.get("source_validation", {}).get("invalid_rules", []),
            "deduplication": processing.get("content_deduplication", {}).get("levels", []),
            "event_clustering": processing.get("event_clustering", {}),
            "event_decision": processing.get("event_decision", []),
            "risk_tags": processing.get("risk_gate", {}).get("risk_tags", []),
        },
        "hotspot": {
            "current_output": "公开搜索事件固定为‘热点不可判定’，并列出缺失原因",
            "required_capabilities": processing.get("hotspot_data_readiness", {}).get("required_capabilities", []),
            "prohibited_signals": processing.get("hotspot_data_readiness", {}).get("prohibited_heat_signals", []),
            "production_dependency": hotspot.get("capability_boundary", {}).get("production_dependency"),
            "bypass_allowed": False,
        },
        "drafts": {
            "target_platforms": draft_config.get("platform_recommendation", {}).get("supported_target_platforms", []),
            "member_label_source": draft_config.get("member_selection", {}).get("source"),
            "required_fields": draft_config.get("task_draft_templates", {}).get("shared_required_fields", []),
            "generation_rule": draft_config.get("task_draft_templates", {}).get("original_growth", {}).get("generation_rule"),
            "boost_generation_rule": draft_config.get("task_draft_templates", {}).get("source_content_boost", {}).get("generation_rule"),
            "boost_target_rule": draft_config.get("task_draft_templates", {}).get("source_content_boost", {}).get("target_rule"),
            "boost_actions": draft_config.get("task_draft_templates", {}).get("source_content_boost", {}).get("supported_actions", []),
            "hotspot_disclaimer_rule": draft_config.get("task_draft_templates", {}).get("hotspot_disclaimer_rule"),
        },
    }
