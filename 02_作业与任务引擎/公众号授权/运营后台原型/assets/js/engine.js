// 护卫军原型引擎 (含跨帧通信与在线编辑功能)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEngine);
} else {
    initEngine();
}

function initEngine() {
    // ==========================================
    // 1. 作为子页面（或者独立页面），绑定图钉事件
    // ==========================================
    const pins = document.querySelectorAll('.pm-pin');
    pins.forEach(pin => {
        pin.addEventListener('click', (e) => {
            e.stopPropagation();
            const annotationKey = pin.getAttribute('data-key');
            const pinNum = pin.getAttribute('data-num');
            
            if (typeof PRD_ANNOTATIONS === 'undefined') {
                alert('批注数据尚未加载，请检查 annotations.js 是否被正确引入');
                return;
            }
            let data = PRD_ANNOTATIONS[annotationKey];
            if(!data) {
                alert('未找到对应的批注数据：' + annotationKey);
                return;
            }

            // 读取本地修改覆盖 (用于静态模式)
            const localDataStr = localStorage.getItem('PM_PIN_MODIFIED_' + annotationKey);
            if (localDataStr) {
                try {
                    const localData = JSON.parse(localDataStr);
                    data = Object.assign({}, data, localData);
                } catch(e){}
            }

            const rect = pin.getBoundingClientRect();
            
            if (window.parent && window.parent !== window) {
                window.parent.postMessage({
                    type: 'PM_ENGINE_OPEN_MODAL',
                    key: annotationKey,
                    num: pinNum,
                    data: data,
                    rect: {
                        top: rect.top,
                        bottom: rect.bottom,
                        left: rect.left
                    },
                    scrollY: window.scrollY,
                    scrollX: window.scrollX
                }, '*');
            } else {
                renderPinModal(annotationKey, pinNum, data, rect.top, rect.bottom, rect.left, window.scrollY, window.scrollX, 0, 0);
            }
        });
    });

    // 绑定点击空白处关闭
    document.addEventListener('click', (e) => {
        const popover = document.getElementById('pin-popover');
        // 编辑模式下点击外部不关闭，防止误触丢失数据
        if (popover && popover.classList.contains('active') && !popover.classList.contains('edit-mode') && !popover.contains(e.target)) {
            closePinModal();
            if (window.parent && window.parent !== window) {
                window.parent.postMessage({ type: 'PM_ENGINE_CLOSE_MODAL' }, '*');
            }
        }
    });

    // ==========================================
    // 2. 作为父级页面，监听 iframe 的呼叫
    // ==========================================
    window.addEventListener('message', (e) => {
        if (!e.data) return;
        if (e.data.type === 'PM_ENGINE_OPEN_MODAL') {
            let frameOffsetX = 0;
            let frameOffsetY = 0;
            const iframes = document.getElementsByTagName('iframe');
            for(let i = 0; i < iframes.length; i++) {
                if(iframes[i].contentWindow === e.source) {
                    const fRect = iframes[i].getBoundingClientRect();
                    frameOffsetX = fRect.left;
                    frameOffsetY = fRect.top;
                    break;
                }
            }
            renderPinModal(e.data.key, e.data.num, e.data.data, e.data.rect.top, e.data.rect.bottom, e.data.rect.left, e.data.scrollY, e.data.scrollX, frameOffsetX, frameOffsetY);
        } else if (e.data.type === 'PM_ENGINE_CLOSE_MODAL') {
            closePinModal();
        }
    });
}

