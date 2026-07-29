import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix head div error and add title
content = content.replace("    <script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\"></script>\n    </div>\n\n    <script>mermaid.initialize({startOnLoad:true});</script>\n</head>", 
                          "    <title>护卫军用户新增保密承诺书签字功能说明</title>\n    <script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\"></script>\n    <script>mermaid.initialize({startOnLoad:true});</script>\n</head>")

# 2. Add visual Header at the very top of body
if "护卫军用户新增保密承诺书签字功能说明</h1>" not in content:
    header_html = """
    <!-- 页面大标题 -->
    <div class="w-full text-center mb-4">
        <h1 class="text-3xl font-bold text-gray-800 tracking-tight">护卫军用户新增保密承诺书签字功能说明</h1>
        <p class="text-gray-500 mt-2">测试与开发验证基准原型 (涵盖场景判定、阻断交互、手写签名存根流转)</p>
    </div>
    """
    content = content.replace("<body class=\"bg-gray-100 min-h-screen flex items-center justify-center p-8 gap-12 font-sans flex-wrap\">\n", 
                              "<body class=\"bg-gray-100 min-h-screen flex items-center justify-center p-8 gap-12 font-sans flex-wrap\">\n" + header_html)


# 3. Replace Scenario 1 Description
old_scenario_1 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-red-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">① 【场景 1：全局弹窗拦截】(对应右侧设备)</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>老用户、以及情况A（匹配成功自动签约的新用户）。</p>
            <p class="text-sm text-gray-600 mb-2"><strong>触发逻辑（开发注意）：</strong>判断用户进入护卫军前端<strong>任何页面</strong>，接口返回若 `签字状态 = 未签`，则强制全局弹出此阻断协议。</p>
            <p class="text-sm text-gray-600"><strong>交互与功能说明：</strong><br>1. 滑动到底部解锁同意并唤起手写签名。<br>2. <strong>（后端联动）</strong>签名完成后，更新用户状态为“已签”，并<strong>保存签字图片存根</strong>，解锁页面遮罩。<br>3. 若坚持点击“不同意”，页面变为权限锁定空状态，防止物理看到敏感作业。</p>
        </div>"""

new_scenario_1 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-red-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">① 【场景 1：全局弹窗拦截】(对应右侧设备)</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>老用户、情况A（身份匹配自动签约的新用户）。</p>
            <p class="text-sm text-gray-600 mb-2"><strong>触发逻辑（研发与QA重点）：</strong>全局路由守卫拦截。只要接口返回 <code>is_signed = false</code>，进入前端<strong>任何路由/页面</strong>均强制弹窗。底层真实业务DOM进行 <code>blur</code> 高斯模糊处理，严防数据泄露。</p>
            <div class="text-sm text-gray-600 space-y-1">
                <strong>交互与测试流转说明：</strong>
                <ul class="list-decimal pl-4 space-y-1">
                    <li><strong>防误触/盲签：</strong>默认【同意并继续】按钮置灰，必须监听 <code>scroll</code> 触底事件后方可高亮解锁。</li>
                    <li><strong>唤起画板：</strong>点击解锁后的同意，划出手写签名区。</li>
                    <li><strong>签名校验测试：</strong>空白画布直接点提交，需Toast阻断提示“请先完成手写签名”。画线后点击“清空”，状态需重置为空白拦截状态。</li>
                    <li><strong>提交闭环：</strong>签名确认后，向后端提交 <code>Base64图片/流</code>。后端保存存根并修改状态 <code>is_signed=true</code>。前端收到成功回调后，销毁弹窗并解除底部页面的模糊遮罩。</li>
                    <li><strong>拒绝异常流：</strong>点击【暂不同意】出二次确认，执意拒绝则页面转为无权限空状态，彻底销毁/隐藏真实业务DOM。</li>
                </ul>
            </div>
        </div>"""
content = content.replace(old_scenario_1, new_scenario_1)


# 4. Replace Scenario 2 Description
old_scenario_2 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-blue-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">② 【场景 2：签约表单嵌入】(对应左侧设备)</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>情况B（走签约表单界面，未匹配到手机号的新用户）。</p>
            <p class="text-sm text-gray-600 mb-2"><strong>触发时机：</strong>用户在新注册填表时触发。</p>
            <p class="text-sm text-gray-600"><strong>交互与功能说明：</strong><br>1. 用户点击“同意协议”单选框时，从底部弹出协议正文。<br>2. 物理滑动到底部后解锁“同意”按钮。<br>3. 点击“同意”后划出手写签名区。<br>4. <strong>（前端交互）</strong>在签名区点击“返回”，会直接收起所有弹窗，回到填写表单页面。<br>5. <strong>（后端联动）</strong>签名确认后，单选框自动勾选，允许点击“立即签约”。点击签约时提交表单数据并<strong>保存签字图片</strong>。</p>
        </div>"""

new_scenario_2 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-blue-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">② 【场景 2：签约表单嵌入】(对应左侧设备)</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>情况B（需手填注册表单的新用户）。</p>
            <p class="text-sm text-gray-600 mb-2"><strong>触发时机：</strong>用户在新注册填表页底部勾选协议时触发。</p>
            <div class="text-sm text-gray-600 space-y-1">
                <strong>交互与测试流转说明：</strong>
                <ul class="list-decimal pl-4 space-y-1">
                    <li><strong>强阻断拉起：</strong>用户无法直接在表单页打勾。点击单选框或《保密承诺书》文本时，从底部弹出协议正文抽屉。</li>
                    <li><strong>滑动解锁：</strong>必须物理滑动协议抽屉内容到底部，【我已阅读并同意】按钮才会由灰变红。</li>
                    <li><strong>唤起画板：</strong>点击同意后，滑出手写签名区。</li>
                    <li><strong>中断重置测试：</strong>在签名区点击左上角“返回( < )”，需同时收起签名板和协议抽屉。表单页的单选框<strong>必须恢复为未勾选状态</strong>。</li>
                    <li><strong>提交闭环：</strong>签名确认（非空校验）后，收起弹窗，表单页的单选框变为<strong>已勾选状态</strong>（解锁“立即签约”大按钮）。最后点击签约时将表单数据与签名图片一同Submit给后端。</li>
                </ul>
            </div>
        </div>"""
content = content.replace(old_scenario_2, new_scenario_2)


with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated HTML with title and detailed QA descriptions")
