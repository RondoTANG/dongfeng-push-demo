file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the flex container to prevent wrapping and increase max-width
content = content.replace(
    '<div class="flex items-start justify-center gap-12 flex-wrap w-full max-w-7xl mx-auto">',
    '<div class="flex items-start justify-center gap-8 flex-nowrap w-full max-w-[1400px] mx-auto overflow-x-auto pb-4">'
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Wrap fixed.")
