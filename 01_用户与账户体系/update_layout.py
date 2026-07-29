import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Adjust sequence diagram width
content = content.replace('<div class="w-full mt-4 bg-white p-8 rounded-xl shadow-sm border border-gray-200">', 
                          '<div class="w-full max-w-5xl mx-auto mt-4 bg-white p-8 rounded-xl shadow-sm border border-gray-200">')

# 2. Swap layout: Devices on the left, Annotations on the right
# Current structure:
# <!-- 批注区域 -->
# <div class="w-[350px] shrink-0 space-y-6">
# ...
# </div>
# <!-- Toast 提示 -->
# ...
# <!-- 左侧设备...
# ...
# <!-- 右侧设备...
# ...
# <script>

# Let's extract the annotation block
match_annotation = re.search(r'(<!-- 批注区域 -->\s*<div class="w-\[350px\].*?</div>\s*</div>)', content, re.DOTALL)
if match_annotation:
    annotation_html = match_annotation.group(1)
    # increase width
    annotation_html = annotation_html.replace('w-[350px]', 'w-[450px]')
    
    # Remove it from current position
    content = content.replace(match_annotation.group(1), "")
    
    # Insert it right before the Toast / Script or actually right after the devices
    # The devices end at `    </div>\n\n    <script>`
    # Wait, the Toast is before devices currently, let's just put annotation right before the `<script>` tag
    # Actually, the layout is flex. 
    # Current flex items:
    # 1. Annotations
    # 2. Toast (fixed, doesn't matter)
    # 3. Device 1
    # 4. Device 2
    # So if we put Annotations after Device 2, it will naturally appear on the right.
    content = content.replace('    <script>', '    <!-- 批注区域 -->\n' + annotation_html + '\n\n    <script>')
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Layout updated successfully.")
else:
    print("Could not find annotation block.")

