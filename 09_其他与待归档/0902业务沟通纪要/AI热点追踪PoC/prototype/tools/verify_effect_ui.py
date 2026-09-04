from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright


base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(f"{base_url}/#page=effects", wait_until="networkidle")
    page.locator("h1", has_text="原创后效追踪").wait_for()
    page.locator("text=原创后效闭环验证内容").first.wait_for()
    page.locator("text=观察到指标增长").wait_for()
    page.locator("text=生成二次加热草案").first.wait_for()
    page.locator("button", has_text="查看二次加热草案").click()
    page.wait_for_url("**/#page=drafts")
    page.locator("text=原创后二次加热").first.wait_for()
    page.screenshot(path="/tmp/df-hotspot-effect-ui.png", full_page=True)
    assert not console_errors, f"浏览器控制台错误：{console_errors}"
    print({"page": page.title(), "url": page.url, "screenshot": "/tmp/df-hotspot-effect-ui.png", "console_errors": 0})
    browser.close()
