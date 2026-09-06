from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

import yaml

from .config_loader import CONFIG_FILES, reload_configs
from .settings import SOURCE_CONFIG_DIR


_LOCK = RLock()


def _path(config_key: str) -> Path:
    if config_key not in CONFIG_FILES:
        raise KeyError(config_key)
    return SOURCE_CONFIG_DIR / CONFIG_FILES[config_key]


def _read(config_key: str) -> dict[str, Any]:
    payload = yaml.safe_load(_path(config_key).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("配置文件格式错误")
    return payload


def _write(config_key: str, payload: dict[str, Any]) -> None:
    path = _path(config_key)
    payload["updated_at"] = datetime.now().astimezone().date().isoformat()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    temporary.replace(path)
    reload_configs()


def _require_identifier(value: str, label: str) -> str:
    value = value.strip()
    if not value or len(value) > 80 or not all(char.isalnum() or char in "_-" for char in value):
        raise ValueError(f"{label}仅支持字母、数字、下划线和短横线")
    return value


def upsert_brand(payload: dict[str, Any], *, original_id: str | None = None, create_only: bool = False) -> dict[str, Any]:
    with _LOCK:
        config = _read("brands")
        items = config.setdefault("brands", [])
        brand_id = _require_identifier(str(payload.get("brand_id") or original_id or ""), "品牌编号")
        if original_id and original_id != brand_id:
            raise ValueError("品牌编号创建后不可修改")
        canonical_name = str(payload.get("canonical_name") or "").strip()
        if not canonical_name:
            raise ValueError("品牌名称不能为空")
        duplicate = next((item for item in items if item.get("canonical_name") == canonical_name and item.get("brand_id") != brand_id), None)
        if duplicate:
            raise ValueError("品牌名称已存在")
        entry = {
            "brand_id": brand_id,
            "canonical_name": canonical_name,
            "entity_type": payload.get("entity_type") or "brand",
            "status": payload.get("status") if payload.get("status") in {"active", "inactive"} else "active",
            "exact_aliases": list(dict.fromkeys(payload.get("exact_aliases") or [])),
            "weak_aliases": list(dict.fromkeys(payload.get("weak_aliases") or [])),
            "weak_alias_context_terms": list(dict.fromkeys(payload.get("weak_alias_context_terms") or [])),
            "official_domains": list(dict.fromkeys(payload.get("official_domains") or [])),
            "official_accounts": list(dict.fromkeys(payload.get("official_accounts") or [])),
        }
        index = next((i for i, item in enumerate(items) if item.get("brand_id") == brand_id), None)
        if create_only and index is not None:
            raise ValueError("品牌编号已存在")
        if index is None:
            items.append(entry)
        else:
            items[index] = entry
        _write("brands", config)
        return entry


def delete_brand(brand_id: str) -> None:
    with _LOCK:
        query_config = _read("queries")
        if any(item.get("brand_id") == brand_id for item in query_config.get("brand_queries", [])):
            raise ValueError("该品牌仍被品牌查询引用，请先删除或调整关联查询")
        source_config = _read("sources")
        if any(brand_id in item.get("related_brand_ids", []) for item in source_config.get("domain_rules", [])):
            raise ValueError("该品牌仍被来源域名规则引用，请先解除关联")
        config = _read("brands")
        before = len(config.get("brands", []))
        config["brands"] = [item for item in config.get("brands", []) if item.get("brand_id") != brand_id]
        if len(config["brands"]) == before:
            raise LookupError("品牌不存在")
        _write("brands", config)


def upsert_query(payload: dict[str, Any], *, original_id: str | None = None, create_only: bool = False) -> dict[str, Any]:
    with _LOCK:
        config = _read("queries")
        query_id = _require_identifier(str(payload.get("query_id") or original_id or ""), "查询编号")
        if original_id and original_id != query_id:
            raise ValueError("查询编号创建后不可修改")
        group = payload.get("query_group")
        if group not in {"brand", "topic"}:
            raise ValueError("查询类型必须为品牌或行业主题")
        query_text = str(payload.get("query") or "").strip()
        if not query_text:
            raise ValueError("实际查询词不能为空")
        brands = {item.get("brand_id"): item.get("status") for item in _read("brands").get("brands", [])}
        if group == "brand" and payload.get("brand_id") not in brands:
            raise ValueError("品牌查询必须选择已登记品牌")
        if group == "brand" and payload.get("enabled", True) and brands.get(payload.get("brand_id")) != "active":
            raise ValueError("启用的品牌查询只能引用启用品牌")
        exists = any(
            item.get("query_id") == query_id
            for key in ("brand_queries", "topic_queries")
            for item in config.get(key, [])
        )
        if create_only and exists:
            raise ValueError("查询编号已存在")
        entry = {"query_id": query_id}
        if group == "brand":
            entry["brand_id"] = payload.get("brand_id")
        else:
            entry["topic_id"] = _require_identifier(str(payload.get("topic_id") or query_id.lower()), "主题编号")
        entry.update({"query": query_text, "enabled": bool(payload.get("enabled", True))})
        for key in ("brand_queries", "topic_queries"):
            config[key] = [item for item in config.get(key, []) if item.get("query_id") != query_id]
        config["brand_queries" if group == "brand" else "topic_queries"].append(entry)
        _write("queries", config)
        return {**entry, "query_group": group}


def delete_query(query_id: str) -> None:
    with _LOCK:
        config = _read("queries")
        before = sum(len(config.get(key, [])) for key in ("brand_queries", "topic_queries"))
        for key in ("brand_queries", "topic_queries"):
            config[key] = [item for item in config.get(key, []) if item.get("query_id") != query_id]
        after = sum(len(config.get(key, [])) for key in ("brand_queries", "topic_queries"))
        if before == after:
            raise LookupError("查询不存在")
        _write("queries", config)


def upsert_platform(payload: dict[str, Any], *, original_id: str | None = None, create_only: bool = False) -> dict[str, Any]:
    with _LOCK:
        config = _read("sources")
        platform_id = _require_identifier(str(payload.get("platform_id") or original_id or ""), "平台编号")
        if original_id and original_id != platform_id:
            raise ValueError("平台编号创建后不可修改")
        display_name = str(payload.get("display_name") or "").strip()
        if not display_name:
            raise ValueError("平台名称不能为空")
        entry = {
            "platform_id": platform_id,
            "display_name": display_name,
            "account_fields_supported": bool(payload.get("account_fields_supported")),
            "poc_coverage": payload.get("poc_coverage") or "public_web",
        }
        items = config.setdefault("platform_registry", [])
        index = next((i for i, item in enumerate(items) if item.get("platform_id") == platform_id), None)
        if create_only and index is not None:
            raise ValueError("平台编号已存在")
        if index is None:
            items.append(entry)
        else:
            items[index] = entry
        _write("sources", config)
        return entry


def delete_platform(platform_id: str) -> None:
    if platform_id in {"unknown", "other_website"}:
        raise ValueError("系统兜底平台不可删除")
    with _LOCK:
        config = _read("sources")
        if any(item.get("source_platform") == platform_id for item in config.get("domain_rules", [])):
            raise ValueError("该平台仍被域名规则引用，请先调整域名规则")
        for provider in config.get("provider_registry", []):
            if platform_id in provider.get("platform_metric_availability", {}):
                raise ValueError("该平台仍被效果采集能力引用，不能直接删除")
        before = len(config.get("platform_registry", []))
        config["platform_registry"] = [item for item in config.get("platform_registry", []) if item.get("platform_id") != platform_id]
        if len(config["platform_registry"]) == before:
            raise LookupError("平台不存在")
        _write("sources", config)


def upsert_domain(payload: dict[str, Any], *, original_domain: str | None = None, create_only: bool = False) -> dict[str, Any]:
    with _LOCK:
        config = _read("sources")
        domain = str(payload.get("domain") or original_domain or "").strip().lower()
        if not domain or "/" in domain or " " in domain:
            raise ValueError("请输入不含协议和路径的有效域名")
        if original_domain and original_domain != domain:
            raise ValueError("域名创建后不可修改")
        platforms = {item.get("platform_id") for item in config.get("platform_registry", [])}
        if payload.get("source_platform") not in platforms:
            raise ValueError("请选择已登记来源平台")
        known_brands = {item.get("brand_id") for item in _read("brands").get("brands", [])}
        related = list(dict.fromkeys(payload.get("related_brand_ids") or []))
        if set(related) - known_brands:
            raise ValueError("域名规则引用了不存在的品牌")
        entry = {
            "domain": domain,
            "source_platform": payload.get("source_platform"),
            "source_site_name": str(payload.get("source_site_name") or domain).strip(),
            "publisher_type": payload.get("publisher_type") or "media",
            "related_brand_ids": related,
            "status": payload.get("status") if payload.get("status") in {"active", "inactive"} else "active",
        }
        items = config.setdefault("domain_rules", [])
        index = next((i for i, item in enumerate(items) if item.get("domain") == domain), None)
        if create_only and index is not None:
            raise ValueError("域名规则已存在")
        if index is None:
            items.append(entry)
        else:
            items[index] = entry
        _write("sources", config)
        return entry


def delete_domain(domain: str) -> None:
    with _LOCK:
        config = _read("sources")
        before = len(config.get("domain_rules", []))
        config["domain_rules"] = [item for item in config.get("domain_rules", []) if item.get("domain") != domain]
        if len(config["domain_rules"]) == before:
            raise LookupError("域名规则不存在")
        _write("sources", config)
