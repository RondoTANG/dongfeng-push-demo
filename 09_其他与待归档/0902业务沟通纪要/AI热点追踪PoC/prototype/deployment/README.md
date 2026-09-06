# AI 热点 PoC 服务器部署

## 推荐拓扑

```text
手机／电脑浏览器
  → https://hotspot.dbuddy.uk
  → 现有 Cloudflare Tunnel
  → 127.0.0.1:8765
  → FastAPI（页面＋API）
  → /var/lib/ai-hotspot-poc/data/ai_hotspot_poc.db
```

本原型的页面和 API 由同一个 FastAPI 进程提供，不需要再建设一套前端 Nginx 站点。复用现有服务器 Cloudflare Tunnel，新增一个域名入口即可。应用自身的管理员／访客密钥仍是业务访问门禁；Cloudflare Access 可作为额外的外围门禁，但不是当前必需项。

## 一、服务器目录与账号

```bash
sudo useradd --system --home /var/lib/ai-hotspot-poc --shell /usr/sbin/nologin ai-hotspot || true
sudo install -d -o ai-hotspot -g ai-hotspot -m 0750 \
  /opt/ai-hotspot-poc/releases \
  /var/lib/ai-hotspot-poc/data \
  /var/lib/ai-hotspot-poc/config \
  /var/lib/ai-hotspot-poc/codex-home
sudo install -d -o root -g ai-hotspot -m 0750 /etc/ai-hotspot-poc
python3 -m venv /opt/ai-hotspot-poc/venv
```

发布包保持以下结构，`current` 指向当前版本：

```text
/opt/ai-hotspot-poc/current/
├── config/
├── prototype/
├── run_doubao_search.py
└── validate_config.py
```

每次从本机上传新版本时，不上传 `prototype/data/`、缓存、测试截图和密钥；运行数据始终写入 `/var/lib/ai-hotspot-poc/data/`，可编辑业务配置写入 `/var/lib/ai-hotspot-poc/config/`，升级版本不会覆盖 SQLite 或管理员已修改的配置。

从本机项目根目录生成发布包（将 `<发布编号>` 替换为日期或Git提交号）：

```bash
tar \
  --exclude='prototype/data' \
  --exclude='prototype/tests/screenshots' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  -czf /tmp/ai-hotspot-poc-<发布编号>.tar.gz \
  config prototype run_doubao_search.py validate_config.py README.md
scp /tmp/ai-hotspot-poc-<发布编号>.tar.gz 你的SSH别名:/tmp/
```

首次或升级时在服务器解包并切换版本：

```bash
sudo install -d -o root -g ai-hotspot -m 0750 /opt/ai-hotspot-poc/releases/<发布编号>
sudo tar -xzf /tmp/ai-hotspot-poc-<发布编号>.tar.gz \
  -C /opt/ai-hotspot-poc/releases/<发布编号>
sudo chown -R root:ai-hotspot /opt/ai-hotspot-poc/releases/<发布编号>
sudo chmod -R g+rX,o-rwx /opt/ai-hotspot-poc/releases/<发布编号>
sudo ln -sfn /opt/ai-hotspot-poc/releases/<发布编号> /opt/ai-hotspot-poc/current

# 首次部署时用发布包中的配置作为服务器初始值；升级不得覆盖后台已修改的运行配置。
sudo -u ai-hotspot cp -n /opt/ai-hotspot-poc/current/config/*.yaml /var/lib/ai-hotspot-poc/config/
```

发布包不包含Git目录，也不包含本机SQLite和密钥。若需要把当前本地业务数据迁到服务器，应单独停服复制数据库，不能混在代码发布包中。

### 从Mac自动发布

复制本目录的`deploy.env.example`为`deploy.env`，填写SSH目标、远端目录和公开地址。`deploy.env`已被Git忽略，不得提交账号、密钥或Token。随后在PoC根目录执行：

```bash
./prototype/deployment/deploy_from_mac.sh
```

脚本依次完成SSH连通性检查、无数据／无密钥打包、上传、版本目录切换、依赖安装、配置种子首装、systemd重启、内外网健康检查及旧版本回收。首次部署前仍需先在服务器创建`/etc/ai-hotspot-poc/runtime.env`并完成Codex CLI登录；脚本不会替用户生成或覆盖这些凭证。

## 二、安装 Python 与 Codex CLI

```bash
sudo apt update
sudo apt install -y python3 python3-venv nodejs npm
sudo /opt/ai-hotspot-poc/venv/bin/pip install -U pip
sudo /opt/ai-hotspot-poc/venv/bin/pip install -r /opt/ai-hotspot-poc/current/prototype/requirements.txt
sudo npm install -g @openai/codex
```

