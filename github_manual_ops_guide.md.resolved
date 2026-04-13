# GitHub 项目手动维护与部署指南

当 `github-pages-deploy` Skill 出现 Token 失效或环境变动时，请参考此指南手动完成代码同步。

## 场景 A：快速通过 gh 工具修复
这是最推荐的方式，可以恢复 Skill 的全自动运行。

1. **设置环境变量**
   ```zsh
   export PATH="/Users/RondoT/.gemini/antigravity/scratch/bin:$PATH"
   ```

2. **重新授权登录**
   ```zsh
   gh auth login
   ```
   *   **选择项目**：`GitHub.com`
   *   **协议**：`HTTPS`
   *   **Git 授权**：`Yes`
   *   **登录方式**：`Login with a web browser`
   *   **操作**：复制终端显示的 8 位 code，在浏览器打开的页面中输入。

---

## 场景 B：使用原生 Git 指令手动上传
如果您不希望使用 Skill，可以手动操作部署目录。

1. **进入部署目录**
   ```zsh
   cd "/Users/RondoT/.gemini/antigravity/scratch/dongfeng-push-demo"
   export PATH="/Users/RondoT/.gemini/antigravity/scratch/bin:$PATH"
   ```

2. **提交改动**
   ```zsh
   # 检查改动
   git status

   # 暂存并提交
   git add .
   git commit -m "update: 手动更新项目内容"
   ```

3. **推送到远程**
   ```zsh
   # 推送到 GitHub
   git push origin main
   ```

---

## 常见问题排查 (Troubleshooting)

### 1. 权限报错 (403 Forbidden)
如果 `git push` 提示权限错误，请运行：
```zsh
gh auth setup-git
```
这会将 `gh` 的登录状态注入到 Git 的凭证管理器中。

### 2. 在线链接无法访问
- 检查 [GitHub Repository Settings](https://github.com/RondoTANG/dongfeng-push-demo/settings/pages)。
- 确认 **Build and deployment** 下的 **Branch** 已设置为 `main`。
- 确认在线链接：[https://rondotang.github.io/dongfeng-push-demo/](https://rondotang.github.io/dongfeng-push-demo/)

---

## 常用工具路径参考
- **本地项目路径**: `/Users/RondoT/.gemini/antigravity/scratch/dongfeng-push-demo`
- **gh 工具路径**: `/Users/RondoT/.gemini/antigravity/scratch/bin/gh`
