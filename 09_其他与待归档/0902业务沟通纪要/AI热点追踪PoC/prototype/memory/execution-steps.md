# 可执行步骤

## 步骤 01：建立本地服务与持久化底座

### 需求来源
- SRC-001、SRC-003、SRC-013；D-002、D-005、D-006。

### 目标
本机可一条命令启动 FastAPI 与静态页面；健康检查和 SQLite 初始化成功，重启后数据保留。

### 文件
- `service/app.py`（create）
- `service/database.py`（create）
- `service/models.py`（create）
- `service/settings.py`（create）
- `service/__init__.py`（create）
- `scripts/start_local.command`（create）
- `.gitignore`（update）
- `CLAUDE.md`（update）

### 预期变更类型
- create、update

### 输入
- `memory/project.md`、`memory/business-rules.md`、`memory/field-map.md`、`docs/decisions.md`

### 工作
- 建立运行、查询、原始结果、来源、无效、事件、证据、工作项、审核、草案和审计表。
- 提供 `/api/health`，静态托管当前原型入口，数据库文件写入 `data/`。
- 统一 API 成功／错误结构，错误不泄露凭证。

### 验收
- `FLD-001`、`FLD-003`、`FLD-049`、`FLD-050`、`FLD-051` 有可持久化表结构。
- 服务重启后健康检查成功，数据库记录不丢失。
- `data/*.db` 和运行时产物不进入 Git。

### 验证
- 启动服务并请求 `/api/health`；检查 SQLite schema；重启后再次查询。
- 检查静态资源无 404，日志不含 API Key。

### 验证技能
- Verification Skill: `prototype-verifier`
- Browser Evidence Tool: `playwright-cli when needed`

### 标注影响
- affected-pages: None
- annotation-required: no

### 依赖
- None

### 失败处理
- 使用 `systematic-debugging` 定位依赖、端口、路径或数据库迁移问题；不伪造成功响应。

## 步骤 02：跑通真实采集与来源处理

### 需求来源
- SRC-004、SRC-006、SRC-007、SRC-009、SRC-010；D-004、D-005、D-006。

### 目标
用户可导入真实豆包样本或发起快速／完整查询，得到可追溯运行批次、查询任务、统一来源和自动无效记录。

### 文件
- `service/collector.py`（create）
- `service/pipeline.py`（create）
- `service/config_loader.py`（create）
- `service/repositories.py`（create）
- `service/app.py`（update）
- `scripts/import_real_sample.py`（create）
- `scripts/run_collection.py`（create）

### 预期变更类型
- create、update

### 输入
- 父目录 `config/*.yaml`、`热点采集规则_v0.2.yaml`、`run_doubao_search.py`
- `memory/field-map.md`：FLD-001–FLD-021、FLD-052–FLD-056

### 工作
- 复用现有密钥读取和豆包调用约束，解析 `web_search_items_json` 字符串。
- 建立手动、定时、导入运行模式；记录真实查询覆盖、重试和提供方结果。
- 执行平台／站点识别、URL 归一、时间归一、去重和自动无效过滤。
- 提供运行、查询、来源和无效记录 API。

### 验收
- 真实样本导入产生非 Mock 的运行、来源和无效记录。
- `FLD-006` 显示实际执行覆盖而非配置数量；`FLD-010` 显示真实失败／无结果。
- `FLD-013`–`FLD-021` 映射正确，无法识别的平台为 `unresolved`。
- 未配置凭证时真实运行失败并给出安全提示。

### 验证
- 导入 SRC-010 并对照标题、URL、domain、hostname、时间和摘要。
- 执行至少 1 条真实豆包快速查询；核对数据库与 API。

### 验证技能
- Verification Skill: `prototype-verifier`
- Support Skill: `verification-before-completion`

### 标注影响
- affected-pages: run-center, clues, audit
- annotation-required: yes

### 依赖
- STEP-01

### 失败处理
- 将解析、调用、配置或规则失败落入运行错误与审计；使用 `systematic-debugging` 定位。

