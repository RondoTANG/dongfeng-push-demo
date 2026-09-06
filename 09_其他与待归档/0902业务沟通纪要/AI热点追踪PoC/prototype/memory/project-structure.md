# 项目结构摘要

## 当前结构

后台采用静态HTML/CSS/JavaScript＋FastAPI＋SQLite，已接入真实本地服务，不是占位页面。唯一运行入口是本地HTTP，不能用file协议替代服务。

| 相对prototype的路径 | 当前职责 |
|---|---|
| index.html、js/app.js | 应用入口、路由、服务连接状态 |
| js/pages/ | 运行中心、信息线索、事件审核、草案审批、原创后效、配置和审计共7页 |
| js/components/、js/common.js | 列表分页、抽屉、审核表单、中文映射及只读内容排版 |
| assets/css/ | 现有后台视觉及响应式布局 |
| service/ | 查询编排、来源处理、事件、草案、后效、持久化与审计 |
| scripts/start_local.command | 启动本地服务，不自动执行搜索 |
| scripts/ | 本地运行、离线重处理及验证辅助脚本 |
| tests/ | 隔离数据库服务测试、真实页面只读验证和交互测试 |
| data/ | 数据库、运行时产物及备份；不公开发布 |
| config/ | 导航及旧loop工程配置，不是采集业务配置 |
| ../config/ | 7份业务配置，现行总控为热点总控配置.yaml |
| ../prd/ | 当前需求、业务汇报、供应商要求及可视化文档 |
| ../archive/ | 停用规则及历史编写计划，服务不得加载 |
| ../运行结果/ | 历史实测报告与原始响应，只作追溯 |
| docs/interaction.html | 页面交互说明；docs/index.html为展示入口 |
| flowcharts/ | 本地流程图及展示入口 |
| memory/ | 当前工程记忆与历史验证记录 |
| annotations/ | 已有标注数据及运行时，默认不启用空标注入口 |
| tools/ | 旧loop工具，非业务功能，不在本轮改造 |

## 配置与数据边界

- 服务通过service/settings.py定位../config/热点总控配置.yaml；校验器在父目录validate_config.py。
- 总控config_refs以总控文件所在的config目录为基准；业务配置与工程配置分离。
- 核心列表来自/api/*，不得以mock/data.js冒充真实数据。
- 旧热点采集规则_v0.1.yaml归档至../archive/config/，prd/_module-plan.md归档至../archive/planning/。
- 保留原数据库、用户审核和草案，不改写历史运行配置快照；密钥继续通过环境或钥匙串读取。
- 已有旧loop全量终检存在标注／日志格式历史缺项；服务测试通过不代表该全量终检通过。

## 验证入口

- 父目录：python3 validate_config.py。
- 当前目录：python3 -m unittest tests.test_poc_services -q。
- 当前目录：python3 tests/ui_smoke.py、python3 tests/ui_relevance.py。
- 本轮排版与迁移验证：tests/ui_content_layout.py、tests/test_project_layout.py。
