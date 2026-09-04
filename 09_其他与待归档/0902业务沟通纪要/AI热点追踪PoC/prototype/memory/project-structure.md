# 项目结构摘要

## 当前结构结论

- 当前工程已具备原型 Loop 的标准静态结构、三视图交付壳、项目记忆、标注运行时和确定性门禁脚本。
- 业务页面仍为初始化入口，`js/pages/`、`js/components/` 只有占位文件，FastAPI／SQLite 服务目录尚未创建。
- S6 可按已确认范围把页面和服务拆到下述业务边界；不得修改总控工具包。

## 可编辑业务文件清单

| 路径 | 类型 | 当前责任 | 可编辑原因 |
| --- | --- | --- | --- |
| `index.html` | entry | 原型主入口和脚本加载 | 需要改为后台应用壳与默认页容器 |
| `assets/css/global.css` | style | 全局设计变量与通用组件 | 需要建立成长体系后台风格的统一 token |
| `assets/css/app.css` | style | 当前应用布局 | 需要实现侧栏、顶栏、筛选、表格、详情、抽屉、状态与响应式 |
| `js/app.js` | app | 当前入口逻辑 | 需要负责路由装载、API 健康检查和全局错误态 |
| `js/common.js` | utility | 通用函数占位 | 需要提供请求、格式化、状态映射、消息提示等共用能力 |
| `js/nav.js` | navigation | 从配置渲染业务导航 | 需要支持当前 6 个页面和选中态 |
| `config/nav.json` | configuration | 当前只有首页和流程图入口 | 需要改为当前产品导航的唯一业务真源 |
| `mock/data.js` | fallback | 空 Mock 数据入口 | 核心链路不得放演示数据；仅允许无接口时的静态枚举或开发占位 |
| `docs/interaction.html` | documentation | 交互说明模板 | S7 后补页面、状态、接口和边界说明 |
| `docs/decisions.md` | documentation | 已确认架构与范围决策 | 仅追加新的已确认决策，不覆盖历史 |
| `flowcharts/processon-links.txt` | configuration | 当前项目流程图链接 | 仅由 PM 后续补充真实 ProcessOn 链接 |
| `annotations/annotations.js` | annotation data | 空标注数据 | S9 后再根据全局验收生成，不在 S7 预填 |

## 允许新增的业务实现边界

| 目录 | 责任 | 约束 |
| --- | --- | --- |
| `js/components/` | 筛选栏、状态标签、表格、分页、抽屉、确认框等公共组件 | 公共组件不得硬编码业务数据 |
| `js/pages/` | 运行中心、线索工作台、事件详情、草案审批、配置、无效与审计的页面控制器 | 只通过 API 或公共数据层获取核心数据 |
| `service/` | FastAPI、SQLite、采集适配、处理引擎、工作项和审计 | 状态流转、去重、无效与审批必须确定性执行 |
| `scripts/` | 本地启动、真实导入、运行触发和验证脚本 | 不保存 API Key；脚本应可重复执行 |
| `data/` | SQLite 数据库和运行时产物 | 运行时文件不入版本库；页面不可直接读取 |
| `pages/` | 如采用多 HTML 入口，承载独立产品页面 | 优先保留统一应用壳；不得复制整套导航代码 |

## 页面与入口

- `index.html`：唯一主入口；由 `js/app.js` 根据 URL hash 加载业务页面。
- `config/nav.json`：业务导航配置的唯一来源。
- `js/nav.js`：业务侧栏渲染和路由选中态。
- `js/pages/*.js`：页面级渲染、筛选、操作与 API 协调。
- `js/delivery-nav.js`：原型／说明文档／流程图集的统一内部切换壳，必须保留。
- `docs/index.html`：说明文档展示入口。
- `flowcharts/index.html`：流程图集入口。

## 公共组件与复用边界

- `js/components/`：公共组件层；修改需评估所有使用页面。
- `js/common.js`：跨页面 API 请求、日期格式、状态文案、脱敏和提示工具。
- `assets/css/global.css`：设计 token 与全局基础样式。
- `assets/css/app.css`：业务组件和页面布局样式。
- 页面不得自行重复实现顶栏、侧栏、状态标签、空状态和错误提示。

## 数据与配置来源

- 业务数据：后续 `service/` 提供的 `/api/*` 真实接口，SQLite 持久化。
- 初始配置：父目录 `config/*.yaml` 和 `热点采集规则_v0.2.yaml`，由后端读取并冻结版本。
- 真实样本：父目录 `运行结果/2026-09-03_豆包原始结果.json`，用于导入和解析验收。
- 前端 `mock/data.js`：不得承载核心运行、线索、事件或草案记录。
- `config/project.json`：稳定 projectId 和依赖策略；当前 `allowDependencies=false`。
- `config/workflow.json`：Loop 阶段状态，不是业务配置。

## 标注与交互说明位置

- 源码锚点：业务页面或组件中的稳定 `data-anno` 属性，S9 再补标注数据。
- 标注运行时：`annotations/annotation-runtime.js`、`annotations/annotation.css`。
- 标注数据：`annotations/annotations.js`。
- 交互说明：`docs/interaction.html`。
- 决策记录：`docs/decisions.md`。

## 框架与流程文件

- `CLAUDE.md`：本地运行和验证命令约束。
- `.clauderules`：标注系统规则。
- `memory/`：项目事实、拆解、验收、验证和阶段记录。
- `tools/loop_run.py`、`tools/loop_preflight.py`：确定性阶段门禁，只由总控调用。

## 不纳入实现／交付的目录

- `tools/prototype-loop-orchestrator/`：项目内总控工具包，不作为业务实现范围，不参与页面或服务拆分，不修改。
- `tools/loop_run.py`、`tools/loop_preflight.py`：工作流门禁脚本，不作为产品功能。
- 参考底座 `04_成长与激励体系/04_成长体系UI原型`：只读参考，不在原目录修改。
- 父目录 PRD、YAML、运行结果：作为输入资料读取，不由原型工程覆盖。
