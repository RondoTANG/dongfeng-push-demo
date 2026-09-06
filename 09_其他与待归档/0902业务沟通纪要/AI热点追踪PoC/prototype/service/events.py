from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any

from .database import add_audit, connection, fetch_all, fetch_one, json_text, new_id, now_iso
from .config_loader import active_brands, risk_rules
from .pipeline import _match_brands
from .business_relation import assess_business_relation


HOTSPOT_MISSING = [
    "缺少平台原生播放、点赞、评论、转发等互动指标",
    "没有同一内容在1小时、3小时、24小时的连续快照",
    "无法稳定识别独立UGC作者及账号影响力",
    "公开搜索的社交平台覆盖范围与漏采情况不可审计",
]


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
    return [rule["tag"] for rule in risk_rules() if rule.get("enabled", True) and any(term.casefold() in text.casefold() for term in rule.get("keywords", []))]


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
        source_relation = assess_business_relation(source)
        if not source_relation["eligible"]:
            # 二次防护：历史数据或其他写入入口不得绕过业务关联检查。
            continue
        for candidate in _source_candidates(source):
            text = f"{candidate['event_title']}\n{candidate['content']}"
            brands = assess_business_relation({"title": candidate["event_title"], "snippet": candidate["content"]})["relations"]
            if not brands:
                continue
            event_key = _normalized_key(candidate["event_title"], candidate["event_date"], brands)
            event_id = f"EVT-{hashlib.sha256(f'{run_id}|{event_key}'.encode()).hexdigest()[:14]}"
            official = source.get("source_platform") == "brand_official_website"
            mentions, uncertainties = _entity_resolution(text, source["source_id"], official)
            risks = _risk_tags(text)
            event_status = "pending_review"
            suggested_conclusion = (
                "品牌内容机会" if official and not risks and not uncertainties and brands
                else "相关事件线索" if not risks and not uncertainties and brands
                else "存在风险、实体或品牌关系存疑"
            )
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
                            f"公开搜索已形成事件线索；系统建议按“{suggested_conclusion}”方向研判，最终是否通过及生成何种作业由运营审核。",
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


def list_events(status: str | None = None, run_id: str | None = None, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if status:
        conditions.append("event_status=?")
        params.append(status)
    if run_id:
        conditions.append("run_id=?")
        params.append(run_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])
    return fetch_all(f"SELECT * FROM events {where} ORDER BY event_date DESC, created_at DESC LIMIT ? OFFSET ?", tuple(params))


