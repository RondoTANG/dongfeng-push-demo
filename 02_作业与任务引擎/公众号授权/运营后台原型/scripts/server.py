import http.server
import socketserver
import json
import os
import glob
import re
import subprocess
import urllib.parse

PORT = 8000
DIRECTORY = os.getcwd()

class PinEditHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # 允许跨域，方便调试
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/update_pin':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                pin_key = data.get('key')
                pin_data = data.get('data') # 包含 title, definition, dataSource, logic, interaction, fields
                
                if not pin_key or not pin_data:
                    self.send_error_response(400, "Missing key or data")
                    return
                
                success = self.update_markdown_file(pin_key, pin_data)
                
                if success:
                    # 重新构建 annotations.js
                    try:
                        subprocess.run(['python3', 'scripts/build.py'], check=True)
                        self.send_success_response({"status": "success", "message": "Markdown updated and annotations rebuilt."})
                    except Exception as e:
                        self.send_error_response(500, f"Updated Markdown but failed to rebuild: {str(e)}")
                else:
                    self.send_error_response(404, f"Pin key {pin_key} not found in any Markdown file.")
                    
            except json.JSONDecodeError:
                self.send_error_response(400, "Invalid JSON")
            except Exception as e:
                self.send_error_response(500, str(e))
        else:
            self.send_error_response(404, "Not Found")

    def send_success_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": message}).encode('utf-8'))

    def update_markdown_file(self, pin_key, new_data):
        # 扫描所有 .md 文件
        md_files = glob.glob('docs/**/*.md', recursive=True)
        
        for file_path in md_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 寻找对应的图钉区块: ### 📍 图钉批注：[key]
            # 匹配到下一个 ### 📍 或者文件末尾
            pattern = re.compile(rf'(### 📍 图钉批注：\[{re.escape(pin_key)}\].*?)(?=### 📍 图钉批注：\[|\Z)', re.DOTALL)
            match = pattern.search(content)
            
            if match:
                original_block = match.group(1)
                
                # 构建新的 block
                new_block = f"### 📍 图钉批注：[{pin_key}]\n"
                new_block += f"- **功能名称**：{new_data.get('title', '')}\n"
                new_block += f"- **功能定义**：{new_data.get('definition', '')}\n"
                new_block += f"- **数据来源**：{new_data.get('dataSource', '')}\n"
                new_block += f"- **取值逻辑**：{new_data.get('logic', '')}\n"
                new_block += f"- **交互说明**：{new_data.get('interaction', '')}\n"
                new_block += f"- **字段说明**：{new_data.get('fields', '')}\n\n"
                
                # 替换内容
                new_content = content[:match.start()] + new_block + content[match.end():]
                
                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                return True
                
        return False

if __name__ == "__main__":
    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", PORT), PinEditHandler) as httpd:
        print(f"🚀 PM Engineering Server is running at http://localhost:{PORT}")
        print("  - Serving static files")
        print("  - API /api/update_pin ready for local markdown sync")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
