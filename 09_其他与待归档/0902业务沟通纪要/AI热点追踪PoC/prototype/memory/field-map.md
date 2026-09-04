# 字段映射

## 使用规则

- 页面、接口、数据库、执行步骤和验收使用稳定的 `FLD-*` 编号引用。
- `Source ID` 引用 `memory/source-materials.md`。
- 正式任务执行仍在范围外；已审批原创的实际发布登记、后效快照与二次加热草案进入本期页面和数据库主流程。

## Fields

| Field ID | Source ID | Page / Area | API / Data Field | Display Name | Display Format | Enum / Mapping | Empty / Error Rule | Annotation Point | Used In |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FLD-001 | SRC-003 | 运行中心 | `run_id` | 运行编号 | `RUN-YYYYMMDD-HHMMSS` | 唯一值 | 不可为空 | 批次追溯入口 | 运行列表、详情 |
| FLD-002 | SRC-003 | 运行中心 | `trigger_type` | 触发方式 | 中文标签 | `manual`手动、`schedule`定时、`import`导入 | 不可为空 | 区分手动与三小时自动化 | 运行列表 |
| FLD-003 | SRC-001 | 运行中心 | `run_status` | 运行状态 | 状态标签 | pending/running/partial_success/success/failed | 异常状态展示原因 | 状态机 | 运行列表、进度 |
| FLD-004 | SRC-003 | 运行中心 | `started_at`、`finished_at` | 开始／结束时间 | `YYYY-MM-DD HH:mm:ss` | 本地时区 | 未结束显示“执行中” | 耗时计算 | 运行列表 |
| FLD-005 | SRC-003 | 运行中心 | `config_versions` | 配置快照 | 版本标签组 | 品牌／查询／来源／处理／草案规则 | 缺失则阻止执行 | 可追溯规则 | 运行详情 |
| FLD-006 | SRC-004 | 运行中心 | `query_coverage` | 查询覆盖 | 已执行／计划 | 9 品牌＋8 行业主题 | 未全量执行突出缺口 | 不以配置代替执行 | 运行卡片 |
| FLD-007 | SRC-003 | 运行中心 | `provider_summary` | 提供方结果 | 成功／无结果／失败计数 | doubao/codex/push | 提供方异常单列 | 失败可重试 | 运行详情 |
| FLD-008 | SRC-004 | 运行中心 | `query_id` | 查询编号 | 文本 | 品牌或行业主题目录 ID | 不可为空 | 查询级追溯 | 查询任务表 |
| FLD-009 | SRC-004 | 运行中心 | `query_text` | 查询词 | 完整文本 | 由配置生成 | 不可为空 | 实际执行内容 | 查询任务表 |
| FLD-010 | SRC-009 | 运行中心 | `query_status`、`retry_count` | 查询状态／重试 | 状态＋次数 | pending/running/success/no_result/failed | 失败显示安全错误摘要 | 不回显凭证 | 查询任务表 |
| FLD-011 | SRC-003 | 线索工作台 | `source_id` | 线索编号 | 文本 | 唯一值 | 不可为空 | 来源追溯 | 线索列表 |
| FLD-012 | SRC-006 | 线索工作台 | `retrieved_by` | 获取方式 | 提供方标签 | doubao_global_search/codex_search/standard_push | 未识别显示 unresolved | 区分数据能力 | 线索列表 |
| FLD-013 | SRC-006 | 线索工作台 | `source_platform` | 来源平台 | 图标＋中文名 | 官网／新闻／微博／抖音／小红书／B站／头条／微信系／其他／unresolved | 不能猜测；显示域名 | 平台覆盖边界 | 列表、事件证据 |
| FLD-014 | SRC-006 | 线索工作台 | `source_site_name`、`source_account` | 站点／账号 | 文本 | 域名规则或页面信息 | 无账号显示“未识别” | 平台与账号分开 | 列表、详情 |
| FLD-015 | SRC-003 | 线索工作台 | `original_url`、`canonical_url` | 原始／规范链接 | 可点击链接 | 去参数后的 canonical URL | URL 不可访问显示失败 | 去重依据 | 列表、详情 |
| FLD-016 | SRC-010 | 线索工作台 | `title` | 标题 | 最多两行 | 原始返回 | 无标题使用摘要首句并标记推断 | 保留原文证据 | 列表 |
| FLD-017 | SRC-010 | 线索详情 | `snippet` | 内容摘要 | 多行文本 | 原始摘要 | 无摘要显示“未返回正文摘要” | 不替代原文 | 详情 |
| FLD-018 | SRC-010 | 线索工作台 | `published_at` | 发布时间 | 日期时间＋置信标签 | exact/inferred/unknown | 空值显示“时间不明” | 旧闻过滤依据 | 列表、筛选 |
| FLD-019 | SRC-003 | 线索工作台 | `fetched_at`、`first_seen_at` | 抓取／首次发现 | 日期时间 | 系统时间 | 不可为空 | 与发布时间区分 | 详情 |
| FLD-020 | SRC-007 | 线索工作台 | `source_status` | 处理状态 | 状态标签 | valid/invalid/fetch_failed/pending_review | 未处理显示 pending_review | 自动无效分流 | 列表、筛选 |
| FLD-021 | SRC-007 | 无效记录 | `invalid_rule_id`、`invalid_reason` | 无效规则／原因 | 规则号＋中文原因 | 旧闻／促销／招标／同名误匹配／无实际事件／不可访问 | 规则原因必须可读 | 无需运营逐条否决 | 无效表 |
| FLD-022 | SRC-007 | 事件详情 | `event_id` | 事件编号 | 文本 | 唯一值 | 不可为空 | 事件下钻 | 事件列表、详情 |
| FLD-023 | SRC-003 | 事件详情 | `event_title` | 事件标题 | 一句话事实 | 人工可编辑 | 不确定时避免断言 | 统一事件摘要 | 详情、草案 |
| FLD-024 | SRC-003 | 事件详情 | `primary_entity_id_or_name` | 主体 | 品牌／动态实体 | 品牌 ID 或识别名称 | 存疑时附原因 | 不要求全量车型字典 | 详情 |
| FLD-025 | SRC-003 | 事件详情 | `event_action`、`event_date` | 事件动作／时间 | 动词短语＋日期 | 结构化提取 | 时间不明写 unknown | 聚合主键组成 | 详情 |
| FLD-026 | SRC-003 | 事件详情 | `source_count`、`independent_source_count` | 来源／独立来源数 | 数字 | 转载去重后独立来源 | 不能作为热度值 | 证据质量 | 详情 |
| FLD-027 | SRC-003 | 事件详情 | `source_platforms` | 覆盖平台 | 标签组 | 由来源标准化得出 | unresolved 单列 | 不等于全平台覆盖 | 详情 |
| FLD-028 | SRC-005 | 事件详情 | `brand_relations` | 品牌关系 | 品牌＋状态＋理由 | direct_mention/verified_relation/no_relation/unresolved | 未完成 9 品牌验证显示存疑 | 行业事件关联 | 详情、筛选 |
| FLD-029 | SRC-007 | 事件详情 | `entity_mentions` | 识别实体 | 类型／名称／证据 | model/person/campaign/org | 无则为空列表 | 动态识别 | 详情 |
| FLD-030 | SRC-007 | 事件详情 | `entity_uncertainties` | 实体存疑 | 类型＋原因＋证据 | new_or_unverified/ambiguous/insufficient_evidence | 无存疑显示“暂无” | 交人工判断 | 详情审核 |
| FLD-031 | SRC-007 | 事件详情 | `risk_tags` | 风险标签 | 标签组 | 事实不充分／敏感／争议／版权等 | 无风险显示“未发现明确风险” | 不等于安全承诺 | 详情、草案 |
| FLD-032 | SRC-007 | 事件详情 | `missing_evidence` | 缺失证据 | 清单 | 原始指标／连续快照／作者／覆盖等 | 不可为空时阻止热点判断 | 能力边界 | 详情 |
| FLD-033 | SRC-007 | 事件详情 | `hotspot_judgement_available` | 可否判定热点 | 是／否 | 本期搜索来源固定 false | 必须给出原因 | 数据准入门槛 | 详情 |
| FLD-034 | SRC-007 | 事件详情 | `hotspot_status` | 热点状态 | 状态标签 | 本期固定 unknown | 不显示默认高低热度 | 禁止主观热度 | 详情、列表 |
| FLD-035 | SRC-007 | 事件详情 | `hotspot_unavailable_reason` | 不可判定原因 | 原因清单 | 缺平台原生量／时序快照／UGC作者／覆盖审计 | `unknown` 时必填 | 用户明确要求 | 详情 |
| FLD-036 | SRC-007 | 事件详情 | `event_status` | 事件结论 | 状态标签 | needs_evidence/pending_review/relevant_event_clue/brand_content_opportunity/manual_review/watch/rejected | 无结论保持 pending_review | 业务可行动性 | 列表、审核 |
| FLD-037 | SRC-007 | 事件详情 | `decision_reason` | 判断依据 | 结构化段落 | 证据＋存疑＋建议 | 审核后必填 | 不输出空泛评分 | 审核抽屉 |
| FLD-038 | SRC-003 | 事件审核 | `review_result` | 审核结果 | 单选 | pending/approved/approved_after_edit/rejected | 提交时必选 | 人工门槛 | 审核表单 |
| FLD-039 | SRC-003 | 事件审核 | `reviewer`、`reviewed_at`、`review_note` | 审核人／时间／备注 | 身份＋时间＋文本 | operator | 驳回时备注必填 | 审计留痕 | 事件详情 |
| FLD-040 | SRC-003 | 草案审批 | `task_draft_id` | 草案编号 | 文本 | 唯一值 | 不可为空 | 草案追溯 | 草案列表 |
| FLD-041 | SRC-008 | 草案审批 | `task_type` | 作业类型 | 中文标签 | original_comment/original_content/source_content_boost/original_post_boost | 必须与草案目的匹配 | 范围门槛 | 列表、表单 |
| FLD-042 | SRC-008 | 草案审批 | `task_title`、`task_brief` | 标题／任务简述 | 标题＋富文本 | 运营可编辑 | 通过前必填 | AI 初稿非最终稿 | 草案详情 |
| FLD-043 | SRC-008 | 草案审批 | `recommended_platforms` | 建议平台 | 多选标签 | 来自事件来源和内容适配 | 运营可调整 | 不等于正式分发 | 草案表单 |
| FLD-044 | SRC-008 | 草案审批 | `target_member_tags` | 目标成员标签 | 多选标签 | 复用现有平台能力标签 | 未接接口时显示“待运营确认” | 选人建议 | 草案表单 |
| FLD-045 | SRC-008 | 草案审批 | `response_deadline` | 建议截止时间 | 日期时间 | 依据事件时效 | 空值需人工补充 | 时效提示 | 草案表单 |
| FLD-046 | SRC-003 | 草案审批 | `evidence_source_ids` | 证据来源 | 可展开列表 | 有效 source_id | 至少 1 条 | 草案可追溯 | 草案详情 |
| FLD-047 | SRC-008 | 草案审批 | `prohibited_claims`、`risk_notes` | 禁用表述／风险提示 | 清单 | AI 建议＋人工修订 | 无内容显示“暂无明确项，仍需审核” | 防止过度断言 | 草案表单 |
| FLD-048 | SRC-014 | 草案审批 | `task_status` | 草案状态 | 状态标签 | draft_pending_review/approved/rejected | 不出现 published | 本期终点 | 列表、审批 |
| FLD-049 | SRC-013 | 审计记录 | `actor_type`、`actor_id` | 操作者 | 类型＋名称 | system/codex/operator/admin | 不可为空 | 区分自动与人工 | 审计列表 |
| FLD-050 | SRC-013 | 审计记录 | `action`、`object_type`、`object_id` | 操作与对象 | 动作＋对象链接 | create/update/review/retry/config_change | 不可为空 | 全链路追溯 | 审计列表 |
| FLD-051 | SRC-013 | 审计记录 | `before_json`、`after_json`、`created_at` | 变更前后／时间 | 差异视图 | 敏感字段脱敏 | 无前态允许为空 | 配置和审批审计 | 审计详情 |
| FLD-052 | SRC-005 | 配置管理 | `brand_id`、`canonical_name`、`aliases`、`status` | 品牌与别名 | 表格＋标签 | active/inactive | 变更需校验重复别名 | 9 品牌主数据 | 品牌配置 |
| FLD-053 | SRC-004 | 配置管理 | `query_catalog` | 查询目录 | 分组表格 | 品牌／行业／关联／补证 | 禁用项仍保留历史版本 | 全量覆盖 | 查询配置 |
| FLD-054 | SRC-006 | 配置管理 | `domain_rules` | 来源识别规则 | 域名→平台／站点 | 优先级匹配 | 未命中 unresolved | 来源可解释 | 来源配置 |
| FLD-055 | SRC-007 | 配置管理 | `processing_rules` | 处理规则 | 规则卡＋启停 | 无效／去重／聚合／关系／风险／热点准入 | 变更前校验并留痕 | 人类可读配置 | 规则配置 |
| FLD-056 | SRC-013 | 配置管理 | `config_version`、`effective_at`、`changed_by` | 配置版本／生效 | 版本＋时间＋人 | 草稿／生效／停用 | 运行使用已冻结版本 | 防止改动污染历史 | 配置历史 |
| FLD-057 | SRC-015 | 草案审批 | `draft_purpose` | 草案目的 | 类型标签 | original_growth/source_content_boost/original_post_boost | 不可为空；三类草案分别审批 | 作业路径判断 | 列表、详情、筛选 |
| FLD-058 | SRC-015 | 事件审核／草案审批 | `target_source_id` | 加热目标来源 | 来源编号 | 必须属于当前事件证据 | 原创增长为空；源内容加热必填 | 目标归属校验 | 审核抽屉、草案详情 |
| FLD-059 | SRC-015 | 草案审批 | `target_url` | 目标内容链接 | 可点击URL | 来自已选来源的规范链接 | 无效URL或非可互动目标时拒绝生成 | 作业执行对象 | 草案详情 |
| FLD-060 | SRC-015 | 草案审批 | `target_content_title` | 目标内容标题 | 最多两行 | 继承已选来源标题 | 无标题时使用可追溯摘要并标记 | 确认加热对象 | 草案详情 |
| FLD-061 | SRC-015 | 草案审批 | `engagement_actions` | 互动动作 | 多选标签 | like/positive_comment/share/favorite | 源内容加热至少一项；运营可调整，具体平台动作规则见SRC-008 | 动作建议 | 草案编辑 |
| FLD-062 | 用户修订 | 原创后效追踪 | `publication_id`、`source_draft_id` | 发布记录／原草案 | 关联编号 | 仅关联 approved original_growth | 前置不满足拒绝登记 | 原创路径追溯 | 列表、详情 |
| FLD-063 | 用户修订 | 原创后效追踪 | `publication_url`、`platform`、`platform_content_id` | 实际发布内容 | 可点击URL＋平台 | 支持平台枚举 | URL无效或重复拒绝；内容ID可空 | 实际观察对象 | 登记抽屉、详情 |
| FLD-064 | 用户修订 | 原创后效追踪 | `published_at`、`registration_source` | 发布时间／登记来源 | 日期时间＋来源标签 | operator/business_push/import | 发布时间必填 | 登记证据 | 详情 |
| FLD-065 | 用户修订 | 原创后效追踪 | `snapshot_at`、`data_source` | 快照时间／数据来源 | 日期时间＋来源标签 | existing_collector/business_push/manual_evidence | 时间必填 | 快照可追溯 | 快照列表 |
| FLD-066 | 用户修订 | 原创后效追踪 | `metrics_json` | 指标快照 | 指标卡 | view_count/like_count/comment_count/share_count/favorite_count | 非负；无指标需不可用原因 | 同口径数据 | 快照列表 |
| FLD-067 | 用户修订 | 原创后效追踪 | `delta_metrics_json`、`data_status` | 指标增量／数据状态 | 首末差值＋状态 | tracking/ready_for_evaluation/growth_observed/no_growth_observed/data_anomaly | 少于2快照不评价；回退为异常 | 确定性计算 | 详情、评价 |
| FLD-068 | 用户修订 | 原创后效追踪 | `decision`、`decision_reason` | 后效结论／原因 | 单选＋文本 | create_followup_boost/watch/no_boost/manual_review | 提交时必填 | 人工门槛 | 评价抽屉 |
| FLD-069 | 用户修订 | 草案审批 | `target_submission_id`、`trigger_evaluation_id` | 原创后二次加热目标／触发判断 | 关联编号 | 仅 original_post_boost 必填 | 不得与target_source_id混用 | 两类加热隔离 | 草案详情 |

## Open Field Questions

- `target_member_tags` 与正式护卫军标签接口尚未接入；本期先从配置读取并允许运营调整，见 OI-006。
- 豆包真实响应中 `web_search_items_json` 是 JSON 字符串，解析失败时必须记录原始请求级错误，见 OI-002。
- Codex 补证结果的最终结构化字段在 S7 按 `event_evidence` 契约落地并通过接口校验，见 OI-001。
