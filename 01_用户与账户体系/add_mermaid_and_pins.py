import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Mermaid JS to head
mermaid_script = """
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({startOnLoad:true});</script>
</head>"""
if "mermaid.min.js" not in content:
    content = content.replace("</head>", mermaid_script)

# 2. Add Mermaid diagram container at the bottom before </body>
mermaid_html = """
    <!-- 时序图区域 -->
    <div class="w-full mt-4 bg-white p-8 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-xl font-bold text-gray-800 mb-6 flex items-center gap-2">
            <i class="fas fa-project-diagram text-[#C60024]"></i> 后端交互时序图 (供研发参考)
        </h3>
        <div class="mermaid flex justify-center">
sequenceDiagram
    participant U as 用户 (C端前端)
    participant S as 服务端 (Backend)

    Note over U, S: 全局拦截逻辑 (如进入任意页面时)
    U->>S: 访问前端系统 (获取用户 Token/状态)
    S-->>U: 返回用户信息 (包含 is_signed 签字状态)
    
    alt is_signed == false (未签状态)
        U->>U: 强制弹出【保密协议】遮罩层
        U->>U: 物理滑动到底部，解锁同意按钮
        U->>U: 点击“同意并继续” -> 弹出【手写签名画板】
        
        opt 用户中断 (点击返回)
            U->>U: 隐藏签名画板与协议弹窗，恢复阻断/空状态
        end
        
        U->>U: 在 Canvas 完成手写签名
        U->>U: 点击“签名确认” (前端校验画板非空)
        U->>S: 提交签约请求 (包含签字图片的 Base64/文件流)
        S->>S: 保存签字图片存根，更新用户状态为已签
        S-->>U: 返回签约成功
        U->>U: 解除全局弹窗与页面模糊遮罩，正常访问系统
    else is_signed == true (已签状态)
        U->>U: 正常渲染并进入业务页面
    end
        </div>
    </div>
"""
if "class=\"mermaid" not in content:
    content = content.replace("</body>", mermaid_html + "\n</body>")

# 3. Add pins to the device mockups
# Device 1 (Left, Scenario 2)
left_device_pin = """<div class="device-mockup bg-gray-50">
        <!-- 图钉批注：场景2 -->
        <div class="absolute -top-1 -left-1 bg-blue-500 text-white rounded-full w-10 h-10 flex items-center justify-center font-bold text-xl shadow-lg z-[100] border-4 border-gray-100 ring-2 ring-blue-500">2</div>"""
content = content.replace('<div class="device-mockup bg-gray-50">', left_device_pin, 1)

# Device 2 (Right, Scenario 1)
right_device_pin = """<div class="device-mockup bg-gray-50 relative">
        <!-- 图钉批注：场景1 -->
        <div class="absolute -top-1 -left-1 bg-red-500 text-white rounded-full w-10 h-10 flex items-center justify-center font-bold text-xl shadow-lg z-[100] border-4 border-gray-100 ring-2 ring-red-500">1</div>"""
content = content.replace('<div class="device-mockup bg-gray-50 relative">', right_device_pin, 1)


# Also add pin titles to annotations if not already clear
# We can prepend the numbers to the annotation titles
if "① 【场景 1" not in content:
    content = content.replace("【场景 1：全局弹窗拦截】", "① 【场景 1：全局弹窗拦截】")
    content = content.replace("【场景 2：签约表单嵌入】", "② 【场景 2：签约表单嵌入】")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Added mermaid diagram and pins.")
