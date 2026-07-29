# 修订记录

按时间倒序记录有产品或工程影响的修改。

## 2026-07-29｜评论截图审核改为提取全部本人评论

- 需求：同一截图存在多条“我/me”本人评论时全部提取，并避免将昵称旁的视频号等独立平台图标误识别为昵称字符。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动检测智能体设计/互动-评论检测智能体_擎天+阿里/ali_bailian_comments_vision_audit_prompt.md`、`docs/project-memory/CURRENT.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：昵称比较改为机械生成`nickname_key`，仅保留中英文和数字，不再判断图形属于UI徽章还是昵称Emoji；各匹配通道在命中后扫描完整评论列表；`user_comments`按截图顺序返回全部命中评论；输出示例使用中性虚构内容并明确禁止复用，避免真实调试样本形成提示锚定。
- 修改原因：原Prompt的“任意通道命中即停止”和“提取该评论”容易让模型只取第一条；后续按视觉区分徽章与Emoji仍会让模型反复权衡，导致长时间推理及`MATCHED/MISMATCHED`波动。
- 影响范围：`pinglun + screenshot`的昵称识别与评论提取；不改变内容语义、情绪和字数业务规则。
- 验证：规则已覆盖同图两条“我”评论、独立平台图标排除、真实昵称Emoji保留，以及全部评论按序输出。
- 未完成：需在百炼工作流中使用本次截图重复回归，并补充真实昵称含Emoji、仅一条本人评论及非微信平台对照样本。

## 2026-07-29｜过滤直播间平台事件提示

- 需求：避免将直播公屏中的“白龙马 来了”等平台自动入场提示误判为用户主动评论。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动检测智能体设计/互动-直播检测智能体/ali_bailian_prompt.md`、`docs/project-memory/CURRENT.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：在双通道评论校验前增加平台事件过滤；只有“昵称：实质正文”等有效评论结构才进入昵称匹配；入场、关注、分享、点赞、送礼等系统事件一律排除。
- 修改原因：原规则只校验昵称字面一致，模型会把系统事件中的动作词“来了”误提取为用户评论。
- 影响范围：直播间用户评论提取；不改变场景分类、直播间账号识别及既有业务结算规则。
- 验证：已核对规则明确覆盖“白龙马 来了”和“白龙马：来了”两类相反场景，并约束无有效评论时返回`user_comment_found=false`、`name_match_status=NOT_FOUND`、`user_comment=""`。
- 未完成：需在实际百炼工作流中用原失败截图及真实发送“来了”的对照截图回归。

## 2026-07-28｜进一步精简对话智能体Prompt

- 需求：业务系统已保证输入格式规范，删除多余的参数提取与兼容规则。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/conversation_agent_workflow_prompt.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：Prompt仅保留三个标准区块到工作流字段的映射、单次资源调用和`output`原样返回。
- 修改原因：空值、别名、JSON序列化和顺序保护均由业务系统保证，不需要对话智能体重复处理。
- 影响范围：对话智能体Prompt；工作流和Python逻辑不变。
- 验证：Prompt已删除参数提取规则整节及所有兼容分支。
- 未完成：无。

## 2026-07-28｜对话Prompt改为区块到工作流字段直接映射

- 需求：避免用JSON入参示例误导对话智能体输出中间参数对象。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/conversation_agent_workflow_prompt.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：将调用说明改为任务背景、评论列表、优质比例区块分别映射到`task_background/comments/ratio`字段，并禁止展示中间参数。
- 修改原因：对话智能体只需完成资源字段映射，不应构造或返回参数JSON。
- 影响范围：对话智能体工作流调用Prompt。
- 验证：调用章节已不包含工作流入参JSON示例。
- 未完成：无。

## 2026-07-28｜移除对话智能体的评论入参校验

- 需求：评论入参已由业务系统保证规范，对话智能体无需再次校验。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/conversation_agent_workflow_prompt.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：删除JSON合法性、必需字段和重复`comment_id`检查及对应错误响应。
- 修改原因：避免职责重复和对话智能体产生非预期拦截。
- 影响范围：对话智能体调用工作流前的处理；工作流评分和Python比例逻辑不变。
- 验证：Prompt现在只执行参数提取、单次工作流调用和`output`原样返回。
- 未完成：无。

## 2026-07-28｜新增对话智能体调用工作流Prompt

