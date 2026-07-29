import pandas as pd
from bs4 import BeautifulSoup

file_path = '/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/员工党委分布列表.xlsx'
df = pd.read_excel(file_path).fillna('-')

# Build tree
tree = {"type": "集团党委", "name": "中国共产党东风汽车集团有限公司委员会", "children": {}}

for _, row in df.iterrows():
    l1 = str(row['所在党委']).strip()
    l2 = str(row['下属党委']).strip()
    l3 = str(row['三级党委']).strip()
    l4 = str(row['四级党委']).strip()
    l5 = str(row['党支部']).strip()
    
    if l1 == '-': continue
    if l1 not in tree["children"]: tree["children"][l1] = {"type": "所在党委", "level": 2, "children": {}}
    curr = tree["children"][l1]
    
    if l2 != '-':
        if l2 not in curr["children"]: curr["children"][l2] = {"type": "下属党委", "level": 3, "children": {}}
        curr = curr["children"][l2]
        
        if l3 != '-':
            if l3 not in curr["children"]: curr["children"][l3] = {"type": "三级党委", "level": 4, "children": {}}
            curr = curr["children"][l3]
            
            if l4 != '-':
                if l4 not in curr["children"]: curr["children"][l4] = {"type": "四级党委", "level": 5, "children": {}}
                curr = curr["children"][l4]
    
    if l5 != '-':
        if l5 not in curr["children"]:
            # Limit leaf nodes (党支部) to max 3 per parent to avoid DOM explosion
            if len([k for k,v in curr["children"].items() if v["type"] == "党支部"]) < 3:
                curr["children"][l5] = {"type": "党支部", "level": 6, "children": {}}

def render_node(name, node, is_root=False, level_num=1):
    html = []
    is_leaf = len(node["children"]) == 0
    
    # Checkbox container
    extra_classes = " border-b border-gray-200 pb-2 mb-3" if is_root else " mt-2 mb-2"
    html.append(f'<div class="flex items-center cursor-pointer org-node hover:bg-gray-50 rounded{extra_classes}" data-type="{node["type"]}" data-level="{level_num}" data-name="{name}" title="{name}">')
    
    # Toggle icon
    if is_root:
        html.append('<div class="w-4 h-4 mr-1 flex-shrink-0"></div>') # No toggle for root
    elif not is_leaf:
        html.append('<div class="toggle-icon flex items-center justify-center w-4 h-4 mr-1 flex-shrink-0"><i class="fas fa-chevron-down text-gray-400 text-[10px]"></i></div>')
    else:
        html.append('<div class="w-4 h-4 mr-1 flex-shrink-0"></div>') # Spacer
        
    # Checkbox itself
    html.append('<div class="checkbox-box w-4 h-4 border border-gray-300 rounded mr-2 bg-white flex-shrink-0 flex items-center justify-center"></div>')
    
    # Icon
    if is_root:
        html.append('<i class="fas fa-university text-gray-500 mr-2 flex-shrink-0"></i>')
    elif node["type"] == "党支部":
        html.append('<i class="fas fa-users text-gray-400 mr-2 text-xs flex-shrink-0"></i>')
    else:
        html.append('<i class="fas fa-building text-blue-500 mr-2 flex-shrink-0"></i>')
    
    # Text with title for hover
    html.append(f'<span class="text-gray-800 flex-1 truncate {"text-sm font-medium" if is_root else "text-[11px]"}">{name}</span>')
    
    # Badges
    if node["type"] == "所在党委":
        html.append('<span class="flex-shrink-0 text-[10px] bg-blue-100 text-blue-600 px-1 rounded mr-1">二级</span>')
    elif node["type"] == "下属党委":
        html.append('<span class="flex-shrink-0 text-[10px] bg-indigo-100 text-indigo-600 px-1 rounded mr-1">三级</span>')
    
    html.append('</div>')
    
    # Children
    if not is_leaf:
        margin_class = "" if is_root else "pl-6"
        html.append(f'<div class="children-container {margin_class}">')
        for child_name in sorted(node["children"].keys()):
            html.extend(render_node(child_name, node["children"][child_name], False, level_num + 1))
        html.append('</div>')
        
    return html

tree_html_lines = render_node(tree["name"], tree, True, 1)
tree_html = "\n".join(tree_html_lines)

html_path = '/Users/RondoT/Documents/护卫军相关/04_成长与激励体系/04_成长体系UI原型/B端_成长数据健康度大盘.html'

with open(html_path, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

sidebar = soup.find('div', id='org-tree-sidebar')
tree_container = sidebar.find_all('div', class_='flex-1 overflow-y-auto p-3 text-sm')
if len(tree_container) > 0:
    target_div = tree_container[0]
    target_div.clear()
    
    parsed_tree = BeautifulSoup(tree_html, 'html.parser')
    target_div.append(parsed_tree)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(str(soup))

print("Injected HTML successfully!")
