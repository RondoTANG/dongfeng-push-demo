import os, re, json

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
modules_dir = os.path.join(base_dir, "docs", "modules")
js_path = os.path.join(base_dir, "docs", "annotations.js")

def build_annotations():
    annotations = {}
    
    if not os.path.exists(modules_dir):
        print(f"Directory {modules_dir} not found.")
        return
        
    for filename in os.listdir(modules_dir):
        if not filename.endswith(".md"):
            continue
            
        filepath = os.path.join(modules_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Parse pins using regex
        # Pattern looks for: ### 📍 图钉批注：[key] followed by bullet points
        pin_blocks = re.split(r'###\s*📍\s*图钉批注：\s*([a-zA-Z0-9_]+)', content)
        
        # pin_blocks[0] is everything before the first pin
        # pin_blocks[1] is the first key, pin_blocks[2] is its content, etc.
        for i in range(1, len(pin_blocks), 2):
            key = pin_blocks[i].strip()
            block_content = pin_blocks[i+1]
            
            data = {}
            # Extract fields
            title_match = re.search(r'-\s*\*\*功能名称\*\*\s*[：:]\s*(.+)', block_content)
            def_match = re.search(r'-\s*\*\*功能定义\*\*\s*[：:]\s*(.+)', block_content)
            source_match = re.search(r'-\s*\*\*数据来源\*\*\s*[：:]\s*(.+)', block_content)
            logic_match = re.search(r'-\s*\*\*取值逻辑\*\*\s*[：:]\s*(.+)', block_content)
            interaction_match = re.search(r'-\s*\*\*交互说明\*\*\s*[：:]\s*(.+)', block_content)
            fields_match = re.search(r'-\s*\*\*字段说明\*\*\s*[：:]\s*(.+)', block_content)
            
            data["title"] = title_match.group(1).strip() if title_match else ""
            data["definition"] = def_match.group(1).strip() if def_match else ""
            data["dataSource"] = source_match.group(1).strip() if source_match else ""
            data["logic"] = logic_match.group(1).strip() if logic_match else ""
            data["interaction"] = interaction_match.group(1).strip() if interaction_match else ""
            data["fields"] = fields_match.group(1).strip() if fields_match else ""
            
            annotations[key] = data

    # Write JS file
    js_content = f"""// 护卫军原型工程 - 全局批注数据字典
// 【注意】此文件由 scripts/build.py 自动根据 docs/modules 下的 Markdown 文件生成，请勿手动修改！
const PRD_ANNOTATIONS = {json.dumps(annotations, ensure_ascii=False, indent=4)};
"""
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)
        
    print(f"Successfully built {len(annotations)} annotations to {js_path}")

if __name__ == "__main__":
    build_annotations()
