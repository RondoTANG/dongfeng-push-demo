#!/usr/bin/env python3
"""校验AI热点追踪PoC配置之间的引用和覆盖关系。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"配置根节点必须是对象: {path}")
    return value


def ensure_unique(values: list[str], label: str, errors: list[str]) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        errors.append(f"{label}存在重复值: {duplicates}")


def main() -> int:
    master_path = BASE_DIR / "热点采集规则_v0.2.yaml"
    master = load_yaml(master_path)

    configs: dict[str, dict] = {}
    errors: list[str] = []
    for name, relative_path in master.get("config_refs", {}).items():
        path = BASE_DIR / relative_path
        if not path.exists():
            errors.append(f"缺少配置文件: {name} -> {relative_path}")
            continue
        configs[name] = load_yaml(path)

    required_configs = {
        "entity_registry",
        "source_registry",
        "query_catalog",
        "cleaning_and_decision",
        "output_contract",
        "task_generation_and_distribution",
    }
    missing_configs = required_configs - set(configs)
    if missing_configs:
        errors.append(f"总控缺少配置引用: {sorted(missing_configs)}")

    if errors:
        print(json.dumps({"success": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    entity = configs["entity_registry"]
    source = configs["source_registry"]
    query = configs["query_catalog"]
    decision = configs["cleaning_and_decision"]
    output = configs["output_contract"]
    task = configs["task_generation_and_distribution"]

    brands = entity.get("brands", [])
    active_brands = [item for item in brands if item.get("status") == "active"]
    active_brand_ids = {item.get("brand_id") for item in active_brands}
    brand_ids = [item.get("brand_id") for item in brands]
    ensure_unique(brand_ids, "brand_id", errors)
    ensure_unique([item.get("canonical_name") for item in brands], "品牌标准名", errors)
    if len(active_brands) != 9:
        errors.append(f"active品牌必须为9个，实际为{len(active_brands)}个")

    alias_owners: dict[str, set[str]] = {}
    for brand in active_brands:
        for alias in brand.get("exact_aliases", []):
            alias_owners.setdefault(alias, set()).add(brand["brand_id"])
    conflicts = {key: sorted(value) for key, value in alias_owners.items() if len(value) > 1}
    if conflicts:
        errors.append(f"active品牌exact_alias冲突: {conflicts}")

    brand_queries = [item for item in query.get("brand_queries", []) if item.get("enabled")]
    query_brand_ids = {item.get("brand_id") for item in brand_queries}
    if query_brand_ids != active_brand_ids:
        errors.append(
            "品牌查询未完整覆盖active品牌: "
            f"缺失={sorted(active_brand_ids - query_brand_ids)}, "
            f"多余={sorted(query_brand_ids - active_brand_ids)}"
        )
    if len(brand_queries) != 9:
        errors.append(f"启用品牌查询必须为9条，实际为{len(brand_queries)}条")

    topic_queries = [item for item in query.get("topic_queries", []) if item.get("enabled")]
    if len(topic_queries) != 8:
        errors.append(f"启用行业主题查询必须为8条，实际为{len(topic_queries)}条")

    all_query_ids = [item.get("query_id") for item in brand_queries + topic_queries]
    ensure_unique(all_query_ids, "query_id", errors)

    providers = {item.get("provider_id") for item in source.get("provider_registry", [])}
    provider_items = {
        item.get("provider_id"): item for item in source.get("provider_registry", [])
    }
    referenced_providers = set(query.get("execution", {}).get("base_providers", []))
    referenced_providers.update(query.get("execution", {}).get("relation_providers", []))
    referenced_providers.update(query.get("industry_brand_relation", {}).get("providers", []))
    referenced_providers.update(query.get("evidence_expansion", {}).get("providers", []))
    unknown_providers = referenced_providers - providers
    if unknown_providers:
        errors.append(f"查询配置引用未登记采集器: {sorted(unknown_providers)}")

    for provider_id in ("doubao_global_search", "codex_web_search"):
        item = provider_items.get(provider_id)
        if item is None:
            errors.append(f"缺少PoC搜索采集器: {provider_id}")
            continue
        capabilities = item.get("data_capabilities", {})
        if capabilities.get("hotspot_judgement") is not False:
            errors.append(f"{provider_id}不得配置为可判定真实热点")
        if capabilities.get("native_engagement_metrics") is not False:
            errors.append(f"{provider_id}不得声明具备平台原生互动指标")
        if capabilities.get("metric_timeseries") is not False:
            errors.append(f"{provider_id}不得声明具备连续指标快照")

    domain_rules = source.get("domain_rules", [])
    domains = [item.get("domain") for item in domain_rules]
    ensure_unique(domains, "来源域名", errors)
    platform_ids = {item.get("platform_id") for item in source.get("platform_registry", [])}
    invalid_platforms = sorted(
        {
            item.get("source_platform")
            for item in domain_rules
            if item.get("source_platform") not in platform_ids
        }
    )
    if invalid_platforms:
        errors.append(f"域名规则引用未登记平台: {invalid_platforms}")

    collector = provider_items.get("existing_engagement_collector")
    if collector is None:
        errors.append("缺少已知链接效果采集器existing_engagement_collector")
    else:
        collector_source_ref = collector.get("source_ref")
        if not collector_source_ref or not (CONFIG_DIR / collector_source_ref).resolve().exists():
            errors.append(
                f"效果采集器来源文件不存在: {collector_source_ref}"
            )
        metric_platforms = set(
            collector.get("platform_metric_availability", {}).keys()
        )
        unknown_metric_platforms = metric_platforms - platform_ids
        if unknown_metric_platforms:
            errors.append(
                f"效果采集器引用未登记平台: {sorted(unknown_metric_platforms)}"
            )
        for wechat_platform in (
            "wechat_official_account",
            "wechat_channels",
        ):
            availability = collector.get("platform_metric_availability", {}).get(
                wechat_platform, {}
            )
            if availability.get("available") is not False:
                errors.append(f"{wechat_platform}必须明确为不可自动采集")

    boost = task.get("boost_followup", {})
    if boost.get("trigger_metric_source") != "existing_engagement_collector":
        errors.append("加热规则必须引用existing_engagement_collector")
    if boost.get("auto_publish_enabled") is not False:
        errors.append("PoC加热作业不得自动发布")

    event_enums = set(output.get("enums", {}).get("event_status", []))
    decision_statuses = {item.get("status") for item in decision.get("event_decision", [])}
    if event_enums != decision_statuses:
        errors.append(
            "事件状态与输出契约不一致: "
            f"契约独有={sorted(event_enums - decision_statuses)}, "
            f"规则独有={sorted(decision_statuses - event_enums)}"
        )
    if "external_hotspot" in event_enums:
        errors.append("搜索线索PoC事件枚举不得包含external_hotspot")
    if "relevant_event_clue" not in event_enums:
        errors.append("事件枚举缺少relevant_event_clue")

    hotspot_data_readiness = decision.get("hotspot_data_readiness", {})
    required_readiness_capabilities = {
        "platform_content_id",
        "native_engagement_metrics",
        "metric_timeseries",
        "author_or_unique_ugc_identity",
        "platform_coverage_and_collected_at",
    }
    configured_readiness_capabilities = set(
        hotspot_data_readiness.get("required_capabilities", [])
    )
    missing_readiness_capabilities = (
        required_readiness_capabilities - configured_readiness_capabilities
    )
    if missing_readiness_capabilities:
        errors.append(
            "热点判定数据准入条件缺失: "
            f"{sorted(missing_readiness_capabilities)}"
        )
    search_default = hotspot_data_readiness.get("search_provider_default", {})
    if search_default.get("hotspot_judgement_available") is not False:
        errors.append("公开搜索默认不得通过热点判定数据准入")
    if search_default.get("hotspot_status") != "unknown":
        errors.append("公开搜索默认热点状态必须为unknown")

    hotspot_enums = set(output.get("enums", {}).get("hotspot_status", []))
    if "unknown" not in hotspot_enums:
        errors.append("热点状态枚举必须包含unknown")

    event_contract = output.get("datasets", {}).get("event", {})
    event_required = set(event_contract.get("required_fields", []))
    hotspot_required_fields = {
        "hotspot_judgement_available",
        "hotspot_status",
        "hotspot_unavailable_reason",
    }
    missing_hotspot_fields = hotspot_required_fields - event_required
    if missing_hotspot_fields:
        errors.append(f"事件契约缺少热点能力字段: {sorted(missing_hotspot_fields)}")

    event_entity_fields = {"entity_mentions", "entity_uncertainties"}
    missing_event_entity_fields = event_entity_fields - event_required
    if missing_event_entity_fields:
        errors.append(
            f"事件契约缺少事件级实体判断字段: {sorted(missing_event_entity_fields)}"
        )
    if "entity_confirmation_queue" in output.get("datasets", {}):
        errors.append("不得设置独立实体待确认队列；不确定项必须随事件进入人工审核")

    granular_master_groups = {
        group: entity.get(group, []) for group in ("models", "people", "campaigns")
    }
    non_empty_granular_groups = sorted(
        group for group, items in granular_master_groups.items() if items
    )
    if non_empty_granular_groups:
        errors.append(
            "车型、人物和活动不得作为必须维护的全局主数据: "
            f"{non_empty_granular_groups}"
        )
    dynamic_entity_types = set(
        entity.get("event_entity_resolution", {}).get("entity_types", [])
    )
    required_dynamic_entity_types = {"model", "person", "campaign"}
    missing_dynamic_types = required_dynamic_entity_types - dynamic_entity_types
    if missing_dynamic_types:
        errors.append(
            f"事件级实体判断缺少类型: {sorted(missing_dynamic_types)}"
        )

    required_post_publish_datasets = {
        "task_submission",
        "platform_metric_snapshot",
        "submission_metric_delta",
    }
    missing_post_publish_datasets = required_post_publish_datasets - set(
        output.get("datasets", {})
    )
    if missing_post_publish_datasets:
        errors.append(
            f"缺少回填链接效果数据集: {sorted(missing_post_publish_datasets)}"
        )

    master_boundary = master.get("capability_boundary", {})
    if master_boundary.get("search_is_hotspot_source") is not False:
        errors.append("总控必须明确search_is_hotspot_source=false")
    if master_boundary.get("hotspot_status") != "unknown":
        errors.append("总控搜索来源热点状态必须为unknown")

    result = {
        "success": not errors,
        "summary": {
            "active_brand_count": len(active_brands),
            "brand_query_count": len(brand_queries),
            "topic_query_count": len(topic_queries),
            "base_query_count": len(brand_queries) + len(topic_queries),
            "provider_count": len(providers),
            "domain_rule_count": len(domain_rules),
            "granular_master_entity_count": sum(
                len(items) for items in granular_master_groups.values()
            ),
            "event_dynamic_entity_type_count": len(dynamic_entity_types),
            "event_status_count": len(event_enums),
        },
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
