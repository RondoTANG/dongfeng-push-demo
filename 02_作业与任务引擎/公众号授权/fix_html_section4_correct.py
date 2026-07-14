import re

html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'

with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to replace section 4 entirely
pattern = re.compile(r'(<section id="section4">.*?</section>)\s*(?=<!-- 5\. 本地数据模型设计 -->)', re.DOTALL)

new_section4 = """<section id="section4">
            <h2>4. 微信接口与交互对照表 (V1.0)</h2>

            <table>
                <thead>
                    <tr>
                        <th>业务场景</th>
                        <th>微信机制</th>
                        <th>护卫军系统应对方式</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Token 失效</td>
                        <td><code>authorizer_access_token</code> 两小时过期</td>
                        <td>定时任务 / 懒加载刷新，持久化存入 <code>accounts.json</code></td>
                    </tr>
                    <tr>
                        <td>公众号群发</td>
                        <td>事件推送 <code>MASSSENDJOBFINISH</code></td>
                        <td>接收 XML，解析 <code>ArticleUrl</code>，发送 HTTP 请求抓取页面获取标题/摘要/封面</td>
                    </tr>
                    <tr>
                        <td>公众号发布</td>
                        <td>事件推送 <code>PUBLISHJOBFINISH</code></td>
                        <td>接收 XML，获取 <code>article_id</code>，调用 <code>freepublish/batchget</code> 官方接口</td>
                    </tr>
                    <tr>
                        <td>历史数据同步</td>
                        <td>历史群发/发布查询</td>
                        <td>调用 <code>freepublish/batchget</code> API 主动拉取已发布文章</td>
                    </tr>
                </tbody>
            </table>

            <h3>4.1 授权凭证管理 — 刷新 Access Token</h3>
            <p><strong>(保持原样，通过 component 授权体系获取)</strong></p>

            <h3>4.2 群发事件接收 — MASSSENDJOBFINISH (仅限服务号/订阅号群发)</h3>
            <p><strong>说明：</strong> 该事件仅在公众号执行“群发 (Mass Send)”操作完成后推送。</p>
            <table>
                <tr>
                    <td style="width: 25%;"><strong>接收 URL</strong></td>
                    <td><code>https://api.huweijun.com/v1/wechat/events/$APPID$</code></td>
                </tr>
                <tr>
                    <td><strong>方法</strong></td>
                    <td>POST</td>
                </tr>
                <tr>
                    <td><strong>格式</strong></td>
                    <td>XML</td>
                </tr>
                <tr>
                    <td><strong>官方文档</strong></td>
                    <td><a href="https://developers.weixin.qq.com/doc/service/guide/product/message/Batch_Sends.html" target="_blank">微信官方文档 · 群发消息结果推送</a></td>
                </tr>
            </table>

            <h4>XML 报文示例：</h4>
            <pre><code>&lt;xml&gt;
  &lt;ToUserName&gt;&lt;![CDATA[gh_dongfeng]]&gt;&lt;/ToUserName&gt;
  &lt;FromUserName&gt;&lt;![CDATA[o_admin_id]]&gt;&lt;/FromUserName&gt;
  &lt;CreateTime&gt;1778483734&lt;/CreateTime&gt;
  &lt;MsgType&gt;&lt;![CDATA[event]]&gt;&lt;/MsgType&gt;
  &lt;Event&gt;&lt;![CDATA[MASSSENDJOBFINISH]]&gt;&lt;/Event&gt;
  &lt;MsgID&gt;1000001625&lt;/MsgID&gt;
  &lt;Status&gt;&lt;![CDATA[sendsuccess]]&gt;&lt;/Status&gt;
  &lt;ArticleUrlResult&gt;
    &lt;Count&gt;1&lt;/Count&gt;
    &lt;ResultList&gt;
      &lt;item&gt;
        &lt;ArticleIdx&gt;1&lt;/ArticleIdx&gt;
        &lt;ArticleUrl&gt;&lt;![CDATA[https://mp.weixin.qq.com/s/xxx]]&gt;&lt;/ArticleUrl&gt;
      &lt;/item&gt;
    &lt;/ResultList&gt;
  &lt;/ArticleUrlResult&gt;
&lt;/xml&gt;</code></pre>
            <p><strong>说明：</strong> 群发事件的 XML 中包含 <code>ArticleUrlResult</code> 节点。系统需提取 <code>ArticleUrl</code> 并通过网页爬虫抓取标题、摘要和封面。</p>

            <h3>4.3 普通发布事件接收 — PUBLISHJOBFINISH (已发布文章)</h3>
            <p><strong>说明：</strong> 该事件在公众号执行普通的“发布 (Publish)”操作完成后推送。</p>
            <table>
                <tr>
                    <td style="width: 25%;"><strong>接收 URL</strong></td>
                    <td>同上</td>
                </tr>
                <tr>
                    <td><strong>方法</strong></td>
                    <td>POST</td>
                </tr>
                <tr>
                    <td><strong>格式</strong></td>
                    <td>XML</td>
                </tr>
                <tr>
                    <td><strong>官方文档</strong></td>
                    <td><a href="https://developers.weixin.qq.com/doc/service/guide/product/publish.html" target="_blank">微信官方文档 · 发布结果事件推送</a></td>
                </tr>
            </table>

            <h4>XML 报文示例：</h4>
            <pre><code>&lt;xml&gt;
  &lt;ToUserName&gt;&lt;![CDATA[gh_dongfeng]]&gt;&lt;/ToUserName&gt;
  &lt;FromUserName&gt;&lt;![CDATA[o_admin_id]]&gt;&lt;/FromUserName&gt;
  &lt;CreateTime&gt;1600000000&lt;/CreateTime&gt;
  &lt;MsgType&gt;&lt;![CDATA[event]]&gt;&lt;/MsgType&gt;
  &lt;Event&gt;&lt;![CDATA[PUBLISHJOBFINISH]]&gt;&lt;/Event&gt;
  &lt;PublishEventInfo&gt;
    &lt;publish_id&gt;100000001&lt;/publish_id&gt;
    &lt;publish_status&gt;0&lt;/publish_status&gt;
    &lt;article_id&gt;&lt;![CDATA[ARTICLE_ID]]&gt;&lt;/article_id&gt;
    &lt;article_detail&gt;
      &lt;count&gt;1&lt;/count&gt;
      &lt;item&gt;
        &lt;idx&gt;1&lt;/idx&gt;
        &lt;article_url&gt;&lt;![CDATA[https://mp.weixin.qq.com/s/xxx]]&gt;&lt;/article_url&gt;
      &lt;/item&gt;
    &lt;/article_detail&gt;
  &lt;/PublishEventInfo&gt;
&lt;/xml&gt;</code></pre>
            <p><strong>说明：</strong> 发布事件的 XML 包含 <code>article_id</code>。收到事件后直接调用下方的 <strong>4.5 获取已发布文章列表 API</strong> 获取元数据，无需使用爬虫。</p>

            <h3>4.4 文章元数据获取机制 (网页抓取 - 仅限群发文章)</h3>
            <p>对于<strong>群发</strong>（MASSSENDJOBFINISH）事件，系统接收到 <code>ArticleUrl</code> 后：</p>
            <ol>
                <li>发送 HTTP GET 请求抓取页面。</li>
                <li>解析 HTML 中的标准 Open Graph (OG) 属性及 JS 变量：
                    <ul>
                        <li>标题：<code>og:title</code> 或 JS 变量 <code>msg_title</code></li>
                        <li>封面：<code>og:image</code> 或 JS 变量 <code>msg_cdn_url</code></li>
                        <li>摘要：<code>og:description</code> 或 JS 变量 <code>msg_desc</code></li>
                        <li>发布时间：提取 JS 变量 <code>ct</code></li>
                    </ul>
                </li>
            </ol>

            <h3>4.5 获取已发布文章列表 API (主动同步 & 替代爬虫)</h3>
            <p><strong>说明：</strong> 专门针对“已发布文章”（非群发）的接口，无需走网页爬虫逻辑即可获取完整结构化数据。</p>
            <table>
                <tr>
                    <td style="width: 25%;"><strong>接口 URL</strong></td>
                    <td><code>https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={TOKEN}</code></td>
                </tr>
                <tr>
                    <td><strong>方法</strong></td>
                    <td>POST</td>
                </tr>
                <tr>
                    <td><strong>官方文档</strong></td>
                    <td><a href="https://developers.weixin.qq.com/doc/service/api/public/api_freepublish_batchget.html" target="_blank">微信官方文档 · 获取成功发布列表</a></td>
                </tr>
            </table>

            <h4>请求参数示例 (Request)：</h4>
            <pre><code>{
  "offset": 0,
  "count": 20,
  "no_content": 1
}</code></pre>
            <p><em>(注: <code>no_content: 1</code> 表示不返回冗长的 HTML 正文，只获取 metadata)</em></p>

            <h4>成功响应示例 (Response)：</h4>
            <pre><code>{
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
}</code></pre>

        </section>"""

content = pattern.sub(new_section4, content)

# Check if the bad injection exists at the end and remove it
bad_html_pattern = re.compile(r'</html><h2 id="4-微信接口与交互对照表">.*', re.DOTALL)
content = bad_html_pattern.sub('</html>', content)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)
