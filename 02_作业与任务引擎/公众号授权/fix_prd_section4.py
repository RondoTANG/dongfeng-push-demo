import re

md_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.md'
html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'

with open(md_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace section 4 completely
start_marker = "## 4. 微信接口与交互对照表"
end_marker = "## 5. 本地数据模型设计"
start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

new_section4 = """## 4. 微信接口与交互对照表

| 业务场景 | 微信机制 | 护卫军系统应对方式 |
|---------|---------|------------------|
| Token 失效 | `authorizer_access_token` 两小时过期 | 定时任务 / 懒加载刷新，持久化存入 `accounts.json` |
| 公众号群发 | 事件推送 `MASSSENDJOBFINISH` | 接收 XML，解析 `ArticleUrl`，发送 HTTP 请求抓取页面获取标题/摘要/封面 |
| 公众号发布 | 事件推送 `PUBLISHJOBFINISH` | 接收 XML，获取 `article_id`，调用 `freepublish/batchget` 或直接使用自带 URL |
| 历史数据同步 | 历史群发/发布查询 | 调用 `freepublish/batchget` API 主动拉取已发布文章 |

### 4.1 授权凭证管理 — 刷新 Access Token

**(保持原样，通过 component 授权体系获取)**
...

### 4.2 群发事件接收 — MASSSENDJOBFINISH (仅限服务号/订阅号群发)

**说明：** 该事件仅在公众号执行“群发 (Mass Send)”操作完成后推送。

| 字段 | 值 |
|------|-----|
| **接收 URL** | `https://api.huweijun.com/v1/wechat/events/$APPID$` |
| **方法** | POST |
| **格式** | XML |
| **官方文档** | [微信官方文档 · 群发消息结果推送](https://developers.weixin.qq.com/doc/service/guide/product/message/Batch_Sends.html) |

**XML 报文示例：**
```xml
<xml>
  <ToUserName><![CDATA[gh_dongfeng]]></ToUserName>
  <FromUserName><![CDATA[o_admin_id]]></FromUserName>
  <CreateTime>1778483734</CreateTime>
  <MsgType><![CDATA[event]]></MsgType>
  <Event><![CDATA[MASSSENDJOBFINISH]]></Event>
  <MsgID>1000001625</MsgID>
  <Status><![CDATA[sendsuccess]]></Status>
  <ArticleUrlResult>
    <Count>1</Count>
    <ResultList>
      <item>
        <ArticleIdx>1</ArticleIdx>
        <ArticleUrl><![CDATA[https://mp.weixin.qq.com/s/xxx]]></ArticleUrl>
      </item>
    </ResultList>
  </ArticleUrlResult>
</xml>
```
**说明：**
群发事件的 XML 中包含 `ArticleUrlResult` 节点。后续系统需要提取 `ArticleUrl` 并通过网页爬虫抓取标题、摘要和封面。

### 4.3 普通发布事件接收 — PUBLISHJOBFINISH (已发布文章)

**说明：** 该事件在公众号执行普通的“发布 (Publish)”操作完成后推送。

| 字段 | 值 |
|------|-----|
| **接收 URL** | 同上 |
| **方法** | POST |
| **格式** | XML |
| **官方文档** | [微信官方文档 · 发布结果事件推送](https://developers.weixin.qq.com/doc/service/guide/product/publish.html) |

**XML 报文示例：**
```xml
<xml>
  <ToUserName><![CDATA[gh_dongfeng]]></ToUserName>
  <FromUserName><![CDATA[o_admin_id]]></FromUserName>
  <CreateTime>1600000000</CreateTime>
  <MsgType><![CDATA[event]]></MsgType>
  <Event><![CDATA[PUBLISHJOBFINISH]]></Event>
  <PublishEventInfo>
    <publish_id>100000001</publish_id>
    <publish_status>0</publish_status>
    <article_id><![CDATA[ARTICLE_ID]]></article_id>
    <article_detail>
      <count>1</count>
      <item>
        <idx>1</idx>
        <article_url><![CDATA[https://mp.weixin.qq.com/s/xxx]]></article_url>
      </item>
    </article_detail>
  </PublishEventInfo>
</xml>
```
**说明：**
发布事件的 XML 结构是 `PublishEventInfo`，包含 `article_id`。系统收到此事件后，为了获取完整的文章元数据（标题、封面等），直接调用下方的 **4.5 获取已发布文章列表 API**，无需使用爬虫。

### 4.4 文章元数据获取机制 (网页抓取 - 仅限群发文章)

对于**群发**（MASSSENDJOBFINISH）事件，由于微信未提供根据 URL 查询文章详情的直接 API，系统接收到 `ArticleUrl` 后：
1. 发送 HTTP GET 请求抓取页面。
2. 解析 HTML 中的标准 Open Graph (OG) 属性及 JS 变量：
   - 标题：`og:title` 或 JS 变量 `msg_title` / H1 标签内容。
   - 封面：`og:image` 或 JS 变量 `msg_cdn_url`。
   - 摘要：`og:description` 或 JS 变量 `msg_desc`。
   - 发布时间：提取 HTML 中全局 JS 变量 `ct` 对应的秒级时间戳。

### 4.5 获取已发布文章列表 API (主动同步 & 替代爬虫)

**说明：** 专门针对“已发布文章”（非群发）的接口，无需走网页爬虫逻辑即可获取完整结构化数据。

| 字段 | 值 |
|------|-----|
| **接口 URL** | `https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={TOKEN}` |
| **方法** | POST |
| **官方文档** | [微信官方文档 · 获取成功发布列表](https://developers.weixin.qq.com/doc/service/api/public/api_freepublish_batchget.html) |

**请求示例 (Request)：**
```json
{
  "offset": 0,
  "count": 20,
  "no_content": 1
}
```
*(注: `no_content: 1` 表示不返回冗长的 HTML 正文，只获取 metadata)*

**成功响应示例 (Response)：**
```json
{
  "total_count": 1,
  "item_count": 1,
  "item": [
    {
      "article_id": "ARTICLE_ID",
      "content": {
        "news_item": [
          {
            "title": "护卫军文章标题",
            "author": "作者",
            "digest": "文章摘要描述",
            "content": "",
            "content_source_url": "",
            "thumb_media_id": "MEDIA_ID",
            "show_cover_pic": 1,
            "url": "https://mp.weixin.qq.com/s/xxx",
            "is_deleted": false
          }
        ],
        "create_time": 1568202561,
        "update_time": 1568202561
      },
      "update_time": 1568202561
    }
  ]
}
```

---

"""

content = content[:start_idx] + new_section4 + content[end_idx:]

with open(md_path, 'w', encoding='utf-8') as f:
    f.write(content)

