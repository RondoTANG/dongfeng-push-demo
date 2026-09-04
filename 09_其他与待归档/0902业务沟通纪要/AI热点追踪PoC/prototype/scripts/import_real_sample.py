#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.pipeline import import_real_sample  # noqa: E402
from service.repositories import get_run  # noqa: E402


if __name__ == "__main__":
    run_id = import_real_sample()
    print(json.dumps(get_run(run_id), ensure_ascii=False, indent=2))
