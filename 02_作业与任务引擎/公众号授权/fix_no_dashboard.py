import re

html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the menu item for 数据大屏
content = re.sub(r'<!-- 独立菜单: 数据大屏 -->\s*<a[^>]*data-page="dashboard"[^>]*>\s*<span>数据大屏</span>\s*</a>', '', content)

# Remove the page-dashboard div
content = re.sub(r'<div id="page-dashboard"[^>]*>.*?</div>\s*<!-- 2\. Wechat Management -->', '<!-- Wechat Management -->', content, flags=re.DOTALL)

# Set the initial switchPage call at the end of the script (if it exists)
content = re.sub(r"switchPage\('dashboard',\s*'数据大屏概览'\);", "switchPage('wechat', '公众号管理');", content)

# Check if page-wechat needs "active"
# It's better to ensure the default switchPage is called in DOMContentLoaded or similar.
# Wait, let's look at the bottom of the script.
if "switchPage(" not in content[-1000:]:
    # append default load
    content = content.replace('</body>', '    <script>\n        document.addEventListener("DOMContentLoaded", () => {\n            switchPage("wechat", "公众号管理");\n        });\n    </script>\n</body>')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)
