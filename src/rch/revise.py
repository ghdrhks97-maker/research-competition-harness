"""Revise loop (`rch revise-loop`).

Collects feedback from three sources — the critic lane's machine feedback,
the harness check report, and the render check — into one prioritized
revision backlog. Each task is tagged auto-fixable or needs-human so the
next pass (agents or people) knows exactly what to change. This closes the
quality loop: draft → check → render-check → revise → draft again.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SEVERITY_ORDER = {"blocking": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@dataclass
class RevisionTask:
    id: str
    source: str
    severity: str
    location: str
    instruction: str
    auto_fixable: bool


@dataclass
class RevisionBacklog:
    tasks: list[RevisionTask] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"tasks": [asdict(task) for task in self.tasks]}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _collect_critic(workspace: Path, backlog: RevisionBacklog) -> None:
    index = 0
    for path in sorted(workspace.glob("lanes/critic/*/machine-feedback.json")):
        data = _read_json(path)
        issues = data.get("issues") if isinstance(data, dict) else None
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            index += 1
            backlog.tasks.append(
                RevisionTask(
                    id=f"critic-{index}",
                    source="critic",
                    severity=str(issue.get("severity", "medium")),
                    location=str(issue.get("location", "")),
                    instruction=str(issue.get("instruction", issue.get("text", ""))),
                    auto_fixable=bool(issue.get("auto_fixable", False)),
                )
            )


def _collect_check(workspace: Path, backlog: RevisionBacklog) -> None:
    data = _read_json(workspace / "output" / "harness-check.json")
    if not isinstance(data, dict):
        return
    for index, error in enumerate(data.get("errors", []), 1):
        backlog.tasks.append(
            RevisionTask(
                id=f"check-error-{index}",
                source="check",
                severity="blocking",
                location="",
                instruction=str(error),
                auto_fixable=False,
            )
        )
    for index, warning in enumerate(data.get("warnings", []), 1):
        backlog.tasks.append(
            RevisionTask(
                id=f"check-warn-{index}",
                source="check",
                severity="medium",
                location="",
                instruction=str(warning),
                auto_fixable=False,
            )
        )


def _collect_render(workspace: Path, backlog: RevisionBacklog) -> None:
    data = _read_json(workspace / "output" / "render-check.json")
    if not isinstance(data, dict):
        return
    for index, error in enumerate(data.get("errors", []), 1):
        backlog.tasks.append(
            RevisionTask(
                id=f"render-error-{index}",
                source="render-check",
                severity="blocking",
                location=str(data.get("hwpx_path", "")),
                instruction=str(error),
                auto_fixable=False,
            )
        )
    for index, warning in enumerate(data.get("warnings", []), 1):
        backlog.tasks.append(
            RevisionTask(
                id=f"render-warn-{index}",
                source="render-check",
                severity="high",
                location=str(data.get("hwpx_path", "")),
                instruction=str(warning),
                auto_fixable=False,
            )
        )


def build_backlog(workspace: Path) -> RevisionBacklog:
    backlog = RevisionBacklog()
    _collect_critic(workspace, backlog)
    _collect_check(workspace, backlog)
    _collect_render(workspace, backlog)
    backlog.tasks.sort(key=lambda task: (SEVERITY_ORDER.get(task.severity, 5), task.id))
    return backlog


def render_backlog_markdown(backlog: RevisionBacklog) -> str:
    lines = ["# 수정 백로그", "", f"- 총 {len(backlog.tasks)}건", ""]
    if not backlog.tasks:
        lines.append("현재 수집된 수정 요청이 없다. critic/check/render-check를 먼저 실행한다.")
        lines.append("")
        return "\n".join(lines)
    lines += ["| ID | 출처 | 심각도 | 자동수정 | 위치 | 지시 |", "| --- | --- | --- | --- | --- | --- |"]
    for task in backlog.tasks:
        lines.append(
            f"| {task.id} | {task.source} | {task.severity} | {'예' if task.auto_fixable else '아니오'} "
            f"| {task.location} | {task.instruction} |"
        )
    lines.append("")
    lines.append("## 처리 순서")
    lines.append("")
    lines.append("1. blocking 항목을 먼저 해소한다.")
    lines.append("2. 자동수정 항목은 해당 lane 재실행으로 반영한다.")
    lines.append("3. 사람 확인 항목은 근거/동의/개인정보를 확인한 뒤 반영한다.")
    lines.append("")
    return "\n".join(lines)


def run_revise_loop(workspace: Path) -> RevisionBacklog:
    if not workspace.exists():
        raise SystemExit(f"workspace missing: {workspace}")
    backlog = build_backlog(workspace)
    output_dir = workspace / "output"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "revision-tasks.json").write_text(
        json.dumps(backlog.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "revision-tasks.md").write_text(render_backlog_markdown(backlog), encoding="utf-8")
    return backlog
