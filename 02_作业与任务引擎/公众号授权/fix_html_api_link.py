import re

html_path = '/Users/RondoT/Documents/护卫军相关/02_作业与任务引擎/公众号授权/technical_prd.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

target = """                <tr>
                    <td><strong>请求方法</strong></td>
                    <td>POST</td>
                </tr>
                <tr>
                    <td><strong>功能用途</strong></td>"""

replacement = """                <tr>
                    <td><strong>请求方法</strong></td>
                    <td>POST</td>
                </tr>
                <tr>
                    <td><strong>官方文档</strong></td>
                    <td><a href="https://developers.weixin.qq.com/doc/service/api/public/api_freepublish_batchget.html" target="_blank">微信官方文档 · 获取成功发布列表</a></td>
                </tr>
                <tr>
                    <td><strong>功能用途</strong></td>"""

html_content = html_content.replace(target, replacement)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)
