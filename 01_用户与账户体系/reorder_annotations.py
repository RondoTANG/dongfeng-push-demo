import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the annotation block
match = re.search(r'(<!-- 批注区域 -->\s*<div class="w-\[350px\] shrink-0 space-y-6">)(.*?)(</div>\s*<!-- Toast 提示 -->)', content, re.DOTALL)
if match:
    prefix = match.group(1)
    inner = match.group(2)
    suffix = match.group(3)
    
    # Split the inner content into the two divs.
    # It has two <div class="bg-white p-6 ..."> blocks.
    divs = re.split(r'(<div class="bg-white p-6)', inner)
    
    # divs[0] is whitespace
    # divs[1] is `<div class="bg-white p-6`
    # divs[2] is the rest of the first block
    # divs[3] is `<div class="bg-white p-6`
    # divs[4] is the rest of the second block
    
    if len(divs) >= 5:
        # Swap them
        new_inner = "\n        " + divs[3] + divs[4] + "\n        " + divs[1] + divs[2]
        new_content = content[:match.start()] + prefix + new_inner + suffix + content[match.end():]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("Swapped annotations successfully.")
    else:
        print("Failed to split divs")
else:
    print("Could not find annotation block")
