import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Annotations
old_annotation_2 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-blue-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">【场景 2：签约表单嵌入】</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>情况B（走签约界面，未匹配到手机号的新用户）。</p>
            <p class="text-sm text-gray-600"><strong>交互说明：</strong>在原有的《用户协议》旁新增《保密承诺书》。当用户点击单选框或协议文本时，弹出协议正文。用户在正文内点击“同意”后，单选框自动勾选上，方可点击“立即签约”。</p>
        </div>"""

new_annotation_2 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-blue-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">【场景 2：签约表单嵌入】(对应左侧设备)</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>情况B（走签约表单界面，未匹配到手机号的新用户）。</p>
            <p class="text-sm text-gray-600 mb-2"><strong>触发时机：</strong>用户在新注册填表时触发。</p>
            <p class="text-sm text-gray-600"><strong>交互与功能说明：</strong><br>1. 用户点击“同意协议”单选框时，从底部弹出协议正文。<br>2. 物理滑动到底部后解锁“同意”按钮。<br>3. 点击“同意”后划出手写签名区。<br>4. <strong>（前端交互）</strong>在签名区点击“返回”，会直接收起所有弹窗，回到填写表单页面。<br>5. <strong>（后端联动）</strong>签名确认后，单选框自动勾选，允许点击“立即签约”。点击签约时提交表单数据并<strong>保存签字图片</strong>。</p>
        </div>"""
content = content.replace(old_annotation_2, new_annotation_2)

old_annotation_1 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-red-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">【场景 1：全局弹窗拦截】</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>老用户、以及情况A（匹配成功自动签约的新用户）。</p>
            <p class="text-sm text-gray-600"><strong>微信 H5 无退出概念的阻断方案：</strong><br>1. 进入首页时直接被弹窗遮罩。<br>2. 若点击“暂不同意”，弹出二次挽留。<br>3. 若坚持不同意，则收起弹窗，但页面变为<strong>“权限锁定（空状态）”</strong>，只保留重新唤起协议的按钮，实现物理隔绝，防止看到首页敏感作业。</p>
        </div>"""

new_annotation_1 = """<div class="bg-white p-6 rounded-xl shadow-sm border-l-4 border-red-500">
            <h3 class="text-lg font-bold text-gray-800 mb-2">【场景 1：全局弹窗拦截】(对应右侧设备)</h3>
            <p class="text-sm text-gray-600 mb-2"><strong>适用对象：</strong>老用户、以及情况A（匹配成功自动签约的新用户）。</p>
            <p class="text-sm text-gray-600 mb-2"><strong>触发逻辑（开发注意）：</strong>判断用户进入护卫军前端<strong>任何页面</strong>，接口返回若 `签字状态 = 未签`，则强制全局弹出此阻断协议。</p>
            <p class="text-sm text-gray-600"><strong>交互与功能说明：</strong><br>1. 滑动到底部解锁同意并唤起手写签名。<br>2. <strong>（后端联动）</strong>签名完成后，更新用户状态为“已签”，并<strong>保存签字图片存根</strong>，解锁页面遮罩。<br>3. 若坚持点击“不同意”，页面变为权限锁定空状态，防止物理看到敏感作业。</p>
        </div>"""
content = content.replace(old_annotation_1, new_annotation_1)

# 2. Update JS closeSignatureInner
js_close_inner_old = """        function closeSignatureInner() {
            document.getElementById('signatureModalInner').classList.add('hidden');
            document.getElementById('innerAgreementModal').classList.remove('hidden');
        }"""
js_close_inner_new = """        function closeSignatureInner() {
            // 左边场景：点击返回，直接跳回到填写表单页面（隐藏签名板和协议弹窗）
            document.getElementById('signatureModalInner').classList.add('hidden');
            document.getElementById('innerAgreementModal').classList.add('hidden');
            // 取消 checkbox 勾选状态（因为没有完成签名）
            checkbox.checked = false;
            updateBtnState();
        }"""
content = content.replace(js_close_inner_old, js_close_inner_new)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated HTML annotations and JS logic")
