# AI热点业务规划与公开搜索线索PoC

本目录用于实际验证“公开信息线索发现 → 证据核验 → 品牌关联与风险判断 → 是否值得发作业 → 生成作业草案”的最小闭环。搜索结果不等于平台热点，本阶段不验证真实热度。

## 当前边界

- 采集端使用Codex公开网页搜索，只作为PoC线索发现和证据核验手段。
- 叠加豆包Global Search进行公开网页广召回；调用参数与结果解析复用`03_审核与AI中台/AI评论与直播话术生成/`的现有实现。
- 规则由`热点采集规则_v0.1.yaml`维护。
- 每次运行结果写入`运行结果/`，保留来源、判断、草案和待运营反馈。
- PoC阶段不接护卫军系统、不自动下发、不自动加热。
- 豆包与Codex均不提供平台原生互动指标和连续快照，不得输出真实热点评级。
- 真实热点阶段依赖具备平台内容ID、原生互动指标、时序增速、覆盖说明和SLA的稳定数据源。
- 项目现有效果采集与前置热点发现是两类能力：用户回填原创链接后，除公众号、视频号外可采部分点赞、评论等基础指标，能够形成多次快照并生成加热草案；但不能据此发现尚未知晓的全平台热点。
- 运营反馈是下一轮规则调整的依据。

## v0.2解决方案与配置

- 详细PRD：`prd/AI热点业务规划与现阶段线索PoC解决方案_PRD_v0.2.md`
- 可视化PRD HTML：`prd/AI热点发现与护卫军作业联动_PRD_v0.2.html`
- 面向业务汇报内容：`prd/面向业务汇报内容_AI热点_v0.2.md`
- 豆包热点能力实测：`运行结果/2026-09-03_豆包热点判定能力验证.md`
- 总控配置：`热点采集规则_v0.2.yaml`
- 品牌实体：`config/品牌实体字典_v0.1.yaml`
- 来源平台：`config/来源平台字典_v0.1.yaml`
- 查询目录：`config/查询目录_v0.1.yaml`
- 清洗聚合与判定：`config/清洗聚合与判定规则_v0.1.yaml`
- 作业生成与分发：`config/作业生成与分发规则_v0.1.yaml`
- 输出数据契约：`config/输出数据契约_v0.1.yaml`

当前只把品牌及其别名作为长期维护的主数据，只有`status=active`的品牌可参与确定性品牌匹配。车型、人物、活动和机构由AI在具体事件内识别：证据充分时写入事件识别结果；证据不足或关系冲突时，必须写明不确定原因、建议关系和证据来源，并随事件进入人工审核，不建立独立的全局实体待确认队列。

运行配置一致性校验：

```bash
python3 validate_config.py
```

## 豆包搜索接入

本目录提供`run_doubao_search.py`。接口调用方式已按Global版文档固定：

- URL：`https://open.feedcoopapi.com/search_api/global_search`
- Method：`POST`
- Content-Type：`application/json`
- Authorization：`Bearer <API_KEY>`

API Key不写入项目文件。脚本运行时按顺序读取环境变量`DOUBAO_SEARCH_API_KEY`或macOS Keychain：

- service：`guard-army-doubao-search`
- account：`api-key`

不熟悉终端配置时，直接运行`配置豆包搜索.command`，按提示粘贴一次API Key并回车即可。输入过程不显示，保存后脚本会自动检查配置。

不配置Key也可以查看实际请求结构，输出会自动脱敏：

```bash
python3 run_doubao_search.py \
  --query "东风汽车 最新动态" \
  --show-request
```

本机具备Key后可执行无请求检查：

```bash
python3 run_doubao_search.py --check-config
```

再执行真实搜索：

```bash
python3 run_doubao_search.py \
  --query "东风汽车 最新动态" \
  --query "岚图汽车 最新动态"
```

单次PoC在运行环境检测到API Key后，可以同时使用豆包和Codex公开搜索；豆包失败时保留Codex搜索结果并记录失败原因，不中断本轮验证。当前阶段不创建定时任务，先通过单次运行确认召回质量和业务判断口径。

## 本阶段成功标准

- 连续运行能够发现与东风直接相关的公开信息线索，并量化漏检情况；不将其表述为热点覆盖率。
- 每个候选都有可访问证据和明确的纳入/排除原因。
- 所有搜索来源事件固定输出`hotspot_judgement_available=false`、`hotspot_status=unknown`。
- 运营能在较短时间内做出“可发、改后可发、不可发”的判断。
- 误报、漏报和业务改题原因可被记录并反哺规则。
- 非微信平台原创链接能够形成至少两个效果快照、指标增量和待审批加热草案；公众号、视频号进入人工凭证流程。
