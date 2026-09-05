"""提取可追溯的发布时间，不将正文提到的事件日期当作发布日期。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")


def parse_date(value: str | None, reference: datetime) -> datetime | None:
    if not value:
        return None
    value = str(value).strip()
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.replace(tzinfo=TZ) if date.tzinfo is None else date.astimezone(TZ)
    except ValueError:
        pass
    match = re.fullmatch(r"(?:(20\d{2})[-/年])?\s*(\d{1,2})[-/月]\s*(\d{1,2})日?(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?", value)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            date = datetime(int(year or reference.year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0), tzinfo=TZ)
            if not year and date > reference + timedelta(days=1):
                date = date.replace(year=date.year - 1)
            return date
        except ValueError:
            return None
    match = re.fullmatch(r"(\d+)\s*(分钟|小时|天)前", value)
    if match:
        return reference - timedelta(seconds=int(match[1]) * {"分钟": 60, "小时": 3600, "天": 86400}[match[2]])
    return None


def resolve_publication_time(item: dict, reference: datetime | None = None) -> dict:
    reference = reference or datetime.now(TZ)
    provider_date = parse_date(item.get("publish_time"), reference)
    candidates = []
    # 只读取正文头部的元信息行；长段落中的“8月18日发生……”不作为发布日期。
    date_pattern = r"(?:(?:20\d{2})[-/年])?\s*\d{1,2}[-/月]\s*\d{1,2}日?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?"
    for line in (item.get("snippet") or "").splitlines()[:8]:
        line = line.strip()
        if len(line) > 100:
            break
        if not line:
            continue
        if re.search(r"发布(?:于|时间)?|来源[:：]|浏览|阅读|作者[:：]|发表于", line) or re.fullmatch(date_pattern, line):
            match = re.search(date_pattern, line)
            if match:
                date = parse_date(match[0].strip(), reference)
                if date:
                    candidates.append((date, line))
    # 页面头部的发布日期优先于搜索供应商字段；保留差异供复核。
    date, evidence = candidates[0] if candidates else (provider_date, str(item.get("publish_time") or ""))
    conflict = bool(candidates and provider_date and abs((date - provider_date).total_seconds()) > 86400)
    return {
        "published_at": date.isoformat(timespec="seconds") if date else None,
        "confidence": "medium" if candidates else "high" if date else "unknown",
        "basis": "正文头部发布时间" if candidates else "搜索供应商发布时间" if date else "未找到可核验的发布时间",
        "evidence": evidence,
        "provider_value": item.get("publish_time"),
        "conflict": conflict,
    }
