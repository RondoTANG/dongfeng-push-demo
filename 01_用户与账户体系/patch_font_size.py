with open("/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/inject_tree_html.py", "r") as f:
    content = f.read()

content = content.replace('"text-sm font-medium" if is_root else "text-xs"', '"text-sm font-medium" if is_root else "text-[11px]"')

with open("/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/inject_tree_html.py", "w") as f:
    f.write(content)
