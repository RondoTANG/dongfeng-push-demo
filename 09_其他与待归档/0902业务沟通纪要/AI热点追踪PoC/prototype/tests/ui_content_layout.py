"""只读检查真实关联依据和真实作业草案的排版。"""
import json
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


def main():
    base = "http://127.0.0.1:8765"
    sources = json.load(urlopen(base + "/api/sources?page_size=100"))["items"]
    target = next(s for s in sources if len(s["business_relation"].get("relations", [])) > 1)
    drafts = json.load(urlopen(base + "/api/drafts?page_size=100"))["items"]
    assert drafts, "需要用户已有真实草案，不创建测试业务记录"
    output = Path("tests/screenshots/content-layout-20260906")
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "/#page=clues", wait_until="networkidle")
        page.locator(f'[data-source-detail="{target["source_id"]}"]').click()
        page.wait_for_function("getComputedStyle(document.querySelector('.drawer-mask')).opacity === '1'")
        relation = page.locator(".relation-context")
        relation.scroll_into_view_if_needed()
        assert relation.locator(".relation-evidence-group").count() < len(target["business_relation"]["relations"])
        for brand in target["business_relation"]["relations"]:
            assert brand["brand_name"] in relation.inner_text()
        page.screenshot(path=str(output / "relation-evidence.png"))
        page.locator("[data-drawer-close]").first.click()
        page.wait_for_selector(".drawer", state="detached")
        page.goto(base + "/#page=drafts", wait_until="networkidle")
        page.wait_for_selector(".brief-section h4")
        assert page.locator(".brief-section h4").count() >= 4
        heading = page.locator(".brief-section h4").first
        body = page.locator(".brief-section .brief-line").first
        assert heading.evaluate("(el)=>getComputedStyle(el).color") != body.evaluate("(el)=>getComputedStyle(el).color")
        assert float(heading.evaluate("(el)=>getComputedStyle(el).fontSize").replace("px","")) > float(body.evaluate("(el)=>getComputedStyle(el).fontSize").replace("px",""))
        page.screenshot(path=str(output / "draft-brief.png"))
        # 编辑仍显示原始纯文本，不因只读排版而改写或丢失字段。
        page.locator("[data-edit-draft]").click()
        assert page.locator('[name="task_brief"]').input_value() == drafts[0]["task_brief"]
        page.locator("[data-drawer-close]").first.click()
        assert not errors, errors
        browser.close()
    print(json.dumps({"ok": True, "real_drafts": len(drafts), "business_writes": 0, "screenshots": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
