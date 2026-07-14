import re

html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Change "成长体系与AI中台" to "成长体系"
content = content.replace('<span class="font-bold text-gray-800">成长体系与AI中台</span>', '<span class="font-bold text-gray-800">成长体系</span>')

# Add "生态巡航分析智能体" independent menu at the end of the sidebar
ai_menu = """
                <!-- 生态巡航分析智能体 -->
                <a class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors menu-link hover:bg-gray-50 text-gray-800 font-bold" onclick="alert('即将打开AI悬浮面板')">
                    <span>生态巡航分析智能体</span>
                    <i class="fas fa-robot text-xs text-blue-500"></i>
                </a>
"""
content = re.sub(r'(<!-- 成长体系.*?</div>\s*</div>)', r'\1' + '\n' + ai_menu, content, flags=re.DOTALL)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)