## 步骤 03：形成统一事件与 Codex 工作项

### 需求来源
- SRC-003、SRC-005、SRC-007、SRC-013；D-003、D-004、D-005、D-007。

### 目标
有效来源能聚合成可审核事件；每个事件显示品牌关系、证据、存疑和热点不可判定原因；Codex 可领取补证／分析工作项并结构化回传。

### 文件
- `service/pipeline.py`（update）
- `service/work_items.py`（create）
- `service/repositories.py`（update）
- `service/app.py`（update）

### 预期变更类型
- create、update

### 输入
- `memory/field-map.md`：FLD-022–FLD-037
- `memory/open-items.md`：OI-001、OI-003、OI-004、OI-008

### 工作
- 以规范标题、品牌／主体和日期窗口进行确定性初聚合并绑定证据。
- 识别 9 品牌及别名；动态实体不确定时写原因，不冒充 active 主数据。
- 对搜索事件写入 `hotspot_status=unknown` 和具体缺失原因。
- 建立 Codex 工作项查询、领取、完成和失败接口；结构由后端校验后写入事件。
- 支持运营人工合并／拆分的 API 和审计。

### 验收
- `FLD-026` 区分来源数和独立来源数，转载条数不变成热度。
- `FLD-028`、`FLD-030`、`FLD-032` 有证据或具体存疑原因。
- `FLD-033=false`、`FLD-034=unknown`，`FLD-035` 至少一条具体原因。
- Codex 不能直接任意改状态，只能提交契约允许的分析结果。

### 验证
- 用真实样本生成至少 1 个事件；检查证据绑定、聚合结果和热点字段。
- 模拟领取并回传一个工作项，验证非法枚举和缺字段被拒绝。

### 验证技能
- Verification Skill: `prototype-verifier`
- Support Skill: `systematic-debugging`

### 标注影响
- affected-pages: clues, event-detail
- annotation-required: yes

### 依赖
- STEP-02

### 失败处理
- 聚合不确定时保留待审核，不强制合并；接口校验失败时保留工作项并记录错误。

## 步骤 04：完成事件审核与双路作业草案

### 需求来源
- SRC-003、SRC-008、SRC-014、SRC-015；D-001、D-005、D-009、D-010。

### 目标
运营确认事件值得响应后，可选择“原创增长”“源内容加热”或两者同时。系统分别生成可编辑、有证据和风险约束的草案，并分别记录审批结果。

### 文件
- `service/drafts.py`（create）
- `service/repositories.py`（update）
- `service/app.py`（update）

### 预期变更类型
- create、update

### 输入
- `memory/field-map.md`：FLD-036–FLD-048、FLD-057–FLD-061
- `memory/business-rules.md` 事件审核与草案规则

### 工作
- 提供事件审核 API，只有允许的事件结论才能生成草案；审核请求显式传入行动方向。
- 生成 `original_comment` 或 `original_content` 原创增长草案，带标题、简述、平台、标签、截止时间、证据、禁用表述和风险。
- 生成 `source_content_boost` 草案时，强制绑定当前事件证据中的具体来源，保存目标平台、URL、标题和点赞／正向评论等互动动作。
- 同一事件允许同时生成两类草案；两类草案使用独立唯一键和审批状态。
- 提供草案编辑、通过和驳回 API；所有操作审计。如需修改，先保存编辑内容再单独通过。
- 草案通过仅标记 `approved`，不产生正式下发、任务执行、原创投稿或发布后效果对象。

### 验收
- `FLD-038`、`FLD-039` 审核结果和留痕齐全。
- `FLD-041` 与 `FLD-057` 匹配；`FLD-046` 至少 1 条有效证据。
- 源内容加热草案必须满足 `FLD-058`–`FLD-061`；目标不属于事件、链接无效或不可互动时拒绝生成并说明原因。
- `FLD-048` 仅出现 draft_pending_review/approved/rejected。
- 被拒绝或风险不允许的事件不能生成草案。