def count_events(status: str | None = None, run_id: str | None = None) -> int:
    conditions: list[str] = []; params: list[Any] = []
    if status: conditions.append("event_status=?"); params.append(status)
    if run_id: conditions.append("run_id=?"); params.append(run_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    row = fetch_one(f"SELECT COUNT(*) total FROM events {where}", tuple(params)) or {}
    return int(row.get("total") or 0)


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
    event["evidence_requests"] = fetch_all("SELECT * FROM evidence_requests WHERE event_id=? ORDER BY created_at DESC", (event_id,))
    event["split_unavailable_reason"] = _split_block_reason(event)
    if not event["split_unavailable_reason"] and fetch_one("SELECT task_draft_id FROM task_drafts WHERE event_id=? LIMIT 1", (event_id,)):
        event["split_unavailable_reason"] = "事件已有作业草案，不能直接拆分"
    event["can_split"] = not event["split_unavailable_reason"]
    return event


def _split_block_reason(event: dict[str, Any]) -> str | None:
    if len({s["source_id"] for s in event.get("sources", [])}) < 2:
        return "当前事件不足两条来源，不能按来源拆分"
    if event.get("event_status") != "pending_review" or event.get("reviews"):
        return "已有审核结论的事件不能直接拆分"
    if any(w.get("status") in ("running", "in_progress", "completed") for w in event.get("work_items", [])):
        return "事件已有执行中或已完成的补充分析，不能直接拆分"
    if any(r.get("status") in ("confirmed", "running", "completed") for r in event.get("evidence_requests", [])):
        return "事件已有确认执行或已完成的补证，不能直接拆分"
    return None


def _refresh_split_metadata(db, event_id: str, timestamp: str) -> None:
    """按拆分后的实际来源重算两边字段，禁止复制另一事件的风险和实体。"""
    rows = [dict(row) for row in db.execute(
        "SELECT DISTINCT s.* FROM source_items s JOIN event_evidence e ON e.source_id=s.source_id WHERE e.event_id=?",
        (event_id,),
    ).fetchall()]
    relations, mentions, uncertainties, risks = {}, [], [], set()
    for source in rows:
        for relation in assess_business_relation(source)["relations"]:
            relations[relation["brand_id"]] = relation
        text = f"{source.get('title') or ''}\n{source.get('snippet') or ''}"
        found, unsure = _entity_resolution(text, source["source_id"], source.get("source_platform") == "brand_official_website")
        mentions.extend(found); uncertainties.extend(unsure); risks.update(_risk_tags(text))
    brands = list(relations.values())
    # 独立来源延续聚合器的域名去重口径，不等同于自然讨论量。
    independent = {s.get("domain") or s.get("source_site_name") or s["source_id"] for s in rows}
    dates = sorted(s["published_at"] for s in rows if s.get("published_at"))
    db.execute(
        """UPDATE events SET source_count=?, independent_source_count=?, source_platforms_json=?,
        brand_relations_json=?, primary_entity_id_or_name=?, entity_mentions_json=?,
        entity_uncertainties_json=?, risk_tags_json=?, event_date=?, event_status='pending_review',
        decision_reason='来源已经人工拆分，需根据当前保留证据重新审核。', updated_at=? WHERE event_id=?""",
        (len(rows), len(independent), json_text(sorted({s.get("source_platform") or "unknown" for s in rows})),
         json_text(brands), brands[0]["brand_name"] if brands else None, json_text(mentions),
         json_text(uncertainties), json_text(sorted(risks)), dates[-1][:10] if dates else None, timestamp, event_id),
    )
    title = db.execute("SELECT event_title FROM events WHERE event_id=?", (event_id,)).fetchone()[0]
    db.execute(
        "UPDATE codex_work_items SET input_json=? WHERE event_id=? AND status='pending'",
        (json_text({"event_title": title, "brand_relations": brands, "source_ids": [s["source_id"] for s in rows],
                    "required_output": ["summary", "decision_reason", "evidence", "risk_tags", "entity_mentions", "entity_uncertainties"]}), event_id),
    )


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
    block_reason = _split_block_reason(source_event)
    if block_reason:
        raise ValueError(block_reason)
    source_ids = list(dict.fromkeys(source_ids))
    new_title = new_title.strip()
    if not 4 <= len(new_title) <= 160:
        raise ValueError("新事件标题须为4至160个字符")
    available = {item.get("source_id") for item in source_event.get("sources", [])}
    if not source_ids or not set(source_ids).issubset(available):
        raise ValueError("拆分来源不属于当前事件")
    if set(source_ids) == available:
        raise ValueError("原事件至少保留一条来源，不能移走全部来源")
    new_event_id = new_id("EVT")
    timestamp = now_iso()
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        # 在同一事务中再次检查，防止其他窗口已审核或移动来源。
        current = get_event(event_id)
        if not current:
            raise LookupError("事件不存在")
        if _split_block_reason(current):
            raise ValueError(_split_block_reason(current))
        current_ids = {s["source_id"] for s in current["sources"]}
        if current_ids != available:
            raise ValueError("来源已变化，请刷新事件后重试")
        if db.execute("SELECT 1 FROM task_drafts WHERE event_id=?", (event_id,)).fetchone():
            raise ValueError("事件已有作业草案，不能直接拆分")
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
                'unknown', hotspot_unavailable_reason_json, 'pending_review',
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
        # 未执行的补证方案引用旧证据集合，拆分后失效，保留记录但不可继续确认。
        db.execute("UPDATE evidence_requests SET status='cancelled' WHERE event_id=? AND status='pending_confirmation'", (event_id,))
        _refresh_split_metadata(db, event_id, timestamp)
        _refresh_split_metadata(db, new_event_id, timestamp)
    add_audit("split", "event", event_id, actor_type="operator", actor_id=actor_id, after={"new_event_id": new_event_id, "source_ids": source_ids})
    return get_event(new_event_id) or {}
