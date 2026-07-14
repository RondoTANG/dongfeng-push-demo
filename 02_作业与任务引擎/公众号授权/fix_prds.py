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

# Fix MD file
md_content = read_file(md_path)

md_content = md_content.replace(
    '**文章元数据获取机制 (ArticleUrl 抓取)：**\n由于微信未提供根据 URL 查询文章详情的直接 API',
    '### 4.3 文章元数据获取机制 (ArticleUrl 抓取 - 仅限群发文章)\n\n对于群发（MASSSENDJOBFINISH）事件，由于微信未提供根据 URL 查询文章详情的直接 API'
)

md_content = md_content.replace(
    '### 4.3 获取已发布文章列表 API (主动同步)',
    '### 4.4 获取已发布文章列表 API (主动同步)'
)

api_examples_md = """
**请求参数示例：**
```json
{
  "offset": 0,
  "count": 20,
  "no_content": 1
}
```
*(注: `no_content: 1` 表示不返回冗长的 HTML 正文，只获取 metadata)*

**成功响应示例：**
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
            "title": "文章标题",
            "author": "作者",
            "digest": "文章摘要",
            "content": "",
            "content_source_url": "来源链接",
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

**关键返回字段：**"""
md_content = md_content.replace(
    '**请求参数示例：**\n```json\n{\n  "offset": 0,\n  "count": 20\n}\n```\n**关键返回字段：**',
    api_examples_md
)
write_file(md_path, md_content)


# Fix HTML file
html_content = read_file(html_path)

html_content = html_content.replace(
    '<h3>4.3 文章元数据获取机制 (ArticleUrl 抓取)</h3>',
    '<h3>4.3 文章元数据获取机制 (ArticleUrl 抓取 - 仅限群发文章)</h3>'
)

html_content = html_content.replace(
    '微信官方未提供通过接口获取群发详情的 API，因此系统通过向 ArticleUrl 发送轻量级请求抓取页面元信息',
    '对于群发（MASSSENDJOBFINISH）事件，微信官方未提供通过接口获取详情的 API，因此系统需要通过向 ArticleUrl 发送轻量级请求抓取页面元信息'
)

# Find if 4.4 is in HTML already. If not, insert it before section 5.
if '4.3 获取已发布文章列表 API' in html_content:
    # This was inserted by previous script if it ever worked, but we know it failed
    html_content = html_content.replace('4.3 获取已发布文章列表 API', '4.4 获取已发布文章列表 API')
else:
    # We need to insert it.
    api_html_section = """
            <h3>4.4 获取已发布文章列表 API (主动同步)</h3>
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
                    <td><strong>获取已发布文章的完整元数据</strong>。官方接口直接下发了文章标题、摘要、封面和 URL，系统<strong>不需要走任何爬虫逻辑</strong>，直接解析 JSON 即可。</td>
                </tr>
            </table>
            <p><strong>请求参数示例：</strong></p>
            <pre><code>{
  "offset": 0,
  "count": 20,
  "no_content": 1
}</code></pre>
            <p><em>(注: <code>no_content: 1</code> 表示不返回冗长的 HTML 正文，只获取 metadata)</em></p>

            <p><strong>成功响应示例：</strong></p>
            <pre><code>{
  "total_count": 1,
  "item_count": 1,
  "item": [
    {
      "article_id": "ARTICLE_ID",
      "content": {
        "news_item": [
          {
            "title": "文章标题",
            "author": "作者",
            "digest": "文章摘要",
            "content": "",
            "content_source_url": "来源链接",
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
}</code></pre>
            <p><strong>关键返回字段：</strong></p>
            <ul>
                <li><code>item[].article_id</code>：文章标识（类似 MsgID 的作用）</li>
                <li><code>item[].content.news_item[].url</code>：文章永久链接</li>
                <li><code>item[].content.news_item[].title</code>：文章标题</li>
            </ul>
"""
    # Try inserting before "        <!-- 5. 数据模型 -->"
    if '<!-- 5. 数据模型 -->' in html_content:
        # We need to put it inside the section4, before section4 closes.
        html_content = html_content.replace('        </section>\n\n        <!-- 5. 数据模型 -->', api_html_section + '\n        </section>\n\n        <!-- 5. 数据模型 -->')

write_file(html_path, html_content)
