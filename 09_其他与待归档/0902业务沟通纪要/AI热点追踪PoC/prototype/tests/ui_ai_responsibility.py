"""只读核验流程图与PRD的AI／规则分工，不发起采集或业务写入。"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    root = Path(__file__).resolve().parents[1]
    prd = root.parent / 'prd' / 'AI热点发现与护卫军作业联动_PRD_v0.2.html'
    output = root / 'tests/screenshots/ai-responsibility'
    output.mkdir(parents=True, exist_ok=True)
    targets = [('flow', 'http://127.0.0.1:8765/flowcharts/poc-flow.html'), ('prd', prd.as_uri() + '#module-3')]
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        admin_secret = (root / 'data/admin_access.key').read_text(encoding='utf-8').strip()
        page.goto('http://127.0.0.1:8765', wait_until='networkidle')
        page.locator('#access-key').fill(admin_secret)
        page.locator('[data-login-form] button[type=submit]').click()
        page.wait_for_selector('#app-shell:not([hidden])')
        for name, url in targets:
            for width in (1440, 1280, 768):
                page.set_viewport_size({'width': width, 'height': 1000})
                page.goto(url, wait_until='networkidle')
                assert page.locator('.responsibility-table tbody tr').count() == 11
                assert '尚未接通' in page.locator('.responsibility-table').inner_text()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (name, width)
                if name == 'flow':
                    assert page.locator('.flow .step').count() == 9
                    assert page.locator('.flow .missing').count() == 2
                else:
                    page.locator('#module-3').scroll_into_view_if_needed()
                page.screenshot(path=str(output / f'{name}-{width}.png'))
                checks.append([name, width])
        # 窄屏按现有设计隐藏批量折叠按钮；在桌面尺寸核验此交互。
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.locator('#searchInput').fill('个性化作业')
        assert page.locator('#module-3').is_visible()
        page.locator('#searchInput').fill('')
        page.locator('#expandAll').click()
        page.locator('#collapseAll').click()
        page.emulate_media(media='print')
        assert page.locator('.responsibility-table').is_visible()
        assert not errors, errors
        browser.close()
    print(json.dumps({'ok': True, 'checks': checks, 'page_errors': errors, 'business_writes': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
