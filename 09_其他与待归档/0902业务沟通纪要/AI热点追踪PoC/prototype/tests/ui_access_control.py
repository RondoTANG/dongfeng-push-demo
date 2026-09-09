"""真实浏览器验证登录、角色隔离与手机端响应式；不执行采集或业务审批。"""
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8765"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from service.database import connection
SCREENSHOT_DIR = ROOT / "tests" / "screenshots" / "access-control-20260906"


def login(page, secret: str) -> None:
    page.goto(BASE_URL, wait_until="networkidle")
    page.locator("#access-key").fill(secret)
    page.locator("[data-login-form] button[type=submit]").click()
    page.wait_for_selector("#app-shell:not([hidden])")


def main() -> None:
    admin_secret = (ROOT / "data" / "admin_access.key").read_text(encoding="utf-8").strip()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        anonymous = browser.new_context(viewport={"width": 390, "height": 844})
        anonymous_page = anonymous.new_page()
        anonymous_page.goto(BASE_URL + "/flowcharts/poc-flow.html", wait_until="networkidle")
        assert anonymous_page.url.rstrip("/") == BASE_URL
        assert anonymous_page.locator("#access-key").count() == 1
        assert anonymous_page.locator("#poc-conclusion-title").is_visible()
        assert "不能判断真实热点" in anonymous_page.locator("#poc-conclusion-title").inner_text()
        assert anonymous_page.get_by_text("公开信息线索与内容机会PoC", exact=True).is_visible()
        assert anonymous_page.locator("[data-page='access-keys']").count() == 0
        assert anonymous_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert anonymous_page.evaluate("document.documentElement.scrollHeight > window.innerHeight")
        anonymous_page.screenshot(path=str(SCREENSHOT_DIR / "anonymous-mobile-conclusion.png"), full_page=True)
        anonymous.close()
        admin = browser.new_context(viewport={"width": 1440, "height": 900})
        admin_page = admin.new_page()
        login(admin_page, admin_secret)
        for row in admin_page.request.get(BASE_URL + "/api/access-keys").json()["items"]:
            if row["label"] == "响应式验收临时密钥" and row["status"] == "active":
                admin_page.request.post(BASE_URL + "/api/access-keys/" + row["access_key_id"] + "/revoke")
        admin_page.locator('[data-page="access-keys"]').click()
        admin_page.wait_for_selector("[data-create-access-key]")
        admin_page.locator("[data-create-access-key]").click()
        admin_page.locator('[name="key_label"]').fill("响应式验收临时密钥")
        admin_page.locator("[data-confirm-create-key]").click()
        generated = admin_page.locator(".generated-key code")
        generated.wait_for()
        visitor_secret = generated.text_content().strip()
        assert visitor_secret.startswith("VIS-")
        admin_page.screenshot(path=str(SCREENSHOT_DIR / "admin-key-created.png"), full_page=True)
        admin_page.get_by_role("button", name="完成").click()
        rows = admin_page.request.get(BASE_URL + "/api/access-keys").json()["items"]
        target = next(row for row in rows if row["label"] == "响应式验收临时密钥")
        admin_page.locator('[data-reveal-key="' + target["access_key_id"] + '"]').click()
        admin_page.locator('[name="admin_key"]').fill(admin_secret)
        admin_page.locator("[data-confirm-reveal-key]").click()
        admin_page.locator("[data-copy-revealed-key]").wait_for()
        assert admin_page.locator(".generated-key code").text_content().strip() == visitor_secret
        admin_page.locator(".drawer__footer [data-drawer-close]").click()

        visitor = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        visitor_page = visitor.new_page()
        login(visitor_page, visitor_secret)
        assert visitor_page.locator('[data-page="access-keys"]').count() == 0
        assert visitor_page.locator("body.is-viewer").count() == 1
        assert visitor_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        response = visitor_page.request.post(BASE_URL + "/api/runs", data={"mode": "quick", "trigger_type": "manual"})
        assert response.status == 403
        response = visitor_page.request.get(BASE_URL + "/api/access-keys")
        assert response.status == 403
        visitor_page.locator("[data-mobile-nav-toggle]").click()
        visitor_page.wait_for_timeout(260)
        assert visitor_page.locator("body.nav-open").count() == 1
        sidebar_box = visitor_page.locator(".app-sidebar").bounding_box()
        assert sidebar_box and sidebar_box["x"] == 0 and sidebar_box["width"] >= 280
        visitor_page.screenshot(path=str(SCREENSHOT_DIR / "viewer-mobile-nav.png"), full_page=True)

        visitor_page.locator('[data-page="event-detail"]').click()
        visitor_page.wait_for_selector(".event-workspace.is-mobile-list")
        visitor_page.wait_for_timeout(260)
        assert visitor_page.locator("body.nav-open").count() == 0
        closed_sidebar = visitor_page.locator(".app-sidebar").bounding_box()
        assert closed_sidebar and closed_sidebar["x"] + closed_sidebar["width"] <= 1
        assert visitor_page.locator(".event-queue").is_visible()
        assert not visitor_page.locator(".event-detail-panel").is_visible()
        assert visitor_page.locator(".event-queue__list").evaluate("el => getComputedStyle(el).overflowY") == "visible"
        visitor_page.screenshot(path=str(SCREENSHOT_DIR / "viewer-mobile-event-list.png"), full_page=False)
        visitor_page.locator("[data-select-event]").first.click()
        visitor_page.wait_for_selector(".event-workspace.is-mobile-detail")
        assert not visitor_page.locator(".event-queue").is_visible()
        assert visitor_page.locator("[data-mobile-event-back]").is_visible()
        event_actions = visitor_page.locator(".event-detail-panel .event-detail-head > .page-head__actions")
        event_actions_box = event_actions.bounding_box()
        assert event_actions_box and 740 <= event_actions_box["y"] < 844
        assert event_actions_box["y"] + event_actions_box["height"] >= 840
        app_scroll = visitor_page.locator("#app")
        assert app_scroll.evaluate("el => el.scrollHeight > el.clientHeight")
        visitor_page.screenshot(path=str(SCREENSHOT_DIR / "viewer-mobile-event-detail-top.png"), full_page=False)
        app_scroll.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        visitor_page.wait_for_timeout(100)
        assert app_scroll.evaluate("el => el.scrollTop") > 0
        visitor_page.screenshot(path=str(SCREENSHOT_DIR / "viewer-mobile-event-detail.png"), full_page=True)
        visitor_page.locator("[data-mobile-event-back]").click()
        visitor_page.wait_for_selector(".event-workspace.is-mobile-list")
        assert visitor_page.locator(".event-queue").is_visible()

        visitor_page.locator("[data-mobile-nav-toggle]").click()
        visitor_page.wait_for_timeout(260)
        visitor_page.locator('[data-page="drafts"]').click()
        visitor_page.wait_for_selector(".draft-workspace.is-mobile-list")
        visitor_page.wait_for_timeout(260)
        assert visitor_page.locator("body.nav-open").count() == 0
        closed_sidebar = visitor_page.locator(".app-sidebar").bounding_box()
        assert closed_sidebar and closed_sidebar["x"] + closed_sidebar["width"] <= 1
        assert visitor_page.locator(".draft-list").is_visible()
        assert not visitor_page.locator(".draft-detail").is_visible()
        assert visitor_page.locator(".event-queue__list").evaluate("el => getComputedStyle(el).overflowY") == "visible"
        assert visitor_page.locator("[data-select-draft]").count() > 0
        visitor_page.screenshot(path=str(SCREENSHOT_DIR / "viewer-mobile-draft-list.png"), full_page=False)
        visitor_page.locator("[data-select-draft]").first.click()
        visitor_page.wait_for_selector(".draft-workspace.is-mobile-detail")
        assert not visitor_page.locator(".draft-list").is_visible()
        assert visitor_page.locator("[data-mobile-draft-back]").is_visible()
        draft_actions = visitor_page.locator(".draft-detail .event-detail-head > .page-head__actions")
        draft_actions_box = draft_actions.bounding_box()
        assert draft_actions_box and 740 <= draft_actions_box["y"] < 844
        assert draft_actions_box["y"] + draft_actions_box["height"] >= 840
        app_scroll = visitor_page.locator("#app")
        assert app_scroll.evaluate("el => el.scrollHeight > el.clientHeight")
        visitor_page.screenshot(path=str(SCREENSHOT_DIR / "viewer-mobile-draft-detail-top.png"), full_page=False)
        app_scroll.evaluate("el => { el.scrollTop = el.scrollHeight; }")
        visitor_page.wait_for_timeout(100)
        assert app_scroll.evaluate("el => el.scrollTop") > 0
        visitor_page.screenshot(path=str(SCREENSHOT_DIR / "viewer-mobile-draft-detail.png"), full_page=True)
        visitor_page.locator("[data-mobile-draft-back]").click()
        visitor_page.wait_for_selector(".draft-workspace.is-mobile-list")
        assert visitor_page.locator(".draft-list").is_visible()

        admin_page.request.post(BASE_URL + "/api/access-keys/" + target["access_key_id"] + "/revoke")
        assert visitor_page.request.get(BASE_URL + "/api/runs").status == 401
        visitor.close()
        admin.close()
        browser.close()
    with connection() as db:
        ids = [row[0] for row in db.execute("SELECT access_key_id FROM access_keys WHERE label=?", ("响应式验收临时密钥",)).fetchall()]
        for access_key_id in ids:
            db.execute("DELETE FROM access_sessions WHERE access_key_id=?", (access_key_id,))
            db.execute("DELETE FROM audit_logs WHERE object_type='access_key' AND object_id=?", (access_key_id,))
            db.execute("DELETE FROM access_keys WHERE access_key_id=?", (access_key_id,))
    print("访问控制与手机端验证通过：管理员可二次验证查看密钥；访客只读；事件和草案均在手机端使用列表／独立详情，详情可完整滚动。")


if __name__ == "__main__":
    main()
