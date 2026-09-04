# 标注准备覆盖清单

> 本清单只记录当前手动标注提示词的覆盖情况。`annotations/annotations.js` 仍为空对象，不表示页面标注已回写。

## Coverage

| Annotation ID / Prompt Item | Page | Target / Area | Requirement ID | Source Refs | Field Refs | Coverage Note |
| --- | --- | --- | --- | --- | --- | --- |
| Prompt-01 | 运行中心 | `[data-anno="run-center-metrics"]` | R-003、R-004、R-016 | SRC-003、SRC-004、SRC-009、SRC-010 | FLD-001—FLD-010 | 实际执行覆盖、真实状态和异常统计 |
| Prompt-02 | 运行中心 | `[data-anno="local-automation"]` | R-002、R-010、R-023、R-024 | SRC-001、SRC-009、SRC-013 | FLD-002、FLD-005、FLD-007 | 每3小时幂等执行、Codex工作项和MCP非前置边界 |
| Prompt-03 | 运行中心 | `[data-anno="run-center-batches"]` | R-001、R-004、R-016、R-021 | SRC-003、SRC-009 | FLD-001—FLD-010 | 批次、配置快照、查询状态和追溯 |
| Prompt-04 | 信息线索工作台 | `[data-anno="clues-workbench"]` | R-003、R-005、R-006、R-017 | SRC-003、SRC-006、SRC-007、SRC-010 | FLD-011—FLD-021 | 来源标准化、筛选、未知处理和自动无效分流 |
| Prompt-05 | 事件审核 | `[data-anno="event-evidence-review"]` | R-007—R-012、R-018、R-025 | SRC-003、SRC-005、SRC-007、SRC-013 | FLD-022—FLD-039 | 事件、证据、动态实体存疑、热点不可判定原因与人工门槛 |
| Prompt-06 | 双路作业草案与审批 | `[data-anno="draft-approval-workbench"]` | R-012—R-014、R-019、R-025、R-027—R-029 | SRC-003、SRC-008、SRC-014、SRC-015 | FLD-040—FLD-048、FLD-057—FLD-061 | 原创增长与源内容加热草案、目标文章／视频、互动动作、分别审批与本轮终点 |
| Prompt-07 | 配置管理 | `[data-anno="business-config-management"]` | R-002、R-020、R-021、R-024 | SRC-004—SRC-009、SRC-013 | FLD-052—FLD-056 | 业务可读规则、凭证安全、版本冻结与解析异常 |
| Prompt-08 | 无效与审计记录 | `[data-anno="invalid-and-audit-records"]` | R-006、R-011、R-022、R-025 | SRC-007、SRC-013 | FLD-021、FLD-049—FLD-051 | 自动无效与业务决策分离，前后快照可追溯 |
| Interaction-Doc | 六个业务页 | `docs/interaction.html` | R-014、R-015、R-024、R-026 | SRC-001—SRC-014 | FLD-001—FLD-056 | 交互说明已覆盖项目范围、功能、取值、异常、状态和边界 |

## Gaps

- 本轮未自动回写页面标注；如 PM 后续确认，再基于 `memory/annotation-prompt.md` 生成并手动合并。
- 未给顶层导航和服务健康状态生成独立标注；其为全局壳能力，不是本轮核心业务验收对象。
- 不包含正式作业下发、任务执行、原创投稿回流、发布后效果追踪、企业级平台数据源或MCP对接标注，因为这些不在当前实现范围；源内容加热草案本身属于当前实现。

## 完整追溯索引

- 需求：R-001、R-002、R-003、R-004、R-005、R-006、R-007、R-008、R-009、R-010、R-011、R-012、R-013、R-014、R-015、R-016、R-017、R-018、R-019、R-020、R-021、R-022、R-023、R-024、R-025、R-026、R-027、R-028、R-029。
- 来源：SRC-001、SRC-002、SRC-003、SRC-004、SRC-005、SRC-006、SRC-007、SRC-008、SRC-009、SRC-010、SRC-011、SRC-012、SRC-013、SRC-014、SRC-015。
- 字段：FLD-001、FLD-002、FLD-003、FLD-004、FLD-005、FLD-006、FLD-007、FLD-008、FLD-009、FLD-010、FLD-011、FLD-012、FLD-013、FLD-014、FLD-015、FLD-016、FLD-017、FLD-018、FLD-019、FLD-020、FLD-021、FLD-022、FLD-023、FLD-024、FLD-025、FLD-026、FLD-027、FLD-028、FLD-029、FLD-030、FLD-031、FLD-032、FLD-033、FLD-034、FLD-035、FLD-036、FLD-037、FLD-038、FLD-039、FLD-040、FLD-041、FLD-042、FLD-043、FLD-044、FLD-045、FLD-046、FLD-047、FLD-048、FLD-049、FLD-050、FLD-051、FLD-052、FLD-053、FLD-054、FLD-055、FLD-056、FLD-057、FLD-058、FLD-059、FLD-060、FLD-061。
