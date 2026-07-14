import requests
import time
import logging
import xml.etree.ElementTree as ET
import re
import html

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class WeChatClient:
    def __init__(self, authorizer_appid, refresh_token, component_appid, component_access_token):
        self.authorizer_appid = authorizer_appid
        self.refresh_token = refresh_token
        self.component_appid = component_appid
        self.component_access_token = component_access_token
        self.access_token = None
        self.expires_at = 0
        self.is_mock = True  # 默认为 Mock 模式，方便演示

    def _refresh_access_token(self):
        """用 refresh_token 刷新 authorizer_access_token"""
        if self.is_mock:
            logging.info(f"Mock: 刷新公众号 {self.authorizer_appid} 的 access_token")
            self.access_token = f"mock_access_token_{int(time.time())}"
            self.expires_at = time.time() + 7200
            return True

        url = f"https://api.weixin.qq.com/cgi-bin/component/api_authorizer_token?component_access_token={self.component_access_token}"
        payload = {
            "component_appid": self.component_appid,
            "authorizer_appid": self.authorizer_appid,
            "authorizer_refresh_token": self.refresh_token
        }
        try:
            resp = requests.post(url, json=payload).json()
            if 'authorizer_access_token' in resp:
                self.access_token = resp['authorizer_access_token']
                self.expires_at = time.time() + resp['expires_in'] - 200 # 预留缓冲时间
                return True
            else:
                logging.error(f"刷新 Token 失败: {resp}")
        except Exception as e:
            logging.error(f"刷新 Token 异常: {e}")
        return False

    def get_token(self):
        if not self.access_token or time.time() > self.expires_at:
            self._refresh_access_token()
        return self.access_token

    def get_published_articles(self, count=10):
        """获取已发布的消息列表 (freepublish/batchget)"""
        if self.is_mock:
            return self._mock_articles()

        token = self.get_token()
        url = f"https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={token}"
        payload = {"offset": 0, "count": count, "no_content": 0}
        try:
            resp = requests.post(url, json=payload).json()
            return resp.get('item', [])
        except Exception as e:
            logging.error(f"拉取文章失败: {e}")
            return []

    def get_comments(self, article_id, index=0):
        """查看指定文章的评论数据 (comment/list)"""
        if self.is_mock:
            return self._mock_comments()

        token = self.get_token()
        url = f"https://api.weixin.qq.com/cgi-bin/comment/list?access_token={token}"
        payload = {
            "msg_data_id": article_id, # 注意：微信接口字段可能根据发布方式有所不同
            "index": index,
            "begin": 0,
            "count": 50,
            "type": 0
        }
        try:
            resp = requests.post(url, json=payload).json()
            return resp.get('comment', [])
        except Exception as e:
            logging.error(f"拉取评论失败: {e}")
            return []

    def _mock_articles(self):
        return [{
            "article_id": f"mock_art_{int(time.time())}",
            "content": {
                "news_item": [{
                    "title": "东风汽车2026战略发布：全面转型新能源",
                    "author": "东风君",
                    "digest": "东风汽车今日在武汉发布最新战略，计划在2026年前实现全系车型电动化。",
                    "content_url": "https://mp.weixin.qq.com/s/example",
                    "thumb_url": "https://via.placeholder.com/100x60",
                    "create_time": int(time.time())
                }]
            }
        }]

    def _mock_comments(self):
        return [
            {"content": "支持东风！国产车加油！", "create_time": int(time.time())},
            {"content": "请问岚图追光有最新优惠政策吗？", "create_time": int(time.time()) - 300}
        ]

    @staticmethod
    def parse_mass_send_event(xml_str):
        """
        解析微信 MASSSENDJOBFINISH 事件的 XML 报文
        返回 MsgID, 状态以及文章 URL 列表
        """
        try:
            root = ET.fromstring(xml_str)
            event = root.findtext('Event')
            if event != 'MASSSENDJOBFINISH':
                return None
                
            msg_id = root.findtext('MsgID')
            status = root.findtext('Status')
            
            articles = []
            article_list_node = root.find('.//ResultList')
            if article_list_node is not None:
                for item in article_list_node.findall('item'):
                    idx = item.findtext('ArticleIdx')
                    url = item.findtext('ArticleUrl')
                    if url:
                        articles.append({
                            "article_idx": int(idx) if idx else 1,
                            "url": url
                        })
            return {
                "msg_id": msg_id,
                "status": status,
                "articles": articles
            }
        except Exception as e:
            logging.error(f"解析微信 XML 事件失败: {e}")
            return None

    @staticmethod
    def fetch_article_meta(article_url):
        """
        通过公开的 ArticleUrl 抓取微信图文网页，并用正则提取 Open Graph 元数据及发布时间。
        零依赖且高效。
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            # 抓取真实页面。若网络不通或 URL 是 mock，则返回 Mock 元数据
            if "mock" in article_url or "example" in article_url:
                raise ValueError("检测到 Mock URL，切换至演示数据")

            resp = requests.get(article_url, headers=headers, timeout=5)
            if resp.status_code != 200:
                logging.error(f"抓取文章失败，HTTP 状态码: {resp.status_code}")
                return None
            
            html_content = resp.text
            
            # 使用正则快速匹配 Open Graph 元数据与发布时间
            title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_content)
            image_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_content)
            desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html_content)
            ct_match = re.search(r'var\s+ct\s*=\s*["\'](\d+)["\']', html_content)
            
            # 兼容微信页面内 JS 变量声明
            if not title_match:
                title_match = re.search(r'var\s+msg_title\s*=\s*["\']([^"\']+)["\']', html_content)
            if not image_match:
                image_match = re.search(r'var\s+msg_cdn_url\s*=\s*["\']([^"\']+)["\']', html_content)
            if not desc_match:
                desc_match = re.search(r'var\s+msg_desc\s*=\s*["\']([^"\']+)["\']', html_content)
                
            # 兼容富文本 h1 标题
            title = None
            if title_match:
                title = title_match.group(1)
            else:
                title_h1 = re.search(r'<h1\s+class=["\']rich_media_title["\'][^>]*>\s*([^<]+)\s*</h1>', html_content)
                if title_h1:
                    title = title_h1.group(1).strip()
            
            if not title or title.strip() == "":
                raise ValueError("微信页面防采集拦截或未找到有效标题，启用兜底模拟数据")
                
            image = image_match.group(1) if image_match else ""
            desc = desc_match.group(1) if desc_match else ""
            publish_time = int(ct_match.group(1)) if ct_match else int(time.time())
            
            # 兼容微信 HTML 实体字符
            title = html.unescape(title)
            desc = html.unescape(desc)
            
            return {
                "title": title,
                "thumb": image,
                "digest": desc,
                "publish_time": publish_time
            }
        except Exception as e:
            logging.info(f"解析文章元数据（使用模拟兜底数据，原因: {e}）")
            # 模拟数据兜底
            return {
                "title": f"模拟文章-{article_url.split('/')[-1]}",
                "thumb": "https://via.placeholder.com/100x60",
                "digest": "这是通过公众号群发事件触发并抓取到的模拟文章摘要信息。",
                "publish_time": int(time.time())
            }
