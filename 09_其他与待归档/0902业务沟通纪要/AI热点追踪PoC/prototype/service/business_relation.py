"""进入业务工作台前的目标品牌关联检查；搜索词本身不作为关联证据。"""
from __future__ import annotations

import re
from typing import Any

from .config_loader import active_brands, load_configs


def assess_business_relation(item: dict[str, Any]) -> dict[str, Any]:
    policy = load_configs()["processing"]["business_relevance"]
    title = item.get("title") or ""
    snippet = item.get("snippet") or ""
    # 推荐区、版权和导航里的品牌名称不能证明当前文章的业务关联。
    for marker in policy.get("non_evidence_markers", []):
        snippet = re.split(marker, snippet, maxsplit=1)[0]
    text = f"{title}\n{snippet}"
    relations = []
    ambiguous = []
    for brand in active_brands():
        terms = [brand["canonical_name"], *brand.get("exact_aliases", [])]
        hit = next((term for term in terms if term and term in text), None)
        if not hit:
            for weak in brand.get("weak_aliases", []):
                if not weak or weak not in text:
                    continue
                # 弱别名与汽车语境必须出现在同一段，不能借用页面其他段落。
                paragraphs = [part for part in text.splitlines() if weak in part]
                if any(any(ctx in part for ctx in brand.get("weak_alias_context_terms", [])) for part in paragraphs):
                    hit = weak
                    break
                ambiguous.append(weak)
        if hit:
            position = text.index(hit)
            relations.append({
                "brand_id": brand["brand_id"], "brand_name": brand["canonical_name"],
                "relation_status": "direct_mention", "matched_term": hit,
                "evidence_excerpt": text[max(0, position - 70):position + len(hit) + 160],
                "reason": "标题或正文直接提及目标品牌；仅作为业务关联线索，行动价值仍需事件审核",
            })
    if relations:
        return {"eligible": True, "status": "direct_mention", "relations": relations,
                "reason": "当前内容直接涉及目标品牌", "rule_id": "BRG001"}
    if ambiguous:
        return {"eligible": False, "status": "pending_verification", "relations": [],
                "reason": f"品牌简称存在歧义（{'、'.join(sorted(set(ambiguous)))}），缺少同段汽车语境；需核验当前内容是否确实涉及目标品牌，不进入业务有效列表", "rule_id": "INV009"}
    return {"eligible": False, "status": "no_relation", "relations": [],
            "reason": "当前标题与正文没有目标品牌关联证据；仅属汽车行业、其他品牌动态或命中搜索词不足以证明东风业务相关性", "rule_id": "INV007"}


def event_has_business_evidence(event: dict[str, Any]) -> bool:
    """审批端复核真实来源，不能只信任可被修改的事件标签。"""
    return any(assess_business_relation(source)["eligible"]
               for source in event.get("sources", []) if source.get("source_status") == "valid")
