import re
file_path = "/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/C端_用户签约与保密协议演示.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix Device 1 (Left, Scenario 2, Blue pin)
bad_left_device_pin = """<div class="device-mockup bg-gray-50">
        <!-- 图钉批注：场景2 -->
        <div class="absolute -top-1 -left-1 bg-blue-500 text-white rounded-full w-10 h-10 flex items-center justify-center font-bold text-xl shadow-lg z-[100] border-4 border-gray-100 ring-2 ring-blue-500">2</div>"""

good_left_device_pin = """<div class="relative">
        <!-- 图钉批注：场景2 -->
        <div class="absolute -top-3 -left-3 bg-blue-500 text-white rounded-full w-12 h-12 flex items-center justify-center font-bold text-2xl shadow-xl z-[100] border-4 border-white">2</div>
        <div class="device-mockup bg-gray-50">"""

if bad_left_device_pin in content:
    content = content.replace(bad_left_device_pin, good_left_device_pin, 1)

# Fix Device 2 (Right, Scenario 1, Red pin)
bad_right_device_pin = """<div class="device-mockup bg-gray-50 relative">
        <!-- 图钉批注：场景1 -->
        <div class="absolute -top-1 -left-1 bg-red-500 text-white rounded-full w-10 h-10 flex items-center justify-center font-bold text-xl shadow-lg z-[100] border-4 border-gray-100 ring-2 ring-red-500">1</div>"""

good_right_device_pin = """<div class="relative">
        <!-- 图钉批注：场景1 -->
        <div class="absolute -top-3 -left-3 bg-red-500 text-white rounded-full w-12 h-12 flex items-center justify-center font-bold text-2xl shadow-xl z-[100] border-4 border-white">1</div>
        <div class="device-mockup bg-gray-50 relative">"""

if bad_right_device_pin in content:
    content = content.replace(bad_right_device_pin, good_right_device_pin, 1)

# We need to close the wrapping `<div class="relative">` after each device mockup.
# Device 1 closing: It ends right before `<!-- 右侧设备：全局系统弹窗模拟 -->` or `<!-- 右侧设备` or `<div class="relative">` of right device.
# Wait, the structure is:
# <div class="device-mockup bg-gray-50">
# ...
#     </div> <!-- end inner modal -->
# </div> <!-- end device 1 -->
# 
# <!-- 右侧设备：全局系统弹窗模拟 -->

# Device 1 is between "<!-- 左侧设备：情况B 签约界面 -->" and "<!-- 右侧设备：全局系统弹窗模拟 -->"
# The end of Device 1 is the </div> just before "<!-- 右侧设备：全局系统弹窗模拟 -->".
content = content.replace("    <!-- 右侧设备：全局系统弹窗模拟 -->", "    </div>\n\n    <!-- 右侧设备：全局系统弹窗模拟 -->")

# The end of Device 2 is the </div> just before "<script>"
content = content.replace("    <script>", "    </div>\n\n    <script>")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed pins by wrapping devices")
