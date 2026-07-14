import re

prd_html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'
with open(prd_html_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'href="dashboard.html" target="_blank" onclick="if(window.parent!==window){window.parent.location.hash=\'dashboard/wechat\'; return false;}"',
    'href="dashboard.html#wechat" target="_blank" onclick="if(window.parent!==window){window.parent.location.hash=\'dashboard/wechat\'; return false;}"'
)

content = content.replace(
    'href="dashboard.html" target="_blank" onclick="if(window.parent!==window){window.parent.location.hash=\'dashboard/jobs\'; return false;}"',
    'href="dashboard.html#jobs" target="_blank" onclick="if(window.parent!==window){window.parent.location.hash=\'dashboard/jobs\'; return false;}"'
)

with open(prd_html_path, 'w', encoding='utf-8') as f:
    f.write(content)

prd_md_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.md'
with open(prd_md_path, 'r', encoding='utf-8') as f:
    md_content = f.read()

md_content = md_content.replace('[进入「公众号管理」原型](dashboard.html)', '[进入「公众号管理」原型](dashboard.html#wechat)')
md_content = md_content.replace('[进入「作业管理」原型](dashboard.html)', '[进入「作业管理」原型](dashboard.html#jobs)')

with open(prd_md_path, 'w', encoding='utf-8') as f:
    f.write(md_content)

