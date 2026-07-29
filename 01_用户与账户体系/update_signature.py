import re

file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update onclick in buttons
content = content.replace('onclick="agreeInnerModal()"', 'onclick="openSignatureInner()"')
content = content.replace('onclick="agreeGlobalModal()"', 'onclick="openSignatureGlobal()"')

# 2. Inject HTML for SignatureModalInner
inner_html = """
        <!-- 内部弹窗：保密承诺书（签约表单用，底部抽屉） -->"""
signature_html_inner = """
        <!-- 签名画板 (情况B 签约表单) -->
        <div id="signatureModalInner" class="absolute inset-0 bg-white z-[60] hidden flex-col slide-up">
            <div class="px-4 py-3 flex items-center justify-between border-b border-gray-100 bg-white shrink-0 pt-12">
                <div class="flex items-center gap-4 text-gray-700">
                    <i class="fas fa-chevron-left text-xl cursor-pointer" onclick="closeSignatureInner()"></i>
                    <i class="fas fa-home text-lg"></i>
                </div>
                <h3 class="font-bold text-gray-800 text-[17px]">手写签名</h3>
                <div class="flex items-center gap-3 border border-gray-200 rounded-full px-3 py-1 text-gray-600 text-sm">
                    <i class="fas fa-ellipsis-h"></i>
                    <div class="w-px h-3 bg-gray-200"></div>
                    <i class="far fa-dot-circle"></i>
                </div>
            </div>
            <div class="flex-1 p-5 flex flex-col relative bg-white">
                <div class="flex-1 border border-dashed border-gray-300 rounded relative overflow-hidden bg-white" style="touch-action: none;">
                    <canvas id="sigCanvasInner" class="absolute inset-0 w-full h-full cursor-crosshair"></canvas>
                    <div id="sigPlaceholderInner" class="absolute inset-0 pointer-events-none flex items-center justify-center">
                        <span class="text-4xl font-bold tracking-[0.2em] text-gray-100 rotate-[-15deg] select-none">请在此处签名</span>
                    </div>
                </div>
            </div>
            <div class="px-5 pb-8 pt-4 flex gap-4 bg-white shrink-0">
                <button onclick="clearSignatureInner()" class="flex-1 bg-white border border-gray-300 text-gray-600 font-medium py-3 rounded-lg text-sm hover:bg-gray-50 transition">清空</button>
                <button onclick="confirmSignatureInner()" class="flex-[1.5] bg-[#2196F3] text-white font-medium py-3 rounded-lg text-sm shadow-md transition hover:bg-blue-600">签名确认</button>
            </div>
        </div>
        
        <!-- 内部弹窗：保密承诺书（签约表单用，底部抽屉） -->"""
content = content.replace(inner_html, signature_html_inner)

# 3. Inject HTML for SignatureModalGlobal
global_html = """
        <!-- 全局弹窗遮罩层（限制在手机壳内部） -->"""
signature_html_global = """
        <!-- 签名画板 (情况A 全局阻断) -->
        <div id="signatureModalGlobal" class="absolute inset-0 bg-white z-[60] hidden flex-col slide-up">
            <div class="px-4 py-3 flex items-center justify-between border-b border-gray-100 bg-white shrink-0 pt-12">
                <div class="flex items-center gap-4 text-gray-700">
                    <i class="fas fa-chevron-left text-xl cursor-pointer" onclick="closeSignatureGlobal()"></i>
                    <i class="fas fa-home text-lg"></i>
                </div>
                <h3 class="font-bold text-gray-800 text-[17px]">手写签名</h3>
                <div class="flex items-center gap-3 border border-gray-200 rounded-full px-3 py-1 text-gray-600 text-sm">
                    <i class="fas fa-ellipsis-h"></i>
                    <div class="w-px h-3 bg-gray-200"></div>
                    <i class="far fa-dot-circle"></i>
                </div>
            </div>
            <div class="flex-1 p-5 flex flex-col relative bg-white">
                <div class="flex-1 border border-dashed border-gray-300 rounded relative overflow-hidden bg-white" style="touch-action: none;">
                    <canvas id="sigCanvasGlobal" class="absolute inset-0 w-full h-full cursor-crosshair"></canvas>
                    <div id="sigPlaceholderGlobal" class="absolute inset-0 pointer-events-none flex items-center justify-center">
                        <span class="text-4xl font-bold tracking-[0.2em] text-gray-100 rotate-[-15deg] select-none">请在此处签名</span>
                    </div>
                </div>
            </div>
            <div class="px-5 pb-8 pt-4 flex gap-4 bg-white shrink-0">
                <button onclick="clearSignatureGlobal()" class="flex-1 bg-white border border-gray-300 text-gray-600 font-medium py-3 rounded-lg text-sm hover:bg-gray-50 transition">清空</button>
                <button onclick="confirmSignatureGlobal()" class="flex-[1.5] bg-[#2196F3] text-white font-medium py-3 rounded-lg text-sm shadow-md transition hover:bg-blue-600">签名确认</button>
            </div>
        </div>
        
        <!-- 全局弹窗遮罩层（限制在手机壳内部） -->"""
content = content.replace(global_html, signature_html_global)

# 4. Replace JS agree logic and add Canvas logic
js_to_replace = """        function agreeInnerModal() {
            closeInnerModal();
            checkbox.checked = true; // 自动勾选
            updateBtnState();
        }"""
