import os
from datetime import datetime

source_file = '/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/员工党委树结构.md'
target_dir = '/Users/RondoT/Desktop/Rondo的知识库/AI协作资产/02_产品设计模型'
target_file = os.path.join(target_dir, '员工党委树结构.md')

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

frontmatter = f"""---
title: 员工党委树结构梳理
tags:
  - 产品模型
  - 组织架构
  - 护卫军
date: {date_str}
---

"""

with open(target_file, 'w', encoding='utf-8') as f:
    f.write(frontmatter + content)

print(f"Archived to {target_file}")