### 验证
- 对一个事件完成“审核通过→同时生成两类草案→分别编辑／筛选／审批”。
- 验证源内容目标归属与可执行性、驳回、缺证据、非法状态跳转返回明确错误。

### 验证技能
- Verification Skill: `prototype-verifier`
- Support Skill: `verification-before-completion`

### 标注影响
- affected-pages: event-detail, drafts
- annotation-required: yes

### 依赖
- STEP-03

### 失败处理
- 状态冲突返回 409 并保留原状态；使用 `systematic-debugging` 检查状态机。

## 步骤 05：搭建统一后台应用壳

### 需求来源
- SRC-001、SRC-012；D-008。

### 目标
6 个产品页面在统一的护卫军 B 端后台壳内可达，信息密度、字号、侧栏、顶栏、筛选和状态样式接近成长体系后台，而不是营销官网或 PPT。

### 文件
- `index.html`（update）
- `assets/css/global.css`（update）
- `assets/css/app.css`（update）
- `js/common.js`（update）
- `js/app.js`（update）
- `js/nav.js`（update）
- `config/nav.json`（update）
- `js/components/layout.js`（create）
- `js/components/ui.js`（create）

### 预期变更类型
- create、update

### 输入
- `memory/project-structure.md`、SRC-012

### 工作
- 实现 256px 侧栏、64px 顶栏、面包屑、内容容器和 6 页 hash 路由。
- 建立设计 token、紧凑表格、筛选栏、状态标签、抽屉、弹窗、空态、加载态和错误态。
- 建立统一 API 请求、错误提示、日期／状态格式化和页面装载机制。
- 保留 `js/delivery-nav.js` 的三视图内部切换。

### 验收
- 导航只出现当前范围，不出现中台、正式发布、投稿或加热。
- 页面标题不使用英文主标题、版本、时间或保密标识；无重复标语。
- 1440px 常用桌面宽度下内容区不拥挤，侧栏靠左，表格可读。
- API 断开时显示统一错误态而非空白页。

### 验证
- 浏览器逐个切换 6 页；检查选中态、面包屑、DOM、console 和资源 404。
- 截图对比后台参考页的信息密度和视觉层级。

### 验证技能
- Verification Skill: `prototype-verifier`
- Browser Evidence Tool: `playwright-cli when needed`

### 标注影响
- affected-pages: all
- annotation-required: no

### 依赖
- STEP-01

### 失败处理
- 使用 `systematic-debugging` 区分路由、样式、资源或 API 连接问题。

## 步骤 06：实现运行中心与线索工作台

### 需求来源
- SRC-003、SRC-004、SRC-006、SRC-007、SRC-010。

### 目标
运营能在页面发起快速／完整运行、观察真实进度和失败，并按平台、品牌关系、时间和状态筛选真实线索。

### 文件
- `js/pages/run-center.js`（create）
- `js/pages/clues.js`（create）
- `js/components/filters.js`（create）
- `js/components/table.js`（create）
- `assets/css/app.css`（update）

### 预期变更类型
- create、update

### 输入
- `memory/field-map.md`：FLD-001–FLD-021

### 工作
- 运行中心展示批次、查询覆盖、提供方状态、步骤计数和查询详情；提供手动运行与失败重试。
- 线索工作台展示来源平台、站点／账号、标题、时间、状态和关联事件；支持组合筛选和下钻。
- 自动无效记录不混入主工作台，但展示本轮数量并链接到无效记录。

### 验收
- 运行按钮调用真实 API，按钮有执行中和防重复状态。
- `FLD-006`、`FLD-007`、`FLD-010` 与 API 一致。
- `FLD-013`–`FLD-020` 空值和 unresolved 规则正确。
- 刷新页面后列表和筛选仍基于持久化数据。

### 验证
- 从页面发起一次快速运行并观察状态变化。
- 组合筛选、打开来源、跳转事件；检查空状态、加载状态和失败状态。

