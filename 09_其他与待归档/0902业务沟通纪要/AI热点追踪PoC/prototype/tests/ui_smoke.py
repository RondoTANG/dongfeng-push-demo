from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8765"
PAGES = ["run-center", "clues", "event-detail", "drafts", "effects", "config", "audit"]


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
        page.goto(f"{BASE_URL}/?smoke=run-check#page=run-center")
        page.wait_for_load_state("networkidle")
        assert "已暂停" in page.locator(".automation-strip").inner_text()
        assert page.locator("#anno-toggle-btn").inner_text() == "产品标注"
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
