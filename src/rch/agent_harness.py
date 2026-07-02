from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rch import agent_harness_state as state_mod
from rch import rules as rules_mod
from rch.agent_harness_render import render_conductor_prompt, render_harness_markdown
from rch.agent_harness_spec import ANTI_FABRICATION_RULES, commands, phases, quality_gates


@dataclass(frozen=True, slots=True)
class HarnessResult:
    json_path: str
    markdown_path: str
    prompt_path: str
    final_candidate_ready: bool
    missing_inputs: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def generate_agent_harness(
    workspace: Path,
    agents: tuple[str, ...] = ("codex",),
    offline_research: bool = False,
) -> HarnessResult:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "output").mkdir(exist_ok=True)
    (workspace / "prompts" / "conductor").mkdir(parents=True, exist_ok=True)
    rules_mod.rules_root(workspace)

    pack = build_agent_harness_pack(workspace, agents, offline_research)
    json_path = workspace / "output" / "agent-harness.json"
    markdown_path = workspace / "output" / "agent-harness.md"
    prompt_path = workspace / "prompts" / "conductor" / "agent-harness.md"
    json_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_harness_markdown(pack), encoding="utf-8")
    prompt_path.write_text(render_conductor_prompt(pack), encoding="utf-8")
    return HarnessResult(
        json_path=json_path.relative_to(workspace).as_posix(),
        markdown_path=markdown_path.relative_to(workspace).as_posix(),
        prompt_path=prompt_path.relative_to(workspace).as_posix(),
        final_candidate_ready=bool(pack["final_candidate_ready"]),
        missing_inputs=list(pack["missing_inputs"]),
    )


def build_agent_harness_pack(workspace: Path, agents: tuple[str, ...], offline_research: bool) -> dict[str, Any]:
    input_state = state_mod.input_state(workspace)
    missing_inputs = state_mod.missing_inputs(input_state)
    final_check = state_mod.final_check(workspace)
    final_candidate_ready = state_mod.final_candidate_ready(workspace, missing_inputs, final_check)
    return {
        "schema": "rch.agent-harness.v1",
        "workspace": str(workspace),
        "final_candidate_ready": final_candidate_ready,
        "readiness": state_mod.readiness(final_candidate_ready, missing_inputs, final_check),
        "missing_inputs": missing_inputs,
        "collection_kit": state_mod.collection_kit(missing_inputs),
        "agents": list(agents),
        "phases": phases(),
        "commands": commands(agents, offline_research),
        "quality_gates": quality_gates(),
        "anti_fabrication_rules": list(ANTI_FABRICATION_RULES),
        "input_state": input_state,
        "final_check": final_check,
    }
