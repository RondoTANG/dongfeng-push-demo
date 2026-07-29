# AGENTS.md

<!-- project-memory:start -->
## 项目记忆规则

开始任何项目修改前：

1. 阅读 `docs/project-memory/CURRENT.md`。
2. 在 `docs/project-memory/INDEX.md` 中定位相关模块。
3. 使用搜索、真实源文件及 `git status` / `git diff` 核实当前状态；源代码优先于记忆文件。
4. 修改前确认目标文件、预期行为和影响范围。
5. 修改并验证后，更新 `CURRENT.md`；结构变化时更新 `INDEX.md`；向 `CHANGELOG.md` 追加修订记录。
6. 不在项目记忆中记录密钥、Token、账号、个人隐私或生产环境敏感信息。
<!-- project-memory:end -->

## 项目上下文入口

1. 业务规则与 Antigravity 原型规范：`.agents/AGENTS.md`
2. 项目综合理解与当前优先级：`.agents/PROJECT_UNDERSTANDING.md`
3. 模块定位与当前状态：`docs/project-memory/INDEX.md`、`docs/project-memory/CURRENT.md`

记忆文档不替代源代码、PRD、最新会议纪要和线上数据；发生冲突时先核实再修正记忆。
