import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix clipping
content = content.replace(
    'class="flex items-start justify-center gap-8 flex-nowrap w-full max-w-[1400px] mx-auto overflow-x-auto pb-4"',
    'class="flex items-start justify-center gap-8 flex-nowrap w-full max-w-[1400px] mx-auto overflow-x-auto pt-6 pb-4"'
)

# Device 2 (currently first) starts at: <!-- 左侧设备：情况B 签约界面 -->
# and ends at: </div>\n        </div>
match_dev2 = re.search(r'(<!-- 左侧设备：情况B 签约界面 -->.*?</div>\s*</div>)', content, re.DOTALL)
# Device 1 (currently second) starts at: <!-- 右侧设备：全局系统弹窗模拟 -->
# and ends at: </div>\n        </div>
match_dev1 = re.search(r'(<!-- 右侧设备：全局系统弹窗模拟 -->.*?</div>\s*</div>)', content, re.DOTALL)

if match_dev1 and match_dev2:
    dev1_html = match_dev1.group(1)
    dev2_html = match_dev2.group(1)
    
    # Let's replace the whole body of the flex container to be safe
    # We find where Device 2 starts and where Device 1 ends
    start_idx = content.find('<!-- 左侧设备：情况B 签约界面 -->')
    end_idx = content.find('<!-- 批注区域 -->', start_idx)
    
    if start_idx != -1 and end_idx != -1:
        # We replace the text between start_idx and end_idx with dev1_html + "\n\n" + dev2_html + "\n\n        "
        new_content = content[:start_idx] + dev1_html + "\n\n        " + dev2_html + "\n\n        " + content[end_idx:]
        
        # update the comments inside the dev blocks to reflect their new position
        new_content = new_content.replace('<!-- 左侧设备：情况B 签约界面 -->', '<!-- 右侧设备：情况B 签约界面 -->')
        new_content = new_content.replace('<!-- 右侧设备：全局系统弹窗模拟 -->', '<!-- 左侧设备：全局系统弹窗模拟 -->')
        
        # Update annotations text
        new_content = new_content.replace('① 【场景 1：全局弹窗拦截】(对应右侧设备)', '① 【场景 1：全局弹窗拦截】(对应左侧设备)')
        new_content = new_content.replace('② 【场景 2：签约表单嵌入】(对应左侧设备)', '② 【场景 2：签约表单嵌入】(对应右侧设备)')
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Devices swapped.")
    else:
        print("Indices not found.")
else:
    print("Match failed.")
