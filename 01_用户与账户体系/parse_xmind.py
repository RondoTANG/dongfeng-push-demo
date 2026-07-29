import zipfile
import json
import os

def print_xmind(file_path):
    print(f"--- {os.path.basename(file_path)} ---")
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            if 'content.json' in z.namelist():
                content = json.loads(z.read('content.json'))
                # Just print a rough dump of the text
                def extract_text(node, level=0):
                    print("  " * level + str(node.get('title', '')))
                    for child in node.get('children', {}).get('attached', []):
                        extract_text(child, level + 1)
                
                for sheet in content:
                    extract_text(sheet.get('rootTopic', {}))
    except Exception as e:
        print("Error:", e)

print_xmind('标签解决思路 -2 (1).xmind')
