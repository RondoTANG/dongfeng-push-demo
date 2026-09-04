# 东风护卫军 AI 热点线索 PoC

本地可运行的 B 端产品原型，用于验证以下链路：

`公开信息采集 → 来源清洗 → 事件聚合 → 证据研判 → 事件审核 → 双路作业草案 → 分别审批`

双路作业包括：

- **原创增长**：判断哪些事件值得组织原创评论或内容作业。
- **源内容加热**：直接选择事件中的具体平台文章或视频，形成点赞、正向评论等互动草案。

源内容加热不是原创发布后的二次加热。本期只到草案审批，不创建正式作业、不触达用户、不执行互动，也不进入原创投稿与发布后效果追踪。

## 本地启动

```bash
python3 -m pip install -r requirements.txt
./scripts/start_local.command
```

浏览器打开：`http://127.0.0.1:8765/`

## 真实搜索配置

豆包搜索密钥只从环境变量或 macOS Keychain 读取，不写入仓库：

- 环境变量：`DOUBAO_SEARCH_API_KEY`
- Keychain 服务名：`dongfeng_hotspot_doubao`

未配置凭证时，页面和接口会返回真实失败状态，不使用 Mock 结果冒充采集成功。

## 每三小时运行

当前 Codex 心跳自动化 ID 为 `poc`。自动化负责触发采集、来源处理、事件聚合和 Codex 补证工作项；事件结论、行动方向和两类草案审批仍由运营人工完成。

## 数据与边界

- SQLite 运行库位于 `data/ai_hotspot_poc.db`，已被 `.gitignore` 排除。
- 公开搜索只用于发现线索，不能单独证明真实热点。
- 源内容加热草案必须绑定当前事件中的可执行平台来源、URL和至少一项互动动作。
- 正式系统可后续选择标准数据推送或受控 MCP 调用；MCP 不是本地 PoC 的前置依赖。

## 验证入口

- 产品功能说明：`docs/interaction.html`
- 处理流程图：`flowcharts/poc-flow.html`
- 验收映射：`memory/acceptance-map.md`
- 验证记录：`memory/verification-log.md`
