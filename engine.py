import time
import logging
import random
import os
from storage import StorageManager
from wechat_api import WeChatClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MonitorEngine:
    def __init__(self, base_path):
        self.storage = StorageManager(base_path)
        self.interval = 30 # 演示目的，设为 30 秒轮询一次

    def process_wechat_event(self, xml_payload):
        """
        接收并处理微信推送的 XML 事件 (MASSSENDJOBFINISH)
        """
        logging.info("收到微信服务器事件推送，开始解析 XML 报文...")
        event_data = WeChatClient.parse_mass_send_event(xml_payload)
        
        if not event_data:
            logging.warning("XML 报文解析失败，或非群发完成事件。")
            return "fail"
        
        msg_id = event_data["msg_id"]
        status = event_data["status"]
        articles = event_data["articles"]
        
        logging.info(f"解析成功：MsgID={msg_id}, 群发状态={status}, 包含图文数={len(articles)}")
        
        if status != "sendsuccess":
            logging.warning(f"群发状态非成功状态 ({status})，跳过作业生成。")
            return "success" # 状态非成功也回复 success，避免微信重试

        # 加载本地已授权账号列表，用来匹配公众号昵称
        accounts = self.storage.load_accounts()
        account_map = {acc.get('original_id', 'gh_dongfeng'): acc['nickname'] for acc in accounts}
        # 如果 mock 账号没有 original_id，也做下兼容
        for acc in accounts:
            account_map[acc['appid']] = acc['nickname']

        # 获取 ToUserName 查找账号昵称
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml_payload)
            to_user_name = root.findtext('ToUserName') or "gh_dongfeng"
        except:
            to_user_name = "gh_dongfeng"

        account_name = account_map.get(to_user_name, "东风汽车(官方)")

        # 遍历图文列表，生成作业
        for item in articles:
            url = item["url"]
            idx = item["article_idx"]
            
            logging.info(f"正在通过 ArticleUrl 抓取第 {idx} 篇图文详情: {url}")
            
            # 调用 wechat_api.py 中的抓取解析方法
            meta = WeChatClient.fetch_article_meta(url)
            if not meta:
                logging.error(f"抓取文章元数据失败: {url}")
                continue
            
            # 实例化 WeChatClient 拉取评论
            client = WeChatClient(
                authorizer_appid="wx4f2a3b4c5d6e7f89", # 默认 appid
                refresh_token="mock_refresh",
                component_appid="wx_component_123",
                component_access_token="comp_token_abc"
            )
            # 拉取评论
            comments = client.get_comments(msg_id, index=idx-1)
            
            # 组装作业数据
            job = {
                "article_id": f"{msg_id}_{idx}",
                "account_name": account_name,
                "title": meta["title"],
                "url": url,
                "digest": meta["digest"],
                "thumb": meta["thumb"],
                "publish_time": meta["publish_time"],
                "comments_count": len(comments),
                "comments": comments,
                "status": "pending_review",
                "fetched_at": int(time.time())
            }
            
            # 保存作业并执行全局去重校验 (根据 url)
            if self.storage.save_job(job):
                logging.info(f"🎉 发现新群发内容:《{meta['title']}》，去重校验通过，已成功生成监控作业！")
            else:
                logging.info(f"⚠️ 文章已存在（URL去重拦截）:《{meta['title']}》，静默丢弃，避免重复创建作业。")
                
        return "success"

    def run_once(self):
        logging.info("========================================")
        logging.info("开始执行一轮公众号事件感知监控模拟...")
        
        # 确保至少有一个测试账号
        accounts = self.storage.load_accounts()
        if not accounts:
            self._add_test_account()
            
        # 模拟微信群发事件，在演示和真实 URL 之间交替，方便测试去重与网络抓取
        demo_urls = [
            "https://mp.weixin.qq.com/s/V68C0ZlX1qQ63cPl8D1LdQ",  # 真实的微信公开文章
            "https://mp.weixin.qq.com/s/mock_article_111",
            "https://mp.weixin.qq.com/s/mock_article_222"
        ]
        
        chosen_url = random.choice(demo_urls)
        # MsgID 可以随机，但在演示中，若 chosen_url 重复，应能成功触发去重
        msg_id = "100000" + str(random.randint(1000, 9999))
        
        xml_template = f"""<xml>
  <ToUserName><![CDATA[gh_dongfeng]]></ToUserName>
  <FromUserName><![CDATA[o_admin_id]]></FromUserName>
  <CreateTime>{int(time.time())}</CreateTime>
  <MsgType><![CDATA[event]]></MsgType>
  <Event><![CDATA[MASSSENDJOBFINISH]]></Event>
  <MsgID>{msg_id}</MsgID>
  <Status><![CDATA[sendsuccess]]></Status>
  <ArticleUrlResult>
    <Count>1</Count>
    <ResultList>
      <item>
        <ArticleIdx>1</ArticleIdx>
        <ArticleUrl><![CDATA[{chosen_url}]]></ArticleUrl>
      </item>
    </ResultList>
  </ArticleUrlResult>
</xml>"""

        # 触发核心处理链路
        self.process_wechat_event(xml_template)

    def _add_test_account(self):
        test_acc = {
            "appid": "wx4f2a3b4c5d6e7f89",
            "original_id": "gh_dongfeng",
            "nickname": "东风汽车",
            "refresh_token": "mock_refresh_token_xyz",
            "authorized_at": int(time.time())
        }
        self.storage.save_accounts([test_acc])
        logging.info("已自动添加演示账号 [东风汽车] (original_id: gh_dongfeng)")

    def start(self):
        try:
            while True:
                self.run_once()
                logging.info(f"单次感知演练结束，等待 {self.interval} 秒后模拟下一次微信群发...")
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logging.info("监控引擎已手动停止。")

if __name__ == "__main__":
    import os
    base_path = os.path.dirname(os.path.abspath(__file__))
    engine = MonitorEngine(base_path)
    engine.run_once()