- 需求：在原对话智能体中引入互动评论打分工作流，由对话智能体解析用户输入并传递工作流变量。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/conversation_agent_workflow_prompt.md`、`README.md`、`docs/project-memory/CURRENT.md`、`CHANGELOG.md`
- 核心变化：对话智能体从评分执行者改为参数解析与工作流调用器；提取`task_background/comments/ratio`三个String参数；工作流End将Python的`finalresult`映射为String类型`output`，对话智能体原样返回。
- 修改原因：避免原对话Prompt与新工作流重复执行评分、比例计算和业务知识判断。
- 影响范围：对话智能体Prompt、工作流资源入参/出参配置、最终响应链路和接入文档。
- 验证：已依据界面截图核对Start三个String输入和`output` String输出；已补充缺失背景、缺失比例、评论JSON校验和原样返回规则。
- 未完成：需要在实际对话智能体中通过`@资源`绑定已发布工作流，并确认平台资源的真实显示名称。

## 2026-07-28｜补充 ranking_score 计算公式

- 需求：在README中明确`ranking_score`的计算方式。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/README.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：增加五维求和公式、0～100范围、不同初评分处理、具体算例及与提分门槛的关系。
- 修改原因：仅说明“五项相加”不足以支持研发核算和测试验收。
- 影响范围：工作流实施与接口字段理解；Python逻辑不变。
- 验证：公式与`quota_adjuster.py`中的`RANKING_FIELDS`及求和逻辑一致。
- 未完成：无。

## 2026-07-28｜补全最终输出字段说明

- 需求：在README中完整说明Python最终输出字段。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/README.md`、`quota_adjuster.py`、`test_quota_adjuster.py`、`docs/project-memory/CHANGELOG.md`
- 核心变化：分层说明`finalresult`、`results`和`quota_meta`全部字段；区分模型候选数量与通过Python硬门槛数量，新增`promotion_eligible_count`。
- 修改原因：仅有返回示例不足以支持研发联调、数据落库和比例问题排查。
- 影响范围：接口文档、批次审计元数据和回归测试。
- 验证：已核对README字段与Python实际返回键一致，并补充候选计数测试。
- 未完成：下游系统需确认是否保存全部审计字段，还是仅保存`comment_id/score/tags/reasoning`。

## 2026-07-28｜明确小样本比例的整数化处理

- 需求：确认Python是否处理小样本无法精确达到配置比例，并将规则写入README。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quota_adjuster.py`、`test_quota_adjuster.py`、`README.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：明确采用四舍五入目标条数而非`ratio±2%`判断；返回`final_quality_ratio`、`ratio_deviation`和`integer_ratio_handling`审计字段。
- 修改原因：11条×20%只能落为2条，实际比例18.18%，需区分“整数目标达成”与“实际百分比精确相等”。
- 影响范围：比例结果解释、接口返回元数据、测试和工作流说明。
- 验证：新增11条20%转换为2条、实际18.18%、偏差-1.82%的回归测试。
- 未完成：无。

## 2026-07-28｜移除质量Prompt中的比例和脚本实现描述

- 需求：避免在未接收ratio的模型Prompt中提及批次比例，减少无关信息干扰。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：删除批次比例、后续脚本和数值硬门槛相关表述，仅保留评论语义评分与候选判断标准。
- 修改原因：模型无需理解比例执行方式，相关描述可能诱导模型猜测比例并扭曲初评。
- 影响范围：大模型质量评估Prompt；Python比例调节逻辑不变。
- 验证：Prompt中已无“比例”“脚本”“后续”“门槛”等实现词。
- 未完成：无。

## 2026-07-28｜评论初评顺序调整为0→15→10

