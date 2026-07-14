import re
import os

md_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.md'
html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

md_content = read_file(md_path)

replacements = [
    ('群发事件实时捕获', '群发及发布事件实时捕获'),
    ('**群发内容毫秒感知** | 公众号运营后台执行群发，系统通过 Webhook 推送毫秒级感知。', '**群发与发布内容感知** | 公众号运营后台执行群发或正常发布，系统通过 Webhook 毫秒级感知，同时支持官方 API 获取已发布文章。'),
    ('`MASSSENDJOBFINISH`（群发结束）推送', '`MASSSENDJOBFINISH`（群发）与 `PUBLISHJOBFINISH`（发布）推送'),
    ('当任何已授权的子品牌公众号群发文章时', '当任何已授权的子品牌公众号群发或发布文章时'),
    ('事件（如群发结束事件 `MASSSENDJOBFINISH`）', '事件（如群发 `MASSSENDJOBFINISH` 及发布 `PUBLISHJOBFINISH`）'),
    ('公众号运营者<br/>微信后台群发', '公众号运营者<br/>微信后台群发/发布'),
    ('群发完成', '群发/发布完成'),
    ('MASSSENDJOBFINISH<br/>XML 推送', 'MASSSENDJOBFINISH / PUBLISHJOBFINISH<br/>XML 推送'),
    ('“群发（Mass Send）”场景。', '“群发（Mass Send）”与“发布（Publish）”场景。'),
    ('群发完成即时推送', '群发/发布完成即时推送'),
    ('4.2 群发事件接收 — MASSSENDJOBFINISH', '4.2 群发与发布事件接收 — MASSSENDJOBFINISH / PUBLISHJOBFINISH'),
    ('XML 报文结构：', 'XML 报文结构示例 (群发/发布类似)：'),
    ('接收 `MASSSENDJOBFINISH` 事件推送', '接收 `MASSSENDJOBFINISH` 与 `PUBLISHJOBFINISH` 事件推送'),
    ('Webhook 接收 MASSSENDJOBFINISH → 解析', 'Webhook 接收 MASSSENDJOBFINISH / PUBLISHJOBFINISH → 解析'),
    ('接收微信 `MASSSENDJOBFINISH` 推送的 HTTP 网关服务', '接收微信 `MASSSENDJOBFINISH` / `PUBLISHJOBFINISH` 推送的 HTTP 网关服务')
]

for old, new in replacements:
    md_content = md_content.replace(old, new)

api_section = """
### 4.3 获取已发布文章列表 API (主动同步)

| 字段 | 值 |
|------|-----|
| **接口 URL** | `https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={TOKEN}` |
| **方法** | POST |
| **用途** | 获取公众号已成功发布的图文列表（包含非群发的普通发布文章）。用于同步历史文章及作为推送异常时的兜底对账机制。 |

**请求参数示例：**
```json
{
  "offset": 0,
  "count": 20
}
```
**关键返回字段：**
- `item[].article_id`：文章标识（类似 MsgID 的作用）
- `item[].content.news_item[].url`：文章永久链接
- `item[].content.news_item[].title`：文章标题
"""

md_content = md_content.replace('---\n\n## 5. 数据模型', api_section + '\n---\n\n## 5. 数据模型')

write_file(md_path, md_content)


html_content = read_file(html_path)

html_replacements = [
    ('群发事件实时捕获', '群发及发布事件实时捕获'),
    ('<strong>群发内容毫秒感知</strong></td>\n                        <td>公众号运营后台执行群发，系统通过 Webhook 推送毫秒级感知。', '<strong>群发与发布内容感知</strong></td>\n                        <td>公众号运营后台执行群发或正常发布，系统通过 Webhook 毫秒级感知，同时支持官方 API 获取已发布文章。'),
    ('<code>MASSSENDJOBFINISH</code>（群发结束）推送', '<code>MASSSENDJOBFINISH</code>（群发）与 <code>PUBLISHJOBFINISH</code>（发布）推送'),
    ('当任何已授权的子品牌公众号群发文章时', '当任何已授权的子品牌公众号群发或发布文章时'),
    ('事件（如群发结束事件 <code>MASSSENDJOBFINISH</code>）', '事件（如群发 <code>MASSSENDJOBFINISH</code> 及发布 <code>PUBLISHJOBFINISH</code>）'),
    ('公众号运营者<br/>微信后台群发', '公众号运营者<br/>微信后台群发/发布'),
    ('群发完成', '群发/发布完成'),
    ('MASSSENDJOBFINISH<br/>XML 推送', 'MASSSENDJOBFINISH / PUBLISHJOBFINISH<br/>XML 推送'),
    ('“群发（Mass Send）”场景。', '“群发（Mass Send）”与“发布（Publish）”场景。'),
    ('群发完成即时推送', '群发/发布完成即时推送'),
    ('4.2 群发事件接收 — MASSSENDJOBFINISH', '4.2 群发与发布事件接收 — MASSSENDJOBFINISH / PUBLISHJOBFINISH'),
    ('XML 报文结构示例：', 'XML 报文结构示例 (群发/发布类似)：'),
]

for old, new in html_replacements:
    html_content = html_content.replace(old, new)

api_html_section = """
            <h3>4.3 获取已发布文章列表 API (主动同步)</h3>
            <table>
                <tr>
                    <td style="width: 25%;"><strong>接口 URL</strong></td>
                    <td><code>https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={TOKEN}</code></td>
                </tr>
                <tr>
                    <td><strong>请求方法</strong></td>
                    <td>POST</td>
                </tr>
                <tr>
                    <td><strong>功能用途</strong></td>
                    <td>获取公众号已成功发布的图文列表（包含非群发的普通发布文章）。用于同步历史文章及作为推送异常时的兜底对账机制。</td>
                </tr>
            </table>
            <p><strong>请求参数示例：</strong></p>
            <pre><code>{
  "offset": 0,
  "count": 20
}</code></pre>
"""

html_content = html_content.replace('</section>\n\n        <!-- 5. 数据模型 -->', api_html_section + '\n        </section>\n\n        <!-- 5. 数据模型 -->')

write_file(html_path, html_content)
