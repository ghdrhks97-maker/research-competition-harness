from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "next_competition_workspace"

LANES = (
    "brainstorm",
    "reference-miner",
    "draft-writer",
    "table-layout",
    "summary-sheet",
    "icon-visual",
    "critic",
    "finalizer",
)

FINAL_FORBIDDEN = ("예정", "추후", "보완 예정", "초안", "미정", "TODO")
CLAIM_STATUSES = {"real", "placeholder", "derived", "forbidden"}
FINAL_ALLOWED_STATUSES = {"real", "derived"}


@dataclass
class CheckResult:
    ok: bool
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"missing required file: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {path}: {exc}") from None


def init_workspace(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"refusing to init non-empty directory: {target}")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE, target, dirs_exist_ok=True)
    print(f"initialized {target}")


def create_lane(workspace: Path, lane: str, agent: str) -> None:
    if lane not in LANES:
        raise SystemExit(f"unknown lane {lane}; expected one of: {', '.join(LANES)}")
    lane_dir = workspace / "lanes" / lane / agent
    lane_dir.mkdir(parents=True, exist_ok=True)
    (lane_dir / "evidence").mkdir(exist_ok=True)
    input_path = lane_dir / "lane-input.md"
    if not input_path.exists():
        input_path.write_text(_lane_input_template(lane, agent), encoding="utf-8")
    print(lane_dir)


def _lane_input_template(lane: str, agent: str) -> str:
    lines = [
        "# Lane Input",
        "",
        f"lane: {lane}",
        f"agent: {agent}",
        "",
        "## Task",
        "",
        "Fill this lane using only workspace inputs and cited evidence.",
        "",
        "## Required Outputs",
        "",
        "- lane-output.md",
        "- lane-output.json",
        "- claim-ledger.json",
        "- verdict.json",
        "- evidence/",
        "",
        "## Guardrails",
        "",
        "- Do not fabricate student data, quotes, screenshots, dissemination proof, or class results.",
        "- Mark uncertain final-report material as `placeholder`.",
        "- Extract reference-report structure only; do not copy text.",
        "",
    ]
    return "\n".join(lines)


def check_workspace(workspace: Path, final: bool = False) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not workspace.exists():
        return CheckResult(False, [f"workspace missing: {workspace}"], [])

    lanes_root = workspace / "lanes"
    if not lanes_root.exists():
        errors.append("missing lanes/")

    for lane_dir in sorted(lanes_root.glob("*/*")) if lanes_root.exists() else []:
        if not lane_dir.is_dir():
            continue
        _check_lane(lane_dir, errors, warnings, final)

    claim_files = list(workspace.glob("lanes/*/*/claim-ledger.json"))
    if not claim_files:
        warnings.append("no claim-ledger.json files found yet")

    result = CheckResult(not errors, errors, warnings)
    (workspace / "output").mkdir(exist_ok=True)
    (workspace / "output" / "harness-check.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _check_lane(lane_dir: Path, errors: list[str], warnings: list[str], final: bool) -> None:
    required = ("lane-output.md", "lane-output.json", "claim-ledger.json", "verdict.json")
    missing = [name for name in required if not (lane_dir / name).exists()]
    if missing:
        warnings.append(f"{lane_dir}: incomplete lane outputs: {', '.join(missing)}")
        return

    try:
        lane_output = _read_json(lane_dir / "lane-output.json")
        claim_ledger = _read_json(lane_dir / "claim-ledger.json")
        verdict = _read_json(lane_dir / "verdict.json")
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(lane_output, dict):
        errors.append(f"{lane_dir}: lane-output.json must be object")
    if not isinstance(verdict, dict):
        errors.append(f"{lane_dir}: verdict.json must be object")
    elif verdict.get("status") not in {"pass", "needs-work", "blocked"}:
        errors.append(f"{lane_dir}: verdict.status must be pass, needs-work, or blocked")

    claims = claim_ledger.get("claims") if isinstance(claim_ledger, dict) else None
    if not isinstance(claims, list):
        errors.append(f"{lane_dir}: claim-ledger.json must contain claims[]")
        return

    text = (lane_dir / "lane-output.md").read_text(encoding="utf-8", errors="replace")
    for forbidden in FINAL_FORBIDDEN:
        if final and forbidden in text:
            errors.append(f"{lane_dir}: final output contains forbidden marker: {forbidden}")

    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"{lane_dir}: claim {index} must be object")
            continue
        status = claim.get("status")
        if status not in CLAIM_STATUSES:
            errors.append(f"{lane_dir}: claim {index} has invalid status {status!r}")
        if final and status not in FINAL_ALLOWED_STATUSES:
            errors.append(f"{lane_dir}: final claim {index} not allowed: {status}")
        if not claim.get("text"):
            errors.append(f"{lane_dir}: claim {index} missing text")
        if status in FINAL_ALLOWED_STATUSES and not claim.get("evidence"):
            errors.append(f"{lane_dir}: claim {index} needs evidence path")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="create a clean competition workspace")
    init_p.add_argument("workspace")

    lane_p = sub.add_parser("lane", help="create lane inbox for an agent")
    lane_p.add_argument("workspace")
    lane_p.add_argument("lane", choices=LANES)
    lane_p.add_argument("agent")

    check_p = sub.add_parser("check", help="validate lane contracts and claim ledger")
    check_p.add_argument("workspace")
    check_p.add_argument("--final", action="store_true", help="enforce final-candidate rules")

    args = parser.parse_args(argv)

    if args.cmd == "init":
        init_workspace(Path(args.workspace))
        return 0
    if args.cmd == "lane":
        create_lane(Path(args.workspace), args.lane, args.agent)
        return 0
    if args.cmd == "check":
        result = check_workspace(Path(args.workspace), final=args.final)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