- 需求：优化Prompt中10分与15分规则的呈现顺序，降低模型理解歧义。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`README.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：先定义有效评论基础条件，再优先判断15分突出加分项，未达到15分的评论回落为10分并判断提分候选。
- 修改原因：先呈现10分容易产生评分锚定，并让模型混淆“直接15分”与“10分提分候选”。
- 影响范围：评论初评决策顺序，不改变Python比例调节逻辑。
- 验证：已核对输出Schema、初评分字段和Python输入契约无变化。
- 未完成：需用同一批样本对比新旧Prompt的初评15分稳定性。

## 2026-07-28｜恢复高质量10分候选的受控提分

- 需求：保留原Prompt中“15分不足时从高质量10分候选提分”的规则，并与五维评价结合。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`quota_adjuster.py`、`test_quota_adjuster.py`、`README.md`、`docs/project-memory/CURRENT.md`、`CHANGELOG.md`
- 核心变化：五维调整为相关细节、共鸣、表达影响、生动角色、讨论互动；模型为10分输出`promotion_candidate`；Python采用语义候选与数值门槛双重拦截，总分≥50、峰值≥14、相关细节≥10方可提分。
- 修改原因：完全禁止提分会丢失原业务的批次优化能力，但机械补足比例又会把差评论提为优质，需要有限提分与严格止损。
- 影响范围：模型输出Schema、比例双向调节、标签与理由、测试和工作流说明。
- 验证：测试覆盖超额降分、候选提分、数值门槛拦截、候选不足短缺标记、默认比例和真实输出包装。
- 未完成：五维提分阈值需用人工标注历史样本校准，当前50/14/10为首版保守值。

## 2026-07-28｜恢复运营0/10/15标准并改为比例只降不升

- 需求：兼容ratio为空时默认40%，Python节点仅配置`input1/input2`，并避免为凑比例把低质量评论上调为15分。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`quota_adjuster.py`、`test_quota_adjuster.py`、`README.md`、`docs/project-memory/CURRENT.md`、`CHANGELOG.md`
- 核心变化：Prompt恢复运营文档的0/10/15业务语义；五维改为初评15分内部排序维度；Python以`input1`接模型输出、`input2`接ratio，空值默认40%、非法非空值报错；仅在初评15分超额时降分，优质不足时不提分。
- 修改原因：此前按Top-K直接分配15分可能把运营标准中的10分评论强制提升为优质，影响业务判断。
- 影响范围：大模型输出Schema、Python节点变量、比例策略、结果审计和工作流配置。
- 验证：回归测试覆盖5条20%、11条50%、默认40%、只降不升、0分分母、`raw_output`解析和排序保留。
- 未完成：若需完整判断互动量、角色配图、平台折叠、ID或简介暴露，业务入参需补充对应字段。

## 2026-07-28｜兼容大模型节点 raw_output 实际返回格式

- 需求：根据质量评估节点真实调试结果，确认并修正 Python 配额节点的输入解析。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quota_adjuster.py`、`test_quota_adjuster.py`、`README.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：解析器新增 `raw_output` 包装支持并忽略 `reasoning_content`；README补充完整节点输出与子字段两种映射方式；新增真实包装格式回归测试。
- 修改原因：实际模型节点返回 `{raw_output, reasoning_content}`，原脚本只支持直接JSON和 `output.text`，映射完整输出时无法定位 `assessments`。
- 影响范围：评论质量评估节点到Python配额节点的变量映射与结果解析。
- 验证：自动测试覆盖换行前缀、`raw_output`二次反序列化、11条50%配额及原有格式。
- 未完成：实际工作流联调时需确认映射的是完整节点输出还是 `raw_output` 子字段。

## 2026-07-28｜精简评论质量评估 Prompt 的实现信息

- 需求：移除大模型无需理解的 Python 总分计算说明。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：删除后续节点实现说明，仅通过输出Schema约束模型返回五个评分维度和必要字段。
- 修改原因：Prompt应聚焦模型任务与输出契约，工作流实现细节会增加上下文噪声。
- 影响范围：评论质量评估Prompt。
- 验证：已核对输出示例中不存在 `quality_score`，Python节点仍独立计算总分。
- 未完成：无。

## 2026-07-28｜质量总分改由 Python 节点计算

- 需求：评估让大模型执行五项分数加法的稳定性风险。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`quota_adjuster.py`、`test_quota_adjuster.py`、`README.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：模型输出契约移除 `quality_score`；Python节点校验五个分项后自动求和并用于排序；新增总分计算测试。
- 修改原因：大模型可能出现漏加、算错或分项调整后总分未同步，精确算术应由确定性脚本负责。
- 影响范围：大模型输出结构、Python配额节点和工作流字段说明。
- 验证：自动测试覆盖Python总分计算及既有比例、解析和稳定性场景。
- 未完成：上线时需同步更新大模型节点的结构化输出Schema，移除必填 `quality_score`。

## 2026-07-28｜明确评论有效资格与硬失败枚举

