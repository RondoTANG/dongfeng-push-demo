import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add 'flex' before 'flex-col' for the signature modals
content = content.replace('hidden flex-col slide-up', 'hidden flex flex-col slide-up')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed missing flex class")
