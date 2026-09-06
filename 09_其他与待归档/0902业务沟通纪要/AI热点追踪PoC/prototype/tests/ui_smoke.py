from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8765"
PAGES = ["run-center", "clues", "event-detail", "drafts", "effects", "config", "audit"]
MOBILE_PAGES = PAGES + ["access-keys"]


def main() -> None:
    errors: list[str] = []
    bad_responses: list[str] = []
    snapshots: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("response", lambda response: bad_responses.append(f"{response.status} {response.url}") if response.status >= 400 else None)
        admin_secret = (Path(__file__).resolve().parents[1] / "data/admin_access.key").read_text(encoding="utf-8").strip()
        page.goto(BASE_URL, wait_until="networkidle")
        page.locator("#access-key").fill(admin_secret)
        page.locator("[data-login-form] button[type=submit]").click()
        page.wait_for_selector("#app-shell:not([hidden])")
        for page_key in PAGES:
            page.goto(f"{BASE_URL}/?smoke={page_key}#page={page_key}")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("#app .page")
            service_text = page.locator("#service-status .service-status__text").inner_text()
            snapshots.append({
                "page": page_key,
                "title": page.title(),
                "service": service_text,
                "h1": page.locator("#app h1").first.inner_text(),
            })
            if service_text != "本地服务正常":
                raise AssertionError(f"{page_key} 未连接本地服务：{service_text}")
        page.goto(f"{BASE_URL}/?smoke=clues-check#page=clues")
        page.wait_for_load_state("networkidle")
        assert page.locator('[data-filter="fetched_from"]').count() == 1
        assert page.locator('[data-filter="published_from"]').count() == 1
        page.evaluate('window.dispatchEvent(new Event("resize")); window.dispatchEvent(new Event("scroll"));')
        assert page.locator("#anno-toggle-btn").count() == 0
        assert "搜索来源" in page.locator("table").first.inner_text()
        assert "正文／搜索摘要" in page.locator("table").first.inner_text()
        page.goto(f"{BASE_URL}/?smoke=run-check#page=run-center")
        page.wait_for_load_state("networkidle")
        automation_text = page.locator(".automation-control").inner_text()
        assert "自动采集" in automation_text and "采集周期" in automation_text
        assert page.locator("#anno-toggle-btn").count() == 0
        assert page.locator("[data-import-sample]").count() == 0

        page.set_viewport_size({"width": 390, "height": 844})
        for page_key in MOBILE_PAGES:
            page.goto(f"{BASE_URL}/?mobile-smoke={page_key}#page={page_key}")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("#app .page")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), page_key

        def assert_drawer_footer(selector: str) -> None:
            page.locator(selector).first.click()
            page.wait_for_selector(".drawer-mask.is-open")
            footer = page.locator(".drawer__footer").bounding_box()
            assert footer and footer["y"] + footer["height"] >= 840
            page.locator(".drawer__footer [data-drawer-close]").first.click()

        page.goto(f"{BASE_URL}/?mobile-smoke=run-drawer#page=run-center", wait_until="networkidle")
        assert_drawer_footer('[data-run-mode="quick"]')
        page.goto(f"{BASE_URL}/?mobile-smoke=clue-drawer#page=clues", wait_until="networkidle")
        assert_drawer_footer("[data-source-detail]")
        page.goto(f"{BASE_URL}/?mobile-smoke=config-drawer#page=config", wait_until="networkidle")
        assert_drawer_footer("[data-config-versions]")
        page.locator('[data-config-tab="queries"]').click()
        assert_drawer_footer('[data-edit-config="query"]')
        page.goto(f"{BASE_URL}/?mobile-smoke=key-drawer#page=access-keys", wait_until="networkidle")
        assert_drawer_footer("[data-create-access-key]")
        browser.close()
    if errors:
        raise AssertionError("浏览器错误：" + " | ".join(errors))
    if bad_responses:
        raise AssertionError("失败响应：" + " | ".join(bad_responses))
    evidence = Path("tests/ui_smoke_result.json")
    evidence.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "pages": snapshots}, ensure_ascii=False))


if __name__ == "__main__":
    main()
