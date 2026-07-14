import re

html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Inject FontAwesome
if 'font-awesome' not in content:
    content = content.replace('</title>', '</title>\n    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">')

# 2. Replace the aside block
aside_pattern = re.compile(r'<!-- ================= Sidebar ================= -->.*?<!-- ================= Main Content ================= -->', re.DOTALL)

new_aside = """<!-- ================= Sidebar ================= -->
    <aside class="w-64 flex flex-col shrink-0 text-sm overflow-hidden select-none bg-white text-gray-600 border-r border-gray-200" id="org-sidebar">
        <div class="h-16 flex items-center px-6 bg-white border-b border-gray-100 shrink-0">
            <div class="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center text-white font-bold mr-3">东</div><span class="text-base font-bold tracking-wider text-gray-900">护卫军后台</span>
        </div>
        <div class="flex-1 overflow-y-auto pb-6 pt-2 space-y-1">
            <nav class="flex flex-col">

                <!-- 独立菜单: 数据大屏 -->
                <a class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors menu-link bg-blue-50 text-blue-600 font-bold" onclick="switchPage('dashboard', '数据大屏概览')" data-page="dashboard">
                    <span>数据大屏</span>
                </a>

                <!-- 作业管理 -->
                <div class="menu-group">
                    <div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu(this)">
                        <span class="font-bold text-gray-800">作业管理</span>
                        <i class="fas text-xs fa-chevron-up text-blue-600"></i>
                    </div>
                    <div class="flex flex-col pb-1 pt-1">
                        <a class="pl-10 pr-4 py-2.5 transition-colors menu-link hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer" onclick="switchPage('jobs', '作业管理')" data-page="jobs">新建作业</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">作业管理列表</a>
                    </div>
                </div>

                <!-- 审核管理 -->
                <div class="menu-group">
                    <div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu(this)">
                        <span class="font-bold text-gray-800">审核管理</span>
                        <i class="fas text-xs text-gray-400 fa-chevron-down"></i>
                    </div>
                    <div class="flex flex-col hidden pb-1 pt-1">
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">审核管理列表</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">人工审核</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors menu-link hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer" onclick="switchPage('audit', '任务审核')" data-page="audit">反馈审核列表</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">作业审核记录</a>
                    </div>
                </div>

                <!-- 用户管理 -->
                <div class="menu-group">
                    <div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu(this)">
                        <span class="font-bold text-gray-800">用户管理</span>
                        <i class="fas text-xs text-gray-400 fa-chevron-down"></i>
                    </div>
                    <div class="flex flex-col hidden pb-1 pt-1">
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">平台列表</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors menu-link hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer" onclick="switchPage('users', '用户与权限')" data-page="users">用户列表</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">员工列表</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">用户标签管理</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">人群包管理</a>
                    </div>
                </div>

                <!-- 内容管理 -->
                <div class="menu-group">
                    <div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu(this)">
                        <span class="font-bold text-gray-800">内容管理</span>
                        <i class="fas text-xs text-gray-400 fa-chevron-down"></i>
                    </div>
                    <div class="flex flex-col hidden pb-1 pt-1">
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">文章编辑</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">广告管理</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">作业素材管理</a>
                    </div>
                </div>

                <!-- 系统设置 -->
                <div class="menu-group">
                    <div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu(this)">
                        <span class="font-bold text-gray-800">系统设置</span>
                        <i class="fas text-xs fa-chevron-up text-blue-600"></i>
                    </div>
                    <div class="flex flex-col pb-1 pt-1">
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">系统日志</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">成长规则配置</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors menu-link hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer" onclick="switchPage('wechat', '公众号管理')" data-page="wechat">公众号管理</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">文章管理</a>
                    </div>
                </div>

                <!-- 统计分析 -->
                <div class="menu-group">
                    <div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu(this)">
                        <span class="font-bold text-gray-800">统计分析</span>
                        <i class="fas text-xs text-gray-400 fa-chevron-down"></i>
                    </div>
                    <div class="flex flex-col hidden pb-1 pt-1">
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">成长数据大盘</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">用户台账</a>
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">党委排名数据</a>
                    </div>
                </div>

                <!-- 成长体系与AI中台 -->
                <div class="menu-group">
                    <div class="flex items-center justify-between px-5 py-3 cursor-pointer transition-colors hover:bg-gray-50" onclick="toggleMenu(this)">
                        <span class="font-bold text-gray-800">成长体系与AI中台</span>
                        <i class="fas text-xs text-gray-400 fa-chevron-down"></i>
                    </div>
                    <div class="flex flex-col hidden pb-1 pt-1">
                        <a class="pl-10 pr-4 py-2.5 transition-colors hover:bg-gray-50 hover:text-blue-600 text-gray-600 cursor-pointer">体系规则配置</a>
                    </div>
                </div>

            </nav>
        </div>
    </aside>

    <!-- ================= Main Content ================= -->"""

content = aside_pattern.sub(new_aside, content)

# 3. Add toggleMenu function and modify switchPage function
js_additions = """
        function toggleMenu(header) {
            const submenu = header.nextElementSibling;
            const icon = header.querySelector('i');
            const isHidden = submenu.classList.contains('hidden');
            if (isHidden) {
                submenu.classList.remove('hidden');
                if (icon) {
                    icon.classList.remove('fa-chevron-down', 'text-gray-400');
                    icon.classList.add('fa-chevron-up', 'text-blue-600');
                }
            } else {
                submenu.classList.add('hidden');
                if (icon) {
                    icon.classList.remove('fa-chevron-up', 'text-blue-600');
                    icon.classList.add('fa-chevron-down', 'text-gray-400');
                }
            }
        }

        function switchPage(pageId, title) {
            // Update active states
            document.querySelectorAll('.menu-link').forEach(el => {
                el.classList.remove('bg-blue-50', 'text-blue-600', 'font-medium', 'font-bold');
                
                // For top level independent menu
                if(el.parentElement.tagName === 'NAV') {
                    el.classList.add('text-gray-800', 'font-bold');
                } else {
                    // For submenus
                    el.classList.add('text-gray-600');
                }
            });

            const activeLink = document.querySelector(`.menu-link[data-page="${pageId}"]`);
            if (activeLink) {
                if(activeLink.parentElement.tagName === 'NAV') {
                    // Top level
                    activeLink.classList.remove('text-gray-800');
                    activeLink.classList.add('bg-blue-50', 'text-blue-600', 'font-bold');
                } else {
                    // Sub menu
                    activeLink.classList.remove('text-gray-600');
                    activeLink.classList.add('bg-blue-50', 'text-blue-600', 'font-medium');
                }
            }
            
            document.getElementById('topBarTitle').textContent = title;
            document.querySelectorAll('.page-section').forEach(el => el.classList.remove('active'));
            const page = document.getElementById(`page-${pageId}`);
            if (page) page.classList.add('active');
        }"""

switch_page_pattern = re.compile(r'function switchPage\(pageId, title\)\s*\{.*?(?=function switchInnerTab)', re.DOTALL)
content = switch_page_pattern.sub(js_additions + '\n\n        ', content)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

