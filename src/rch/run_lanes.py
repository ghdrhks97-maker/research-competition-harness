"""Run lanes (`rch run-lanes`).

The harness does not embed external agents. Instead it builds a portable
prompt bundle per lane: the lane instruction plus a listing of the input
files that lane should read, plus the exact output contract. Hand each
bundle to Codex, Antigravity, Claude, or a person. A run manifest
records which lanes were prepared so a conductor can dispatch them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rch.lane_specs import LANE_SPECS, render_lane_input

# Which input folders each lane should be pointed at when bundling prompts.
LANE_INPUT_HINTS: dict[str, tuple[str, ...]] = {
    "intake": ("input/ideas", "input/rules", "input/references", "input/evidence", "input/photos", "input/surveys"),
    "brainstorm": ("input/ideas", "input/rules", "input/evidence"),
    "reference-miner": ("input/references", "input/references/analysis"),
    "evidence-curator": ("input/evidence", "input/surveys/analysis", "input/photos/analysis"),
    "survey-analyzer": ("input/surveys", "input/surveys/analysis"),
    "photo-curator": ("input/photos", "input/photos/analysis"),
    "draft-writer": ("lanes", "input/rules", "input/surveys/analysis"),
    "table-layout": ("lanes/draft-writer", "lanes/reference-miner"),
    "summary-sheet": ("lanes/brainstorm", "lanes/draft-writer"),
    "toc-builder": ("lanes/draft-writer", "lanes/table-layout"),
    "appendix-builder": ("input/evidence", "input/photos/analysis", "input/surveys/analysis"),
    "icon-visual": ("lanes/brainstorm", "lanes/table-layout"),
    "critic": ("lanes", "input/rules"),
    "finalizer": ("lanes", "output"),
}


def _list_inputs(workspace: Path, hints: tuple[str, ...]) -> list[str]:
    files: list[str] = []
    for hint in hints:
        base = workspace / hint
        if not base.exists():
            continue
        if base.is_file():
            files.append(hint)
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.name != ".gitkeep":
                files.append(path.relative_to(workspace).as_posix())
    return files[:200]


def _build_prompt(workspace: Path, lane: str, agent: str) -> str:
    instruction = render_lane_input(lane, agent)
    hints = LANE_INPUT_HINTS.get(lane, ())
    inputs = _list_inputs(workspace, hints)
    lines = [instruction, "", "## 읽을 입력 파일", ""]
    if inputs:
        lines += [f"- `{item}`" for item in inputs]
    else:
        lines.append("- (해당 입력 폴더가 비어 있음. 필요 자료를 먼저 채운다.)")
    lines += [
        "",
        "## 출력 위치",
        "",
        f"`lanes/{lane}/{agent}/` 아래에 lane 계약 파일을 작성한다.",
        "",
    ]
    return "\n".join(lines)


def run_lanes(workspace: Path, agent: str, lanes: list[str] | None = None) -> dict[str, Any]:
    if not workspace.exists():
        raise SystemExit(f"workspace missing: {workspace}")
    selected = lanes or list(LANE_SPECS)
    unknown = [lane for lane in selected if lane not in LANE_SPECS]
    if unknown:
        raise SystemExit(f"unknown lanes: {', '.join(unknown)}")

    prompts_dir = workspace / "prompts" / agent
    prompts_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"agent": agent, "lanes": []}
    for lane in selected:
        prompt = _build_prompt(workspace, lane, agent)
        prompt_path = prompts_dir / f"{lane}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        # Ensure the lane inbox exists so the agent has somewhere to write.
        (workspace / "lanes" / lane / agent / "evidence").mkdir(parents=True, exist_ok=True)
        manifest["lanes"].append({"lane": lane, "prompt": prompt_path.relative_to(workspace).as_posix()})

    manifest_path = prompts_dir / "run-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