new_js_inner = """        // function agreeInnerModal is replaced by openSignatureInner
        function openSignatureInner() {
            closeInnerModal();
            const modal = document.getElementById('signatureModalInner');
            modal.classList.remove('hidden');
            if (!window.sigPadInner) {
                window.sigPadInner = new SignaturePad('sigCanvasInner', 'sigPlaceholderInner');
            } else {
                window.sigPadInner.resize();
            }
        }
        function closeSignatureInner() {
            document.getElementById('signatureModalInner').classList.add('hidden');
            document.getElementById('innerAgreementModal').classList.remove('hidden');
        }
        function confirmSignatureInner() {
            if (window.sigPadInner.isEmpty()) {
                showToast('请先完成手写签名');
                return;
            }
            document.getElementById('signatureModalInner').classList.add('hidden');
            checkbox.checked = true;
            updateBtnState();
            showToast('签署成功！');
        }
        function clearSignatureInner() {
            window.sigPadInner.clear();
        }"""
content = content.replace(js_to_replace, new_js_inner)


js_to_replace_global = """        // 假装同意
        function agreeGlobalModal() {
            globalModalOverlay.classList.add('hidden');
            blockedState.classList.add('hidden');
            // 移除主页的模糊效果，假装正常使用
            homeContent.querySelectorAll('.task-card').forEach(el => el.classList.remove('blur-[3px]'));
            showToast('签署成功！您现在可以正常访问护卫军系统了。');
        }"""
new_js_global = """        // function agreeGlobalModal is replaced by openSignatureGlobal
        function openSignatureGlobal() {
            globalModalOverlay.classList.add('hidden');
            const modal = document.getElementById('signatureModalGlobal');
            modal.classList.remove('hidden');
            if (!window.sigPadGlobal) {
                window.sigPadGlobal = new SignaturePad('sigCanvasGlobal', 'sigPlaceholderGlobal');
            } else {
                window.sigPadGlobal.resize();
            }
        }
        function closeSignatureGlobal() {
            document.getElementById('signatureModalGlobal').classList.add('hidden');
            globalModalOverlay.classList.remove('hidden');
        }
        function confirmSignatureGlobal() {
            if (window.sigPadGlobal.isEmpty()) {
                showToast('请先完成手写签名');
                return;
            }
            document.getElementById('signatureModalGlobal').classList.add('hidden');
            blockedState.classList.add('hidden');
            homeContent.querySelectorAll('.task-card').forEach(el => el.classList.remove('blur-[3px]'));
            showToast('签署成功！您现在可以正常访问护卫军系统了。');
        }
        function clearSignatureGlobal() {
            window.sigPadGlobal.clear();
        }"""
content = content.replace(js_to_replace_global, new_js_global)


# 5. Inject SignaturePad class at the top of script tag
script_tag = "<script>"
signature_class = """<script>
        // ======= Signature Pad 绘图类 =======
        class SignaturePad {
            constructor(canvasId, placeholderId) {
                this.canvas = document.getElementById(canvasId);
                this.ctx = this.canvas.getContext('2d');
                this.placeholder = document.getElementById(placeholderId);
                this.isDrawing = false;
                this.hasDrawn = false;
                
                this.resize();
                window.addEventListener('resize', () => this.resize());
                
                this.bindEvents();
            }
            
            resize() {
                const rect = this.canvas.parentElement.getBoundingClientRect();
                this.canvas.width = rect.width;
                this.canvas.height = rect.height;
                this.ctx.lineWidth = 4;
                this.ctx.lineCap = 'round';
                this.ctx.lineJoin = 'round';
                this.ctx.strokeStyle = '#000000';
            }
            
            bindEvents() {
                const getPos = (e) => {
                    const rect = this.canvas.getBoundingClientRect();
                    let clientX, clientY;
                    if (e.touches && e.touches.length > 0) {
                        clientX = e.touches[0].clientX;
                        clientY = e.touches[0].clientY;
                    } else {
                        clientX = e.clientX;
                        clientY = e.clientY;
                    }
                    return { x: clientX - rect.left, y: clientY - rect.top };
                };

                const start = (e) => {
                    e.preventDefault();
                    this.isDrawing = true;
                    this.hasDrawn = true;
                    if (this.placeholder) this.placeholder.style.display = 'none';
                    const pos = getPos(e);
                    this.ctx.beginPath();
                    this.ctx.moveTo(pos.x, pos.y);
                };

                const draw = (e) => {
                    e.preventDefault();
                    if (!this.isDrawing) return;
                    const pos = getPos(e);
                    this.ctx.lineTo(pos.x, pos.y);
                    this.ctx.stroke();
                };

                const end = (e) => {
                    e.preventDefault();
                    if (this.isDrawing) {
                        this.ctx.closePath();
                        this.isDrawing = false;
                    }
                };

                this.canvas.addEventListener('mousedown', start);
                this.canvas.addEventListener('mousemove', draw);
                this.canvas.addEventListener('mouseup', end);
                this.canvas.addEventListener('mouseout', end);

                this.canvas.addEventListener('touchstart', start, {passive: false});
                this.canvas.addEventListener('touchmove', draw, {passive: false});
                this.canvas.addEventListener('touchend', end);
            }
            
            clear() {
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                this.hasDrawn = false;
                if (this.placeholder) this.placeholder.style.display = 'flex';
            }
            
            isEmpty() { return !this.hasDrawn; }
        }
"""
content = content.replace(script_tag, signature_class, 1)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Modification complete.")
