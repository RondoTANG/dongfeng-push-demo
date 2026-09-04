from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright


url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8766/prd/AI热点发现与护卫军作业联动_PRD_v0.2.html"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(url, wait_until="networkidle")
    page.locator("h1", has_text="AI热点发现与护卫军作业联动").wait_for()
    assert page.locator(".requirement").count() == 18
    assert page.locator(".acceptance").count() == 18
    assert page.locator("text=原创发布后的后效处理时序").count() == 1
    assert page.locator("text=原创后二次加热判断与草案").count() == 1
    overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    assert not overflow, "页面存在横向溢出"
    assert not console_errors, f"浏览器控制台错误：{console_errors}"
    page.screenshot(path="/tmp/df-hotspot-prd-effect.png", full_page=False)
    print({"requirements": 18, "acceptance": 18, "overflow": False, "console_errors": 0, "screenshot": "/tmp/df-hotspot-prd-effect.png"})
    browser.close()
