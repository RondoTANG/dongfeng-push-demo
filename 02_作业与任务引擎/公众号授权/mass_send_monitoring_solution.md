# 护卫军 - 微信群发内容实时感知解决方案

## 1. 背景与痛点分析
在最初的架构探索中，系统尝试通过主动调用微信 `freepublish/batchget`（发布/草稿箱接口）来轮询获取公众号的最新文章。但在实际业务对齐中发现了以下致命局限性：
- **能力盲区（无法获取群发）**：该接口（`https://api.weixin.qq.com/cgi-bin/freepublish/batchget`）只能拉取通过“发布（不占用次数的静默发布）”能力推送的文章，无法获取真正占据公众号每日群发次数的“群发（Mass Send）”图文。
- **风控与限流**：采取主动轮询策略会快速消耗微信 API 的每日调用限额。在未来多账号、高并发的监控场景下，极易触发微信风控导致接口封禁。

## 2. 核心解决方案：事件驱动与被动感知
为了打破轮询瓶颈并覆盖群发场景，系统采用了“被动感知”的重构方案：**依托微信第三方平台（开放平台）的消息与事件推送机制**。系统只需在开放平台配置并挂载事件网关（例如：`https://[系统域名]/v1/wechat/events/$APPID$`），在接收到群发完成（事件类型 `Event` 为 `MASSSENDJOBFINISH`，详见[官方文档：群发消息 - 事件推送群发结果](https://developers.weixin.qq.com/doc/service/guide/product/message/Batch_Sends.html)）的 XML 回调报文后进行轻量级解析，即可实现毫秒级的新内容捕获。
*(注：事件感知体系底层仍依赖公众号的长期授权，需通过开放平台接口 `https://api.weixin.qq.com/cgi-bin/component/api_authorizer_token` 维护授权凭证的生命周期。)*

## 3. 技术时序流转图

```mermaid
sequenceDiagram
    autonumber
    participant Op as 公众号运营者
    participant Wx as 微信官方服务器
    participant Gw as 护卫军事件网关 (Webhook)
    participant Core as 护卫军处理引擎
    participant DB as 作业数据库

    Note over Gw: 前提: 开放平台网关配置完毕且具有[群发权限集]
    
    Op->>+Wx: 在微信后台点击“群发”并扫码确认
    Wx-->>-Op: 提示：群发任务已提交并在后台执行
    
    Note over Wx: 微信服务器向受众下发图文...
    
    Wx->>+Gw: 触发事件推送: MASSSENDJOBFINISH (XML报文)
    Gw->>+Core: 将 XML Payload 压入解析队列
    Gw-->>-Wx: 响应 "success" (向微信确认已接收，避免重试)
    
    Core->>Core: XML 解析与字段解构
    Note over Core: 提取核心字段: <br/>1. ArticleUrl (永久阅读链接)<br/>2. MsgID (群发任务唯一标识)
    
    Core->>+DB: 依据 ArticleUrl 发起全局去重校验
    alt URL 库内不存在 (新内容)
        DB-->>Core: 校验通过 (Not Found)
        Core->>DB: 生成监控作业 (绑定 MsgID 以备后续拉取评论)
        DB-->>-Core: 作业入库成功
    else URL 已存在 (重复)
        DB-->>-Core: 校验未通过 (Found)
        Core->>Core: 静默抛弃该事件
    end
```

## 4. XML 核心字段解析说明

当系统接收到 `<Event><![CDATA[MASSSENDJOBFINISH]]></Event>` 事件时，核心逻辑是从微信推送的完整 XML 报文中剥离以下两项高价值资产：

### 4.1 提取底层阅读链接 (`ArticleUrl`)
用于业务层面的**全局去重**，并作为后续质检（AI 审核图文）的抓取入口。
- **XPath 解析路径**：`xml -> ArticleUrlResult -> ResultList -> item -> ArticleUrl`
- **示例值**：`https://mp.weixin.qq.com/s/df_demo_xxx`

### 4.2 提取群发身份标识 (`MsgID`)
打通微信互动生态的“钥匙”。将该 ID 随同作业持久化后，后续可以通过护卫军的服务集群，调用微信官方提供的评论接口精准拉取该篇文章下的用户留言数据。
- **关联接口地址**：`https://api.weixin.qq.com/cgi-bin/comment/list` (POST请求，入参中需传入此处的 `MsgID`)
- **XPath 解析路径**：`xml -> MsgID`
- **示例值**：`1000001625`

## 5. 产品业务收益
1. **监控 0 盲区**：100% 覆盖真实运营最关注的公众号群发（Mass Send）场景。
2. **感知 0 延迟**：将原本受限于定时轮询的分钟级延迟，降维打击至“发完即达”的毫秒级推送。
3. **API 0 损耗**：彻底释放了文章拉取接口的额度压力，系统资源占用极低，高并发下依然稳如泰山。

## 6. 全局去重与重试处理机制

### 6.1 去重背景（微信的重试机制）
当微信服务器向系统网关推送 `MASSSENDJOBFINISH` 事件时，系统必须在 **5 秒内** 响应 `success` 字符串。
如果在网络抖动、数据库写入缓慢、或者解析超时等情况下，网关未能在 5 秒内返回 `success`，**微信官方服务器会自动重试推送该事件（通常重试 2~3 次）**。
若不对推送事件进行全局去重，系统就会为同一篇文章重复创建监控作业、重复拉取评论，甚至导致统计数据翻倍。

### 6.2 去重技术实现
系统在解析出事件中的核心标识后，采取以下两阶段去重策略：
1. **第一阶段：网关层幂等去重（高并发防并发）**
   - 提取 `MsgID`（群发任务ID）或 `ArticleUrl`（文章永久链接）作为 Redis 的分布式锁 Key，设置 10 秒过期时间。
   - 当多个重试请求几乎同时到达时，仅第一个请求成功获得锁并进入业务处理。
2. **第二阶段：存储层唯一约束（最终防重）**
   - 在数据库中，对 `jobs` 表的 `url`（即 `ArticleUrl`）建立**唯一索引 (Unique Index)**。
   - 处理引擎在向数据库写入新作业时，如果触发唯一键冲突，直接捕获异常并静默抛弃，向微信回复 `success` 即可。

---

## 7. 文章元数据获取方案 (ArticleUrl 抓取解析)

### 7.1 为什么采用抓取解析方案
微信官方没有提供类似“根据 URL 或 MsgID 获取已群发文章详情（如标题、摘要、封面图、发布时间）”的直接 API。
而对于已经群发的文章，微信生成的 `ArticleUrl` 属于**公开可访问的永久链接**。
因此，系统可以通过向 `ArticleUrl` 发送一个轻量级 HTTP GET 请求，获取页面的 HTML，并提取 HTML 中的元数据。

### 7.2 元数据解析映射表
微信文章的 HTML 头部遵循了标准的 **Open Graph (OG)** 协议。我们可以直接利用 XPath 或 HTML 解析器（如 BeautifulSoup/lxml）提取以下特定标签：

| 目标字段 | HTML 标签/脚本特征 | 示例 HTML 源码片段 |
| :--- | :--- | :--- |
| **文章标题** | `meta[property="og:title"]` 的 `content` 属性 | `<meta property="og:title" content="东风汽车2026战略发布" />` |
| **文章封面图** | `meta[property="og:image"]` 的 `content` 属性 | `<meta property="og:image" content="http://mmbiz.qpic.cn/xxx" />` |
| **文章摘要** | `meta[property="og:description"]` 的 `content` 属性 | `<meta property="og:description" content="全面转型新能源..." />` |
| **作者** | `meta[name="author"]` 的 `content` 属性 | `<meta name="author" content="东风汽车" />` |
| **发布时间** | HTML 内 `<script>` 中的变量 `ct` | `var ct = "1778483734";` （通过正则表达式 `var\s+ct\s*=\s*"(\d+)"` 提取时间戳） |

### 7.3 抓取代码参考实现 (Python)
```python
import requests
import re
from bs4 import BeautifulSoup

def fetch_article_meta(article_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(article_url, headers=headers, timeout=5)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 1. 提取 Open Graph 元数据
        title = soup.find('meta', property='og:title')['content'] if soup.find('meta', property='og:title') else ""
        cover_url = soup.find('meta', property='og:image')['content'] if soup.find('meta', property='og:image') else ""
        digest = soup.find('meta', property='og:description')['content'] if soup.find('meta', property='og:description') else ""
        
        # 2. 提取发布时间 (js 变量 ct)
        publish_time = 0
        ct_match = re.search(r'var\s+ct\s*=\s*"(\d+)"', resp.text)
        if ct_match:
            publish_time = int(ct_match.group(1))
            
        return {
            "title": title,
            "thumb": cover_url,
            "digest": digest,
            "publish_time": publish_time
        }
    except Exception as e:
        print(f"解析文章元数据异常: {e}")
        return None
```

---

## 8. 微信官方文档链接速查

为了便于开发阶段随时查阅，微信平台相关的最新文档链接汇总如下：
- **群发消息事件推送文档 (MASSSENDJOBFINISH)**：
  👉 [微信官方文档 · 服务号群发结果事件推送](https://developers.weixin.qq.com/doc/service/guide/product/message/Batch_Sends.html)
- **留言管理 API 文档 (comment/list)**：
  👉 [微信官方文档 · 图文消息留言管理](https://developers.weixin.qq.com/doc/offiaccount/Comments_management/Image_Comments_Management_Interface.html)
- **第三方平台代公众号授权文档 (刷新 Access Token)**：
  👉 [微信官方文档 · 授权方凭证获取与刷新](https://developers.weixin.qq.com/doc/oplatform/Third-party_Platforms/2.0/api/ThirdParty/token/api_authorizer_token.html)
