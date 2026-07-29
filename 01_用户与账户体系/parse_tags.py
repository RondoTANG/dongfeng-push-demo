import zipfile
import json
import os

def print_xmind(file_path):
    print(f"--- {os.path.basename(file_path)} ---")
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            if 'content.json' in z.namelist():
                content = json.loads(z.read('content.json'))
                def extract_text(node, level=0):
                    title = node.get('title', '').strip()
                    if title:
                        print("  " * level + title)
                    for child in node.get('children', {}).get('attached', []):
                        extract_text(child, level + 1)
                
                for sheet in content:
                    extract_text(sheet.get('rootTopic', {}))
            else:
                print("No content.json found in xmind.")
    except Exception as e:
        print("Error:", e)

print_xmind('标签建设.xmind')
