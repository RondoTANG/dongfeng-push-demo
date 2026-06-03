import requests
import re
import html
import time
import json

def test_fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    }
    print(f"\n正在抓取 URL: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"HTTP 状态码: {resp.status_code}")
        if resp.status_code != 200:
            print("抓取失败！")
            return None
            
        html_content = resp.text
        print(f"网页内容大小: {len(html_content)} 字节")
        
        # 1. 尝试从 meta property="og:..." 中提取
        title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html_content)
        image_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html_content)
        desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html_content)
        ct_match = re.search(r'var\s+ct\s*=\s*["\'](\d+)["\']', html_content)
        
        # 2. 如果 og 匹配失败，尝试微信特定的 js 变量（微信文章经常在 js 中定义变量）
        if not title_match:
            title_match = re.search(r'var\s+msg_title\s*=\s*["\']([^"\']+)["\']', html_content)
        if not image_match:
            image_match = re.search(r'var\s+msg_cdn_url\s*=\s*["\']([^"\']+)["\']', html_content)
        if not desc_match:
            desc_match = re.search(r'var\s+msg_desc\s*=\s*["\']([^"\']+)["\']', html_content)
            
        # 3. 尝试从 h1.rich_media_title 中提取标题
        if not title_match:
            title_h1 = re.search(r'<h1\s+class=["\']rich_media_title["\'][^>]*>\s*([^<]+)\s*</h1>', html_content)
            if title_h1:
                title = title_h1.group(1).strip()
            else:
                title = None
        else:
            title = title_match.group(1)
            
        image = image_match.group(1) if image_match else "未获取到封面"
        desc = desc_match.group(1) if desc_match else "未获取到摘要"
        
        publish_time = int(ct_match.group(1)) if ct_match else None
        
        if title:
            title = html.unescape(title)
        if desc:
            desc = html.unescape(desc)
            
        print(f"解析结果:")
        print(f"  - 标题: {title}")
        print(f"  - 封面: {image}")
        print(f"  - 摘要: {desc}")
        print(f"  - 时间戳: {publish_time} (格式化: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(publish_time)) if publish_time else '未知'})")
        
        return {
            "title": title,
            "thumb": image,
            "digest": desc,
            "publish_time": publish_time
        }
    except Exception as e:
        print(f"抓取或解析异常: {e}")
        return None

if __name__ == "__main__":
    urls = [
        "https://mp.weixin.qq.com/s/EYvk7USdgr9RurrntZd25w",
        "https://mp.weixin.qq.com/s/yth4d3Y0jazb_JOAYwgsqA",
        "https://mp.weixin.qq.com/s/p9CtDvLa73YKlpO6IhiPnw"
    ]
    for url in urls:
        test_fetch(url)
