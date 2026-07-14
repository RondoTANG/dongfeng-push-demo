import re

# 1. Update dashboard.html
dashboard_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/dashboard.html'
with open(dashboard_path, 'r', encoding='utf-8') as f:
    content = f.read()

pattern_html = re.compile(r'\s*<!-- 成长体系与AI中台 -->\s*<div class="menu-group">\s*<div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu\(this\)">\s*<span class="font-bold text-gray-800">成长体系</span>\s*<i class="fas text-xs text-gray-400 fa-chevron-down"></i>\s*</div>\s*<div class="flex flex-col hidden pb-1 pt-1">\s*<a class="pl-10 pr-4 py-2\.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">体系规则配置</a>\s*</div>\s*</div>', re.DOTALL)

new_content = pattern_html.sub('', content)

with open(dashboard_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

# 2. Update 护卫军_全端系统菜单架构树.md
md_path = '/Users/RondoT/Documents/护卫军相关/护卫军_全端系统菜单架构树.md'
with open(md_path, 'r', encoding='utf-8') as f:
    md_content = f.read()

pattern_md = re.compile(r'- \*\*🌱 成长体系\*\*\n  - ↳ 体系规则配置\n\n')
new_md_content = pattern_md.sub('', md_content)

with open(md_path, 'w', encoding='utf-8') as f:
    f.write(new_md_content)

