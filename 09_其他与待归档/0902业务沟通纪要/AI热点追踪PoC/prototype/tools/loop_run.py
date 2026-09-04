#!/usr/bin/env python3
"""Deterministic stage runner for generated prototype-loop projects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


LOOP_TOOL_VERSION = "2026-07-14-internal-delivery-v3"

STAGES = [f"S{i}" for i in range(10)]
STAGE_NAMES = {
    "S0": "总控启动",
    "S1": "项目讨论",
    "S2": "计划门禁",
    "S3": "项目记忆生成",
    "S4": "项目初始化",
    "S5": "项目结构读取",
    "S6": "需求实现拆分",
    "S7": "实现与单步验证循环",
    "S8": "全局验证",
    "S9": "标注提示词准备",
}

# A stage is complete only after the gate that allows the next stage has passed.
# S5 completion runs the s6 gate (the "ready to decompose" check) so that the
# pre-decomposition inputs — project memory, field-map and the S5 structure
# summary — are enforced before S6 decomposition, not left to a gate that is
# never triggered automatically.
COMPLETION_GATES = {
    "S4": "s4",
    "S5": "s6",
    "S6": "s7",
    "S7": "s8",
    "S8": "s9",
    "S9": "final",
}

NEXT_STAGE = {
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
}

STAGE_DISPATCH = {
    "S0": {
        "owner": "prototype-loop-orchestrator",
        "skill": "SKILL.md",
        "contract": None,
        "supportSkills": [],
        "tokenPolicy": "control_minimal",
    },
    "S1": {
        "owner": "superpowers-pm-prototype/skills/brainstorming",
        "skill": "skill-library/superpowers-pm-prototype/skills/brainstorming/SKILL.md",
        "contract": "orchestrator/agent-contracts/s1-discussion.yaml",
        "supportSkills": [],
        "tokenPolicy": "brief_scoped",
    },
    "S2": {
        "owner": "prototype-loop-orchestrator",
        "skill": "SKILL.md",
        "contract": None,
        "supportSkills": [],
        "tokenPolicy": "confirmed_plan_scoped",
    },
    "S3": {
        "owner": "memory-generator",
        "skill": "skill-library/memory-generator/SKILL.md",
        "contract": "orchestrator/agent-contracts/s3-memory.yaml",
        "supportSkills": [],
        "tokenPolicy": "source_summary_scoped",
    },
    "S4": {
        "owner": "create-prototype-project",
        "skill": "skill-library/create-prototype-project/SKILL.md",
        "contract": None,
        "supportSkills": [],
        "tokenPolicy": "structure_scoped",
    },
    "S5": {
        "owner": "structure-reader",
        "skill": "skill-library/structure-reader/SKILL.md",
        "contract": None,
        "supportSkills": [],
        "tokenPolicy": "structure_summary_scoped",
    },
    "S6": {
        "owner": "project-decomposer",
        "skill": "skill-library/project-decomposer/SKILL.md",
        "contract": "orchestrator/agent-contracts/s6-decomposer.yaml",
        "supportSkills": [],
        "tokenPolicy": "structure_and_memory_scoped",
    },
    "S7": {
        "owner": "prototype-builder",
        "skill": "skill-library/prototype-builder/SKILL.md",
        "contract": "orchestrator/agent-contracts/s7-builder.yaml",
        "supportSkills": [
            "prototype-verifier",
            "playwright-cli",
            "superpowers-pm-prototype/skills/systematic-debugging",
            "superpowers-pm-prototype/skills/verification-before-completion",
        ],
        "tokenPolicy": "step_scoped",
    },
    "S8": {
        "owner": "prototype-verifier",
        "skill": "skill-library/prototype-verifier/SKILL.md",
        "contract": None,
        "supportSkills": ["playwright-cli", "superpowers-pm-prototype/skills/systematic-debugging"],
        "tokenPolicy": "global_verification_scoped",
    },
    "S9": {
        "owner": "annotation-generator",
        "skill": "skill-library/annotation-generator/SKILL.md",
        "contract": "orchestrator/agent-contracts/s9-annotation.yaml",
        "supportSkills": ["superpowers-pm-prototype/skills/systematic-debugging"],
        "tokenPolicy": "verified_annotation_scoped",
    },
}

STAGE_REMINDERS: dict[str, str] = {
    "S8": "S8 需要进行全局验证（打开入口页面、检查核心导航、验证跨页面流程），完成全局验证并记录 Scope: global / Result: pass 后，再运行 complete --stage S8。",
}

OWNER_ACTIONS = {
    "pm": "PM 确认",
    "agent": "Agent 补齐",
    "verifier": "Agent 验证",
    "system": "脚本/状态修复",
    "cleanup": "交付清理",
}

STARTUP_PLAN_PATH = Path("memory/project-startup-plan.md")
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
STARTUP_PLAN_PLACEHOLDERS = ("待补充", "待确认", "待定", "TODO", "TBD")
CLAUDE_PATH = Path("CLAUDE.md")
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
FINAL_SNAPSHOT_PATH = Path("memory/final-snapshot.json")
FINAL_SNAPSHOT_PATTERNS = [
    "annotations/annotations.js",
    "memory/annotation-prompt.md",
    "memory/annotation-coverage.md",
    "memory/acceptance-map.md",
    "memory/execution-steps.md",
    "memory/verification-log.md",
    "memory/source-materials.md",
    "memory/field-map.md",
    "flowcharts/**/*",
    "docs/**/*.html",
    "index.html",
    "pages/**/*.html",
    "js/**/*.js",
    "mock/**/*.js",
    "assets/css/**/*.css",
]
FINAL_SNAPSHOT_EXCLUDED_PARTS = {".git", "node_modules", "tools"}

PROJECT_MEMORY_REQUIRED = {
    Path("memory/project.md"): [
        "## 产品目标",
        "## 目标用户",
        "## 核心页面列表",
        "## 核心用户路径",
        "## 主要数据对象",
        "## 交付方式",
    ],
    Path("memory/business-rules.md"): ["#"],
    Path("memory/source-materials.md"): ["SRC-"],
    Path("memory/field-map.md"): ["FLD-", "No field-level source"],
    Path("memory/open-items.md"): ["#"],
}

RUNTIME_PACKAGE_ROOT = Path("tools/prototype-loop-orchestrator")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_json(path: Path) -> dict:
    try:
        return json.loads(read_text(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: dict) -> None:
    """Atomically write JSON to path using a temp-file + rename strategy.

    This prevents partial/corrupt files if the process crashes mid-write.  On
    most filesystems rename(2) is atomic when src and dst are on the same volume.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def final_snapshot_files(project: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in FINAL_SNAPSHOT_PATTERNS:
        for path in project.glob(pattern):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(project)
            except ValueError:
                continue
            if any(part in FINAL_SNAPSHOT_EXCLUDED_PARTS for part in relative.parts):
                continue
            files.add(path)
    return sorted(files, key=lambda item: item.relative_to(project).as_posix())


def build_final_snapshot(project: Path) -> dict:
    files = []
    for path in final_snapshot_files(project):
        relative = path.relative_to(project).as_posix()
        stat = path.stat()
        files.append(
            {
                "path": relative,
                "sha256": file_sha256(path),
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return {
        "toolVersion": LOOP_TOOL_VERSION,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "gate": "final",
        "files": files,
    }


def write_final_snapshot(project: Path) -> None:
    write_json(project / FINAL_SNAPSHOT_PATH, build_final_snapshot(project))


def final_dirty_report(project: Path) -> dict:
    workflow = load_json(project / "config" / "workflow.json")
    if str(workflow.get("stage") or "").lower() != "none":
        return {"dirty": False, "reason": "workflow-not-final"}
    snapshot_path = project / FINAL_SNAPSHOT_PATH
    if not snapshot_path.exists():
        return {
            "dirty": True,
            "reason": "missing-final-snapshot",
            "changed": [],
            "message": "项目已进入 none 终态，但缺少 memory/final-snapshot.json；请重新运行 final。",
        }
    snapshot = load_json(snapshot_path)
    old_files = {item.get("path"): item for item in snapshot.get("files", []) if isinstance(item, dict)}
    current = {path.relative_to(project).as_posix(): file_sha256(path) for path in final_snapshot_files(project)}
    changed: list[str] = []
    for relative, old in sorted(old_files.items()):
        if relative not in current:
            changed.append(f"deleted:{relative}")
        elif current[relative] != old.get("sha256"):
            changed.append(f"modified:{relative}")
    for relative in sorted(set(current) - set(old_files)):
        changed.append(f"added:{relative}")
    return {
        "dirty": bool(changed),
        "reason": "hash-mismatch" if changed else "clean",
        "snapshotAt": snapshot.get("createdAt"),
        "toolVersion": snapshot.get("toolVersion"),
        "changed": changed,
    }


def dispatch_resource_path(project: Path, relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    candidates = [
        project / RUNTIME_PACKAGE_ROOT / relative_path,
        project / relative_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.relative_to(project).as_posix()
    return relative_path


def dispatch_resource_available(project: Path, relative_path: str | None) -> bool | None:
    if not relative_path:
        return None
    return any(
        candidate.exists()
        for candidate in [project / RUNTIME_PACKAGE_ROOT / relative_path, project / relative_path]
    )


def final_dirty_errors(project: Path) -> list[str]:
    report = final_dirty_report(project)
    if not report.get("dirty"):
        return []
    changed = report.get("changed") or []
    if changed:
        preview = ", ".join(changed[:10])
        if len(changed) > 10:
            preview += f", ... +{len(changed) - 10}"
        return [f"final 交付快照已失效，需要重新运行 final；变化文件：{preview}"]
    return [str(report.get("message") or "final 交付快照缺失或已失效，需要重新运行 final")]


def validate_startup_plan(project: Path) -> list[str]:
    path = project / STARTUP_PLAN_PATH
    errors: list[str] = []
    if not path.exists():
        return [f"缺失项目启动规划：{STARTUP_PLAN_PATH.as_posix()}"]
    text = read_text(path)
    if len(text.strip()) < 600:
        errors.append("项目启动规划内容过短，不能支撑 S1 启动规划")
    for section in STARTUP_PLAN_REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"项目启动规划缺少章节：{section}")
    content_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if any(marker in line for line in content_lines for marker in STARTUP_PLAN_PLACEHOLDERS):
        errors.append("项目启动规划仍包含占位内容，S1 不能完成")
    return errors


def validate_claude_rules(project: Path) -> list[str]:
    path = project / CLAUDE_PATH
    errors: list[str] = []
    if not path.exists():
        return [f"缺失项目级执行规则：{CLAUDE_PATH.as_posix()}"]
    text = read_text(path)
    if len(text.strip()) < 800:
        errors.append("CLAUDE.md 内容过短，不能作为项目级执行规则")
    for marker in CLAUDE_REQUIRED_MARKERS:
        if marker not in text:
            errors.append(f"CLAUDE.md 缺少项目级执行规则或记忆引用：{marker}")
    content_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if any(marker in line for line in content_lines for marker in STARTUP_PLAN_PLACEHOLDERS):
        errors.append("CLAUDE.md 仍包含占位内容，S2 不能完成")
    return errors


def validate_project_memory(project: Path) -> list[str]:
    errors: list[str] = []
    for relative, markers in PROJECT_MEMORY_REQUIRED.items():
        path = project / relative
        if not path.exists():
            errors.append(f"缺失项目记忆文件：{relative.as_posix()}")
            continue
        text = read_text(path)
        min_length = 10 if relative == Path("memory/open-items.md") else 80
        if len(text.strip()) < min_length:
            errors.append(f"项目记忆内容过短：{relative.as_posix()}")
        if relative == Path("memory/field-map.md"):
            has_field_row = any(re.match(r"^\|\s*FLD-\d+\s*\|", line) for line in text.splitlines())
            has_no_source = any(
                re.match(r"^\s*(?:[-*]\s*)?No field-level source\s*[:：|-]", line.strip(), re.IGNORECASE)
                for line in text.splitlines()
            )
            if not has_field_row and not has_no_source:
                errors.append("字段映射必须包含 FLD-* 字段行，或声明 No field-level source: 原因")
        else:
            for marker in markers:
                if marker not in text:
                    errors.append(f"项目记忆缺少内容标记：{relative.as_posix()} -> {marker}")
        content_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
        if any(marker in line for line in content_lines for marker in STARTUP_PLAN_PLACEHOLDERS):
            errors.append(f"项目记忆仍包含占位内容：{relative.as_posix()}")
    return errors


def freeze_startup_plan(project: Path) -> None:
    path = project / STARTUP_PLAN_PATH
    workflow_path = project / "config" / "workflow.json"
    workflow = load_json(workflow_path)
    frozen = workflow.setdefault("frozenArtifacts", {})
    frozen[STARTUP_PLAN_PATH.as_posix()] = {
        "sha256": file_sha256(path),
        "frozenAtStage": "S2",
        "frozenAt": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(workflow_path, workflow)


def mark_iteration_flags(project: Path, **flags: object) -> None:
    path = project / "config" / "workflow.json"
    workflow = load_json(path)
    iteration = workflow.setdefault("currentIteration", {})
    iteration.update(flags)
    write_json(path, workflow)


def normalize_stage(value: str) -> str:
    value = value.strip().upper()
    if value.startswith("S") and value[1:].isdigit():
        stage = f"S{int(value[1:])}"
    elif value.isdigit():
        stage = f"S{int(value)}"
    else:
        stage = value
    if stage not in STAGES:
        raise argparse.ArgumentTypeError(f"unknown stage: {value}")
    return stage


def run_preflight(project: Path, gate: str, timeout: int = 60, completing_stage: str | None = None) -> tuple[bool, str, str]:
    script = project / "tools" / "loop_preflight.py"
    command = [sys.executable, str(script), str(project), "--stage", gate]
    if completing_stage:
        command += ["--completing-stage", completing_stage]
    if not script.exists():
        output = "- ERROR: 预检脚本缺失：tools/loop_preflight.py"
        return False, " ".join(command), output
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        output = f"- ERROR: 预检脚本执行超时（>{timeout}s）：tools/loop_preflight.py --stage {gate}"
        return False, " ".join(command), output
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0 and "- ERROR:" not in output:
        detail = output.splitlines()[0] if output else "无输出"
        output = f"- ERROR: 预检脚本执行失败：{detail}"
    return result.returncode == 0, " ".join(command), output


def parse_preflight_errors(output: str) -> list[str]:
    errors = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("- ERROR:"):
            errors.append(line.removeprefix("- ERROR:").strip())
    return errors


def classify_error(error: str) -> tuple[str, str, str]:
    """Return owner, summary, suggested action for a technical preflight error."""
    if any(marker in error for marker in ["PM 计划", "计划未标记", "当前迭代名称未确认", "project-startup-plan", "启动规划"]):
        return (
            "pm",
            "计划确认不完整",
            "确认产品目标、目标用户、范围、非范围、资料来源、页面结构和交付目标，并让 Agent 写入 memory/project-startup-plan.md。",
        )
    if any(marker in error for marker in ["field-map", "字段映射", "FLD-"]):
        return (
            "agent",
            "字段级资料未完成",
            "让 Agent 阅读 API 文档、参考项目或截图，提取字段、枚举、页面位置、展示规则，写入 memory/field-map.md。",
        )
    if any(marker in error for marker in ["项目记忆基线", "memory/project.md", "decisions.md"]):
        return (
            "agent",
            "项目记忆未更新到当前迭代",
            "让 Agent 根据已冻结的启动规划更新 memory/project.md、memory/business-rules.md、memory/source-materials.md、memory/field-map.md 和 docs/decisions.md。",
        )
    if any(marker in error for marker in ["source-materials", "SRC-"]):
        return (
            "agent",
            "资料来源未整理",
            "让 Agent 把输入资料、文档、截图、历史项目和口述内容整理为 SRC-* 来源记录。",
        )
    if any(marker in error for marker in ["interaction.html", "交互说明"]):
        return (
            "agent",
            "交互说明未生成",
            "让 Agent 基于已验证原型、验收映射和标注内容生成 docs/interaction.html。",
        )
    if "流程图链接" in error:
        return (
            "pm",
            "ProcessOn 流程图链接无效",
            "修正 flowcharts/processon-links.txt 中对应行，使用有效的 ProcessOn HTTP(S) 分享或嵌入链接。",
        )
    if any(marker in error for marker in ["task-plan", "execution-steps", "acceptance-map", "执行步骤", "验收映射"]):
        return (
            "agent",
            "任务拆分或验收映射不完整",
            "让 Agent 重新执行 S6 拆分，补齐 task-plan、execution-steps 和 acceptance-map。",
        )
    if any(marker in error for marker in ["final 交付快照", "final-snapshot", "重新运行 final"]):
        return (
            "system",
            "final 状态已失效",
            "当前文件已晚于最后一次 final pass 或快照不一致，请重新运行 final 预检并重新完成 S9。",
        )
    if any(marker in error for marker in ["阶段状态不一致", "阶段日志", "预检命令", "workflow.json", "stage-log"]):
        return (
            "system",
            "阶段状态不一致",
            "使用 tools/loop_run.py complete 重新推进阶段，不要手写 stage-log 或 workflow.json。",
        )
    if any(marker in error for marker in ["verification-log", "验证记录", "Evidence", "Result=pass"]):
        return (
            "verifier",
            "验证证据不可信",
            "让 Agent 重新运行对应验证，写入明确的本地命令、浏览器检查和通过证据。",
        )
    if any(marker in error for marker in ["node_modules", "package.json", "package-lock.json", "playwright-report", "test-results", "交付目录"]):
        return (
            "cleanup",
            "交付目录包含不应交付的依赖或测试产物",
            "清理 node_modules、package.json、package-lock.json、playwright-report 或 test-results，除非项目明确允许依赖。",
        )
    if any(marker in error for marker in ["占位", "内容过短", "待补充", "缺失标准文件", "缺失"]):
        return (
            "agent",
            "关键文件缺失或仍是模板内容",
            "让 Agent 补齐对应文件内容，不能用模板占位进入下一阶段。",
        )
    if "熔断" in error:
        return (
            "pm",
            "自动修复已触发熔断",
            "请决定继续修复、回到拆分、回到需求确认，或终止当前 loop。",
        )
    return (
        "agent",
        "存在未分类阻塞项",
        "让 Agent 查看技术错误原文并补齐对应产物。",
    )



def suggest_backflow(error: str) -> tuple[str, str, str] | None:
    """Return target stage, owner, and reason for deterministic PM-readable backflow.

    This is advisory only. It does not mutate workflow state and does not replace
    preflight gates.
    """
    if any(marker in error for marker in ["PM 计划", "project-startup-plan", "启动规划", "当前迭代名称未确认"]):
        return ("S1", STAGE_DISPATCH["S1"]["owner"], "补齐或重新确认启动规划")
    if any(marker in error for marker in ["CLAUDE.md", "项目级执行规则", "计划门禁"]):
        return ("S2", STAGE_DISPATCH["S2"]["owner"], "重写项目级执行规则并复核计划门禁")
    if any(marker in error for marker in ["field-map", "字段映射", "FLD-", "source-materials", "SRC-", "项目记忆基线", "memory/project.md", "business-rules", "decisions.md"]):
        return ("S3", STAGE_DISPATCH["S3"]["owner"], "补项目记忆、资料来源或字段事实")
    if any(marker in error for marker in ["tools/loop_preflight.py", "tools/loop_run.py", "缺失标准文件", "标准原型项目结构"]):
        if "project-structure" in error:
            return ("S5", STAGE_DISPATCH["S5"]["owner"], "重新读取真实项目结构")
        return ("S4", STAGE_DISPATCH["S4"]["owner"], "修复或迁移标准项目结构")
    if any(marker in error for marker in ["project-structure", "项目结构"]):
        return ("S5", STAGE_DISPATCH["S5"]["owner"], "重新生成结构摘要")
    if any(marker in error for marker in ["task-plan", "execution-steps", "acceptance-map", "执行步骤", "验收映射", "步骤 ID"]):
        return ("S6", STAGE_DISPATCH["S6"]["owner"], "修订拆分颗粒度和验收映射")
    if any(marker in error for marker in ["data-anno", "锚点", "target", "change-log"]):
        return ("S7", STAGE_DISPATCH["S7"]["owner"], "修复实现、源码锚点或单步变更记录")
    if any(marker in error for marker in ["verification-log", "验证记录", "Evidence", "Result=pass"]):
        if any(marker in error for marker in ["global", "全局", "Scope: global"]):
            return ("S8", STAGE_DISPATCH["S8"]["owner"], "重跑全局验证并更新验收结果")
        return ("S7", STAGE_DISPATCH["S7"]["owner"], "重跑单步验证并补证据")
    if any(marker in error for marker in ["annotation-prompt", "annotation-coverage", "interaction.html", "annotations.js", "标注", "sourceRefs", "fieldRefs", "final 交付快照", "final-snapshot", "重新运行 final"]):
        return ("S9", STAGE_DISPATCH["S9"]["owner"], "重新生成标注提示词、覆盖清单或重跑收尾终检")
    if "流程图链接" in error:
        return ("PM", "PM", "修正 ProcessOn 链接清单后重新运行 final")
    if "熔断" in error:
        return ("PM", "PM", "暂停自动重试并选择继续、回流或终止")
    return None


def collect_backflows(errors: list[str]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for error in errors:
        item = suggest_backflow(error)
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out

def current_stage_label(workflow: dict) -> str:
    raw_stage = str(workflow.get("stage") or "unknown")
    stage = raw_stage.upper()
    if stage.startswith("S") and stage[1:].isdigit():
        return f"{stage} {STAGE_NAMES.get(stage, '')}".strip()
    return stage


def has_blocking_status(project: Path) -> bool:
    path = project / "memory" / "loop-status.md"
    if not path.exists():
        return False
    text = read_text(path)
    return "- 是否可继续：不能继续" in text or "## 阻塞原因" in text


def write_loop_status(
    project: Path,
    *,
    title: str,
    passed: bool | None,
    gate: str | None = None,
    stage: str | None = None,
    output: str = "",
    next_step: str = "",
) -> None:
    workflow = load_json(project / "config" / "workflow.json")
    errors = parse_preflight_errors(output)
    grouped: dict[str, list[tuple[str, str, str]]] = {}
    seen_actions: set[tuple[str, str, str]] = set()
    for error in errors:
        owner, summary, action = classify_error(error)
        action_key = (owner, summary, action)
        if action_key not in seen_actions:
            grouped.setdefault(owner, []).append((summary, action, error))
            seen_actions.add(action_key)

    dirty_errors = final_dirty_errors(project)
    if dirty_errors and passed is None:
        passed = False
        errors.extend(dirty_errors)
        for error in dirty_errors:
            owner, summary, action = classify_error(error)
            action_key = (owner, summary, action)
            if action_key not in seen_actions:
                grouped.setdefault(owner, []).append((summary, action, error))
                seen_actions.add(action_key)
    status_text = "未运行门禁" if passed is None else ("可以继续" if passed else "不能继续")
    lines = [
        "# Loop 状态",
        "",
        f"- 更新时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 项目目录：`{project}`",
        f"- 当前阶段：{current_stage_label(workflow)}",
        f"- 本次检查：{title}",
        f"- 检查门禁：{gate or 'none'}",
        f"- 阶段操作：{stage or 'none'}",
        f"- 是否可继续：{status_text}",
        "",
    ]

    if passed:
        lines.extend(
            [
                "## 下一步",
                "",
                next_step or "当前检查已通过，可以进入下一步。",
                "",
            ]
        )
    elif errors:
        lines.extend(["## 阻塞原因", ""])
        for owner, items in grouped.items():
            lines.append(f"### {OWNER_ACTIONS.get(owner, owner)}")
            lines.append("")
            for index, (summary, action, _) in enumerate(items, start=1):
                lines.append(f"{index}. {summary}")
                lines.append(f"   - 建议处理：{action}")
            lines.append("")
        backflows = collect_backflows(errors)
        if backflows:
            lines.extend(["## 回流建议", ""])
            for target_stage, owner, reason in backflows:
                if target_stage in STAGE_NAMES:
                    lines.append(f"- {target_stage} {STAGE_NAMES[target_stage]}：{reason}（owner: `{owner}`）")
                else:
                    lines.append(f"- {target_stage}：{reason}（owner: `{owner}`）")
            lines.append("")
        lines.extend(["## 技术错误原文", ""])
        for error in errors:
            lines.append(f"- {error}")
        lines.append("")
    else:
        lines.extend(
            [
                "## 当前状态",
                "",
                next_step or "尚未运行具体门禁。请根据当前阶段运行对应检查。",
                "",
            ]
        )

    path = project / "memory" / "loop-status.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def stage_index(stage: str) -> int:
    return int(stage[1:])


def expected_prior_stages(stage: str) -> list[str]:
    index = stage_index(stage)
    if index <= 0:
        return []
    return [f"S{i}" for i in range(index)]


def workflow_stages(workflow: dict) -> dict:
    stages = workflow.setdefault("stages", {})
    for stage in STAGES:
        stages.setdefault(stage.lower(), "pending")
    return stages


def ensure_prior_completed(project: Path, stage: str) -> list[str]:
    workflow = load_json(project / "config" / "workflow.json")
    stages = workflow_stages(workflow)
    missing = []
    for prior in expected_prior_stages(stage):
        if stages.get(prior.lower()) != "completed":
            missing.append(prior)
    return missing


def current_workflow_stage(project: Path) -> str:
    workflow = load_json(project / "config" / "workflow.json")
    return str(workflow.get("stage") or "").strip().lower()


def project_record_salt(project: Path) -> str:
    """Project-scoped salt for stage-log record ids.

    This is not a cryptographic secret; it prevents a record copied from another
    project or a legacy stage+date-only hash from validating as the current
    project's script-written record.
    """
    for relative_path in [Path("config/project.json"), Path("config/workflow.json")]:
        data = load_json(project / relative_path)
        for key in ["projectId", "annotationProjectId", "id"]:
            value = data.get(key)
            if value:
                return str(value)
    return "missing-project-id"


def expected_current_stage_values(stage: str) -> set[str]:
    return {stage.lower()}


def stage_is_ready_to_complete(project: Path, stage: str) -> bool:
    current = current_workflow_stage(project)
    return current in expected_current_stage_values(stage)


def _record_id(project: Path, stage: str, ts: str) -> str:
    return hashlib.sha256(f"{project_record_salt(project)}:{stage}:{ts}".encode()).hexdigest()[:12]


def _preflight_hash(output: str) -> str:
    return hashlib.sha256(output.encode()).hexdigest()[:16] if output and output != "none" else "none"


def append_stage_log(
    project: Path,
    stage: str,
    preflight_command: str,
    gate_result: str,
    decision: str,
    input_artifacts: str,
    output_artifacts: str,
    blocked_by: str,
    notes: str,
    preflight_output: str = "",
) -> None:
    path = project / "memory" / "stage-log.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# 阶段日志\n\n## History\n", encoding="utf-8")
    ts = datetime.now().isoformat(timespec="seconds")
    entry = (
        "\n"
        f"date: {ts}\n"
        "writer: tools/loop_run.py\n"
        "record_id_version: project-salted-v2\n"
        f"record_id: {_record_id(project, stage, ts)}\n"
        f"preflight_result_hash: {_preflight_hash(preflight_output)}\n"
        f"stage: {stage}\n"
        f"stage_name: {STAGE_NAMES[stage]}\n"
        f"input_artifacts: {input_artifacts or 'none'}\n"
        f"output_artifacts: {output_artifacts or 'none'}\n"
        f"preflight: {preflight_command or 'none'}\n"
        f"gate_result: {gate_result}\n"
        f"decision: {decision}\n"
        f"next_stage: {NEXT_STAGE[stage]}\n"
        f"blocked_by: {blocked_by or 'none'}\n"
        f"notes: {notes or 'none'}\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def mark_workflow_stage(project: Path, stage: str, status: str) -> None:
    path = project / "config" / "workflow.json"
    workflow = load_json(path)
    stages = workflow_stages(workflow)
    stages[stage.lower()] = status
    workflow["stage"] = stage.lower() if status != "completed" else NEXT_STAGE[stage].lower()
    write_json(path, workflow)


def rollback_workflow_stage(project: Path, stage: str) -> bool:
    """Reset workflow.stage to the given stage so it can be re-completed.

    Returns True if a rollback was performed, False if the stage was already current.
    """
    current = current_workflow_stage(project)
    if current == stage.lower():
        return False
    path = project / "config" / "workflow.json"
    workflow = load_json(path)
    stages = workflow_stages(workflow)
    # Mark the target stage as no-longer-completed so it can be re-done.
    stages[stage.lower()] = "pending"
    workflow["stage"] = stage.lower()
    write_json(path, workflow)
    return True


def complete_stage(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    stage = normalize_stage(args.stage)
    force = getattr(args, "force", False)

    if args.allow_missing_prior:
        output = "- ERROR: --allow-missing-prior 已停用；项目必须从 S0 开始按顺序推进，不能跳过前置阶段。"
        write_loop_status(
            project,
            title=f"完成 {stage}",
            passed=False,
            stage=stage,
            output=output,
            next_step="请按顺序完成前置阶段，不要跳过状态机。",
        )
        print(output)
        return 1

    if not stage_is_ready_to_complete(project, stage):
        if force:
            current = current_workflow_stage(project) or "unknown"
            expected_current = NEXT_STAGE[stage].lower()
            if current != expected_current:
                output = (
                    f"- ERROR: --force 只能重做当前阶段的前一阶段；"
                    f"当前 workflow.stage={current}，允许重做的阶段应推进到 {current}，不能重做 {stage}。"
                )
                write_loop_status(
                    project,
                    title=f"完成 {stage}",
                    passed=False,
                    stage=stage,
                    output=output,
                    next_step="请只回退一个阶段；如需更早阶段，先明确记录范围变更并重新走对应流程。",
                )
                print(output)
                return 1
            rolled = rollback_workflow_stage(project, stage)
            if rolled:
                print(f"Workflow stage rolled back to {stage} (--force).")
            else:
                print(f"Workflow stage is already {stage}.")
        else:
            current = current_workflow_stage(project) or "unknown"
            output = f"- ERROR: 当前 workflow.stage={current}，不能完成 {stage}。如需回退并重新完成，请使用 --force。"
            write_loop_status(
                project,
                title=f"完成 {stage}",
                passed=False,
                stage=stage,
                output=output,
                next_step="请查看 config/workflow.json 的当前阶段，或使用 --force 回退并重新完成。",
            )
            print(output)
            return 1

    missing = ensure_prior_completed(project, stage)
    if missing:
        output = f"- ERROR: 前置阶段未完成：{', '.join(missing)}"
        write_loop_status(
            project,
            title=f"完成 {stage}",
            passed=False,
            stage=stage,
            output=output,
            next_step="请先按顺序完成前置阶段，再重新运行阶段完成命令。",
        )
        print(f"Cannot complete {stage}; prior stages are not completed: {', '.join(missing)}")
        return 1

    if stage in {"S1", "S2"}:
        startup_errors = validate_startup_plan(project)
        if startup_errors:
            output = "\n".join(f"- ERROR: {item}" for item in startup_errors)
            write_loop_status(
                project,
                title=f"完成 {stage}",
                passed=False,
                stage=stage,
                output=output,
                next_step="请在 S1 补齐 memory/project-startup-plan.md；S2 后该文件将冻结为只读溯源快照。",
            )
            print(output)
            return 1

    if stage == "S2":
        claude_errors = validate_claude_rules(project)
        if claude_errors:
            output = "\n".join(f"- ERROR: {item}" for item in claude_errors)
            write_loop_status(
                project,
                title=f"完成 {stage}",
                passed=False,
                stage=stage,
                output=output,
                next_step="请根据已确认的 memory/project-startup-plan.md 写入项目级 CLAUDE.md，再重新完成 S2。",
            )
            print(output)
            return 1

    if stage == "S3":
        memory_errors = validate_project_memory(project)
        if memory_errors:
            output = "\n".join(f"- ERROR: {item}" for item in memory_errors)
            write_loop_status(
                project,
                title=f"完成 {stage}",
                passed=False,
                stage=stage,
                output=output,
                next_step="请基于 S1 启动规划和 S2 CLAUDE.md 初始化 memory/project.md、business-rules、source-materials、field-map 和 open-items。",
            )
            print(output)
            return 1

    gate = COMPLETION_GATES.get(stage)
    preflight_command = "none"
    output = ""
    if gate:
        passed, preflight_command, output = run_preflight(project, gate, completing_stage=stage)
        if not passed:
            append_stage_log(
                project,
                stage,
                preflight_command,
                "fail",
                f"{stage} blocked by preflight {gate}",
                args.input_artifacts,
                args.output_artifacts,
                f"preflight {gate}",
                output.splitlines()[0] if output else "preflight failed",
                preflight_output=output,
            )
            write_loop_status(
                project,
                title=f"完成 {stage}",
                passed=False,
                gate=gate,
                stage=stage,
                output=output,
                next_step="请先处理阻塞原因，再重新运行阶段完成命令。",
            )
            print(output)
            return 1

    # Write stage-log BEFORE advancing workflow stage (F20).
    # If the stage-log append fails, the workflow stage is unchanged and the
    # operation can be retried safely.
    reminder = STAGE_REMINDERS.get(NEXT_STAGE[stage], "")
    append_stage_log(
        project,
        stage,
        preflight_command,
        "pass",
        args.decision or f"{stage} completed",
        args.input_artifacts,
        args.output_artifacts,
        "none",
        args.notes,
        preflight_output=output,
    )
    if stage == "S2":
        freeze_startup_plan(project)
        approved_at = datetime.now().isoformat(timespec="seconds")
        mark_iteration_flags(
            project,
            planConfirmed=True,
            projectRulesWritten=True,
            confirmedAt=approved_at,
            pmApprovedAt=approved_at,
            startupPlanFrozenAt=approved_at,
        )
    if stage == "S3":
        mark_iteration_flags(project, memoryInitialized=True)
    if stage == "S9":
        write_final_snapshot(project)
    mark_workflow_stage(project, stage, "completed")
    next_step = f"{stage} 已完成。下一阶段：{NEXT_STAGE[stage]}。"
    if reminder:
        next_step += f" 注意：{reminder}"
    write_loop_status(
        project,
        title=f"完成 {stage}",
        passed=True,
        gate=gate,
        stage=stage,
        output=output,
        next_step=next_step,
    )
    print(f"Stage {stage} completed. Next stage: {NEXT_STAGE[stage]}")
    return 0



def dispatch(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    workflow = load_json(project / "config" / "workflow.json")
    raw_stage = str(workflow.get("stage") or "s0").strip().lower()
    if raw_stage == "none":
        payload = {
            "project": str(project),
            "stage": "none",
            "stageName": "终态",
            "owner": None,
            "skill": None,
            "contract": None,
            "supportSkills": [],
            "preflightStage": "final",
            "completeCommand": None,
            "checkCommand": "python3 tools/loop_run.py check . --preflight-stage final",
            "tokenPolicy": "final_snapshot_scoped",
            "finalDirty": final_dirty_report(project),
            "nextAction": "如果 finalDirty.dirty=true，回到 S9 重跑 final；否则 loop 已结束。",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    stage = raw_stage.upper()
    if stage not in STAGES:
        payload = {
            "project": str(project),
            "stage": raw_stage,
            "error": f"unknown workflow stage: {raw_stage}",
            "nextAction": "检查 config/workflow.json；所有项目必须从 S0 按顺序推进。",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    info = dict(STAGE_DISPATCH[stage])
    gate = COMPLETION_GATES.get(stage)
    skill_source = info["skill"]
    contract_source = info["contract"]
    payload = {
        "project": str(project),
        "stage": stage.lower(),
        "stageName": STAGE_NAMES[stage],
        "owner": info["owner"],
        "skill": dispatch_resource_path(project, skill_source),
        "skillSource": skill_source,
        "skillAvailable": dispatch_resource_available(project, skill_source),
        "contract": dispatch_resource_path(project, contract_source),
        "contractSource": contract_source,
        "contractAvailable": dispatch_resource_available(project, contract_source),
        "supportSkills": info["supportSkills"],
        "preflightStage": gate,
        "completeCommand": f"python3 tools/loop_run.py complete . --stage {stage}",
        "checkCommand": f"python3 tools/loop_run.py check . --preflight-stage {gate}" if gate else None,
        "tokenPolicy": info["tokenPolicy"],
        "finalDirty": final_dirty_report(project),
        "nextAction": "读取 skill 和 contract 指向的项目内文件；完成本阶段产物后交回总控运行 complete。",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def status(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    workflow = load_json(project / "config" / "workflow.json")
    stages = workflow_stages(workflow)
    if not has_blocking_status(project):
        write_loop_status(
            project,
            title="查看状态",
            passed=None,
            output="",
            next_step="请根据当前阶段运行 `tools/loop_run.py check` 或让 Agent 继续处理阻塞项。",
        )
    print(json.dumps({"project": str(project), "stage": workflow.get("stage"), "stages": stages, "toolVersion": LOOP_TOOL_VERSION, "finalDirty": final_dirty_report(project)}, ensure_ascii=False, indent=2))
    return 0


def check(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    gate = args.preflight_stage
    passed, _, output = run_preflight(project, gate)
    write_loop_status(
        project,
        title=f"检查 {gate}",
        passed=passed,
        gate=gate,
        output=output,
        next_step=f"{gate} 检查已通过，可以继续对应阶段。" if passed else "请先处理阻塞原因，再继续下一阶段。",
    )
    print(output)
    return 0 if passed else 1


def report(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    if not has_blocking_status(project):
        write_loop_status(
            project,
            title="生成报告",
            passed=None,
            output="",
            next_step="请查看本文件的当前阶段和建议动作。",
        )
    print(project / "memory" / "loop-status.md")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Print workflow status")
    status_parser.add_argument("project", nargs="?", default=".")
    status_parser.set_defaults(func=status)

    dispatch_parser = subparsers.add_parser("dispatch", help="Print current stage owner, contract, support skills and handoff commands")
    dispatch_parser.add_argument("project", nargs="?", default=".")
    dispatch_parser.set_defaults(func=dispatch)

    report_parser = subparsers.add_parser("report", help="Write PM-readable loop status")
    report_parser.add_argument("project", nargs="?", default=".")
    report_parser.set_defaults(func=report)

    check_parser = subparsers.add_parser("check", help="Run one preflight gate")
    check_parser.add_argument("project", nargs="?", default=".")
    check_parser.add_argument("--preflight-stage", choices=["s4", "s6", "s7", "s8", "s9", "final"], required=True)
    check_parser.set_defaults(func=check)

    complete_parser = subparsers.add_parser("complete", help="Complete a workflow stage")
    complete_parser.add_argument("project", nargs="?", default=".")
    complete_parser.add_argument("--stage", required=True, type=normalize_stage)
    complete_parser.add_argument("--input-artifacts", default="")
    complete_parser.add_argument("--output-artifacts", default="")
    complete_parser.add_argument("--decision", default="")
    complete_parser.add_argument("--notes", default="")
    complete_parser.add_argument("--allow-missing-prior", action="store_true")
    complete_parser.add_argument("--force", action="store_true", help="Rollback workflow stage and re-complete (e.g. to re-enter S7 from S8)")
    complete_parser.set_defaults(func=complete_stage)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