Codex CLI 的安装、登录方式以 OpenAI 官方文档为准：[Codex CLI入门](https://help.openai.com/en/articles/11096431)、[Codex CLI登录说明](https://help.openai.com/en/articles/11381614-api-codex-cli-and-sign-in-with-chatgpt)。

当前服务会在执行完整／快速采集时直接调用运行机器上的 `codex`。因此，服务器部署有两种边界：

1. **当前可直接落地**：在服务器以 `ai-hotspot` 账号登录 Codex CLI。无需开放本机接口，本机也不必保持在线。
2. **坚持使用本机 Codex**：应另做“本机工作进程主动轮询服务器任务并回传”的出站模式，不能把本机 Codex 或本机 FastAPI 直接暴露到公网。当前代码尚未实现基础采集任务的远程领取，不能只改地址就宣称可用。

服务器登录 Codex：

```bash
sudo -u ai-hotspot env \
  HOME=/var/lib/ai-hotspot-poc \
  CODEX_HOME=/var/lib/ai-hotspot-poc/codex-home \
  /usr/local/bin/codex login --device-auth

sudo -u ai-hotspot env \
  HOME=/var/lib/ai-hotspot-poc \
  CODEX_HOME=/var/lib/ai-hotspot-poc/codex-home \
  /usr/local/bin/codex login status
```

## 三、配置密钥与持久化

复制 `runtime.env.example` 到服务器 `/etc/ai-hotspot-poc/runtime.env`，填写后执行：

```bash
sudo chown root:ai-hotspot /etc/ai-hotspot-poc/runtime.env
sudo chmod 0640 /etc/ai-hotspot-poc/runtime.env
```

三个关键值：

- `AI_HOTSPOT_ADMIN_KEY`：管理员登录及重新查看访客密钥时使用。
- `AI_HOTSPOT_KEY_ENCRYPTION_SECRET`：访客密钥密文的加密主密钥，必须跨版本、跨重启保持不变。
- `DOUBAO_SEARCH_API_KEY`：服务器不能读取 Mac Keychain，必须通过服务器环境变量提供。

生成全新服务器密钥可使用 `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`。若迁移当前本地数据库并希望保留“查看／复制既有访客密钥”的能力，服务器的 `AI_HOTSPOT_KEY_ENCRYPTION_SECRET` 必须使用本地 `prototype/data/access_key_encryption.key` 的原值；管理员密钥同理使用本地 `prototype/data/admin_access.key` 的原值。复制过程必须通过受控 SSH／密码管理工具，不能粘贴到 Git、部署脚本或聊天记录。

## 四、安装 systemd 服务

```bash
sudo cp /opt/ai-hotspot-poc/current/prototype/deployment/ai-hotspot-poc.service \
  /etc/systemd/system/ai-hotspot-poc.service
sudo systemctl daemon-reload
sudo systemctl enable --now ai-hotspot-poc
sudo systemctl status ai-hotspot-poc --no-pager
curl -fsS http://127.0.0.1:8765/api/health
```

## 五、接入现有 Cloudflare Tunnel

1. 将 `cloudflared-ingress.example.yml` 中的规则追加到现有 `/etc/cloudflared/config.yml`，放在兜底 `http_status:404` 前。
2. 为同一个 Tunnel 建立 `hotspot.dbuddy.uk` 的 DNS 路由。
3. 校验配置并重启：

```bash
sudo cloudflared tunnel ingress validate
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager
curl -I https://hotspot.dbuddy.uk/
```

若尚未建立 DNS 路由，可在服务器使用现有 Tunnel 名称或 ID 执行：

```bash
sudo cloudflared tunnel route dns 你的Tunnel名称或ID hotspot.dbuddy.uk
```

## 六、首次验收

```bash
curl -fsS http://127.0.0.1:8765/api/health
sudo -u ai-hotspot env \
  HOME=/var/lib/ai-hotspot-poc \
  CODEX_HOME=/var/lib/ai-hotspot-poc/codex-home \
  /usr/local/bin/codex login status
sudo journalctl -u ai-hotspot-poc -n 100 --no-pager
```

浏览器验收：

1. 管理员密钥可登录；访客密钥只能查看且看不到“访问密钥管理”。
2. 手机端事件审核、作业草案均为“列表→独立详情→返回列表”，详情可滚动到底。
3. 运行中心默认显示自动采集已停止；管理员可设置1—168小时周期并启停，访客不可操作。
4. 首次开启或修改周期后，下次执行时间应为一个完整周期后；重启服务不得立即触发收费采集。
5. 配置管理中可增删改品牌、查询、来源平台和域名识别规则；采集器能力保持只读。
6. 先执行一次快速验证，确认豆包与 Codex 两路均成功，再考虑完整运行或自动采集。

## 七、升级与备份

- 升级只替换 `/opt/ai-hotspot-poc/current` 软链接并重启服务，不覆盖 `/var/lib/ai-hotspot-poc/data`。
- `/var/lib/ai-hotspot-poc/config`是服务器运行配置源。升级包中的`config/`只作新环境种子；除非管理员明确执行配置迁移，不得覆盖运行目录。
- 每次升级前备份 `ai_hotspot_poc.db`；备份时优先短暂停服，或使用 SQLite 在线备份命令。
- `runtime.env`、Codex 登录目录和 SQLite 均不进入发布包。
- 自动采集默认关闭；管理员开启后由服务器调度，周期和启停状态持久化在外置数据目录。

代码升级后的固定动作：

```bash
sudo /opt/ai-hotspot-poc/venv/bin/pip install -r /opt/ai-hotspot-poc/current/prototype/requirements.txt
sudo systemctl restart ai-hotspot-poc
curl -fsS http://127.0.0.1:8765/api/health
sudo journalctl -u ai-hotspot-poc -n 50 --no-pager
```
