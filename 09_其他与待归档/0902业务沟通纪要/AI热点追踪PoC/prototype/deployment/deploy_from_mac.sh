#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTOTYPE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
POC_DIR="$(cd "$PROTOTYPE_DIR/.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/deploy.env"

if [[ -f "$CONFIG_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  set +a
fi

DEPLOY_HOST="${AI_HOTSPOT_DEPLOY_HOST:-}"
PUBLIC_URL="${AI_HOTSPOT_PUBLIC_URL:-https://hotspot.dbuddy.uk/}"
KEEP_RELEASES="${AI_HOTSPOT_KEEP_RELEASES:-5}"

die() {
  printf '错误：%s\n' "$*" >&2
  exit 1
}

for command_name in ssh rsync tar curl mktemp python3; do
  command -v "$command_name" >/dev/null 2>&1 || die "缺少命令：$command_name"
done

[[ -n "$DEPLOY_HOST" ]] || die "请先复制 deploy.env.example 为 deploy.env 并填写服务器SSH地址"
[[ "$KEEP_RELEASES" =~ ^[1-9][0-9]*$ ]] || die "AI_HOTSPOT_KEEP_RELEASES 必须是正整数"

ssh -o BatchMode=yes -o ConnectTimeout=10 "$DEPLOY_HOST" "sudo -n true" \
  || die "SSH密钥未解锁、未授权或服务器不可达"

RELEASE_ID="$(date -u +%Y%m%d-%H%M%S)"
STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ai-hotspot-release.XXXXXX")"
ARCHIVE_PATH="$STAGE_DIR/ai-hotspot-poc-$RELEASE_ID.tar.gz"
REMOTE_ARCHIVE="/tmp/ai-hotspot-poc-$RELEASE_ID.tar.gz"
trap 'rm -rf -- "$STAGE_DIR"' EXIT

cd "$POC_DIR"
python3 validate_config.py >/dev/null
tar \
  --no-xattrs \
  --exclude='prototype/data' \
  --exclude='prototype/tests/screenshots' \
  --exclude='prototype/deployment/deploy.env' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  -czf "$ARCHIVE_PATH" \
  config prototype run_doubao_search.py validate_config.py README.md

rsync -a "$ARCHIVE_PATH" "$DEPLOY_HOST:$REMOTE_ARCHIVE"

ssh "$DEPLOY_HOST" sudo -n bash -s -- "$REMOTE_ARCHIVE" "$RELEASE_ID" "$KEEP_RELEASES" <<'REMOTE_SCRIPT'
set -Eeuo pipefail
archive_path="$1"
release_id="$2"
keep_releases="$3"
release_root=/opt/ai-hotspot-poc/releases
release_dir="$release_root/$release_id"
runtime_root=/var/lib/ai-hotspot-poc

id ai-hotspot >/dev/null 2>&1 || useradd --system --home "$runtime_root" --shell /usr/sbin/nologin ai-hotspot
install -d -o root -g ai-hotspot -m 0750 /etc/ai-hotspot-poc "$release_root"
install -d -o ai-hotspot -g ai-hotspot -m 0750 \
  "$runtime_root/data" "$runtime_root/config" "$runtime_root/codex-home"
[[ -f /etc/ai-hotspot-poc/runtime.env ]] || {
  echo "缺少 /etc/ai-hotspot-poc/runtime.env；先按 runtime.env.example 配置服务器密钥" >&2
  exit 1
}

install -d -o root -g ai-hotspot -m 0750 "$release_dir"
tar -xzf "$archive_path" -C "$release_dir"
chown -R root:ai-hotspot "$release_dir"
chmod -R g+rX,o-rwx "$release_dir"

if [[ ! -x /opt/ai-hotspot-poc/venv/bin/python ]]; then
  python3 -m venv /opt/ai-hotspot-poc/venv
fi
/opt/ai-hotspot-poc/venv/bin/pip install -q -r "$release_dir/prototype/requirements.txt"

# 只在首次部署补齐配置；后台已经编辑的运行配置不被发布包覆盖。
find "$release_dir/config" -maxdepth 1 -type f -name '*.yaml' -exec \
  sh -c 'for source_file do target="/var/lib/ai-hotspot-poc/config/$(basename "$source_file")"; [ -e "$target" ] || install -o ai-hotspot -g ai-hotspot -m 0640 "$source_file" "$target"; done' sh {} +

ln -sfn "$release_dir" /opt/ai-hotspot-poc/current
install -o root -g root -m 0644 \
  "$release_dir/prototype/deployment/ai-hotspot-poc.service" \
  /etc/systemd/system/ai-hotspot-poc.service
systemctl daemon-reload
systemctl enable --now ai-hotspot-poc
systemctl restart ai-hotspot-poc
health_ready=false
for health_attempt in {1..10}; do
  if curl --fail --silent http://127.0.0.1:8765/api/health >/dev/null 2>&1; then
    health_ready=true
    break
  fi
  sleep 2
done
if [[ "$health_ready" != true ]]; then
  systemctl status ai-hotspot-poc --no-pager -l >&2 || true
  journalctl -u ai-hotspot-poc -n 80 --no-pager >&2 || true
  exit 1
fi

mapfile -t old_releases < <(find "$release_root" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | awk '{print $2}')
if (( ${#old_releases[@]} > keep_releases )); then
  for old_release in "${old_releases[@]:keep_releases}"; do
    case "$old_release" in
      /opt/ai-hotspot-poc/releases/*) rm -rf -- "$old_release" ;;
    esac
  done
fi
rm -f -- "$archive_path"
echo "server_release=$release_id"
REMOTE_SCRIPT

status="$(curl -L --silent --output /dev/null --write-out '%{http_code}' --max-time 20 "$PUBLIC_URL" || true)"
[[ "$status" == "200" ]] || die "服务器服务已发布，但公网入口返回HTTP $status；请检查Cloudflare Tunnel和DNS"
printf '发布成功：%s\n线上地址：%s\n' "$RELEASE_ID" "$PUBLIC_URL"
