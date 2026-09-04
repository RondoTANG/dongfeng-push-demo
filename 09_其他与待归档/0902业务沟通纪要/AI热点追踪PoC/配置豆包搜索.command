#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"

echo "豆包 Global Search API Key 本机配置"
echo "Key 将保存到 macOS 钥匙串，不会写入项目文件。"
printf "请粘贴 API Key 后按回车（输入不会显示）："
IFS= read -r -s doubao_api_key_value
echo

if [[ -z "$doubao_api_key_value" ]]; then
  echo "未输入内容，配置已取消。"
  exit 1
fi

security add-generic-password \
  -U \
  -s "guard-army-doubao-search" \
  -a "api-key" \
  -w "$doubao_api_key_value" >/dev/null

unset doubao_api_key_value

python3 "$script_dir/run_doubao_search.py" --check-config
echo "配置成功。现在可以执行豆包单次搜索。"
