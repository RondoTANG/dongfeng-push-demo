from __future__ import annotations

from pathlib import Path
import os
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POC_ROOT = PROJECT_ROOT.parent
DATA_DIR = Path(os.getenv("AI_HOTSPOT_DATA_DIR", str(PROJECT_ROOT / "data"))).expanduser().resolve()
DATABASE_PATH = DATA_DIR / "ai_hotspot_poc.db"
ADMIN_KEY_FILE = DATA_DIR / "admin_access.key"
ACCESS_KEY_ENCRYPTION_FILE = DATA_DIR / "access_key_encryption.key"
AUTH_SESSION_HOURS = int(os.getenv("AI_HOTSPOT_SESSION_HOURS", "12"))
AUTH_COOKIE_SECURE = os.getenv("AI_HOTSPOT_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"}
SOURCE_CONFIG_DIR = Path(os.getenv("AI_HOTSPOT_CONFIG_DIR", str(POC_ROOT / "config"))).expanduser().resolve()
HOTSPOT_RULE_PATH = SOURCE_CONFIG_DIR / "热点总控配置.yaml"
AUTOMATION_CONFIG_PATH = DATA_DIR / "automation.json"
AUTOMATION_SEED_PATH = PROJECT_ROOT / "config" / "automation.json"
REAL_SAMPLE_PATH = POC_ROOT / "运行结果" / "2026-09-03_豆包原始结果.json"
DOUBAO_SCRIPT_PATH = POC_ROOT / "run_doubao_search.py"
CODEX_CLI_PATH = os.getenv("CODEX_CLI_PATH") or shutil.which("codex") or "/Applications/ChatGPT.app/Contents/Resources/codex"
CODEX_AI_MODEL = os.getenv("AI_HOTSPOT_CODEX_MODEL", "").strip() or None
CODEX_AI_TIMEOUT_SECONDS = int(os.getenv("AI_HOTSPOT_CODEX_AI_TIMEOUT", "240"))
# 每轮最多从队列领取多少项；模型调用始终按单个事件顺序执行。
CODEX_AI_BATCH_SIZE = max(1, min(20, int(os.getenv("AI_HOTSPOT_CODEX_AI_BATCH_SIZE", "1"))))
FULL_RUN_COOLDOWN_SECONDS = 3 * 60 * 60
QUICK_RUN_COOLDOWN_SECONDS = 10 * 60


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
