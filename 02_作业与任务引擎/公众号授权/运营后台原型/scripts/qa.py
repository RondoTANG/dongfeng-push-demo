import os
import re
import glob

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pages_dir = os.path.join(base_dir, "pages")
modules_dir = os.path.join(base_dir, "docs", "modules")

def run_qa():
    print("=" * 40)
    print("🔍 开始护卫军原型工程自检...")
    print("=" * 40)

    # 1. 扫描所有 MD 中定义的 pin keys
    defined_keys = set()
    for filename in os.listdir(modules_dir):
        if not filename.endswith(".md"):
            continue
        filepath = os.path.join(modules_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            pin_blocks = re.split(r'###\s*📍\s*图钉批注：\s*([a-zA-Z0-9_]+)', content)
            for i in range(1, len(pin_blocks), 2):
                key = pin_blocks[i].strip()
                defined_keys.add(key)
    
    # 2. 扫描所有 HTML 中使用的 pin keys
    used_keys = set()
    key_to_files = {} # 记录 key 在哪些文件里被用了
    html_files = glob.glob(os.path.join(pages_dir, "**", "*.html"), recursive=True)
    
    for fpath in html_files:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            # 查找 data-key="xxx"
            matches = re.findall(r'data-key="([^"]+)"', content)
            for key in matches:
                used_keys.add(key)
                rel_path = os.path.relpath(fpath, base_dir)
                if key not in key_to_files:
                    key_to_files[key] = set()
                key_to_files[key].add(rel_path)
                
    # 3. 对比分析
    missing_in_md = used_keys - defined_keys
    unused_in_html = defined_keys - used_keys
    
    issues_found = False
    
    print("\n✅ 第一项检查：HTML中的图钉是否都有Markdown配置支持？")
    if missing_in_md:
        issues_found = True
        print(f"❌ 发现 {len(missing_in_md)} 个「无头图钉」（HTML 里有，但 MD 里没写配置）：")
        for k in missing_in_md:
            files = ", ".join(key_to_files[k])
            print(f"   - '{k}' (出现在 {files})")
    else:
        print("🎉 完美！所有页面上的图钉都有对应的 Markdown 批注支持。")
        
    print("\n✅ 第二项检查：Markdown中配置的图钉是否都已在页面实装？")
    if unused_in_html:
        issues_found = True
        print(f"⚠️ 发现 {len(unused_in_html)} 个「闲置批注」（MD 里写了，但 HTML 里没挂载）：")
        for k in unused_in_html:
            print(f"   - '{k}'")
    else:
        print("🎉 完美！PRD 里的所有图钉都已经 100% 在前端页面落地。")
        
    print("\n" + "=" * 40)
    if issues_found:
        print("🛑 自检未完全通过，请修复上述问题以保证质量！")
    else:
        print("✨ 恭喜！自检满分通过！当前工程架构非常健康！")

if __name__ == "__main__":
    run_qa()
