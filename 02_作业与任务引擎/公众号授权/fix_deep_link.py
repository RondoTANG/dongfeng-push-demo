import re

dashboard_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/dashboard.html'
index_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/index.html'
prd_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'

# 1. Update dashboard.html DOMContentLoaded
with open(dashboard_path, 'r', encoding='utf-8') as f:
    dashboard_content = f.read()

dashboard_new_init = """        document.addEventListener("DOMContentLoaded", () => {
            const initialPage = window.location.hash.replace('#', '') || 'wechat';
            const pageTitle = initialPage === 'jobs' ? '作业管理' : '公众号管理';
            switchPage(initialPage, pageTitle);
        });"""
dashboard_content = re.sub(r'document\.addEventListener\("DOMContentLoaded".*?\}\);', dashboard_new_init, dashboard_content, flags=re.DOTALL)

with open(dashboard_path, 'w', encoding='utf-8') as f:
    f.write(dashboard_content)

# 2. Update index.html switchTab function
with open(index_path, 'r', encoding='utf-8') as f:
    index_content = f.read()

index_new_switch = """        function switchTab(btn) {
            tabButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            let src = btn.getAttribute('data-src');
            
            // Deep link support for iframe
            const hashParts = window.location.hash.replace('#', '').split('/');
            if (hashParts.length > 1 && btn.id === 'tab-' + hashParts[0]) {
                src += '#' + hashParts[1];
            }

            pcFrame.src = src;
            
            // 更新 URL Hash
            const hash = btn.id.replace('tab-', '');
            if (hashParts.length > 1 && hashParts[0] === hash) {
                window.location.hash = hash + '/' + hashParts[1];
            } else {
                window.location.hash = hash;
            }
        }"""
index_content = re.sub(r'function switchTab\(btn\).*?window\.location\.hash = hash;\n        }', index_new_switch, index_content, flags=re.DOTALL)

# Handle hash route parsing
index_new_handle = """        function handleHashRoute() {
            const hashParts = window.location.hash.replace('#', '').split('/');
            const mainHash = hashParts[0];
            if (mainHash) {
                const targetTab = document.getElementById('tab-' + mainHash);
                if (targetTab) {
                    switchTab(targetTab);
                }
            }
        }"""
index_content = re.sub(r'function handleHashRoute\(\).*?\}\n        \}', index_new_handle, index_content, flags=re.DOTALL)

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(index_content)

# 3. Update technical_prd.html links
with open(prd_path, 'r', encoding='utf-8') as f:
    prd_content = f.read()

prd_content = prd_content.replace(
    "onclick=\"if(window.parent!==window){window.parent.location.hash='dashboard'; setTimeout(()=>window.parent.document.getElementById('pc-frame').contentWindow.switchPage('wechat', '公众号管理'), 100); return false;}\"",
    "onclick=\"if(window.parent!==window){window.parent.location.hash='dashboard/wechat'; return false;}\""
)

prd_content = prd_content.replace(
    "onclick=\"if(window.parent!==window){window.parent.location.hash='dashboard'; setTimeout(()=>window.parent.document.getElementById('pc-frame').contentWindow.switchPage('jobs', '作业管理'), 100); return false;}\"",
    "onclick=\"if(window.parent!==window){window.parent.location.hash='dashboard/jobs'; return false;}\""
)

with open(prd_path, 'w', encoding='utf-8') as f:
    f.write(prd_content)

