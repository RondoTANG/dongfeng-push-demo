from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any

from .database import add_audit, connection, fetch_all, fetch_one, json_text, new_id, now_iso
from .config_loader import active_brands
from .pipeline import _match_brands


HOTSPOT_MISSING = [
    "缺少平台原生播放、点赞、评论、转发等互动指标",
    "没有同一内容在1小时、3小时、24小时的连续快照",
    "无法稳定识别独立UGC作者及账号影响力",
    "公开搜索的社交平台覆盖范围与漏采情况不可审计",
]


RISK_KEYWORDS = {
    "sales_volume": ("销量", "交付量"),
    "price_or_discount": ("售价", "价格", "优惠"),
    "accident_or_safety": ("事故", "安全", "自燃"),
    "recall": ("召回",),
    "regulation": ("监管", "处罚"),
    "competitor_comparison": ("对比", "竞品"),
    "intelligent_driving_l3": ("L3", "智能驾驶", "智驾"),
    "negative_sentiment": ("亏损", "投诉", "争议", "负面"),
}


MODEL_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:M\d{3}|X\d{3}|L\d(?:Y|\+)?|梦想家\d+|eπ\d+)(?![A-Za-z0-9])", re.I)


def _normalized_key(title: str, date: str | None, brands: list[dict[str, Any]]) -> str:
    cleaned = re.sub(r"[\W_]+", "", title.lower())
    for token in ("最新", "消息", "正式", "企业新闻", "首页"):
        cleaned = cleaned.replace(token, "")
    brand_key = ",".join(sorted(item["brand_id"] for item in brands)) or "unresolved"
    date_key = (date or "unknown")[:10]
    return f"{brand_key}|{date_key}|{cleaned[:80]}"


def _list_page_candidates(source: dict[str, Any]) -> list[dict[str, str]]:
    title = source.get("title") or ""
    snippet = source.get("snippet") or ""
    if not any(marker in title for marker in ("企业新闻", "首页")):
        return []
    matches = list(re.finditer(r"(?m)^(20\d{2}-\d{2}-\d{2})\s*\n([^\n]{4,80})\n", snippet))
    candidates: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(snippet)
        candidates.append(
            {
                "event_date": match.group(1),
                "event_title": match.group(2).strip(),
                "content": snippet[match.end():end].strip(),
            }
        )
    return candidates


def _source_candidates(source: dict[str, Any]) -> list[dict[str, str]]:
    split = _list_page_candidates(source)
    if split:
        return split
    return [
        {
            "event_date": (source.get("published_at") or "")[:10],
            "event_title": source.get("title") or "未命名事件",
            "content": source.get("snippet") or "",
        }
    ]


def _risk_tags(text: str) -> list[str]:
    return [tag for tag, terms in RISK_KEYWORDS.items() if any(term in text for term in terms)]


def _official_domain_relations(source: dict[str, Any]) -> list[dict[str, Any]]:
    domain = (source.get("domain") or "").lower()
    relations: list[dict[str, Any]] = []
    for brand in active_brands():
        for official_domain in brand.get("official_domains", []):
            if domain == official_domain or domain.endswith(f".{official_domain}"):
                relations.append(
                    {
                        "brand_id": brand.get("brand_id"),
                        "brand_name": brand.get("canonical_name"),
                        "relation_status": "verified_relation",
                        "reason": "来源域名命中已配置的品牌官方域名",
                    }
                )
                break
    return relations


