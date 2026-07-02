"""Autopilot state machine (`rch next`).

Deterministically inspects a workspace and answers one question: "what is
the next action on the way to a finished report?" The hosting agent app
(Claude Code / Codex / Antigravity) calls this in a loop after the
interview plan is approved — if `needs_user` is empty it executes the
returned actions with its own subagents, then calls `next` again, until
`done` is true or something genuinely requires the user.

This module only reads workspace state and applies the pipeline's
dependency rules; it never generates content and never calls an LLM.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

CONTRACT_FILES = ("lane-output.md", "lane-output.json", "claim-ledger.json", "verdict.json")
SURVEY_SUFFIXES = {".csv", ".tsv", ".tab", ".xlsx", ".xlsm"}

# Dependency groups (a group's lanes may run in parallel).
PHASE1_LANES = (
    "intake",
    "brainstorm",
    "reference-miner",
    "evidence-curator",
    "survey-analyzer",
    "photo-curator",
)
PHASE3B_LANES = ("summary-sheet", "toc-builder", "appendix-builder", "icon-visual")

# Lane -> role briefing to delegate to (.claude/agents/<role>.md).
LANE_ROLES = {
    "intake": "evidence-curator",
    "brainstorm": "brainstorm",
    "reference-miner": "reference-miner",
    "evidence-curator": "evidence-curator",
    "survey-analyzer": "survey-analyst",
    "photo-curator": "photo-curator",
    "draft-writer": "draft-writer",
    "table-layout": "table-layout",
    "summary-sheet": "summary-sheet",
    "toc-builder": "toc-builder",
    "appendix-builder": "appendix-builder",
    "icon-visual": "table-layout",
    "critic": "critic",
    "finalizer": "finalizer",
}

LANE_MISSING = "missing"
LANE_NEEDS_WORK = "needs-work"
LANE_BLOCKED = "blocked"
LANE_PASS = "pass"


@dataclass
class NextPlan:
    phase: str
    done: bool = False
    parallel: bool = False
    needs_user: list[str] = field(default_factory=list)
    actions: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _lane_status(workspace: Path, lane: str) -> tuple[str, str]:
    """Best status across agent dirs of a lane, with the blocking reason if any."""
    lane_root = workspace / "lanes" / lane
    if not lane_root.exists():
        return LANE_MISSING, ""
    best = LANE_MISSING
    reason = ""
    for agent_dir in sorted(path for path in lane_root.iterdir() if path.is_dir()):
        if not all((agent_dir / name).exists() for name in CONTRACT_FILES):
            continue
        verdict = _read_json(agent_dir / "verdict.json")
        status = verdict.get("status") if isinstance(verdict, dict) else None
        if status == "pass":
            return LANE_PASS, ""
        if status == "blocked":
            best = LANE_BLOCKED
            reason = str(verdict.get("reason", "")) if isinstance(verdict, dict) else ""
        elif best == LANE_MISSING:
            best = LANE_NEEDS_WORK
    return best, reason


def _delegate(lane: str, detail: str = "") -> dict[str, str]:
    return {
        "kind": "delegate",
        "lane": lane,
        "role": LANE_ROLES.get(lane, lane),
        "detail": detail or f"lanes/{lane}/ 계약 파일 4종을 완성하고 verdict pass로 만든다.",
    }


def _run(command: str, detail: str) -> dict[str, str]:
    return {"kind": "run", "command": command, "detail": detail}


def plan_approved(workspace: Path) -> bool:
    profile = _read_json(workspace / "input" / "rules" / "competition-profile.json")
    return bool(isinstance(profile, dict) and profile.get("plan_approved"))


def has_expected_claims(workspace: Path) -> bool:
    for path in workspace.glob("lanes/*/*/claim-ledger.json"):
        data = _read_json(path)
        claims = data.get("claims") if isinstance(data, dict) else None
        if isinstance(claims, list) and any(
            isinstance(claim, dict) and claim.get("status") == "expected" for claim in claims
        ):
            return True
    return False


def _pending_survey_file(workspace: Path) -> Path | None:
    surveys = workspace / "input" / "surveys"
    if (surveys / "analysis" / "survey-summary.md").exists():
        return None
    if not surveys.exists():
        return None
    for path in sorted(surveys.iterdir()):
        if path.is_file() and path.suffix.lower() in SURVEY_SUFFIXES:
            return path
    return None


def compute_next(
    workspace: Path,
    final_check: Callable[..., Any] | None = None,
) -> NextPlan:
    """Return the next pipeline step. `final_check` is `cli.check_workspace`
    (injected to avoid a circular import); it must accept
    (workspace, final=, allow_expected=) and return an object with
    `.ok` and `.errors`."""
    if not workspace.exists():
        return NextPlan(
            phase="setup",
            actions=[_run(f"rch init {workspace}", "작업공간 골격 생성")],
        )

    # Any blocked verdict is a hard stop: only the user can unblock it.
    blocked: list[str] = []
    for lane in LANE_ROLES:
        status, reason = _lane_status(workspace, lane)
        if status == LANE_BLOCKED:
            blocked.append(f"{lane}: {reason or 'verdict blocked'}")
    if blocked:
        return NextPlan(phase="blocked", needs_user=blocked)

    if not plan_approved(workspace):
        return NextPlan(
            phase="interview",
            needs_user=[
                "deep-interview 인터뷰와 계획 승인이 필요합니다. 승인되면 "
                'input/rules/competition-profile.json 에 "plan_approved": true 를 기록하세요.'
            ],
        )

    # Phase 1 — parallel analysis/research lanes.
    actions: list[dict[str, str]] = []
    survey_file = _pending_survey_file(workspace)
    if survey_file is not None:
        actions.append(
            _run(
                f"rch import-survey {workspace} {survey_file}",
                "실제 설문 통계를 파이썬으로 계산(survey-analyst보다 먼저)",
            )
        )
    for lane in PHASE1_LANES:
        status, _ = _lane_status(workspace, lane)
        if status != LANE_PASS:
            detail = ""
            if lane == "reference-miner":
                detail = (
                    "우수 보고서 구조 분석. background-researcher도 이 lane에 "
                    "이론적 배경·선행연구를 병렬로 반영한다."
                )
            actions.append(_delegate(lane, detail))
    if actions:
        return NextPlan(phase="phase1-analysis", parallel=True, actions=actions)

    # Phase 2 — draft.
    status, _ = _lane_status(workspace, "draft-writer")
    if status != LANE_PASS:
        return NextPlan(phase="phase2-draft", actions=[_delegate("draft-writer")])

    # Phase 3 — table-layout first, then the parallel companions.
    status, _ = _lane_status(workspace, "table-layout")
    if status != LANE_PASS:
        return NextPlan(phase="phase3-layout", actions=[_delegate("table-layout")])
    actions = [
        _delegate(lane)
        for lane in PHASE3B_LANES
        if _lane_status(workspace, lane)[0] != LANE_PASS
    ]
    if actions:
        return NextPlan(phase="phase3-companions", parallel=True, actions=actions)

    # Phase 4 — critic (needs rubric-score.json as well).
    status, _ = _lane_status(workspace, "critic")
    rubric_done = any(workspace.glob("lanes/critic/*/rubric-score.json"))
    if status != LANE_PASS or not rubric_done:
        return NextPlan(
            phase="phase4-critic",
            actions=[
                _delegate(
                    "critic",
                    "심사자 관점 비평 + machine-feedback.json + rubric-score.json(85% 이상 도달까지 수정 지시)",
                )
            ],
        )

    # Phase 5 — assemble/build/render via finalizer, then the final gate.
    allow_expected = has_expected_claims(workspace)
    gate_flag = " --allow-expected" if allow_expected else ""
    output_dir = workspace / "output"
    bundle_ready = (output_dir / "bundle-manifest.json").exists()
    hwpx_ready = (output_dir / "report.hwpx").exists()
    render = _read_json(output_dir / "render-check.json")
    render_ok = bool(isinstance(render, dict) and render.get("ok"))
    status, _ = _lane_status(workspace, "finalizer")
    if not (bundle_ready and hwpx_ready and render_ok and status == LANE_PASS):
        return NextPlan(
            phase="phase5-finalize",
            actions=[
                _delegate(
                    "finalizer",
                    "소스 위생 → rch assemble → rch check --final"
                    f"{gate_flag} → rch build-hwpx → rch render-check (통과까지 반복 ≤4회)",
                )
            ],
            notes=["예상값(가상) claim이 있어 final 게이트는 --allow-expected 모드"]
            if allow_expected
            else [],
        )

    if final_check is not None:
        result = final_check(workspace, final=True, allow_expected=allow_expected)
        if not getattr(result, "ok", False):
            errors = [str(err) for err in getattr(result, "errors", [])][:10]
            return NextPlan(
                phase="revise",
                actions=[
                    _run(f"rch revise-loop {workspace}", "피드백을 수정 백로그로 통합"),
                    _delegate(
                        "critic",
                        "revision-tasks.md의 blocking 항목을 해당 lane에 재위임해 해소",
                    ),
                ],
                notes=errors,
            )

    notes = [
        "output/report.hwpx 완성. 한컴/HOP에서 페이지 수·표 흐름·이미지·목차를 사람이 최종 확인해야 합니다."
    ]
    if allow_expected and (output_dir / "expected-claims.md").exists():
        notes.append(
            "예상값(가상) 포함 완성본입니다. output/expected-claims.md 의 교체 목록을 사용자에게 안내하세요."
        )
    return NextPlan(phase="done", done=True, notes=notes)


def render_plan_markdown(plan: NextPlan) -> str:
    lines = ["# 다음 작업 판정", "", f"- phase: `{plan.phase}`", f"- done: {plan.done}"]
    if plan.parallel:
        lines.append("- 아래 작업은 **병렬** 실행 가능")
    if plan.needs_user:
        lines += ["", "## 사용자 확인 필요 (자동 진행 중단)", ""]
        lines += [f"- {item}" for item in plan.needs_user]
    if plan.actions:
        lines += ["", "## 다음 작업", ""]
        for action in plan.actions:
            if action["kind"] == "delegate":
                lines.append(f"- 위임: `{action['lane']}` lane → `{action['role']}` 역할 — {action['detail']}")
            else:
                lines.append(f"- 실행: `{action['command']}` — {action['detail']}")
    if plan.notes:
        lines += ["", "## 참고", ""]
        lines += [f"- {note}" for note in plan.notes]
    lines.append("")
    return "\n".join(lines)


def run_next(
    workspace: Path, final_check: Callable[..., Any] | None = None
) -> NextPlan:
    plan = compute_next(workspace, final_check=final_check)
    if workspace.exists():
        output_dir = workspace / "output"
        output_dir.mkdir(exist_ok=True)
        (output_dir / "next-plan.json").write_text(
            json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "next-plan.md").write_text(render_plan_markdown(plan), encoding="utf-8")
    return plan
