import re

md_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.md'
html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

md_content = read_file(md_path)

replacements_md = [
    (
        '提取 ArticleUrl，去重校验后通过 HTTP 抓取解析文章标题、封面、发布时间并写入作业库。',
        '群发文章提取 URL 进行网页抓取；**已发布文章**则直接通过调用微信官方 API（freepublish/batchget）获取结构化元数据，**无需走爬虫**。'
    ),
    (
        '*   **图文信息抓取**：对公开 `ArticleUrl` 发送轻量请求，通过正则匹配兼容解析提取标题、封面、摘要与发布时间。',
        '*   **图文信息获取**：区分场景——**群发文章**通过对 URL 发送轻量请求匹配抓取；**已发布文章**调用官方接口（无爬虫损耗）直接读取结构化数据。'
    ),
    (
        'Engine->>Engine: 发送 HTTP 抓取 ArticleUrl 页面\n        Engine->>Engine: 解析 og 属性/JS 变量，解析出标题、封面、时间',
        'alt 群发场景 (MASSSENDJOBFINISH)\n            Engine->>Engine: 发送 HTTP 抓取 ArticleUrl 页面并解析 og 属性\n        else 发布场景 (PUBLISHJOBFINISH 或 主动拉取)\n            Engine->>WX: 调用官方 API (freepublish/batchget)\n            WX-->>Engine: 直接返回文章结构化元数据 (无需爬虫)\n        end'
    ),
    (
        'HTTP GET ArticleUrl -> 正则提取 og 元数据及时间变量 ct -> 写入作业',
        '群发走 HTTP GET 网页正则提取；发布走官方 API 获取 JSON -> 写入作业'
    ),
    (
        '| **用途** | 获取公众号已成功发布的图文列表（包含非群发的普通发布文章）。用于同步历史文章及作为推送异常时的兜底对账机制。 |',
        '| **用途** | **获取已发布文章的完整元数据**。官方接口直接下发了文章标题、摘要、封面和 URL，系统**不需要走任何爬虫逻辑**，用于替代原先的网页抓取，实现稳定获取。 |'
    )
]

for old, new in replacements_md:
    md_content = md_content.replace(old, new)
    
write_file(md_path, md_content)

html_content = read_file(html_path)

replacements_html = [
    (
        '提取 ArticleUrl，去重校验后通过 HTTP 抓取解析文章标题、封面、发布时间并写入作业库。',
        '群发文章提取 URL 进行网页抓取；<strong>已发布文章</strong>则直接通过调用微信官方 API（freepublish/batchget）获取结构化元数据，<strong>无需走爬虫</strong>。'
    ),
    (
        '<li><strong>图文信息抓取</strong>：对公开 <code>ArticleUrl</code> 发送轻量请求，通过正则匹配兼容解析提取标题、封面、摘要与发布时间。</li>',
        '<li><strong>图文信息获取</strong>：区分场景——<strong>群发文章</strong>通过对 URL 发送轻量请求匹配抓取；<strong>已发布文章</strong>调用官方接口（无爬虫损耗）直接读取结构化数据。</li>'
    ),
    (
        'Engine->>Engine: 发送 HTTP 抓取 ArticleUrl 页面\n        Engine->>Engine: 解析 og 属性/JS 变量，解析出标题、封面、时间',
        'alt 群发场景 (MASSSENDJOBFINISH)\n            Engine->>Engine: 发送 HTTP 抓取 ArticleUrl 页面并解析\n        else 发布场景 (PUBLISHJOBFINISH)\n            Engine->>WX: 调用官方 API 获取文章详情 (freepublish)\n            WX-->>Engine: 返回结构化数据 (无需爬虫)\n        end'
    ),
    (
        'HTTP GET ArticleUrl -&gt; 正则提取 og 元数据及时间变量 ct -&gt; 写入作业',
        '群发走网页正则提取；发布走官方 API 提取 JSON -&gt; 写入作业'
    ),
    (
        '<td>获取公众号已成功发布的图文列表（包含非群发的普通发布文章）。用于同步历史文章及作为推送异常时的兜底对账机制。</td>',
        '<td><strong>获取已发布文章的完整元数据</strong>。官方接口直接下发了文章标题、摘要、封面和 URL，系统<strong>不需要走任何爬虫逻辑</strong>，直接解析 JSON 即可。</td>'
    )
]

for old, new in replacements_html:
    html_content = html_content.replace(old, new)
    
write_file(html_path, html_content)
print("Updated PRDs")