def _entity_resolution(text: str, source_id: str, official: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    names = sorted(set(match.group(0) for match in MODEL_PATTERN.finditer(text)))
    mentions: list[dict[str, Any]] = []
    uncertainties: list[dict[str, Any]] = []
    for name in names:
        if official:
            mentions.append({"entity_name": name, "entity_type": "model", "evidence_source_ids": [source_id]})
        else:
            uncertainties.append(
                {
                    "entity_name_raw": name,
                    "entity_type": "model",
                    "uncertainty_reason": "疑似车型名称，但当前只有公开搜索摘要且未维护全量车型主数据",
                    "proposed_relation": "随事件核验与品牌关系",
                    "evidence_source_ids": [source_id],
                }
            )
    return mentions, uncertainties


def aggregate_run(run_id: str) -> dict[str, int]:
    sources = fetch_all(
        "SELECT * FROM source_items WHERE run_id=? AND source_status='valid' ORDER BY published_at DESC",
        (run_id,),
    )
    created = 0
    linked = 0
    timestamp = now_iso()
    for source in sources:
        for candidate in _source_candidates(source):
            text = f"{candidate['event_title']}\n{candidate['content']}"
            brands = _match_brands(text)
            known_brand_ids = {item.get("brand_id") for item in brands}
            brands.extend(
                relation
                for relation in _official_domain_relations(source)
                if relation.get("brand_id") not in known_brand_ids
            )
            event_key = _normalized_key(candidate["event_title"], candidate["event_date"], brands)
            event_id = f"EVT-{hashlib.sha256(f'{run_id}|{event_key}'.encode()).hexdigest()[:14]}"
            official = source.get("source_platform") == "brand_official_website"
            mentions, uncertainties = _entity_resolution(text, source["source_id"], official)
            risks = _risk_tags(text)
            if risks or uncertainties or not brands:
                event_status = "manual_review"
            elif official:
                event_status = "brand_content_opportunity"
            else:
                event_status = "needs_evidence"
            brand_relations = brands or [
                {
                    "brand_id": None,
                    "brand_name": None,
                    "relation_status": "unresolved",
                    "reason": "当前证据未直接匹配9个已登记品牌，需完成品牌关联核验",
                }
            ]
            with connection() as db:
                existing = db.execute("SELECT event_id FROM events WHERE event_id=?", (event_id,)).fetchone()
                if not existing:
                    db.execute(
                        """
                        INSERT INTO events (
                            event_id, run_id, event_title, primary_entity_id_or_name,
                            event_action, event_date, source_count, independent_source_count,
                            source_platforms_json, brand_relations_json, entity_mentions_json,
                            entity_uncertainties_json, risk_tags_json, missing_evidence_json,
                            hotspot_judgement_available, hotspot_status,
                            hotspot_unavailable_reason_json, event_status, decision_reason,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?, 0, 'unknown', ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            run_id,
                            candidate["event_title"],
                            brands[0]["brand_name"] if brands else None,
                            candidate["event_title"],
                            candidate["event_date"] or None,
                            json_text([source.get("source_platform")]),
                            json_text(brand_relations),
                            json_text(mentions),
                            json_text(uncertainties),
                            json_text(risks),
                            json_text(HOTSPOT_MISSING),
                            json_text(HOTSPOT_MISSING),
                            event_status,
                            "公开搜索已形成事件线索；是否值得生成作业需运营结合证据审核。",
                            timestamp,
                            timestamp,
                        ),
                    )
                    db.execute(
                        """
                        INSERT INTO codex_work_items (
                            work_item_id, event_id, work_type, status, input_json, created_at
                        ) VALUES (?, ?, 'evidence_and_analysis', 'pending', ?, ?)
                        """,
                        (
                            new_id("WRK"),
                            event_id,
                            json_text(
                                {
                                    "event_title": candidate["event_title"],
                                    "event_date": candidate["event_date"],
                                    "brand_relations": brand_relations,
                                    "source_ids": [source["source_id"]],
                                    "required_output": [
                                        "summary",
                                        "decision_reason",
                                        "evidence",
                                        "risk_tags",
                                        "entity_mentions",
                                        "entity_uncertainties",
                                    ],
                                }
                            ),
                            timestamp,
                        ),
                    )
                    created += 1
                evidence_id = f"EVD-{hashlib.sha256(f'{event_id}|{source["source_id"]}'.encode()).hexdigest()[:14]}"
                db.execute(
                    """
                    INSERT OR IGNORE INTO event_evidence (
                        evidence_id, event_id, source_id, evidence_type, evidence_text,
                        evidence_url, provided_by, created_at
                    ) VALUES (?, ?, ?, 'source_excerpt', ?, ?, 'source_pipeline', ?)
                    """,
                    (
                        evidence_id,
                        event_id,
                        source["source_id"],
                        candidate["content"][:1200] or candidate["event_title"],
                        source.get("original_url"),
                        timestamp,
                    ),
                )
                if not _list_page_candidates(source):
                    db.execute("UPDATE source_items SET event_id=? WHERE source_id=?", (event_id, source["source_id"]))
                linked += 1
    add_audit(
        "aggregate",
        "collection_run",
        run_id,
        actor_type="system",
        actor_id="event-engine",
        after={"events_created": created, "evidence_links": linked},
    )
    return {"events_created": created, "evidence_links": linked}


def list_events(status: str | None = None, run_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if status:
        conditions.append("event_status=?")
        params.append(status)
    if run_id:
        conditions.append("run_id=?")
        params.append(run_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    return fetch_all(f"SELECT * FROM events {where} ORDER BY event_date DESC, created_at DESC LIMIT ?", tuple(params))


def get_event(event_id: str) -> dict[str, Any] | None:
    event = fetch_one("SELECT * FROM events WHERE event_id=?", (event_id,))
    if not event:
        return None
    event["evidence"] = fetch_all("SELECT * FROM event_evidence WHERE event_id=? ORDER BY created_at", (event_id,))
    event["sources"] = fetch_all(
        """
        SELECT DISTINCT s.* FROM source_items s
        JOIN event_evidence e ON e.source_id=s.source_id
        WHERE e.event_id=? ORDER BY s.published_at DESC
        """,
        (event_id,),
    )
    event["work_items"] = fetch_all("SELECT * FROM codex_work_items WHERE event_id=? ORDER BY created_at", (event_id,))
    event["reviews"] = fetch_all("SELECT * FROM candidate_reviews WHERE event_id=? ORDER BY reviewed_at DESC", (event_id,))
    return event


def merge_events(event_ids: list[str], event_title: str, actor_id: str) -> dict[str, Any]:
    if len(event_ids) < 2:
        raise ValueError("至少选择两个事件")
    target = get_event(event_ids[0])
    if not target:
        raise LookupError("目标事件不存在")
    with connection() as db:
        for source_event_id in event_ids[1:]:
            if not db.execute("SELECT 1 FROM events WHERE event_id=?", (source_event_id,)).fetchone():
                raise LookupError(f"事件不存在：{source_event_id}")
            db.execute("UPDATE event_evidence SET event_id=? WHERE event_id=?", (event_ids[0], source_event_id))
            db.execute("UPDATE source_items SET event_id=? WHERE event_id=?", (event_ids[0], source_event_id))
            db.execute("UPDATE codex_work_items SET status='cancelled' WHERE event_id=? AND status!='completed'", (source_event_id,))
            db.execute("DELETE FROM events WHERE event_id=?", (source_event_id,))
        source_count = db.execute("SELECT COUNT(DISTINCT source_id) FROM event_evidence WHERE event_id=?", (event_ids[0],)).fetchone()[0]
        db.execute(
            "UPDATE events SET event_title=?, source_count=?, independent_source_count=?, updated_at=? WHERE event_id=?",
            (event_title, source_count, source_count, now_iso(), event_ids[0]),
        )
    add_audit("merge", "event", event_ids[0], actor_type="operator", actor_id=actor_id, before={"event_ids": event_ids}, after={"event_title": event_title})
    return get_event(event_ids[0]) or {}


def split_event(event_id: str, source_ids: list[str], new_title: str, actor_id: str) -> dict[str, Any]:
    source_event = get_event(event_id)
    if not source_event:
        raise LookupError("事件不存在")
    available = {item.get("source_id") for item in source_event.get("sources", [])}
    if not source_ids or not set(source_ids).issubset(available):
        raise ValueError("拆分来源不属于当前事件")
    new_event_id = new_id("EVT")
    timestamp = now_iso()
    with connection() as db:
        db.execute(
            """
            INSERT INTO events (
                event_id, run_id, event_title, primary_entity_id_or_name, event_action,
                event_date, source_count, independent_source_count, source_platforms_json,
                brand_relations_json, entity_mentions_json, entity_uncertainties_json,
                risk_tags_json, missing_evidence_json, hotspot_judgement_available,
                hotspot_status, hotspot_unavailable_reason_json, event_status,
                decision_reason, created_at, updated_at
            ) SELECT ?, run_id, ?, primary_entity_id_or_name, ?, event_date, ?, ?,
                source_platforms_json, brand_relations_json, entity_mentions_json,
                entity_uncertainties_json, risk_tags_json, missing_evidence_json, 0,
                'unknown', hotspot_unavailable_reason_json, 'manual_review',
                '由运营从原事件人工拆分，需重新审核。', ?, ? FROM events WHERE event_id=?
            """,
            (new_event_id, new_title, new_title, len(source_ids), len(source_ids), timestamp, timestamp, event_id),
        )
        placeholders = ",".join("?" for _ in source_ids)
        db.execute(
            f"UPDATE event_evidence SET event_id=? WHERE event_id=? AND source_id IN ({placeholders})",
            (new_event_id, event_id, *source_ids),
        )
        db.execute(f"UPDATE source_items SET event_id=? WHERE source_id IN ({placeholders})", (new_event_id, *source_ids))
        db.execute(
            "INSERT INTO codex_work_items (work_item_id,event_id,work_type,status,input_json,created_at) VALUES (?,?,'evidence_and_analysis','pending',?,?)",
            (new_id("WRK"), new_event_id, json_text({"event_title": new_title, "source_ids": source_ids}), timestamp),
        )
    add_audit("split", "event", event_id, actor_type="operator", actor_id=actor_id, after={"new_event_id": new_event_id, "source_ids": source_ids})
    return get_event(new_event_id) or {}
