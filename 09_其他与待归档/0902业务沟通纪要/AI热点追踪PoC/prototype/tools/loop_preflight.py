#!/usr/bin/env python3
"""Deterministic preflight checks for prototype-loop projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime
import sys
from pathlib import Path
from urllib.parse import urlsplit


def trusted_control_config_root() -> Path | None:
    """Return the repo-owned orchestrator config root, never the project root.

    Generated projects copy this file to tools/loop_preflight.py. In that
    location, project files such as ./artifacts.yaml or ./gates.yaml are
    untrusted and must not override embedded gates. Only the source repository
    layout orchestrator/scripts/loop_preflight.py may load external control
    configs.
    """
    script_dir = Path(__file__).resolve().parent
    if script_dir.name == "scripts" and script_dir.parent.name == "orchestrator":
        return script_dir.parent
    return None


CONFIG_ROOT = trusted_control_config_root()
CONTROL_CONFIG_ERRORS: list[str] = []


def load_control_config(name: str, fallback: dict) -> dict:
    """Load JSON-compatible YAML control config only from the trusted repo."""
    if CONFIG_ROOT is None:
        return fallback
    path = CONFIG_ROOT / name
    if not path.exists():
        return fallback
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        CONTROL_CONFIG_ERRORS.append(
            f"控制配置解析失败：orchestrator/{name} 必须保持 JSON-compatible YAML，不会静默使用该文件"
        )
        return fallback
    return data if isinstance(data, dict) else fallback


DEFAULT_REQUIRED_PATHS = [
    ".clauderules",
    ".gitignore",
    "index.html",
    "CLAUDE.md",
    "assets/css/global.css",
    "assets/css/app.css",
    "js/app.js",
    "js/common.js",
    "js/nav.js",
    "mock/data.js",
    "docs/decisions.md",
    "docs/index.html",
    "docs/interaction.html",
    "flowcharts/index.html",
    "flowcharts/processon-links.txt",
    "memory/project.md",
    "memory/project-startup-plan.md",
    "memory/business-rules.md",
    "memory/source-materials.md",
    "memory/field-map.md",
    "memory/project-structure.md",
    "memory/task-plan.md",
    "memory/execution-steps.md",
    "memory/acceptance-map.md",
    "memory/verification-log.md",
    "memory/loop-status.md",
    "memory/stage-log.md",
    "memory/circuit-state.json",
    "memory/change-log.md",
    "memory/annotation-prompt.md",
    "memory/annotation-coverage.md",
    "memory/open-items.md",
    "config/nav.json",
    "config/workflow.json",
    "config/project.json",
    "annotations/annotation-runtime.js",
    "annotations/annotation.css",
    "annotations/annotations.js",
    "tools/loop_run.py",
    "tools/loop_preflight.py",
]

DEFAULT_CONTENT_REQUIRED_BY_STAGE = {
    "s4": [
        "CLAUDE.md",
        ".clauderules",
        "assets/css/global.css",
        "assets/css/app.css",
        "js/app.js",
    "js/common.js",
    "js/delivery-nav.js",
    "js/nav.js",
        "mock/data.js",
        "config/nav.json",
        "config/workflow.json",
        "config/project.json",
        "memory/project-startup-plan.md",
    ],
    "s6": [
        "CLAUDE.md",
        "docs/decisions.md",
        "memory/project.md",
        "memory/project-startup-plan.md",
        "memory/business-rules.md",
        "memory/source-materials.md",
        "memory/field-map.md",
        "memory/project-structure.md",
    ],
    "s7": [
        "memory/task-plan.md",
        "memory/execution-steps.md",
        "memory/acceptance-map.md",
        "memory/open-items.md",
    ],
    "s8": [
        "memory/change-log.md",
        "memory/verification-log.md",
    ],
    "s9": [
        "memory/acceptance-map.md",
        "memory/verification-log.md",
    ],
    "final": [
        "docs/interaction.html",
        "memory/project.md",
        "memory/project-startup-plan.md",
        "memory/source-materials.md",
        "memory/business-rules.md",
        "memory/field-map.md",
        "memory/task-plan.md",
        "memory/execution-steps.md",
        "memory/acceptance-map.md",
        "memory/change-log.md",
        "memory/verification-log.md",
        "memory/stage-log.md",
        "memory/annotation-prompt.md",
        "memory/annotation-coverage.md",
        "annotations/annotations.js",
    ],
}

PLACEHOLDERS = ["待补充", "待确认", "待定", "未填写", "TODO", "TBD", "N/A"]
TRIVIAL_COMMANDS = {"echo ok", "echo pass", "true", "echo 'pass'", 'echo "pass"'}
TRIVIAL_COMMAND_LEADERS = ("echo ", "printf ")
GLOBAL_ANCHOR_KEY = "__js_global__"
PLACEHOLDER_PATTERNS = [
    re.compile(r"^\s*[-*]\s*(待补充|待确认|待定|未填写|TODO|TBD|N/A)[。.]?\s*$", re.IGNORECASE),
    re.compile(r"[:：|]\s*(待补充|待确认|待定|未填写|TODO|TBD|N/A)[。.]?\s*(?:\||$)", re.IGNORECASE),
    re.compile(r"确认需求后补充本页面|待\s*S9|待标注(?:生成|提示词)|由\s*annotation-generator\s*自动生成", re.IGNORECASE),
]
EMPTY_VALUES = {"", "-", "none", "null", "无", "无失败", "不适用", "n/a", "N/A"}
PASS_VALUES = {"pass", "passed", "complete", "completed", "通过", "已通过", "完成", "已完成"}
BAD_STATUS_VALUES = {
    "pending",
    "planned",
    "todo",
    "tbd",
    "fail",
    "failed",
    "blocked",
    "待补充",
    "待确认",
    "待定",
    "计划中",
    "失败",
    "阻塞",
}
# Terminal statuses that are acceptable at s8/s9/final (not just "pass").
# Items marked as N/A or deferred are treated as resolved — they were
# intentionally descoped, not failed.
TERMINAL_STATUS_VALUES = PASS_VALUES | {
    "n/a",
    "na",
    "not applicable",
    "不适用",
    "deferred",
    "descoped",
    "已取消",
    "已移除",
    "skipped",
    "跳过",
}
NON_PASS_TERMINAL_STATUS_VALUES = TERMINAL_STATUS_VALUES - PASS_VALUES
STARTUP_PLAN_PATH = "memory/project-startup-plan.md"
STARTUP_PLAN_REQUIRED_SECTIONS = [
    "## 文件规则",
    "## 启动来源",
    "## 产品形态",
    "## 项目目的",
    "## 项目范围",
    "## 非本期范围",
    "## UI 风格",
    "## 参考资料",
    "## LLM WIKI 调用计划",
    "## 数据和字段来源",
    "## 整体页面结构",
    "## 核心流程",
    "## 验收方向",
    "## 约束和风险",
    "## S2 前待确认问题",
]
CLAUDE_REQUIRED_MARKERS = [
    "@memory/project.md",
    "@memory/project-startup-plan.md",
    "@memory/business-rules.md",
    "@memory/source-materials.md",
    "@memory/open-items.md",
    "## Loop 阶段预检",
    "## 开始工作前",
    "## 项目执行边界",
]
PROJECT_MEMORY_REQUIRED_SECTIONS = [
    "## 产品目标",
    "## 目标用户",
    "## 核心页面列表",
    "## 核心用户路径",
    "## 主要数据对象",
    "## 交付方式",
]
DEFAULT_MIN_CONTENT_CHARS = {
    "docs/decisions.md": 80,
    "memory/project.md": 240,
    "memory/project-startup-plan.md": 600,
    "memory/business-rules.md": 160,
    "memory/source-materials.md": 160,
    "memory/field-map.md": 160,
    "memory/project-structure.md": 120,
    "memory/task-plan.md": 120,
    "memory/execution-steps.md": 240,
    "memory/acceptance-map.md": 160,
    "memory/change-log.md": 120,
    "memory/verification-log.md": 120,
    "memory/stage-log.md": 120,
    "memory/annotation-prompt.md": 240,
    "memory/annotation-coverage.md": 120,
    "memory/open-items.md": 80,
    "docs/interaction.html": 160,
}

DEFAULT_REQUIRED_STAGE_LOGS_BY_STAGE = {
    "s4": ["S0", "S1", "S2", "S3"],
    # s6 runs at S5 completion (before the S5 log is appended), so it can only
    # require S4; the S5 log is enforced one gate later at s7.
    "s6": ["S0", "S1", "S2", "S3", "S4"],
    "s7": ["S0", "S1", "S2", "S3", "S4", "S5"],
    "s8": ["S0", "S1", "S2", "S3", "S4", "S5", "S6"],
    "s9": ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"],
    "final": ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
}

ARTIFACT_CONFIG = load_control_config("artifacts.yaml", {})
GATE_CONFIG = load_control_config("gates.yaml", {})

REQUIRED_PATHS = ARTIFACT_CONFIG.get("required_paths", DEFAULT_REQUIRED_PATHS)
CONTENT_REQUIRED_BY_STAGE = ARTIFACT_CONFIG.get(
    "content_required_by_stage", DEFAULT_CONTENT_REQUIRED_BY_STAGE
)
MIN_CONTENT_CHARS = ARTIFACT_CONFIG.get("min_content_chars", DEFAULT_MIN_CONTENT_CHARS)
REQUIRED_STAGE_LOGS_BY_STAGE = ARTIFACT_CONFIG.get(
    "required_stage_logs_by_stage", DEFAULT_REQUIRED_STAGE_LOGS_BY_STAGE
)
EXPECTED_PREFLIGHT_BY_STAGE = {
    "S4": "s4",
    "S5": "s6",
    "S6": "s7",
    "S7": "s8",
    "S8": "s9",
    "S9": "final",
}
DELIVERY_POLLUTION_PATHS = [
    "node_modules",
    "package.json",
    "package-lock.json",
    "playwright-report",
    "test-results",
]


def read_text(path: Path) -> str:
    # utf-8-sig strips BOM; errors="replace" preserves character counts so
    # min_content_chars checks are not fooled by silently dropped bytes.
    return path.read_text(encoding="utf-8-sig", errors="replace")


def load_json(path: Path, errors: list[str]) -> dict:
    try:
        return json.loads(read_text(path))
    except FileNotFoundError:
        errors.append(f"缺失 JSON 文件：{path}")
    except json.JSONDecodeError as exc:
        errors.append(f"JSON 格式错误：{path} ({exc})")
    return {}


def load_json_silent(path: Path) -> dict:
    try:
        return json.loads(read_text(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def project_record_salt(target: Path) -> str:
    for relative_path in [Path("config/project.json"), Path("config/workflow.json")]:
        data = load_json_silent(target / relative_path)
        for key in ["projectId", "annotationProjectId", "id"]:
            value = data.get(key)
            if value:
                return str(value)
    return "missing-project-id"


def expected_record_id_v2(target: Path, stage: str, date_value: str) -> str:
    return hashlib.sha256(f"{project_record_salt(target)}:{stage}:{date_value}".encode()).hexdigest()[:12]


def expected_record_id_legacy(stage: str, date_value: str) -> str:
    return hashlib.sha256(f"{stage}:{date_value}".encode()).hexdigest()[:12]


def is_empty_or_placeholder(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return True
    text = read_text(path).strip()
    if not text:
        return True
    if path.name == "source-materials.md" and "SRC-" in text:
        # A bare "SRC-" substring (e.g. in a heading) is not enough; the file
        # must have at least one well-formed SRC-\d+ row in a markdown table.
        if any(re.match(r"^SRC-\d+$", cells[0]) for cells in markdown_table_rows(path, 6)):
            return False
    meaningful_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith(("#", ">", "---", "|"))
    ]
    if not meaningful_lines:
        return True
    # Use regex patterns instead of substring matching to avoid false positives
    # on lines like "// TODO: implement this" or "## TODO List" where TODO is
    # embedded in otherwise meaningful content.  PLACEHOLDER_PATTERNS requires
    # the placeholder to appear in a structured position (e.g. list item or
    # key-value delimiter), not just anywhere in the text.
    return all(
        any(pattern.search(line) for pattern in PLACEHOLDER_PATTERNS)
        for line in meaningful_lines
    )


def contains_unresolved_placeholder(text: str) -> bool:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") and line.strip("# ").endswith("待确认项"):
            continue
        if any(pattern.search(line) for pattern in PLACEHOLDER_PATTERNS):
            return True
    return False


def annotation_is_empty(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return True
    # Strip ALL whitespace (including tabs, non-breaking spaces, etc.) to
    # reliably detect the empty-annotation skeleton regardless of formatting.
    text = re.sub(r"\s+", "", read_text(path))
    return "window.AnnotationData={};" in text or "window.AnnotationData=window.AnnotationData||{};" in text


def value_is_empty(value: str) -> bool:
    return value.strip().lower() in {item.lower() for item in EMPTY_VALUES}


def value_is_pass(value: str) -> bool:
    return value.strip().lower() in {item.lower() for item in PASS_VALUES}


def value_is_bad_status(value: str) -> bool:
    normalized = value.strip().lower()
    return any(mark.lower() in normalized for mark in BAD_STATUS_VALUES)


def strict_bool(value: object) -> bool:
    return value is True


def value_is_iso_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def check_required_paths(target: Path, errors: list[str]) -> None:
    for relative in REQUIRED_PATHS:
        if not (target / relative).exists():
            errors.append(f"缺失标准文件：{relative}")


def check_content(target: Path, stage: str, errors: list[str]) -> None:
    for relative in CONTENT_REQUIRED_BY_STAGE.get(stage, []):
        path = target / relative
        if is_empty_or_placeholder(path):
            errors.append(f"阶段 {stage} 需要有效内容，但文件为空或仍是占位内容：{relative}")
            continue
        if stage != "s4":
            text = read_text(path)
            if contains_unresolved_placeholder(text):
                errors.append(f"阶段 {stage} 不允许关键文件保留占位内容：{relative}")
            min_chars = MIN_CONTENT_CHARS.get(relative)
            if min_chars and len(text.strip()) < min_chars:
                errors.append(f"阶段 {stage} 关键文件内容过短，疑似未完整生成：{relative}")


def check_workflow_state(target: Path, stage: str, errors: list[str], completing_stage: str | None = None) -> None:
    workflow = load_json(target / "config" / "workflow.json", errors)
    if not workflow:
        return
    iteration = workflow.get("currentIteration", {})
    gates = workflow.get("gates", {})
    if stage in {"s4", "s6", "s7", "s8", "s9", "final"}:
        plan_cfm = iteration.get("planConfirmed")
        if not plan_cfm:
            errors.append("计划未标记为已确认：currentIteration.planConfirmed")
        elif not isinstance(plan_cfm, bool):
            errors.append("currentIteration.planConfirmed 必须是布尔值 (true/false)，不能是字符串")
        rules_written = iteration.get("projectRulesWritten")
        if rules_written is not None and not isinstance(rules_written, bool):
            errors.append("currentIteration.projectRulesWritten 必须是布尔值 (true/false)，不能是字符串")
        elif rules_written is False:
            errors.append("项目级 CLAUDE.md 规则未标记为已写入：currentIteration.projectRulesWritten")
        if not value_is_iso_timestamp(iteration.get("pmApprovedAt")):
            errors.append("计划门禁缺少可机读 PM 确认时间：currentIteration.pmApprovedAt")
        if not value_is_iso_timestamp(iteration.get("startupPlanFrozenAt")):
            errors.append("启动规划缺少可机读冻结时间：currentIteration.startupPlanFrozenAt")
    if stage in {"s6", "s7", "s8", "s9", "final"}:
        if not iteration.get("name") or iteration.get("name") in {"待确认", "draft"}:
            errors.append("当前迭代名称未确认：config/workflow.json currentIteration.name")
        memory_initialized = iteration.get("memoryInitialized")
        if not memory_initialized:
            errors.append("项目记忆基线未标记为当前迭代已初始化：currentIteration.memoryInitialized")
        elif not isinstance(memory_initialized, bool):
            errors.append("currentIteration.memoryInitialized 必须是布尔值 (true/false)，不能是字符串")
    if stage in {"s7", "s8", "s9", "final"} and not gates.get("requireStepVerification", True):
        errors.append("验证门禁被关闭：gates.requireStepVerification 必须为 true")
    check_workflow_stage_log_consistency(target, workflow, stage, errors, completing_stage)


def check_workflow_stage_log_consistency(
    target: Path, workflow: dict, stage: str, errors: list[str], completing_stage: str | None = None
) -> None:
    if stage not in {"s6", "s7", "s8", "s9", "final"}:
        return
    stages = workflow.get("stages", {})
    if not isinstance(stages, dict):
        return
    # When loop_run.py is actively re-completing a stage (e.g. complete --force),
    # it rolls that stage's workflow status back to "pending" BEFORE re-running
    # this gate, so the stage's prior pass record in stage-log is transiently
    # inconsistent with workflow by design. Exempt only that one stage; every
    # other stage stays checked, and a standalone preflight run (no
    # --completing-stage) keeps full strictness.
    exempt = (completing_stage or "").strip().upper()
    records = stage_log_records(target)
    for record in records:
        stage_value = record.get("stage", "").strip().upper()
        match = re.search(r"S(?:10|11|0|1|2|3|4|5|6|7|8|9)", stage_value)
        if not match:
            continue
        stage_id = match.group(0)
        if stage_id not in EXPECTED_PREFLIGHT_BY_STAGE:
            continue
        if exempt and stage_id == exempt:
            continue
        if value_is_pass(record.get("gate_result", "")):
            workflow_status = str(stages.get(stage_id.lower(), "")).strip().lower()
            if workflow_status and workflow_status != "completed":
                errors.append(
                    f"阶段状态不一致：memory/stage-log.md 记录 {stage_id} pass，但 config/workflow.json stages.{stage_id.lower()}={workflow_status}"
                )


def check_current_iteration_baseline(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s6", "s7", "s8", "s9", "final"}:
        return
    workflow = load_json(target / "config" / "workflow.json", errors)
    iteration_name = workflow.get("currentIteration", {}).get("name")
    if not iteration_name or iteration_name in {"待确认", "draft"}:
        return
    project_memory = target / "memory" / "project.md"
    if not project_memory.exists():
        return
    lines = read_text(project_memory).splitlines()
    first_content = "\n".join(lines[:40])
    first_heading = next((line.strip() for line in lines if line.strip().startswith("#")), "")
    # Use word-boundary matching so short names like "v1" don't spuriously
    # match inside longer tokens like "v10" or "v1.0-backup".
    iter_pat = re.compile(r"\b" + re.escape(iteration_name) + r"\b")
    if not iter_pat.search(first_content):
        errors.append(
            f"项目记忆顶部未声明当前迭代 `{iteration_name}`，可能未基于本轮启动规划初始化"
        )
    if first_heading and not iter_pat.search(first_heading) and "当前迭代" not in first_content:
        errors.append(
            f"项目记忆标题未反映当前迭代：首个标题为 `{first_heading}`，当前迭代为 `{iteration_name}`"
        )


def check_project_startup_plan(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s4", "s6", "s7", "s8", "s9", "final"}:
        return
    path = target / STARTUP_PLAN_PATH
    if not path.exists():
        errors.append(f"缺失项目启动规划：{STARTUP_PLAN_PATH}")
        return
    text = read_text(path)
    for section in STARTUP_PLAN_REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"项目启动规划缺少章节：{section}")
    if contains_unresolved_placeholder(text):
        errors.append(f"项目启动规划仍包含占位内容：{STARTUP_PLAN_PATH}")
    workflow = load_json(target / "config" / "workflow.json", errors)
    frozen = workflow.get("frozenArtifacts", {})
    startup_freeze = frozen.get(STARTUP_PLAN_PATH, {}) if isinstance(frozen, dict) else {}
    expected_hash = startup_freeze.get("sha256") if isinstance(startup_freeze, dict) else None
    if not expected_hash:
        errors.append(f"项目启动规划未在 S2 冻结：config/workflow.json frozenArtifacts.{STARTUP_PLAN_PATH}.sha256")
        return
    current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if current_hash != expected_hash:
        errors.append(f"项目启动规划已在 S2 冻结后被修改：{STARTUP_PLAN_PATH}")


def check_project_context_bootstrap(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s6", "s7", "s8", "s9", "final"}:
        return
    claude = target / "CLAUDE.md"
    project = target / "memory" / "project.md"
    sources = target / "memory" / "source-materials.md"
    if claude.exists():
        claude_text = read_text(claude)
        for marker in CLAUDE_REQUIRED_MARKERS:
            if marker not in claude_text:
                errors.append(f"CLAUDE.md 缺少总体执行规则或记忆引用：{marker}")
        if contains_unresolved_placeholder(claude_text):
            errors.append("CLAUDE.md 仍包含占位内容，不能作为项目级执行规则")
    if project.exists():
        project_text = read_text(project)
        for marker in PROJECT_MEMORY_REQUIRED_SECTIONS:
            if marker not in project_text:
                errors.append(f"项目记忆缺少必需章节：{marker}")
        if contains_unresolved_placeholder(project_text):
            errors.append("项目记忆仍包含占位内容：memory/project.md")
    if sources.exists():
        source_text = read_text(sources)
        if "SRC-" not in source_text and "No external source" not in source_text:
            errors.append("资料记录缺少 SRC-* 来源编号，也未声明 No external source：memory/source-materials.md")


def markdown_table_rows(path: Path, min_cells: int) -> list[list[str]]:
    if not path.exists():
        return []
    rows: list[list[str]] = []
    fence_depth = 0
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if line.startswith(("```", "~~~")):
            fence_depth = fence_depth - 1 if fence_depth > 0 else 1
            continue
        if fence_depth > 0:
            continue
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= min_cells:
            rows.append(cells)
    return rows


def source_material_ids(target: Path) -> set[str]:
    path = target / "memory" / "source-materials.md"
    if not path.exists():
        return set()
    ids: set[str] = set()
    for cells in markdown_table_rows(path, 6):
        if cells[0].lower() in {"source id", "来源 id"}:
            continue
        if re.match(r"^SRC-\d+$", cells[0]):
            ids.add(cells[0])
    return ids


def field_map_ids(target: Path) -> set[str]:
    return {row["field_id"] for row in field_rows(target)}


def field_rows(target: Path) -> list[dict[str, str]]:
    path = target / "memory" / "field-map.md"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    for cells in markdown_table_rows(path, 10):
        if cells[0].lower() in {"field id", "字段 id"}:
            continue
        if not re.match(r"^FLD-\d+$", cells[0]):
            continue
        rows.append(
            {
                "field_id": cells[0],
                "source_id": cells[1],
                "page_area": cells[2],
                "data_field": cells[3],
                "display_name": cells[4],
                "display_format": cells[5],
                "enum_mapping": cells[6],
                "empty_error_rule": cells[7],
                "annotation_point": cells[8],
                "used_in": cells[9],
            }
        )
    return rows


def field_map_declares_no_source(target: Path) -> bool:
    path = target / "memory" / "field-map.md"
    if not path.exists():
        return False
    pattern = re.compile(r"^\s*(?:[-*]\s*)?No field-level source\s*[:：|-]", re.IGNORECASE)
    return any(pattern.search(line.strip()) for line in read_text(path).splitlines())


def check_field_map(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s6", "s7", "s8", "s9", "final"}:
        return
    path = target / "memory" / "field-map.md"
    if not path.exists():
        errors.append("缺失字段映射：memory/field-map.md")
        return
    rows = field_rows(target)
    if field_map_declares_no_source(target):
        if rows:
            errors.append("字段映射声明 No field-level source，但仍包含 FLD-* 字段行：memory/field-map.md")
        return
    if not rows:
        errors.append("字段映射缺少 FLD-* 字段行：memory/field-map.md")
        return
    source_ids = source_material_ids(target)
    for row in rows:
        if not re.match(r"^FLD-\d+$", row["field_id"]):
            errors.append(f"字段映射 Field ID 格式错误：{row['field_id']}")
        if not re.match(r"^SRC-\d+$", row["source_id"]):
            errors.append(f"字段映射 Source ID 必须引用 SRC-*：{row['field_id']}")
        elif row["source_id"] not in source_ids:
            errors.append(f"字段映射引用了不存在的 Source ID：{row['field_id']} -> {row['source_id']}")
        for key in ["page_area", "data_field", "display_name", "display_format", "annotation_point", "used_in"]:
            if value_is_empty(row[key]) or contains_unresolved_placeholder(row[key]):
                errors.append(f"字段映射 {row['field_id']} 缺少有效字段：{key}")


def check_stage_log(target: Path, stage: str, errors: list[str]) -> None:
    required_stages = REQUIRED_STAGE_LOGS_BY_STAGE.get(stage, [])
    if not required_stages:
        return
    path = target / "memory" / "stage-log.md"
    if not path.exists():
        errors.append("缺失阶段日志：memory/stage-log.md")
        return
    records = stage_log_records(target)
    latest_by_stage: dict[str, dict[str, str]] = {}
    for record in records:
        stage_value = record.get("stage", "").strip().upper()
        match = re.search(r"S(?:10|11|0|1|2|3|4|5|6|7|8|9)", stage_value)
        if match:
            latest_by_stage[match.group(0)] = record
    for required in required_stages:
        record = latest_by_stage.get(required)
        if not record:
            errors.append(f"阶段日志缺少完成记录：{required}")
            continue
        gate_result = record.get("gate_result", "")
        blocked_by = record.get("blocked_by", "")
        if not value_is_pass(gate_result):
            errors.append(f"阶段日志未标记为通过：{required} Gate Result={gate_result or '空'}")
        if record.get("writer") != "tools/loop_run.py":
            errors.append(f"阶段日志 {required} 缺少脚本写入标记：writer=tools/loop_run.py")
        record_id = record.get("record_id", "")
        if not record_id:
            errors.append(f"阶段日志 {required} 缺少防伪字段：record_id")
        else:
            stage_val = record.get("stage", "").strip()
            date_val = record.get("date", "").strip()
            expected_v2 = expected_record_id_v2(target, stage_val, date_val)
            expected_legacy = expected_record_id_legacy(stage_val, date_val)
            version = record.get("record_id_version", "").strip()
            if version == "project-salted-v2":
                if record_id != expected_v2:
                    errors.append(
                        f"阶段日志 {required} record_id 与 projectId+stage+date 不一致，疑似被手工改写而非脚本写入"
                    )
            elif record_id not in {expected_v2, expected_legacy}:
                errors.append(
                    f"阶段日志 {required} record_id 与 projectId+stage+date 或 legacy stage+date 均不一致，疑似被手工改写"
                )
        if not record.get("preflight_result_hash"):
            errors.append(f"阶段日志 {required} 缺少防伪字段：preflight_result_hash")
        if blocked_by and not value_is_empty(blocked_by):
            errors.append(f"阶段日志仍记录阻塞项：{required} Blocked By={blocked_by}")
        expected_next = {
            "S0": "S1",
            "S1": "S2",
            "S2": "S3",
            "S3": "S4",
            "S4": "S5",
            "S5": "S6",
            "S6": "S7",
            "S7": "S8",
            "S8": "S9",
            "S9": "none",
        }.get(required)
        if expected_next and record.get("next_stage") != expected_next:
            errors.append(
                f"阶段日志 {required} next_stage 不正确：需要 {expected_next}，实际为 {record.get('next_stage') or '空'}"
            )
        expected_preflight = EXPECTED_PREFLIGHT_BY_STAGE.get(required)
        preflight = record.get("preflight", "")
        if expected_preflight and f"--stage {expected_preflight}" not in preflight:
            errors.append(
                f"阶段日志 {required} 缺少对应预检命令：需要 --stage {expected_preflight}，实际为 {preflight or '空'}"
            )


def stage_log_records(target: Path) -> list[dict[str, str]]:
    return parse_key_value_records(
        target / "memory" / "stage-log.md",
        key_map={
            "date": "date",
            "writer": "writer",
            "record_id": "record_id",
            "preflight_result_hash": "preflight_result_hash",
            "stage": "stage",
            "stage_name": "stage_name",
            "input_artifacts": "input_artifacts",
            "output_artifacts": "output_artifacts",
            "preflight": "preflight",
            "gate_result": "gate_result",
            "decision": "decision",
            "next_stage": "next_stage",
            "blocked_by": "blocked_by",
            "notes": "notes",
        },
        record_start_key="stage",
    )


def check_control_tool_boundary(target: Path, errors: list[str]) -> None:
    control_tool = target / "tools" / "prototype-loop-orchestrator"
    if not control_tool.exists():
        return
    if not control_tool.is_dir():
        errors.append("tools/prototype-loop-orchestrator 存在但不是目录")
        return
    # Presence is valid; only report if loop artifacts incorrectly point to it.
    tracked_files = [
        "memory/execution-steps.md",
        "memory/acceptance-map.md",
        "memory/change-log.md",
        "memory/verification-log.md",
        "annotations/annotations.js",
    ]
    for relative in tracked_files:
        path = target / relative
        if path.exists() and "tools/prototype-loop-orchestrator" in read_text(path):
            errors.append(f"业务产物不应引用总控工具包作为实现或交付内容：{relative}")


def load_circuit_state(target: Path, errors: list[str]) -> dict:
    path = target / "memory" / "circuit-state.json"
    if not path.exists():
        return {}
    return load_json(path, errors)


def check_circuit_breaker(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s7", "s8", "s9", "final"}:
        return
    circuit_path = target / "memory" / "circuit-state.json"
    if not circuit_path.exists():
        return
    state = load_circuit_state(target, errors)
    if "failures" not in state:
        errors.append("熔断状态结构缺失：memory/circuit-state.json 必须包含 failures 字段（可为空数组）")
        return
    threshold = int(GATE_CONFIG.get("circuit_breaker", {}).get("threshold", 3))
    if "threshold" in state:
        try:
            state_threshold = int(state.get("threshold"))
        except (TypeError, ValueError):
            errors.append("熔断状态格式错误：memory/circuit-state.json threshold 必须是数字")
            return
        if state_threshold != threshold:
            errors.append(
                f"熔断阈值不得由项目状态文件覆盖：circuit-state.json threshold={state_threshold}，控制层 threshold={threshold}"
            )
    failures = state.get("failures", [])
    if not isinstance(failures, list):
        errors.append("熔断状态格式错误：memory/circuit-state.json failures 必须是数组")
        return
    for item in failures:
        if not isinstance(item, dict):
            errors.append("熔断状态格式错误：failures 中每项必须是对象")
            continue
        try:
            count = int(item.get("consecutiveFailures", 0))
        except (TypeError, ValueError):
            errors.append("熔断状态格式错误：consecutiveFailures 必须是数字")
            continue
        if count >= threshold:
            step = item.get("stepId") or "unknown-step"
            checkpoint = item.get("checkpoint") or "unknown-checkpoint"
            summary = item.get("lastError") or "未记录错误摘要"
            errors.append(
                f"熔断已触发：{step} / {checkpoint} 连续失败 {count} 次，最近错误：{summary}"
            )


def extract_step_ids(target: Path) -> list[str]:
    path = target / "memory" / "execution-steps.md"
    if not path.exists():
        return []
    steps: list[str] = []
    # Anchor on '## 步骤/Step N' headings only — matching bare prose like
    # "参考步骤 2" would invent phantom steps that later fail the per-step
    # verification check. Stays consistent with extract_step_blocks().
    for line in read_text(path).splitlines():
        match = re.match(r"^\s*##\s*(?:步骤|Step)\s*0*(\d+)", line, re.IGNORECASE)
        if match:
            step_id = f"step-{int(match.group(1)):02d}"
            if step_id not in steps:
                steps.append(step_id)
    return steps


def parse_key_value_records(
    path: Path,
    key_map: dict[str, str],
    record_start_key: str,
) -> list[dict[str, str]]:
    if not path.exists():
        return []
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    fence_depth = 0
    for raw_line in read_text(path).splitlines():
        stripped = raw_line.strip()
        if stripped.startswith(("```", "~~~")):
            fence_depth = fence_depth - 1 if fence_depth > 0 else 1
            continue
        if fence_depth > 0:
            continue
        line = raw_line.strip().removeprefix("- ").removeprefix("-")
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = key.strip().lower().replace(" ", "_")
        mapped = key_map.get(normalized)
        if not mapped:
            continue
        if mapped == "date" and current and record_start_key in current:
            records.append(current)
            current = {}
        if mapped == record_start_key and current and record_start_key in current:
            records.append(current)
            current = {}
        current[mapped] = value.strip()
    if current:
        records.append(current)
    return records


def parse_verification_records(target: Path) -> list[dict[str, str]]:
    return parse_key_value_records(
        target / "memory" / "verification-log.md",
        key_map={
            "step": "step",
            "step_id": "step",
            "scope": "scope",
            "result": "result",
        "date": "date",
        "timestamp": "date",
        "local_url_/_file": "local_url_file",
        "local_url": "local_url_file",
        "file": "local_url_file",
        "tool": "tool",
        "command_/_check": "command_check",
        "command": "command_check",
        "check": "command_check",
        "passed": "passed",
        "failed": "failed",
        "evidence": "evidence",
        "consecutive_failures": "consecutive_failures",
        "next_action": "next_action",
        },
        record_start_key="step",
    )


def normalize_step(value: str) -> str:
    match = re.search(r"0*(\d+)", value)
    if not match:
        return value.strip().lower()
    return f"step-{int(match.group(1)):02d}"


def extract_step_blocks(target: Path) -> list[tuple[str, str]]:
    path = target / "memory" / "execution-steps.md"
    if not path.exists():
        return []
    text = read_text(path)
    matches = list(re.finditer(r"^##\s*(?:步骤|Step)\s*0*(\d+).*", text, re.IGNORECASE | re.MULTILINE))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((f"step-{int(match.group(1)):02d}", text[start:end]))
    return blocks


def check_execution_step_format(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s7", "s8", "s9", "final"}:
        return
    blocks = extract_step_blocks(target)
    if not blocks:
        errors.append("执行步骤缺失：memory/execution-steps.md 未找到 Step/步骤 标题")
        return
    required_sections = {
        "Files/文件": ["### Files", "### 文件"],
        "Expected Change/预期变更类型": ["### Expected Change", "### 预期变更"],
        "Acceptance/验收": ["### Acceptance", "### 验收"],
        "Verification/验证": ["### Verification", "### 验证"],
        "Verification Skill/验证技能": ["### Verification Skill", "### 验证技能"],
        "Annotation Impact/标注影响": ["### Annotation Impact", "### 标注影响"],
    }
    for step_id, block in blocks:
        for label, markers in required_sections.items():
            if not any(marker.lower() in block.lower() for marker in markers):
                errors.append(f"执行步骤 {step_id} 缺少必需字段：{label}")


def acceptance_rows(target: Path) -> list[dict[str, str]]:
    path = target / "memory" / "acceptance-map.md"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    fence_depth = 0
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if line.startswith(("```", "~~~")):
            fence_depth = fence_depth - 1 if fence_depth > 0 else 1
            continue
        if fence_depth > 0:
            continue
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() in {"requirement id", "需求 id"}:
            continue
        rows.append(
            {
                "id": cells[0],
                "requirement": cells[1],
                "acceptance": cells[2],
                "verification": cells[3],
                "status": cells[4],
                "reason": cells[5] if len(cells) > 5 else "",
            }
        )
    return rows


def check_acceptance_map(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s7", "s8", "s9", "final"}:
        return
    rows = acceptance_rows(target)
    if not rows:
        errors.append("验收映射缺少需求行：memory/acceptance-map.md")
        return
    for row in rows:
        if any(value_is_empty(row[key]) for key in ["id", "requirement", "acceptance", "verification", "status"]):
            errors.append(f"验收映射存在空字段：{row.get('id') or 'unknown'}")
        if not re.match(r"^R-\d+$", row["id"]):
            errors.append(f"验收映射 Requirement ID 格式错误：{row['id']}，应使用 R-001")
        if contains_unresolved_placeholder(" | ".join(row.values())):
            errors.append(f"验收映射仍包含占位内容：{row['id']}")
    if stage in {"s8", "s9", "final"}:
        for row in rows:
            status_norm = row["status"].strip().lower()
            if status_norm not in {s.lower() for s in TERMINAL_STATUS_VALUES}:
                errors.append(f"验收映射未明确通过或标记为不适用：{row['id']} Status={row['status']}")
            elif status_norm in {s.lower() for s in NON_PASS_TERMINAL_STATUS_VALUES}:
                reason = row.get("reason", "").strip()
                if value_is_empty(reason) or contains_unresolved_placeholder(reason) or len(reason) < 8:
                    errors.append(
                        f"验收映射 {row['id']} Status={row['status']}，但缺少 Decision / Reason；"
                        "跳过、延期、移出范围或不适用必须说明原因"
                    )


def check_verification_records(target: Path, stage: str, errors: list[str]) -> None:
    if stage not in {"s8", "s9", "final"}:
        return
    records = parse_verification_records(target)
    if not records:
        errors.append("验证日志缺少机器可读记录；必须包含 Step/Scope/Result 等键值行")
        return
    planned_steps = set(extract_step_ids(target))
    for record in records:
        result = record.get("result", "").lower()
        scope = record.get("scope", "").lower()
        step = normalize_step(record.get("step", ""))
        failed = record.get("failed", "")
        evidence = record.get("evidence", "")
        for key in ["local_url_file", "tool", "command_check", "passed", "evidence", "consecutive_failures"]:
            if value_is_empty(record.get(key, "")):
                errors.append(f"验证日志 {step or 'unknown'} 缺少有效字段：{key}")
        if result == "pass" and len(evidence.strip()) < 20:
            errors.append(f"验证日志 {step or 'unknown'} Evidence 过短，不能支撑通过结论")
        command_check_val = record.get("command_check", "").strip()
        cc_norm = re.sub(r"\s+", " ", command_check_val.lower()).strip().rstrip(";").strip()
        if (
            cc_norm in TRIVIAL_COMMANDS
            or cc_norm in {"true", ":", "echo"}
            or cc_norm.startswith(TRIVIAL_COMMAND_LEADERS)
        ):
            errors.append(f"验证记录 {step or 'unknown'} Command/Check 是无效占位命令：{command_check_val}")
        failed_norm = failed.strip()
        failed_is_clear = value_is_empty(failed_norm) or re.fullmatch(
            r"0+\s*(?:个|项|error\(s\)?|errors?|failures?)?", failed_norm, re.IGNORECASE
        ) is not None
        if result == "pass" and failed_norm and not failed_is_clear:
            errors.append(f"验证记录矛盾：{step} Result=pass 但 Failed={failed}")
        if result == "pass" and evidence_indicates_failure(evidence):
            errors.append(f"验证记录矛盾：{step} Result=pass 但 Evidence 仍显示失败或未完成：{evidence}")
        if result == "pass":
            passed_val = record.get("passed", "").strip().lower()
            if passed_val in {"false", "0", "no", "否", "失败", "fail", "failed"}:
                errors.append(f"验证记录矛盾：{step} Result=pass 但 Passed={record.get('passed', '')}")
            cf_raw = record.get("consecutive_failures", "").strip()
            if cf_raw:
                try:
                    if int(cf_raw) > 0:
                        errors.append(f"验证记录矛盾：{step} Result=pass 但 Consecutive Failures={cf_raw}")
                except ValueError:
                    pass
        if scope == "step" and result in {"pass", "fail"} and step not in planned_steps:
            errors.append(f"验证日志包含未在 execution-steps.md 中定义的步骤：{step}")
    passed_steps = {
        normalize_step(record.get("step", ""))
        for record in records
        if record.get("result", "").lower() == "pass"
        and record.get("scope", "").lower() == "step"
    }
    for step_id in extract_step_ids(target):
        if step_id not in passed_steps:
            errors.append(f"验证日志缺少执行步骤 pass 记录：{step_id}")
    if stage in {"s9", "final"}:
        has_global_pass = any(
            record.get("result", "").lower() == "pass"
            and record.get("scope", "").lower() == "global"
            for record in records
        )
        if not has_global_pass:
            errors.append("验证日志缺少全局验证 pass 记录")


def evidence_indicates_failure(evidence: str) -> bool:
    lowered = evidence.strip().lower()
    if not lowered:
        return True
    # Neutralize explicit zero-count phrases in BOTH orders ("0 error(s)" and
    # "error(s): 0") so a clean result is never misread as a failure. Only a
    # non-zero failure marker that survives neutralization counts.
    zero = r"(?:0+|no|none|zero|无|零)"
    errword = r"(?:error\(s\)|errors?|failures?|failure|failed|失败|错误)"
    neutralized = re.sub(zero + r"\s*个?\s*" + errword, " ", lowered)
    neutralized = re.sub(errword + r"\s*[:：=]?\s*" + zero + r"\b", " ", neutralized)
    failure_markers = [
        "heading toward 0",
        "reduced from",
        "errors to",
        "error(s)",
        "errors",  # plural only; singular "error" left out so "error handling" is not flagged
        "failed",
        "failure",
        "未通过",
        "失败",
        "仍有",
        "还有",
    ]
    # No affirmative pass phrase is required: absence of failure language is not
    # itself a failure (evidence length/structure is enforced elsewhere).
    return any(marker in neutralized for marker in failure_markers)


def _scan_balanced_json_literal(text: str, start: int) -> str | None:
    if start >= len(text) or text[start] not in "[{":
        return None
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    stack = [closer]
    in_string = False
    quote = ""
    escaped = False
    for index in range(start + 1, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue
        if char in {'"', "'"}:
            # Strict mode ultimately requires JSON double-quoted strings, but
            # single-quote awareness keeps brace scanning from slicing wrongly
            # before json.loads reports the format error.
            in_string = True
            quote = char
            continue
        if char in "[{":
            stack.append("}" if char == "{" else "]")
            continue
        if char in "}]":
            if not stack or char != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return text[start:index + 1]
    return None


def _annotation_json_literal(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    if compact in {"window.AnnotationData={};", "window.AnnotationData=window.AnnotationData||{};", "AnnotationData={};"}:
        return "{}"
    assignment = re.search(r"(?:window\.)?AnnotationData\s*=", text)
    if not assignment:
        return None
    index = assignment.end()
    while index < len(text) and text[index].isspace():
        index += 1
    # Support the template fallback form without executing it.
    fallback = re.match(r"(?:window\.)?AnnotationData\s*\|\|\s*", text[index:])
    if fallback:
        index += fallback.end()
        while index < len(text) and text[index].isspace():
            index += 1
    return _scan_balanced_json_literal(text, index)


def _annotation_entries_from_data(data: object) -> list[dict]:
    out: list[dict] = []

    def push_items(page: str, items: object) -> None:
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, dict):
                entry = dict(item)
                entry.setdefault("page", str(entry.get("page") or page or "index"))
                out.append(entry)

    if isinstance(data, dict):
        for page, items in data.items():
            push_items(str(page), items)
    elif isinstance(data, list):
        push_items("index", data)
    return out


def load_annotation_entries(target: Path, errors: list[str]) -> list[dict]:
    path = target / "annotations" / "annotations.js"
    if not path.exists():
        return []
    text = read_text(path)
    literal = _annotation_json_literal(text)
    if literal is None:
        errors.append(
            "annotations/annotations.js 必须使用严格 JSON 赋值给 window.AnnotationData，"
            "不能包含可执行 JS 或动态表达式"
        )
        return []
    try:
        data = json.loads(literal)
    except json.JSONDecodeError as exc:
        errors.append(
            "annotations/annotations.js 不是严格 JSON 标注数据："
            f"{exc.msg}（第 {exc.lineno} 行第 {exc.colno} 列）"
        )
        return []
    entries = _annotation_entries_from_data(data)
    if not isinstance(entries, list):
        errors.append("annotations/annotations.js 未解析出标注数组")
        return []
    return entries


def annotation_anchor_name(selector: object) -> str:
    if not isinstance(selector, str):
        return ""
    match = re.search(r"\[data-anno=(?:\\?[\"']?)([^\\\]\"']+)(?:\\?[\"']?)\]", selector)
    return match.group(1).strip() if match else ""


def annotation_ref_list(entry: dict, key: str) -> list[str]:
    value = entry.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def html_page_key(path: Path, target: Path) -> str:
    text = read_text(path)
    match = re.search(r"AnnotationConfig\s*=\s*\{[^}]*\bpage\s*:\s*[\"']([^\"']+)[\"']", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if path.name == "index.html":
        return "index"
    return path.stem


def source_annotation_anchor_inventory(
    target: Path,
) -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    # NOTE: Generated prototypes are SPA-style — index.html is a shell and pages
    # are rendered by js/*.js, so most data-anno anchors live in JS template
    # strings, not static HTML. JS files are not page-specific, so their anchors
    # are collected into a global set and made available to every page. This
    # accepts a narrow false-negative (an anchor that only renders on another
    # page) in exchange for avoiding a broad false-positive that would block all
    # JS-rendered annotations at final.
    anchors_by_page: dict[str, set[str]] = {}
    global_js_anchors: set[str] = set()
    occurrences: dict[str, list[str]] = {}
    source_files = [
        path
        for path in target.rglob("*.html")
        if not any(part in {".git", "node_modules"} for part in path.parts)
        and "tools/prototype-loop-orchestrator" not in path.relative_to(target).as_posix()
        and not path.relative_to(target).as_posix().startswith("docs/")
        and not path.relative_to(target).as_posix().startswith("flowcharts/")
        and not path.relative_to(target).as_posix().startswith("annotations/")
    ]
    js_dir = target / "js"
    if js_dir.exists():
        source_files.extend(sorted(js_dir.rglob("*.js")))
    pattern = re.compile(r"data-anno\s*=\s*\\?[\"']([^\\\"']+)\\?[\"']")
    for path in source_files:
        if not path.exists():
            continue
        text = read_text(path)
        found: set[str] = set()
        relative = path.relative_to(target).as_posix()
        for match in pattern.finditer(text):
            anchor = match.group(1).strip()
            if not anchor:
                continue
            found.add(anchor)
            line = text.count("\n", 0, match.start()) + 1
            occurrences.setdefault(anchor, []).append(f"{relative}:{line}")
        if not found:
            continue
        if path.suffix.lower() == ".html":
            anchors_by_page.setdefault(html_page_key(path, target), set()).update(found)
        else:
            global_js_anchors.update(found)
    # Store global JS anchors under a sentinel so they reach every page that an
    # annotation references, even pages whose HTML shell has no static anchor.
    if global_js_anchors:
        anchors_by_page[GLOBAL_ANCHOR_KEY] = global_js_anchors
    duplicates = {
        anchor: locations
        for anchor, locations in occurrences.items()
        if len(locations) > 1
    }
    return anchors_by_page, duplicates


def source_annotation_anchors(target: Path) -> dict[str, set[str]]:
    return source_annotation_anchor_inventory(target)[0]


def check_source_annotation_anchor_uniqueness(
    target: Path, stage: str, errors: list[str]
) -> None:
    if stage != "final":
        return
    _, duplicates = source_annotation_anchor_inventory(target)
    for anchor, locations in sorted(duplicates.items()):
        preview = ", ".join(locations[:6])
        if len(locations) > 6:
            preview += f", ... +{len(locations) - 6}"
        errors.append(
            "源码 data-anno 锚点必须全局唯一："
            f"data-anno={anchor} count={len(locations)} locations={preview}"
        )


def check_annotations(target: Path, stage: str, errors: list[str]) -> None:
    if stage != "final":
        return
    if annotation_is_empty(target / "annotations" / "annotations.js"):
        # S9 is manual-prompt-first. An empty annotations.js is acceptable when
        # PM will paste memory/annotation-prompt.md into a separate annotation
        # generation step. If annotations are manually written back, the rest of
        # this function validates them strictly.
        return
    entries = load_annotation_entries(target, errors)
    if not entries:
        errors.append("标注数据非空，但没有解析到真实 AnnotationData 标注记录")
        return
    ids = [str(entry.get("id") or "").strip() for entry in entries]
    if any(not item for item in ids):
        errors.append("标注数据存在缺失 id 的记录；标注 id 必须全局唯一")
    seen: set[str] = set()
    duplicated: set[str] = set()
    for item in ids:
        if not item:
            continue
        if item in seen:
            duplicated.add(item)
        seen.add(item)
    for item in sorted(duplicated):
        errors.append(f"标注 id 不是全局唯一：{item}")
    numeric_ids: list[int] = []
    for item in ids:
        if not item:
            continue
        if not re.fullmatch(r"[1-9]\d*", item):
            errors.append(f"标注 id 必须是从 1 开始的连续数字字符串，不能按页面重置或使用 slug：id={item}")
            continue
        numeric_ids.append(int(item))
    if numeric_ids and len(numeric_ids) == len([item for item in ids if item]) and not duplicated:
        expected_ids = list(range(1, len(numeric_ids) + 1))
        actual_ids = sorted(numeric_ids)
        if actual_ids != expected_ids:
            errors.append(
                "标注 id 必须从 1 开始全局连续编号："
                f"当前={actual_ids} 期望={expected_ids}"
            )
    known_sources = source_material_ids(target)
    for entry in entries:
        refs = annotation_ref_list(entry, "sourceRefs")
        if not refs:
            errors.append(f"标注数据存在缺失 sourceRefs 的记录：id={entry.get('id') or 'unknown'}")
        for ref in refs:
            if ref not in known_sources:
                errors.append(f"标注 sourceRefs 引用了不存在的来源：{ref}")
    known_fields = field_map_ids(target)
    if known_fields:
        for entry in entries:
            refs = annotation_ref_list(entry, "fieldRefs")
            if not refs:
                errors.append(f"标注数据存在缺失 fieldRefs 的记录：id={entry.get('id') or 'unknown'}")
            for ref in refs:
                if ref not in known_fields:
                    errors.append(f"标注 fieldRefs 引用了不存在的字段：{ref}")
    else:
        # No FLD-* rows defined, but annotations may still carry fieldRefs
        # that reference nothing — flag them.
        for entry in entries:
            refs = annotation_ref_list(entry, "fieldRefs")
            if refs:
                errors.append(
                    f"标注数据包含 fieldRefs 但 memory/field-map.md 未定义任何 FLD-* 字段："
                    f"id={entry.get('id') or 'unknown'} refs={refs}"
                )
    anchors_by_page = source_annotation_anchors(target)
    for entry in entries:
        page = str(entry.get("page") or "index")
        target_name = annotation_anchor_name(entry.get("target"))
        if not target_name:
            errors.append(f"标注 target 格式错误或缺失：id={entry.get('id') or 'unknown'}")
            continue
        anchors = anchors_by_page.get(page, set()) | anchors_by_page.get(GLOBAL_ANCHOR_KEY, set())
        if target_name not in anchors:
            errors.append(f"标注 target 没有对应页面锚点：page={page} data-anno={target_name}")


def check_interaction_document(target: Path, stage: str, errors: list[str]) -> None:
    """Enforce the PM-facing interaction document contract independently of annotations."""
    if stage != "final":
        return
    interaction = target / "docs" / "interaction.html"
    if not interaction.exists():
        errors.append("缺失功能说明文档：docs/interaction.html")
        return
    text = read_text(interaction)
    if contains_unresolved_placeholder(text) or re.search(
        r"待补充|待确认|TODO|TBD", text, flags=re.IGNORECASE
    ):
        errors.append("功能说明文档仍是初始化模板或含占位内容：docs/interaction.html")
    if len(text.strip()) < MIN_CONTENT_CHARS.get("docs/interaction.html", 160):
        errors.append("功能说明文档内容过短，疑似未生成：docs/interaction.html")

    required_markers = [
        "功能说明文档",
        "一. 版本说明",
        "二. 项目范围",
        "三. 逻辑说明",
        "四. 功能说明",
        "五. 其他说明",
        "版本号",
        "更新时间",
        "更新内容",
        "系统名称",
        "涉及板块",
        "功能范围",
        "对接系统范围",
        "流程名称",
        "跳转地址",
        "1）功能名称：",
        "2）交互说明：",
        "3）数据来源：",
        "4）逻辑说明：",
        "5）功能明细",
        "数据格式",
        "默认值",
        "异常处理",
    ]
    for marker in required_markers:
        if marker not in text:
            errors.append(f"功能说明文档缺少固定结构：{marker}")

    structural_patterns = [
        (r'class=["\']container["\']', "container 主容器"),
        (r'class=["\']jump-btn["\']', "jump-btn 跳转按钮"),
        (r'class=["\']table-wrap["\']', "table-wrap 表格容器"),
        (r'class=["\']section-divider["\']', "section-divider 功能分隔线"),
        (r'href=["\']\.\./index\.html["\']', "返回原型的 ../index.html 链接"),
        (r"\.container\s*\{[^}]*max-width\s*:\s*1180px", "1180px 文档容器"),
        (r"h1\s*\{[^}]*border-bottom\s*:\s*2px\s+solid\s+#1677ff", "蓝色 H1 分隔线"),
        (r"\.jump-btn\s*\{[^}]*background\s*:\s*#1677ff", "蓝色跳转按钮"),
    ]
    for pattern, label in structural_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is None:
            errors.append(f"功能说明文档未遵循固定视觉基线：{label}")

    forbidden_patterns = [
        (r'class=["\'][^"\']*\bhero\b', "Hero 区块"),
        (r'class=["\'][^"\']*\bchips?\b', "标签墙"),
        (r"linear-gradient\s*\(", "渐变背景"),
    ]
    for pattern, label in forbidden_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            errors.append(f"功能说明文档不得使用自由发挥的营销式样式：{label}")


def check_annotation_prompt(target: Path, stage: str, errors: list[str]) -> None:
    if stage != "final":
        return
    path = target / "memory" / "annotation-prompt.md"
    if not path.exists():
        errors.append("缺失手动标注提示词：memory/annotation-prompt.md")
        return
    text = read_text(path)
    required_markers = [
        "## 手动标注提示词",
        "## 标注输入资料",
        "## 可用 data-anno 锚点清单",
        "## 标注生成要求",
        "## 回写说明",
    ]
    for marker in required_markers:
        if marker not in text:
            errors.append(f"手动标注提示词缺少章节：{marker}")
    if contains_unresolved_placeholder(text):
        errors.append("手动标注提示词仍包含占位内容：memory/annotation-prompt.md")
    for src_id in source_material_ids(target):
        if not id_token_present(text, src_id):
            errors.append(f"手动标注提示词未引用来源：{src_id}")
    if not field_map_declares_no_source(target):
        for fld_id in field_map_ids(target):
            if not id_token_present(text, fld_id):
                errors.append(f"手动标注提示词未引用字段：{fld_id}")
    anchors_by_page = source_annotation_anchors(target)
    available_anchors = sorted(
        {
            anchor
            for page, anchors in anchors_by_page.items()
            if page != GLOBAL_ANCHOR_KEY
            for anchor in anchors
        }
        | anchors_by_page.get(GLOBAL_ANCHOR_KEY, set())
    )
    for anchor in available_anchors:
        if not id_token_present(text, anchor):
            errors.append(f"手动标注提示词未列出页面锚点：data-anno={anchor}")
    # Reverse check: IDs referenced in the prompt that don't exist in source data.
    known_src = source_material_ids(target)
    known_fld = field_map_ids(target)
    for token in extract_id_tokens(text, "SRC"):
        if token not in known_src:
            errors.append(f"手动标注提示词引用了不存在的来源：{token}")
    if known_fld:
        for token in extract_id_tokens(text, "FLD"):
            if token not in known_fld:
                errors.append(f"手动标注提示词引用了不存在的字段：{token}")


def extract_id_tokens(text: str, prefix: str) -> set[str]:
    """Extract all SRC-* or FLD-* tokens from text (whole-token matching)."""
    return set(
        match.group(0)
        for match in re.finditer(
            r"(?<![\w-])" + re.escape(prefix) + r"-\d+(?![\w-])", text
        )
    )


def id_token_present(text: str, ident: str) -> bool:
    """Whole-token match so SRC-001 does not spuriously match inside SRC-0012."""
    if not ident:
        return False
    return re.search(r"(?<![\w-])" + re.escape(ident) + r"(?![\w-])", text) is not None


def check_annotation_coverage(target: Path, stage: str, errors: list[str]) -> None:
    if stage != "final":
        return
    path = target / "memory" / "annotation-coverage.md"
    if not path.exists():
        return
    coverage_text = read_text(path)
    # Node/JS load failures are surfaced by check_annotations (runs just before
    # with the real errors list); here a fresh list keeps coverage focused on
    # what is parseable without double-reporting the same load failure.
    silent: list[str] = []
    entries = load_annotation_entries(target, silent)
    for entry in entries:
        anno_id = str(entry.get("id") or "").strip()
        if anno_id and not id_token_present(coverage_text, anno_id):
            errors.append(f"annotation-coverage.md 未覆盖标注：{anno_id}")
    for row in acceptance_rows(target):
        req_id = row.get("id", "").strip()
        if req_id and not id_token_present(coverage_text, req_id):
            errors.append(f"annotation-coverage.md 未覆盖需求：{req_id}")
    for src_id in source_material_ids(target):
        if not id_token_present(coverage_text, src_id):
            errors.append(f"annotation-coverage.md 未覆盖来源引用：{src_id}")
    if not field_map_declares_no_source(target):
        for fld_id in field_map_ids(target):
            if not id_token_present(coverage_text, fld_id):
                errors.append(f"annotation-coverage.md 未覆盖字段引用：{fld_id}")
    # Reverse checks: IDs in coverage that don't exist in source data.
    known_src_cov = source_material_ids(target)
    known_fld_cov = field_map_ids(target)
    known_anno_ids = {str(e.get("id") or "").strip() for e in entries if e.get("id")}
    known_req_ids = {r.get("id", "").strip() for r in acceptance_rows(target)}
    for token in extract_id_tokens(coverage_text, "SRC"):
        if token not in known_src_cov:
            errors.append(f"annotation-coverage.md 引用了不存在的来源：{token}")
    if known_fld_cov:
        for token in extract_id_tokens(coverage_text, "FLD"):
            if token not in known_fld_cov:
                errors.append(f"annotation-coverage.md 引用了不存在的字段：{token}")
    for token in extract_id_tokens(coverage_text, "R"):
        if token not in known_req_ids:
            errors.append(f"annotation-coverage.md 引用了不存在的需求：{token}")


def check_delivery_pollution(target: Path, stage: str, errors: list[str]) -> None:
    if stage != "final":
        return
    project_config = load_json(target / "config" / "project.json", errors)
    allow_dependencies = strict_bool(project_config.get("allowDependencies"))
    if allow_dependencies:
        return
    for relative in DELIVERY_POLLUTION_PATHS:
        for path in target.rglob(relative):
            rel = path.relative_to(target).as_posix()
            if any(part in {".git", "node_modules"} for part in path.parts):
                continue
            if rel.startswith("tools/prototype-loop-orchestrator/"):
                continue
            errors.append(f"静态原型交付目录不应包含依赖或测试产物：{rel}")


def check_flowchart_links(target: Path, stage: str, errors: list[str]) -> None:
    if stage != "final":
        return
    path = target / "flowcharts" / "processon-links.txt"
    if not path.exists():
        return
    for line_number, raw_line in enumerate(read_text(path).splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 1:
            raw_url = parts[0]
        elif len(parts) == 2:
            raw_url = parts[1]
        else:
            raw_url = "|".join(parts[2:]).strip()
        parsed = urlsplit(raw_url)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or (host != "processon.com" and not host.endswith(".processon.com"))
        ):
            errors.append(
                "流程图链接清单包含无效 ProcessOn 链接："
                f"flowcharts/processon-links.txt:{line_number}"
            )


def check_delivery_navigation(target: Path, stage: str, errors: list[str]) -> None:
    if stage != "final":
        return

    page_scripts = {
        "index.html": "js/delivery-nav.js",
        "docs/index.html": "../js/delivery-nav.js",
        "docs/interaction.html": "../js/delivery-nav.js",
        "flowcharts/index.html": "../js/delivery-nav.js",
    }
    for relative, script_ref in page_scripts.items():
        path = target / relative
        if not path.exists():
            continue
        if script_ref not in read_text(path):
            errors.append(f"交付分页入口未加载统一导航脚本：{relative} -> {script_ref}")

    docs_index = target / "docs" / "index.html"
    if docs_index.exists() and "interaction.html" not in read_text(docs_index):
        errors.append("说明文档分页未展示交互说明：docs/index.html 缺少 interaction.html")

    nav_script = target / "js" / "delivery-nav.js"
    if not nav_script.exists():
        return
    nav_text = read_text(nav_script)
    required_markers = [
        "原型页面",
        "说明文档",
        "流程图集",
        "index.html",
        "docs/interaction.html",
        "flowcharts/index.html",
        "delivery_embed",
        "data-delivery-frame",
        "delivery-switch",
        "postMessage",
        "history.pushState",
        "#delivery=(prototype|docs|flowcharts)",
    ]
    for marker in required_markers:
        if marker not in nav_text:
            errors.append(f"统一交付内部切换脚本缺少机制：js/delivery-nav.js -> {marker}")

    if re.search(
        r"\{\s*key\s*:\s*['\"]docs['\"][^}]*docs/index\.html",
        nav_text,
        flags=re.IGNORECASE,
    ):
        errors.append("说明文档仍使用外部分页入口：js/delivery-nav.js 应内部加载 docs/interaction.html")


def check_stage_specific(target: Path, stage: str, errors: list[str]) -> None:
    check_project_context_bootstrap(target, stage, errors)
    check_field_map(target, stage, errors)
    check_stage_log(target, stage, errors)
    check_execution_step_format(target, stage, errors)
    check_acceptance_map(target, stage, errors)
    check_verification_records(target, stage, errors)
    check_source_annotation_anchor_uniqueness(target, stage, errors)
    check_annotation_prompt(target, stage, errors)
    check_annotations(target, stage, errors)
    check_interaction_document(target, stage, errors)
    check_annotation_coverage(target, stage, errors)
    check_flowchart_links(target, stage, errors)
    check_delivery_navigation(target, stage, errors)
    check_delivery_pollution(target, stage, errors)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="目标原型项目目录")
    parser.add_argument(
        "--stage",
        choices=["s4", "s6", "s7", "s8", "s9", "final"],
        default="s4",
        help="要检查的目标阶段门禁",
    )
    parser.add_argument(
        "--completing-stage",
        default=None,
        help="loop_run.py 重新完成某阶段时传入（如 S9），该阶段在状态一致性检查中临时豁免；独立预检不应传此参数",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not target.exists():
        errors.append(f"目标目录不存在：{target}")
    elif not target.is_dir():
        errors.append(f"目标路径不是目录：{target}")
    else:
        errors.extend(CONTROL_CONFIG_ERRORS)
        check_required_paths(target, errors)
        check_content(target, args.stage, errors)
        check_workflow_state(target, args.stage, errors, completing_stage=args.completing_stage)
        check_current_iteration_baseline(target, args.stage, errors)
        check_control_tool_boundary(target, errors)
        check_circuit_breaker(target, args.stage, errors)
        check_project_startup_plan(target, args.stage, errors)
        check_stage_specific(target, args.stage, errors)

    result = {
        "target": str(target),
        "stage": args.stage,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if not errors else "FAIL"
        print(f"Loop preflight {status}: {target} [{args.stage}]")
        for error in errors:
            print(f"- ERROR: {error}")
        for warning in warnings:
            print(f"- WARN: {warning}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
