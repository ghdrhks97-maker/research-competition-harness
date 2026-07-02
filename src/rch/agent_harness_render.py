from __future__ import annotations

from typing import Any


def render_harness_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# Agent Harness Conductor Pack",
        "",
        f"- Workspace: `{pack['workspace']}`",
        f"- Final candidate ready: `{str(pack['final_candidate_ready']).lower()}`",
        f"- Verdict: `{pack['readiness']['verdict']}`",
        "",
        "## Agents",
        "",
        *[f"- `{agent}`" for agent in pack["agents"]],
        "",
        "## Missing Inputs",
        "",
    ]
    if pack["missing_inputs"]:
        lines += ["| id | item | action | path |", "| --- | --- | --- | --- |"]
        for item in pack["missing_inputs"]:
            lines.append(f"| {item['id']} | {item['item']} | {item['action']} | `{item['path']}` |")
    else:
        lines.append("필수 입력 상태가 충족되었다. 그래도 final gate는 별도로 통과해야 한다.")
    lines += ["", "## Collection Kit", ""]
    lines += [f"{step['step']}. {step['action']} (`{step['path']}`)" for step in pack["collection_kit"]]
    lines += ["", "## Commands", ""]
    lines += [f"- `{command['command']}` - {command['purpose']}" for command in pack["commands"]]
    lines += ["", "## Quality Gates", ""]
    lines += [f"- **{gate['name']}**: {gate['check']}" for gate in pack["quality_gates"]]
    lines += ["", "## Final Check", ""]
    lines += [f"- ok: `{str(pack['final_check']['ok']).lower()}`"]
    lines += [f"- errors: `{len(pack['final_check']['errors'])}`"]
    lines += ["", "## Anti-Fabrication Rules", ""]
    lines += [f"- {rule}" for rule in pack["anti_fabrication_rules"]]
    lines += ["", "## Preserved Rule Files", ""]
    rule_files = pack["input_state"]["rules"]["files"]
    if rule_files:
        lines += [f"- `{item['stored_path']}` ({item['kind']})" for item in rule_files]
    else:
        lines.append("- 없음. `rch import-rules`로 공문·양식·심사표를 먼저 보존한다.")
    lines.append("")
    return "\n".join(lines)


def render_conductor_prompt(pack: dict[str, Any]) -> str:
    lines = [
        "# conductor: rch agent-harness",
        "",
        "You are the conductor for a Korean research competition report workspace.",
        "직접 가짜 증거를 만들지 않는다. 이 pack은 에이전트 실행 순서와 품질 gate를 정리하는 지휘 표면이다.",
        "",
        "## Mission",
        "",
        "1. 대회명, 규정, 심사표, 양식 파일을 먼저 확인한다.",
        "2. 누락 입력은 collection kit 순서로 사용자에게 요청하거나 `input/`에 저장한다.",
        "3. lane 에이전트에게 명령을 배정하되 claim-ledger와 verdict 계약을 유지한다.",
        "4. HWPX는 page budget을 먼저 맞춘 뒤 Hancom/HOP 실제 렌더로 최종 확인한다.",
        "",
        "## Current Verdict",
        "",
        f"- final_candidate_ready: `{str(pack['final_candidate_ready']).lower()}`",
        f"- readiness: `{pack['readiness']['verdict']}`",
        "",
        "## Execute",
        "",
        *[f"- `{command['command']}`" for command in pack["commands"]],
        "",
        "## Anti-Fabrication Rules",
        "",
        *[f"- {rule}" for rule in pack["anti_fabrication_rules"]],
        "",
    ]
    return "\n".join(lines)
