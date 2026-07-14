import re

html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Modify body padding
content = content.replace('padding: 0;\n            line-height: 1.6;\n            display: flex;', 'padding: 0 0 0 290px;\n            line-height: 1.6;\n            display: flex;\n            justify-content: center;')

# Modify .main-content
content = content.replace('.main-content {\n            margin-left: 290px;\n            padding: 3rem 4rem;\n            max-width: 1020px;\n            box-sizing: border-box;\n            width: calc(100% - 290px);\n        }', '.main-content {\n            padding: 3rem 4rem;\n            max-width: 1020px;\n            box-sizing: border-box;\n            width: 100%;\n        }')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)
