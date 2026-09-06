"""只读验证本地真实结果的关联证据、搜索追溯和队列分页布局。"""
import json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    data = json.load(urlopen("http://127.0.0.1:8765/api/sources?page_size=100"))
    assert data["items"], "需要真实采集结果，不用Mock替代"
    assert all(item["business_relation"]["eligible"] and item["discoveries"] for item in data["items"])
    published = [datetime.fromisoformat(item["published_at"]) for item in data["items"]]
    assert published == sorted(published, reverse=True), "接口未按发布时间降序"
    target = max(data["items"], key=lambda item: len(item["discoveries"]))
    folder = Path("tests/screenshots/relevance-20260906")
    folder.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8765/#page=clues", wait_until="networkidle")
        assert page.locator(".clue-window-notice").is_visible()
        assert "72 小时" in page.locator(".clue-window-notice").inner_text()
        assert page.locator(".clue-window-notice").evaluate("(el) => getComputedStyle(el).borderLeftWidth") == "4px"
        assert page.locator(".table-summary").inner_text().startswith("按发布时间从新到旧排序")
        page.screenshot(path=str(folder / "publication-sorting.png"))
        page.locator(f'[data-source-detail="{target["source_id"]}"]').click()
        page.wait_for_selector(".source-search-context")
        page.wait_for_function("getComputedStyle(document.querySelector('.drawer-mask')).opacity === '1'")
        records = page.locator(".search-query-record")
        assert records.count() == len(target["discoveries"])
        for query in target["discoveries"]:
            assert query["query_text"] in records.all_inner_texts()[target["discoveries"].index(query)]
        assert page.locator(".actual-search-query").all_text_contents() == [q["query_text"] for q in target["discoveries"]]
        assert all("配置编号：" in t and "不属于搜索词" in t for t in records.all_inner_texts())
        assert page.locator(".source-search-context").first.bounding_box()["y"] < 180
        page.screenshot(path=str(folder / "search-detail.png"))
        page.locator('[data-drawer-close]').first.click()
        page.wait_for_selector('.drawer', state='detached')
        sizes = []
        for width, height in [(1440, 800), (1120, 640), (960, 540)]:
            page.set_viewport_size({"width": width, "height": height})
            page.goto("http://127.0.0.1:8765/#page=event-detail", wait_until="networkidle")
            page.wait_for_selector(".event-queue>.table-pagination")
            pager = page.locator(".event-queue>.table-pagination").bounding_box()
            assert pager["y"] + pager["height"] <= height
            assert pager["y"] >= 0
            sizes.append({"viewport": [width, height], "pager": pager})
        page.screenshot(path=str(folder / "event-pagination.png"))
        for event_button in page.locator("[data-select-event]").all():
            event_button.click()
            page.wait_for_load_state("networkidle")
            text = page.locator(".event-detail-panel").inner_text()
            assert "direct_mention" not in text and "industry_media" not in text and "unknown" not in text
            assert page.locator("[data-split-event]").count() == 0, "真实单来源事件不应展示拆分"
        browser.close()
        assert not errors, errors
    print(json.dumps({"ok": True, "sources": data["total"], "query_records": len(target["discoveries"]), "sizes": sizes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
