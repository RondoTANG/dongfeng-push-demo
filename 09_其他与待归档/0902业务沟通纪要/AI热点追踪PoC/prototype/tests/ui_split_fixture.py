"""隔离浏览器响应验证多来源拆分交互；所有拆分POST均拦截，不写真实数据库。"""
import copy
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    base = "http://127.0.0.1:8765"
    event_id = json.load(urlopen(base + "/api/events?page_size=1"))["items"][0]["event_id"]
    fixture = json.load(urlopen(base + "/api/events/" + event_id))
    second = copy.deepcopy(fixture["sources"][0])
    second.update(source_id="SRC-UI-FIXTURE", title="仅用于测试的第二个独立事实")
    fixture["sources"].append(second)
    fixture["can_split"] = True
    fixture["source_count"] = 2
    received = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.route("**/api/events/" + event_id, lambda route: route.fulfill(json=fixture))

        def split(route):
            received.append(route.request.post_data_json)
            route.fulfill(json={"event_id": event_id})

        page.route("**/api/events/*/split", split)
        page.goto(base + "/#page=event-detail", wait_until="networkidle")
        page.locator("[data-split-event]").click()
        page.wait_for_selector("[data-confirm-split]")
        assert page.locator("[data-confirm-split]").is_disabled()
        page.locator('[name="split_title"]').fill("测试拆分后的独立事件")
        checks = page.locator('[name="split_source"]')
        checks.nth(1).check()
        assert page.locator("[data-confirm-split]").is_enabled()
        checks.nth(0).check()
        assert page.locator("[data-confirm-split]").is_disabled()
        assert "不能移走全部来源" in page.locator("[data-split-feedback]").inner_text()
        checks.nth(0).uncheck()
        folder = Path("tests/screenshots/relevance-20260906")
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / "split-fixture.png"))
        page.locator("[data-confirm-split]").click()
        page.wait_for_selector(".drawer", state="detached")
        assert received == [{"source_ids": ["SRC-UI-FIXTURE"], "new_title": "测试拆分后的独立事件", "actor_id": "本地运营"}]
        browser.close()
    print(json.dumps({"ok": True, "mode": "隔离浏览器响应", "real_database_writes": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