function renderPinModal(key, num, data, pinTop, pinBottom, pinLeft, childScrollY, childScrollX, frameOffsetX, frameOffsetY) {
    let popover = document.getElementById('pin-popover');
    if (!popover) {
        const html = `
            <div id="pin-popover" class="pin-popover" style="position: absolute; z-index: 99999;">
                <div class="pin-modal-header" id="pin-popover-header">
                    <h3><span id="pin-modal-num" class="pin-num-badge"></span> <span id="pin-modal-title"></span></h3>
                    <div class="pin-header-actions">
                        <i class="fas fa-copy icon-btn" title="复制Markdown" onclick="window.pmEngineCopyMarkdown()"></i>
                        <i class="fas fa-edit icon-btn" title="编辑" onclick="window.pmEngineEnterEdit()"></i>
                        <span class="close-btn" onclick="closePinModal()" title="关闭">&times;</span>
                    </div>
                </div>
                
                <!-- 展示层 -->
                <div id="pin-view-layer" class="pin-modal-body" style="padding: 16px; font-size: 13px; line-height: 1.5; color: #475569; display: flex; flex-direction: column; gap: 12px; max-height: 400px; overflow-y: auto;">
                    <div><label style="color:#94a3b8;font-weight:bold;display:block;margin-bottom:2px;font-size:12px;">功能定义</label><div id="pin-view-definition" style="color:#334155;"></div></div>
                    <div><label style="color:#94a3b8;font-weight:bold;display:block;margin-bottom:2px;font-size:12px;">数据来源</label><div id="pin-view-source" style="color:#334155;"></div></div>
                    <div><label style="color:#94a3b8;font-weight:bold;display:block;margin-bottom:2px;font-size:12px;">取值逻辑</label><div id="pin-view-logic" style="color:#334155;"></div></div>
                    <div><label style="color:#94a3b8;font-weight:bold;display:block;margin-bottom:2px;font-size:12px;">交互说明</label><div id="pin-view-interaction" style="color:#334155;"></div></div>
                    <div><label style="color:#94a3b8;font-weight:bold;display:block;margin-bottom:2px;font-size:12px;">字段说明</label><div id="pin-view-fields" style="color:#334155;"></div></div>
                </div>

                <!-- 密码鉴权层 -->
                <div id="pin-password-layer" class="pin-password-layer">
                    <div style="font-weight:bold; color:#1e293b; font-size:14px;">请输入编辑密码</div>
                    <div style="font-size:12px; color:#64748b;">为防止误操作，请进行身份验证</div>
                    <input type="password" id="pin-pwd-input" placeholder="输入密码" onkeydown="if(event.key==='Enter') window.pmEngineCheckPwd()">
                    <button onclick="window.pmEngineCheckPwd()">解锁并编辑</button>
                    <div id="pin-pwd-error" style="color:red; font-size:12px; display:none;">密码错误</div>
                    <div style="margin-top:8px; font-size:12px; color:#94a3b8; cursor:pointer;" onclick="window.pmEngineSwitchMode('view')">返回</div>
                </div>

                <!-- 编辑表单层 -->
                <div id="pin-edit-layer" class="pin-edit-layer">
                    <div class="pin-form-group">
                        <label>功能名称</label>
                        <input type="text" id="pin-edit-title">
                    </div>
                    <div class="pin-form-group">
                        <label>功能定义</label>
                        <textarea id="pin-edit-definition"></textarea>
                    </div>
                    <div class="pin-form-group">
                        <label>数据来源</label>
                        <textarea id="pin-edit-source"></textarea>
                    </div>
                    <div class="pin-form-group">
                        <label>取值逻辑</label>
                        <textarea id="pin-edit-logic"></textarea>
                    </div>
                    <div class="pin-form-group">
                        <label>交互说明</label>
                        <textarea id="pin-edit-interaction"></textarea>
                    </div>
                    <div class="pin-form-group">
                        <label>字段说明</label>
                        <textarea id="pin-edit-fields"></textarea>
                    </div>
                    <div class="pin-form-actions">
                        <button class="pin-btn default" onclick="window.pmEngineSwitchMode('view')">取消</button>
                        <button class="pin-btn primary" onclick="window.pmEngineSave()">保存并同步</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', html);
        popover = document.getElementById('pin-popover');
        
        dragElement(popover, document);
        popover.addEventListener('click', e => e.stopPropagation());
    }
    
    // 绑定当前数据到全局对象，方便各类操作
    window.currentPinData = { key, num, ...data };
    
    // 更新展示层内容
    document.getElementById('pin-modal-num').innerText = num;
    document.getElementById('pin-modal-title').innerText = data.title || '-';
    document.getElementById('pin-view-definition').innerText = data.definition || '-';
    document.getElementById('pin-view-source').innerText = data.dataSource || '-';
    document.getElementById('pin-view-logic').innerText = data.logic || '-';
    document.getElementById('pin-view-interaction').innerText = data.interaction || '-';
    document.getElementById('pin-view-fields').innerText = data.fields || '-';
    
    // 初始化返回展示模式
    window.pmEngineSwitchMode('view');
    popover.classList.add('active');
    
    const popoverHeight = popover.offsetHeight || 250;
    const popoverWidth = popover.offsetWidth || 320;
    
    let topPos = pinBottom + childScrollY + frameOffsetY + 10;
    let leftPos = pinLeft + childScrollX + frameOffsetX;
    
    if (topPos + popoverHeight + 20 > window.innerHeight) {
        if (pinTop + frameOffsetY > popoverHeight + 20) {
            topPos = pinTop + childScrollY + frameOffsetY - popoverHeight - 10;
        }
    }
    
    if (leftPos + popoverWidth + 20 > window.innerWidth) {
        leftPos = window.innerWidth - popoverWidth - 20;
    }
    if (leftPos < 10) leftPos = 10;
    
    popover.style.top = topPos + 'px';
    popover.style.left = leftPos + 'px';
}

function closePinModal() {
    const popover = document.getElementById('pin-popover');
    if (popover) popover.classList.remove('active');
}

// ---------------- 模式切换逻辑 ----------------
window.pmEngineSwitchMode = function(mode) {
    const popover = document.getElementById('pin-popover');
    const viewLayer = document.getElementById('pin-view-layer');
    const pwdLayer = document.getElementById('pin-password-layer');
    const editLayer = document.getElementById('pin-edit-layer');
    
    if (mode === 'edit') {
        popover.classList.add('edit-mode');
        viewLayer.style.display = 'none';
        pwdLayer.style.display = 'none';
        editLayer.style.display = 'flex';
        
        // 填入数据
        const d = window.currentPinData;
        document.getElementById('pin-edit-title').value = d.title || '';
        document.getElementById('pin-edit-definition').value = d.definition || '';
        document.getElementById('pin-edit-source').value = d.dataSource || '';
        document.getElementById('pin-edit-logic').value = d.logic || '';
        document.getElementById('pin-edit-interaction').value = d.interaction || '';
        document.getElementById('pin-edit-fields').value = d.fields || '';
    } 
    else if (mode === 'pwd') {
        popover.classList.remove('edit-mode');
        viewLayer.style.display = 'none';
        pwdLayer.style.display = 'flex';
        editLayer.style.display = 'none';
        document.getElementById('pin-pwd-error').style.display = 'none';
        document.getElementById('pin-pwd-input').value = '';
        setTimeout(() => document.getElementById('pin-pwd-input').focus(), 100);
    } 
    else {
        // view mode
        popover.classList.remove('edit-mode');
        viewLayer.style.display = 'flex';
        pwdLayer.style.display = 'none';
        editLayer.style.display = 'none';
    }
};

window.pmEngineEnterEdit = function() {
    // 检查 Session 授权状态
    if (sessionStorage.getItem('pm_engine_auth') === 'true') {
        window.pmEngineSwitchMode('edit');
    } else {
        window.pmEngineSwitchMode('pwd');
    }
};

window.pmEngineCheckPwd = function() {
    const pwd = document.getElementById('pin-pwd-input').value;
    const targetPwd = window.EDIT_PASSWORD || 'rondo';
    if (pwd === targetPwd) {
        sessionStorage.setItem('pm_engine_auth', 'true');
        window.pmEngineSwitchMode('edit');
    } else {
        document.getElementById('pin-pwd-error').style.display = 'block';
    }
};

window.pmEngineSave = async function() {
    const key = window.currentPinData.key;
    const newData = {
        title: document.getElementById('pin-edit-title').value,
        definition: document.getElementById('pin-edit-definition').value,
        dataSource: document.getElementById('pin-edit-source').value,
        logic: document.getElementById('pin-edit-logic').value,
        interaction: document.getElementById('pin-edit-interaction').value,
        fields: document.getElementById('pin-edit-fields').value
    };
    
    const btn = document.querySelector('.pin-form-actions .primary');
    const oldText = btn.innerText;
    btn.innerText = '同步中...';
    btn.disabled = true;

    try {
        // 尝试向本地 server.py 发送同步请求
        const res = await fetch('/api/update_pin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, data: newData })
        });
        
        if (res.ok) {
            alert('同步成功！本地 MD 源文件已更新。请手动刷新子页面查看最新效果。');
            
            // 更新当前面板展示
            Object.assign(window.currentPinData, newData);
            document.getElementById('pin-modal-title').innerText = newData.title;
            document.getElementById('pin-view-definition').innerText = newData.definition;
            document.getElementById('pin-view-source').innerText = newData.dataSource;
            document.getElementById('pin-view-logic').innerText = newData.logic;
            document.getElementById('pin-view-interaction').innerText = newData.interaction;
            document.getElementById('pin-view-fields').innerText = newData.fields;
            
            window.pmEngineSwitchMode('view');
        } else {
            throw new Error('API return not ok');
        }
    } catch (e) {
        // 后端失败 (比如静态部署环境)
        console.warn('API Sync Failed, fallback to local storage', e);
        localStorage.setItem('PM_PIN_MODIFIED_' + key, JSON.stringify(newData));
        alert('线上静态环境无法写回文件，已暂存在您的浏览器中。请点击顶部的【复制Markdown】手动写回原文件。');
        
        Object.assign(window.currentPinData, newData);
        document.getElementById('pin-modal-title').innerText = newData.title;
        document.getElementById('pin-view-definition').innerText = newData.definition;
        document.getElementById('pin-view-source').innerText = newData.dataSource;
        document.getElementById('pin-view-logic').innerText = newData.logic;
        document.getElementById('pin-view-interaction').innerText = newData.interaction;
        document.getElementById('pin-view-fields').innerText = newData.fields;
        
        window.pmEngineSwitchMode('view');
    } finally {
        btn.innerText = oldText;
        btn.disabled = false;
    }
};

window.pmEngineCopyMarkdown = function() {
    const d = window.currentPinData;
    const md = `### 📍 图钉批注：[${d.key}]\n` +
               `- **功能名称**：${d.title || ''}\n` +
               `- **功能定义**：${d.definition || ''}\n` +
               `- **数据来源**：${d.dataSource || ''}\n` +
               `- **取值逻辑**：${d.logic || ''}\n` +
               `- **交互说明**：${d.interaction || ''}\n` +
               `- **字段说明**：${d.fields || ''}\n`;
               
    navigator.clipboard.writeText(md).then(() => {
        alert('Markdown 已复制到剪贴板！');
    }).catch(err => {
        alert('复制失败，请手动选择复制：\n\n' + md);
    });
};

// 拖拽逻辑保持纯净
function dragElement(elmnt, targetDoc) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    const header = targetDoc.getElementById(elmnt.id + "-header");
    if (header) {
        header.onmousedown = dragMouseDown;
    } else {
        elmnt.onmousedown = dragMouseDown;
    }

    function dragMouseDown(e) {
        const win = targetDoc.defaultView || window;
        e = e || win.event;
        if(e.target.classList.contains('close-btn') || e.target.classList.contains('icon-btn')) return;
        
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        targetDoc.onmouseup = closeDragElement;
        targetDoc.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        const win = targetDoc.defaultView || window;
        e = e || win.event;
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
        elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
    }

    function closeDragElement() {
        targetDoc.onmouseup = null;
        targetDoc.onmousemove = null;
    }
}