- 需求：说明质量评估 Prompt 中硬失败枚举的完整取值及其判断对象。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`README.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：明确硬失败是对单条评论进入10/15分排序池资格的判断；定义 `eligible` 与 `hard_fail_reason` 的关系、五个枚举值、最终处理和多条件命中优先级。
- 修改原因：原文虽列出枚举，但没有清楚说明对应输出字段、判断目标及同时命中时的选择规则。
- 影响范围：大模型Prompt理解、结果解析、0分判定和工作流搭建说明。
- 验证：已核对 Prompt 输出契约、README 节点说明与 Python 配额逻辑一致。
- 未完成：需用实际坏例验证 `TASK_EXPOSURE` 与普通讨论积分规则的边界。

## 2026-07-28｜评论打分方案补全 HiAgent 节点配置并改用 Python

- 需求：参考直播检测智能体的 HiAgent 指南，说明评论打分工作流的设计流程、节点配置、用途和引用文件，并将脚本改为 Python。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/README.md`、`quota_adjuster.py`、`test_quota_adjuster.py`、`docs/project-memory/CURRENT.md`、`CHANGELOG.md`；移除原 `quota_adjuster.js`、`quota_adjuster.test.js`
- 核心变化：README 重构为可照步骤搭建的工作流指南；明确 Start、大模型、Python、End 四类节点的输入输出映射、异常处理和验收清单；Python 脚本采用 `handler(params)` 入口并兼容对象、JSON字符串、Markdown代码块及 `output.text` 嵌套结果。
- 修改原因：原文档偏方案论证，缺少实施人员需要的节点级配置；目标工作流平台采用 Python 代码节点。
- 影响范围：互动评论额外奖励工作流搭建、接口联调、测试与运维追踪。
- 验证：Python 单元测试覆盖 5×20%、11×50%、无效评论排除、嵌套输出解析和重复运行稳定性。
- 未完成：需在实际 HiAgent 环境确认变量类型名称和大模型节点真实输出包装结构。

## 2026-07-28｜补全评论质量 Prompt 的空背景与品牌知识兼容

- 需求：兼容任务背景为空的评论审核请求，并保留原 Prompt 中的东风品牌与车型知识用于辅助判断。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/quality_assessment_prompt.md`、`README.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：新增空值识别和东风集团通用口碑模式；补充合资、自主及商用车品牌车型映射；明确任务背景、知识库、模型知识的使用优先级。
- 修改原因：任务背景可能为 `null`，若无兜底会导致相关性判断失去统一口径；缺少品牌归属知识也容易造成车型关联误判。
- 影响范围：互动评论质量评估模型的输入解析、相关性评分和品牌车型识别。
- 验证：已人工核对空背景分支、知识使用优先级和评分约束；配额脚本不受影响。
- 未完成：车型库需建立版本维护机制，并以业务最新正式清单为准。

## 2026-07-28｜互动评论打分智能体改为模型排序与脚本配额

- 需求：解决 AI 额外奖励审核未按配置比例输出优质评论的问题，并在 AI 审核优化目录建立独立方案。
- 修改文件：`03_审核与AI中台/护卫军AI审核优化/互动评论打分智能体/README.md`、`quality_assessment_prompt.md`、`quota_adjuster.js`、`quota_adjuster.test.js`、`docs/project-memory/INDEX.md`、`CURRENT.md`、`CHANGELOG.md`
- 核心变化：拆分语义质量评估与比例执行；模型输出 0～100 连续质量分及维度分，脚本按有效评论数和四舍五入目标数稳定分配 15/10/0 分，并增加结构和终态断言。
- 修改原因：现有单智能体在 5 条/20% 和 11 条/50% 两个案例中均出现计数及执行不一致；小样本下目标比例 ±2% 还可能不存在可行整数解。
- 影响范围：互动评论额外奖励审核的 Prompt、工作流节点、评分口径、测试与问题追踪。
- 验证：配额脚本覆盖 5×20%=1、11×50%=6、无效评论排除和重复运行一致性。
- 未完成：需确认生产侧取整口径、工作流脚本节点入参格式及接口是否允许返回 `quota_meta`，并用历史人工标注样本校准排序维度。

## 2026-07-28｜建立项目综合理解与跨 Agent 记忆

- 需求：全面读取护卫军项目及 Obsidian 关联知识，形成可供后续 Agent 使用的项目理解。
- 修改文件：`AGENTS.md`、`.agents/AGENTS.md`、`.agents/PROJECT_UNDERSTANDING.md`、`docs/project-memory/INDEX.md`、`docs/project-memory/CURRENT.md`、`docs/project-memory/CHANGELOG.md`
- 核心变化：统一记录业务全景、当前优先级、端到端链路、模块地图、AI 审核规则、长期蓝图、风险和待核实项。
- 修改原因：项目由 Antigravity IDE 延续而来，资料分散且方案、Demo、现状和当前排期容易混淆。
- 影响范围：后续所有 AI/Agent 接手、需求分析、原型和实现工作。
- 验证：已扫描项目结构、Git 状态、主要 PRD/规则/会议纪要和 Obsidian 护卫军项目归档；已核对两个 `.agents/AGENTS.md` 的作用域。
- 未完成：生产系统实际状态、AI 指标与 8—9 月节点进度仍需后续核实。
