from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POC_ROOT = PROJECT_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "ai_hotspot_poc.db"
SOURCE_CONFIG_DIR = POC_ROOT / "config"
HOTSPOT_RULE_PATH = POC_ROOT / "热点采集规则_v0.2.yaml"
REAL_SAMPLE_PATH = POC_ROOT / "运行结果" / "2026-09-03_豆包原始结果.json"
DOUBAO_SCRIPT_PATH = POC_ROOT / "run_doubao_search.py"


def ensure_runtime_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
