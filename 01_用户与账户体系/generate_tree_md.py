import pandas as pd
import json

file_path = '/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/员工党委分布列表.xlsx'
df = pd.read_excel(file_path)

df = df.fillna('-')

# tree structure: tree[node_name] = {"type": type_name, "children": {}}
tree = {}

for _, row in df.iterrows():
    l1 = str(row['所在党委']).strip()
    l2 = str(row['下属党委']).strip()
    l3 = str(row['三级党委']).strip()
    l4 = str(row['四级党委']).strip()
    l5 = str(row['党支部']).strip()
    
    if l1 == '-': continue
    if l1 not in tree: tree[l1] = {"type": "所在党委", "children": {}}
    
    current_level = tree[l1]["children"]
    
    if l2 != '-':
        if l2 not in current_level: current_level[l2] = {"type": "下属党委", "children": {}}
        current_level = current_level[l2]["children"]
        
        if l3 != '-':
            if l3 not in current_level: current_level[l3] = {"type": "三级党委", "children": {}}
            current_level = current_level[l3]["children"]
            
            if l4 != '-':
                if l4 not in current_level: current_level[l4] = {"type": "四级党委", "children": {}}
                current_level = current_level[l4]["children"]
    
    if l5 != '-':
        if l5 not in current_level: current_level[l5] = {"type": "党支部", "children": {}}


def generate_markdown(node_dict, level=0):
    lines = []
    for key in sorted(node_dict.keys()):
        node = node_dict[key]
        indent = "  " * level
        lines.append(f"{indent}- {key} `[{node['type']}]`")
        lines.extend(generate_markdown(node["children"], level + 1))
    return lines

md_lines = ["# 员工党委树结构梳理（带党委层级标签）\n"]
md_lines.append("根节点：**中国共产党东风汽车集团有限公司委员会** `[集团党委]`\n")
md_lines.extend(generate_markdown(tree))

with open('/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/员工党委树结构.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_lines))

print("Markdown generated successfully at 员工党委树结构.md")
