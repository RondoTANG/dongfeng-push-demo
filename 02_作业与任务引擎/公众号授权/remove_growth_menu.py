import re

# 1. Update dashboard.html
dashboard_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/dashboard.html'
with open(dashboard_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the "成长体系" menu group block
# Specifically look for the menu-group that contains "成长体系" and its closing tags
pattern = re.compile(r'<!-- 成长体系 -->\s*<div class="menu-group">\s*<div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu\(this\)">\s*<span class="font-bold text-gray-800">成长体系</span>.*?</svg>\s*</div>\s*<div class="flex flex-col hidden pb-1 pt-1">\s*<a[^>]*>体系规则配置</a>\s*</div>\s*</div>\s*', re.DOTALL)

# But wait, my previous script used a simple replace. Let's just use a more robust regex or string replacement.
# Let's see the exact HTML snippet first.