### 验证技能
- Verification Skill: `prototype-verifier`
- Browser Evidence Tool: `playwright-cli when needed`

### 标注影响
- affected-pages: run-center, clues
- annotation-required: yes

### 依赖
- STEP-02、STEP-05

### 失败处理
- 修订页面或接口；连续失败按 Loop 熔断规则回到拆解或记忆层。

## 步骤 07：实现事件详情与草案审批

### 需求来源
- SRC-003、SRC-005、SRC-007、SRC-008、SRC-014。

### 目标
运营可在事件详情核验证据和存疑原因，选择原创增长、源内容加热或两者同时；随后在草案页分别修改和审批两类草案。

### 文件
- `js/pages/event-detail.js`（create）
- `js/pages/drafts.js`（create）
- `js/components/review-drawer.js`（create）
- `js/components/evidence-timeline.js`（create）
- `assets/css/app.css`（update）

### 预期变更类型
- create、update

### 输入
- `memory/field-map.md`：FLD-022–FLD-048、FLD-057–FLD-061

### 工作
- 事件页展示事实摘要、品牌关系、实体识别／存疑、证据时间线、风险和热点不可判定原因。
- 提供事件审核抽屉、行动方向多选、可加热来源单选、人工合并／拆分入口和状态校验提示。
- 草案页提供草案目的筛选、编辑表单、证据下钻、平台／标签调整、目标内容、互动动作、禁用表述、风险和审批。
- 明确显示“审批通过不等于正式下发”。

### 验收
- `FLD-033`–`FLD-035` 可见且原因具体，不显示伪热度分。
- `FLD-038`、`FLD-039` 审核交互和留痕正确。
- `FLD-042`–`FLD-048`、`FLD-057`–`FLD-061` 可编辑、校验和状态展示正确。
- 页面允许生成“热点源内容加热草案”，但不出现正式下发、任务执行、原创投稿回流或发布后效果追踪按钮。

### 验证
- 浏览器跑通事件审核到双路草案分别审批；检查 DOM、API、目标来源、刷新后的状态和错误提示。
- 验证驳回备注、缺证据和并发状态冲突。

### 验证技能
- Verification Skill: `prototype-verifier`
- Browser Evidence Tool: `playwright-cli when needed`

### 标注影响
- affected-pages: event-detail, drafts
- annotation-required: yes

### 依赖
- STEP-04、STEP-05

### 失败处理
- 使用 `systematic-debugging` 定位前端校验、API 状态机或持久化差异。

## 步骤 08：实现业务可读配置与审计

### 需求来源
- SRC-004–SRC-008、SRC-013；D-006、D-007。

### 目标
产品／运营能在页面看懂当前配置项、责任和实际生效版本；自动无效、人工审核和配置变化可追溯。

### 文件
- `service/config_loader.py`（update）
- `service/app.py`（update）
- `js/pages/config.js`（create）
- `js/pages/audit.js`（create）
- `assets/css/app.css`（update）

### 预期变更类型
- create、update

### 输入
- `memory/field-map.md`：FLD-021、FLD-049–FLD-056

### 工作
- 将品牌、查询、来源、清洗／聚合、草案和热点准入 YAML 转换为中文分组视图。
- 显示版本、责任、规则解释、启用状态和被哪些运行使用。
- 无效记录与审计记录分栏，支持对象、操作人、时间和原因筛选。
- 凭证不出现在配置页面或审计差异中。

### 验收
- 配置页面无需阅读 YAML 即可理解业务含义。
- `FLD-052`–`FLD-056` 与 YAML 一致，配置版本可追溯到运行。
- `FLD-021` 与 `FLD-049`–`FLD-051` 分开呈现。
- 搜索热点准入规则是说明性门槛，不提供绕过开关。

### 验证
- 对照 6 份 YAML 抽查品牌数、查询数、平台规则和处理规则。
- 完成一次审核后，在审计页核对操作者、动作、对象和前后值。

