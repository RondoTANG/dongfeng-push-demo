# 手动标注生成提示词

> 本文件用于 PM 在需要页面评审标注时手动复制给标注生成器。当前未将标注自动写入 `annotations/annotations.js`。

## 标注输入资料

- 项目目标与边界：`memory/project.md`、`memory/business-rules.md`、`docs/decisions.md`。
- 验收与实现：`memory/acceptance-map.md`、`memory/execution-steps.md`、`memory/change-log.md`、`memory/verification-log.md`。
- 可追溯事实：`memory/source-materials.md` 中的 `SRC-*`，`memory/field-map.md` 中的 `FLD-*`。
- 当前页面：运行中心、信息线索工作台、事件审核、双路作业草案与审批、配置管理、无效与审计记录。
- 范围终点：原创增长与源内容加热两类草案生成和分别人工审批。不生成正式下发、任务执行、原创投稿回流或发布后效果追踪标注。

完整来源索引：SRC-001、SRC-002、SRC-003、SRC-004、SRC-005、SRC-006、SRC-007、SRC-008、SRC-009、SRC-010、SRC-011、SRC-012、SRC-013、SRC-014、SRC-015。

完整字段索引：FLD-001、FLD-002、FLD-003、FLD-004、FLD-005、FLD-006、FLD-007、FLD-008、FLD-009、FLD-010、FLD-011、FLD-012、FLD-013、FLD-014、FLD-015、FLD-016、FLD-017、FLD-018、FLD-019、FLD-020、FLD-021、FLD-022、FLD-023、FLD-024、FLD-025、FLD-026、FLD-027、FLD-028、FLD-029、FLD-030、FLD-031、FLD-032、FLD-033、FLD-034、FLD-035、FLD-036、FLD-037、FLD-038、FLD-039、FLD-040、FLD-041、FLD-042、FLD-043、FLD-044、FLD-045、FLD-046、FLD-047、FLD-048、FLD-049、FLD-050、FLD-051、FLD-052、FLD-053、FLD-054、FLD-055、FLD-056、FLD-057、FLD-058、FLD-059、FLD-060、FLD-061。

## 可用 data-anno 锚点清单

- page: 全局后台壳 | data-anno: shell-nav | selector: [data-anno="shell-nav"] | file: index.html
- page: 全局后台壳 | data-anno: shell-service-status | selector: [data-anno="shell-service-status"] | file: index.html
- page: 运行中心 | data-anno: run-center-metrics | selector: [data-anno="run-center-metrics"] | file: js/pages/run-center.js
- page: 运行中心 | data-anno: local-automation | selector: [data-anno="local-automation"] | file: js/pages/run-center.js
- page: 运行中心 | data-anno: run-center-batches | selector: [data-anno="run-center-batches"] | file: js/pages/run-center.js
- page: 信息线索工作台 | data-anno: clues-workbench | selector: [data-anno="clues-workbench"] | file: js/pages/clues.js
- page: 事件审核 | data-anno: event-evidence-review | selector: [data-anno="event-evidence-review"] | file: js/pages/event-detail.js
- page: 作业草案与审批 | data-anno: draft-approval-workbench | selector: [data-anno="draft-approval-workbench"] | file: js/pages/drafts.js
- page: 配置管理 | data-anno: business-config-management | selector: [data-anno="business-config-management"] | file: js/pages/config.js
- page: 无效与审计记录 | data-anno: invalid-and-audit-records | selector: [data-anno="invalid-and-audit-records"] | file: js/pages/audit.js

## 手动标注提示词

请为“东风护卫军 AI热点线索PoC”生成面向产品、运营、研发和测试评审的页面标注。

只能使用本提示词“可用 data-anno 锚点清单”中的 `selector` 作为 `target`，不得猜测、翻译、缩写或新造 selector。不得读取或继承历史 `annotations/annotations.js`、浏览器缓存、旧导出JSON、旧项目标注ID或底座项目标注。

标注对象只限于本轮验收范围内的页面、业务区块、列表、详情、筛选、状态、操作和表单。不对装饰文本、普通说明、`docs/`、`flowcharts/` 或 `tools/` 生成标注。

全部标注的 `id` 必须是从 `"1"` 到 `"N"` 的连续数字字符串，跨页面继续递增，不得按页面重新从1开始。每条标注必须包含 `sourceRefs`；字段相关标注必须包含 `fieldRefs`。编号只能引用本轮 `memory/source-materials.md` 和 `memory/field-map.md` 中真实存在的值。

## 标注生成要求

每条标注必须输出以下10个维度，不适用时说明原因，不得编造规则：

1. `functionName`：明确功能名称。
2. `functionDesc`：使用场景和目的。
3. `permissionScope`：谁可查看、操作或审批。
4. `dataSource`：数据来源系统、接口和 `SRC-*`。
5. `valueLogic`：从输入到展示／状态的转换逻辑。
6. `fieldDesc`：页面字段含义、格式、枚举和 `FLD-*`。
7. `interactionDesc`：操作触发、页面反馈、跳转或刷新。
8. `judgeRule`：执行前提、状态分支、热点数据检查和人工门槛。
9. `exceptionRule`：空数据、断网、接口失败、凭证缺失、状态冲突或解析失败。
10. `otherDesc`：能力边界、未接入系统、已知限制或必须向评审方提醒的事项。

按以下覆盖项生成，不得增加范围外页面：

1. 运行中心数据概览：`[data-anno="run-center-metrics"]`；引用 SRC-003、SRC-004、SRC-009、SRC-010，FLD-001—FLD-010。
2. 本地三小时自动化：`[data-anno="local-automation"]`；引用 SRC-001、SRC-009、SRC-013，FLD-002、FLD-005、FLD-007。必须说明不依赖MCP，且不自动生成／审批草案。
3. 运行批次列表：`[data-anno="run-center-batches"]`；引用 SRC-003、SRC-009，FLD-001—FLD-010。
4. 信息线索工作台：`[data-anno="clues-workbench"]`；引用 SRC-003、SRC-006、SRC-007、SRC-010，FLD-011—FLD-021。
5. 事件证据与审核：`[data-anno="event-evidence-review"]`；引用 SRC-003、SRC-005、SRC-007、SRC-013，FLD-022—FLD-039。必须说明 `hotspot_status=unknown` 的具体原因和新实体存疑处理。
6. 双路作业草案与审批：`[data-anno="draft-approval-workbench"]`；引用 SRC-003、SRC-008、SRC-014、SRC-015，FLD-040—FLD-048、FLD-057—FLD-061。必须说明两类草案并列且分别审批，源内容加热绑定具体文章／视频而不等待原创投稿，审批通过不等于正式下发或已执行互动。
7. 业务配置管理：`[data-anno="business-config-management"]`；引用 SRC-004—SRC-009、SRC-013，FLD-052—FLD-056。必须说明凭证仅显示状态，历史批次冻结配置版本。
8. 无效与审计记录：`[data-anno="invalid-and-audit-records"]`；引用 SRC-007、SRC-013，FLD-021、FLD-049—FLD-051。必须区分技术噪声与业务驳回。

如果以上任一对象的资料不足，输出“缺口说明”并停止该条标注；不生成“待确认”占位标注，不把搜索结果数或AI主观分数写成真实热度。

## 回写说明

本提示词只准备标注内容，不代表已回写页面。若 PM 后续确认回写，需再校验全局连续ID、`sourceRefs`、`fieldRefs` 和上述精确 `target`。
