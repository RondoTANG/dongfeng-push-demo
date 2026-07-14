import re

html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

nav_cards = """
        <!-- 原型导航卡片 -->
        <div style="display: flex; gap: 1rem; margin-bottom: 2rem;">
            <a href="dashboard.html" target="_blank" onclick="if(window.parent!==window){window.parent.location.hash='dashboard'; setTimeout(()=>window.parent.document.getElementById('pc-frame').contentWindow.switchPage('wechat', '公众号管理'), 100); return false;}" style="flex: 1; text-decoration: none; background: white; border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; display: block; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: all 0.2s ease;">
                <div style="font-weight: 600; color: var(--text-primary); font-size: 1.1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span style="background: #eef2ff; color: #4f46e5; padding: 0.3rem; border-radius: 6px; display:flex;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                    </span>
                    进入「公众号管理」原型
                </div>
                <p style="margin: 0; font-size: 0.9rem; color: var(--text-secondary);">对应 B 端管理后台的公众号授权、群发历史、文章元数据同步等功能演示。</p>
            </a>
            <a href="dashboard.html" target="_blank" onclick="if(window.parent!==window){window.parent.location.hash='dashboard'; setTimeout(()=>window.parent.document.getElementById('pc-frame').contentWindow.switchPage('jobs', '作业管理'), 100); return false;}" style="flex: 1; text-decoration: none; background: white; border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; display: block; box-shadow: 0 1px 3px rgba(0,0,0,0.05); transition: all 0.2s ease;">
                <div style="font-weight: 600; color: var(--text-primary); font-size: 1.1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span style="background: #fff7ed; color: #f97316; padding: 0.3rem; border-radius: 6px; display:flex;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                    </span>
                    进入「作业管理」原型
                </div>
                <p style="margin: 0; font-size: 0.9rem; color: var(--text-secondary);">对应 B 端管理后台的作业分发设置、公众号图文素材关联等功能演示。</p>
            </a>
        </div>
"""

# Avoid adding multiple times
if "进入「公众号管理」原型" not in content:
    content = content.replace('<!-- 1. 项目全景 -->', nav_cards + '\n        <!-- 1. 项目全景 -->')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)


md_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.md'
with open(md_path, 'r', encoding='utf-8') as f:
    md_content = f.read()

md_nav = """
> **💡 原型快速导航**
> * [进入「公众号管理」原型](dashboard.html) - B 端公众号授权与数据大盘
> * [进入「作业管理」原型](dashboard.html) - B 端作业分发与设置

"""

if "原型快速导航" not in md_content:
    md_content = md_content.replace('## 1. 项目全景 (V1.0)', md_nav + '## 1. 项目全景 (V1.0)')

with open(md_path, 'w', encoding='utf-8') as f:
    f.write(md_content)

