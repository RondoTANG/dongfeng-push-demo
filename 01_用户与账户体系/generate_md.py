import pandas as pd

df = pd.read_excel('/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/用户党委分布.xlsx')
df = df.fillna('-')

tree = {}
for _, row in df.iterrows():
    l2 = str(row.get('所在党委', '-')).strip()
    l3 = str(row.get('下属党委', '-')).strip()
    leaf = str(row.get('党支部', '-')).strip()
    
    if l2 == 'nan': l2 = '-'
    if l3 == 'nan': l3 = '-'
    if leaf == 'nan': leaf = '-'
    
    if l2 not in tree:
        tree[l2] = {}
        
    if l3 not in tree[l2]:
        tree[l2][l3] = set()
        
    tree[l2][l3].add(leaf)

lines = []
lines.append('# 用户党委树结构梳理')
lines.append('')
lines.append('> **💡 数据说明**')
lines.append('> 数据来源：护卫军系统的用户列表 `用户党委分布.xlsx`')
lines.append('> 注意：本树形结构严格遵循【所在党委】-【下属党委】-【党支部】的三级业务层级，表中某一层级为空则显示为 `-`。')
lines.append('')
lines.append('- 中国共产党东风汽车集团有限公司委员会 `[集团党委]` (全局根节点)')

for l2 in sorted(tree.keys()):
    lines.append(f'  - {l2} `[所在党委]` - 即二级')
    for l3 in sorted(tree[l2].keys()):
        lines.append(f'    - {l3} `[下属党委]` - 即三级')
        for leaf in sorted(tree[l2][l3]):
            lines.append(f'      - {leaf} `[党支部]` (最末端叶子节点)')

with open('/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/用户党委树结构.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print('Markdown file generated successfully.')