### 验证技能
- Verification Skill: `prototype-verifier`
- Browser Evidence Tool: `playwright-cli when needed`

### 标注影响
- affected-pages: config, audit
- annotation-required: yes

### 依赖
- STEP-02、STEP-05

### 失败处理
- 配置解析失败时保留上一可用快照并明确报错；不静默使用空规则。

## 步骤 09：交付本地运行器与自动化接口

### 需求来源
- SRC-001、SRC-009、SRC-013；D-003、D-006；OI-001、OI-007。

### 目标
本机可通过脚本执行快速／完整采集，并为每三小时 Codex 自动化提供稳定、可重入的调用接口。

### 文件
- `scripts/run_collection.py`（update）
- `scripts/process_codex_work_items.py`（create）
- `service/app.py`（update）
- `CLAUDE.md`（update）

### 预期变更类型
- create、update

### 输入
- `memory/open-items.md`：OI-001、OI-007

### 工作
- 提供 idempotency key，避免定时唤醒造成重复批次。
- 提供快速模式和完整 17 条基础查询模式；完整模式记录调用量、耗时和失败。
- 输出 Codex 可读取的 pending 工作项和可校验的回传示例，不把 MCP 设为依赖。
- 写清本地启动、手动执行、工作项处理和停止方式。

### 验收
- 重复使用同一 idempotency key 不创建第二个运行批次。
- 脚本退出码和输出能区分成功、部分成功、凭证缺失和服务不可达。
- 工作项接口只接受契约字段，异常不会破坏已有事件。

### 验证
- 执行快速模式两次验证幂等；模拟一个 Codex 回传。
- 检查命令帮助、错误输出和日志脱敏。

### 验证技能
- Verification Skill: `prototype-verifier`
- Support Skill: `verification-before-completion`

### 标注影响
- affected-pages: run-center
- annotation-required: yes

### 依赖
- STEP-03、STEP-08

### 失败处理
- 先修复本地运行和工作项接口；在一次真实手动运行通过前不创建三小时自动化。

## 步骤 10：补齐异常态、说明与全链路联调

### 需求来源
- SRC-001、SRC-002、SRC-013、SRC-014；全部决策。

### 目标
6 个页面、真实 API 和完整业务路径在正常与异常场景下均可读、可操作、可追溯；交互说明与实际实现一致。

### 文件
- `js/pages/*.js`（update）
- `js/components/*.js`（update）
- `assets/css/app.css`（update）
- `docs/interaction.html`（update）
- `memory/change-log.md`（update）

### 预期变更类型
- update

### 输入
- 全部项目记忆、验收映射和已实现文件

### 工作
- 补齐空数据、加载、断网、服务错误、凭证缺失、部分成功、全无效、工作项待处理和状态冲突。
- 编写业务流程、页面责任、字段规则、接口、状态、边界和本地运行说明。
- 全链路执行“真实运行→来源→事件→审核→草案→审批”。
- 清理重复文案、越界状态、临时日志和前端演示数据。

### 验收
- 6 页可达且与本期范围一致；console 无阻塞错误，资源无 404。
- 无凭证或停服务时不显示假成功。
- 完整流程数据在运行、事件、草案和审计之间可相互追溯。
- `docs/interaction.html` 与实际页面、API 和限制一致。

### 验证
- 运行全局预检和浏览器全路径检查；验证 1440px、1280px 和窄屏基本可用。
- 使用 `verification-before-completion` 核对验收映射；失败用 `systematic-debugging`。

### 验证技能
- Verification Skill: `prototype-verifier`
- Browser Evidence Tool: `playwright-cli when needed`
- Support Skill: `verification-before-completion`

### 标注影响
- affected-pages: all
- annotation-required: yes

### 依赖
- STEP-06、STEP-07、STEP-08、STEP-09

### 失败处理
- 若失败涉及需求或字段事实，回 S3/S6 修订；涉及实现则回 S7 对应步骤修复。
