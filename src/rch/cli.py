from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rch import agents as agents_mod
from rch import background as background_mod
from rch import brainstorm as brainstorm_mod
from rch import draft as draft_mod
from rch import hwpx as hwpx_mod
from rch import hwpx_edit as hwpx_edit_mod
from rch import icons as icons_mod
from rch import photos as photos_mod
from rch import pipeline as pipeline_mod
from rch import references as references_mod
from rch import render_check as render_check_mod
from rch import revise as revise_mod
from rch import rules as rules_mod
from rch import run_lanes as run_lanes_mod
from rch import survey as survey_mod
from rch.lane_specs import FINAL_BUNDLE_FILES, LANE_SPECS, render_lane_input

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "next_competition_workspace"

LANES = tuple(LANE_SPECS)
INPUT_DIRS = ("ideas", "research", "rules", "references", "evidence", "photos", "surveys", "raw_private")
SURVEY_SUFFIXES = {".csv", ".tsv", ".tab", ".xlsx", ".xlsm"}
FINAL_OUTPUT_MAP = {
    "report-draft.md": ("draft-writer",),
    "summary-sheet.md": ("summary-sheet",),
    "toc.md": ("toc-builder",),
    "appendix.md": ("appendix-builder",),
    "finalization-checklist.md": ("finalizer", "critic"),
}

FINAL_FORBIDDEN = ("예정", "추후", "보완 예정", "초안", "미정", "TODO")
CLAIM_STATUSES = {"real", "placeholder", "derived", "expected", "forbidden"}
FINAL_ALLOWED_STATUSES = {"real", "derived"}
# "expected" claims are clearly-labeled 예상값(가상). They may enter a final
# bundle only via `check --final --allow-expected`, and only when the claim
# itself carries the label so a reader can never mistake it for real data.
EXPECTED_LABEL_TOKENS = ("예상", "가상")
EXPECTED_CLAIMS_REPORT = "expected-claims.md"
FINAL_REQUIRED_LANES = frozenset(lane for lanes in FINAL_OUTPUT_MAP.values() for lane in lanes)
UPSTREAM_REQUIRED_LANES = frozenset(
    (
        "intake",
        "brainstorm",
        "reference-miner",
        "evidence-curator",
        "survey-analyzer",
        "photo-curator",
        "table-layout",
        "icon-visual",
    )
)
FINAL_GATE_REQUIRED_LANES = FINAL_REQUIRED_LANES | UPSTREAM_REQUIRED_LANES
CRITIC_RUBRIC_FILE = "rubric-score.json"
RUBRIC_MIN_PERCENT = 85.0
MIN_RUBRIC_ITEMS = 5
HEX_DIGITS = set("0123456789abcdef")


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
    _ensure_input_dirs(target)
    print(f"initialized {target}")
    print("다음 단계: `rch brainstorm <workspace>` 로 대회명·분야 인터뷰 → 연구 동향 → 주제·제목을 자동 생성해 input/ideas/에 채웁니다.")


def create_lane(workspace: Path, lane: str, agent: str) -> None:
    if lane not in LANES:
        raise SystemExit(f"unknown lane {lane}; expected one of: {', '.join(LANES)}")
    lane_dir = workspace / "lanes" / lane / agent
    lane_dir.mkdir(parents=True, exist_ok=True)
    (lane_dir / "evidence").mkdir(exist_ok=True)
    input_path = lane_dir / "lane-input.md"
    if not input_path.exists():
        input_path.write_text(render_lane_input(lane, agent), encoding="utf-8")
    print(lane_dir)


def bootstrap_lanes(workspace: Path, agent: str) -> None:
    if not workspace.exists():
        raise SystemExit(f"workspace missing: {workspace}")
    _ensure_input_dirs(workspace)
    for lane in LANES:
        create_lane(workspace, lane, agent)
    print(f"bootstrapped {len(LANES)} lanes for {agent}")


def assemble_workspace(workspace: Path) -> None:
    if not workspace.exists():
        raise SystemExit(f"workspace missing: {workspace}")
    output_dir = workspace / "output"
    output_dir.mkdir(exist_ok=True)

    manifest: dict[str, Any] = {"files": [], "missing_sources": []}
    for filename, lanes in FINAL_OUTPUT_MAP.items():
        content, missing, source_files = _render_assembled_file(workspace, filename, lanes)
        target = output_dir / filename
        target.write_text(content, encoding="utf-8")
        manifest["files"].append(
            {
                "path": f"output/{filename}",
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "source_lanes": list(lanes),
                "source_files": source_files,
            }
        )
        manifest["missing_sources"].extend(missing)

    manifest_path = output_dir / "bundle-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def _ensure_input_dirs(workspace: Path) -> None:
    input_root = workspace / "input"
    input_root.mkdir(parents=True, exist_ok=True)
    for name in INPUT_DIRS:
        target = input_root / name
        target.mkdir(exist_ok=True)
        keep = target / ".gitkeep"
        if not keep.exists():
            keep.write_text("\n", encoding="utf-8")
    rules_mod.rules_root(workspace)


def _render_assembled_file(
    workspace: Path, filename: str, lanes: tuple[str, ...]
) -> tuple[str, list[str], list[dict[str, str]]]:
    parts = [f"# {filename}", ""]
    missing: list[str] = []
    source_files: list[dict[str, str]] = []
    for lane in lanes:
        lane_parts, lane_sources = _collect_lane_outputs(workspace, lane)
        if not lane_parts:
            missing.append(lane)
            parts.extend([f"## {lane}", "", "> MISSING: lane-output.md 없음", ""])
            continue
        parts.extend(lane_parts)
        source_files.extend(lane_sources)
    return "\n".join(parts).rstrip() + "\n", missing, source_files


def _collect_lane_outputs(workspace: Path, lane: str) -> tuple[list[str], list[dict[str, str]]]:
    lane_root = workspace / "lanes" / lane
    if not lane_root.exists():
        return [], []
    parts: list[str] = []
    source_files: list[dict[str, str]] = []
    for output_path in sorted(lane_root.glob("*/lane-output.md")):
        agent = output_path.parent.name
        text = output_path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        parts.extend([f"## {lane} / {agent}", "", text, ""])
        source_files.append(
            {
                "path": output_path.relative_to(workspace).as_posix(),
                "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
            }
        )
    return parts, source_files


def check_workspace(
    workspace: Path, final: bool = False, allow_expected: bool = False
) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []
    expected_claims: list[dict[str, str]] = []

    if not workspace.exists():
        return CheckResult(False, [f"workspace missing: {workspace}"], [])

    lanes_root = workspace / "lanes"
    if not lanes_root.exists():
        errors.append("missing lanes/")

    for lane_dir in sorted(lanes_root.glob("*/*")) if lanes_root.exists() else []:
        if not lane_dir.is_dir():
            continue
        _check_lane(lane_dir, errors, warnings, final, allow_expected, expected_claims)

    claim_files = list(workspace.glob("lanes/*/*/claim-ledger.json"))
    if not claim_files:
        warnings.append("no claim-ledger.json files found yet")

    if final:
        _check_final_required_lanes(workspace, errors)
        _check_final_bundle(workspace, errors)

    result = CheckResult(not errors, errors, warnings)
    (workspace / "output").mkdir(exist_ok=True)
    (workspace / "output" / "harness-check.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if final and allow_expected:
        _write_expected_claims_report(workspace, expected_claims)
    return result


def _write_expected_claims_report(workspace: Path, expected_claims: list[dict[str, str]]) -> None:
    lines = ["# 예상값(가상) 교체 목록", ""]
    if expected_claims:
        lines.append(
            "아래 주장은 실제 조사 결과가 아니라 예상값(가상)이다. "
            "실제 자료가 생기면 교체하고 `rch check --final`(플래그 없이)을 다시 통과시킨다."
        )
        lines += ["", "| Lane | 주장 | 교체 방법 |", "| --- | --- | --- |"]
        for item in expected_claims:
            lines.append(f"| {item['lane']} | {item['text']} | {item['notes'] or '실제 자료로 교체'} |")
    else:
        lines.append("남은 예상값(가상) 주장이 없다. 모든 주장이 실제 증거 기반이다.")
    lines.append("")
    (workspace / "output" / EXPECTED_CLAIMS_REPORT).write_text("\n".join(lines), encoding="utf-8")


def _check_lane(
    lane_dir: Path,
    errors: list[str],
    warnings: list[str],
    final: bool,
    allow_expected: bool = False,
    expected_claims: list[dict[str, str]] | None = None,
) -> None:
    required = ("lane-output.md", "lane-output.json", "claim-ledger.json", "verdict.json")
    missing = [name for name in required if not (lane_dir / name).exists()]
    if missing:
        message = f"{lane_dir}: incomplete lane outputs: {', '.join(missing)}"
        warnings.append(message)
        if final and lane_dir.parent.name in FINAL_REQUIRED_LANES:
            errors.append(message)
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
    elif final and lane_dir.parent.name in FINAL_GATE_REQUIRED_LANES and verdict.get("status") != "pass":
        errors.append(f"{lane_dir}: final required lane verdict.status must be pass")

    claims = claim_ledger.get("claims") if isinstance(claim_ledger, dict) else None
    if not isinstance(claims, list):
        errors.append(f"{lane_dir}: claim-ledger.json must contain claims[]")
        return

    text = (lane_dir / "lane-output.md").read_text(encoding="utf-8", errors="replace")
    for forbidden in FINAL_FORBIDDEN:
        if final and forbidden in text:
            errors.append(f"{lane_dir}: final output contains forbidden marker: {forbidden}")

    final_allowed = FINAL_ALLOWED_STATUSES | ({"expected"} if allow_expected else set())
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"{lane_dir}: claim {index} must be object")
            continue
        status = claim.get("status")
        if status not in CLAIM_STATUSES:
            errors.append(f"{lane_dir}: claim {index} has invalid status {status!r}")
        if status == "expected":
            label_source = f"{claim.get('text', '')} {claim.get('notes', '')}"
            if not any(token in label_source for token in EXPECTED_LABEL_TOKENS):
                errors.append(
                    f"{lane_dir}: expected claim {index} must carry an "
                    f"'예상값(가상)' label in text or notes"
                )
        if final and status not in final_allowed:
            hint = (
                " (예상값 완성본은 --allow-expected로 검사)"
                if status == "expected" and not allow_expected
                else ""
            )
            errors.append(f"{lane_dir}: final claim {index} not allowed: {status}{hint}")
        if final and allow_expected and status == "expected":
            warnings.append(
                f"{lane_dir}: claim {index} is expected(가상) — replace with real data when available"
            )
            if expected_claims is not None:
                expected_claims.append(
                    {
                        "lane": lane_dir.parent.name,
                        "text": str(claim.get("text", "")),
                        "notes": str(claim.get("notes", "")),
                    }
                )
        if not claim.get("text"):
            errors.append(f"{lane_dir}: claim {index} missing text")
        evidence = claim.get("evidence")
        if status in FINAL_ALLOWED_STATUSES and not evidence:
            errors.append(f"{lane_dir}: claim {index} needs evidence path")
        elif final and status in FINAL_ALLOWED_STATUSES:
            evidence_error = _check_evidence_path(lane_dir, evidence)
            if evidence_error:
                errors.append(f"{lane_dir}: claim {index} {evidence_error}")

    if final and lane_dir.parent.name == "critic":
        _check_critic_rubric_score(lane_dir, errors)


def _check_final_required_lanes(workspace: Path, errors: list[str]) -> None:
    lanes_root = workspace / "lanes"
    for lane in sorted(FINAL_GATE_REQUIRED_LANES):
        lane_root = lanes_root / lane
        if not lane_root.exists():
            errors.append(f"missing final required lane: {lane}")
            continue
        agent_dirs = [path for path in lane_root.iterdir() if path.is_dir()]
        if not agent_dirs:
            errors.append(f"missing final required lane agent output: {lane}")
            continue
        if not any(_has_lane_contract_files(agent_dir) for agent_dir in agent_dirs):
            errors.append(f"final required lane has no complete agent output: {lane}")


def _has_lane_contract_files(lane_dir: Path) -> bool:
    return all(
        (lane_dir / name).exists()
        for name in ("lane-output.md", "lane-output.json", "claim-ledger.json", "verdict.json")
    )


def _check_critic_rubric_score(lane_dir: Path, errors: list[str]) -> None:
    path = lane_dir / CRITIC_RUBRIC_FILE
    try:
        rubric = _read_json(path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(rubric, dict):
        errors.append(f"{path}: rubric-score.json must be object")
        return

    total_score = rubric.get("total_score")
    max_score = rubric.get("max_score")
    items = rubric.get("items")

    if not _is_number(total_score):
        errors.append(f"{path}: total_score must be number")
    if not _is_number(max_score) or max_score <= 0:
        errors.append(f"{path}: max_score must be positive number")
    if _is_number(total_score) and _is_number(max_score) and max_score > 0:
        if total_score < 0 or total_score > max_score:
            errors.append(f"{path}: total_score must be between 0 and max_score")
        percent = total_score / max_score * 100
        if percent < RUBRIC_MIN_PERCENT:
            errors.append(f"{path}: rubric total {percent:.1f}% below final target {RUBRIC_MIN_PERCENT:.1f}%")

    if not isinstance(items, list) or len(items) < MIN_RUBRIC_ITEMS:
        errors.append(f"{path}: items must contain at least {MIN_RUBRIC_ITEMS} scoring criteria")
        return

    item_score_total = 0.0
    item_max_total = 0.0
    item_totals_valid = True
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{path}: items[{index}] must be object")
            item_totals_valid = False
            continue
        criterion = item.get("criterion")
        score = item.get("score")
        item_max_score = item.get("max_score")
        evidence = item.get("evidence")
        risk = item.get("risk")
        fix = item.get("fix")
        if not isinstance(criterion, str) or not criterion.strip():
            errors.append(f"{path}: items[{index}].criterion must be non-empty string")
        if not _is_number(score):
            errors.append(f"{path}: items[{index}].score must be number")
            item_totals_valid = False
        if not _is_number(item_max_score) or item_max_score <= 0:
            errors.append(f"{path}: items[{index}].max_score must be positive number")
            item_totals_valid = False
        if _is_number(score) and _is_number(item_max_score) and item_max_score > 0:
            if score < 0 or score > item_max_score:
                errors.append(f"{path}: items[{index}].score must be between 0 and max_score")
                item_totals_valid = False
            item_score_total += float(score)
            item_max_total += float(item_max_score)
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"{path}: items[{index}].evidence must be non-empty string")
        if not isinstance(risk, str) or not risk.strip():
            errors.append(f"{path}: items[{index}].risk must be non-empty string")
        if not isinstance(fix, str) or not fix.strip():
            errors.append(f"{path}: items[{index}].fix must be non-empty string")

    if item_totals_valid and _is_number(total_score) and abs(item_score_total - float(total_score)) > 0.01:
        errors.append(f"{path}: total_score must equal sum of item scores")
    if item_totals_valid and _is_number(max_score) and abs(item_max_total - float(max_score)) > 0.01:
        errors.append(f"{path}: max_score must equal sum of item max_score values")


def _check_final_bundle(workspace: Path, errors: list[str]) -> None:
    output_dir = workspace / "output"
    manifest_path = output_dir / "bundle-manifest.json"
    if not manifest_path.exists():
        errors.append("missing final bundle file: output/bundle-manifest.json")
    else:
        try:
            manifest = _read_json(manifest_path)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if not isinstance(manifest, dict):
                errors.append("output/bundle-manifest.json must be object")
            else:
                _check_final_bundle_manifest(workspace, manifest, errors)

    for filename in FINAL_BUNDLE_FILES:
        path = output_dir / filename
        if not path.exists():
            errors.append(f"missing final bundle file: output/{filename}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            errors.append(f"empty final bundle file: output/{filename}")
        for forbidden in FINAL_FORBIDDEN:
            if forbidden in text:
                errors.append(f"final bundle contains forbidden marker: output/{filename}: {forbidden}")


def _check_final_bundle_manifest(workspace: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    files = manifest.get("files")
    missing_sources = manifest.get("missing_sources")

    if not isinstance(files, list):
        errors.append("output/bundle-manifest.json files must be list")
        files = []
    if not isinstance(missing_sources, list):
        errors.append("output/bundle-manifest.json missing_sources must be list")
    elif missing_sources:
        errors.append(f"final bundle has missing source lanes: {', '.join(str(item) for item in missing_sources)}")

    required_paths = {f"output/{filename}" for filename in FINAL_BUNDLE_FILES}
    entries_by_path: dict[str, list[dict[str, Any]]] = {}
    for index, entry in enumerate(files):
        if not isinstance(entry, dict):
            errors.append(f"output/bundle-manifest.json files[{index}] must be object")
            continue

        path = entry.get("path")
        sha256 = entry.get("sha256")
        source_lanes = entry.get("source_lanes")
        source_files = entry.get("source_files")

        if not isinstance(path, str):
            errors.append(f"output/bundle-manifest.json files[{index}].path must be string")
        else:
            entries_by_path.setdefault(path, []).append(entry)
            if path not in required_paths:
                errors.append(f"unexpected final bundle manifest entry: {path}")

        if not _is_sha256_hex(sha256):
            errors.append(f"output/bundle-manifest.json files[{index}].sha256 must be 64-char hex string")
        elif isinstance(path, str) and path in required_paths:
            output_path = workspace / path
            if output_path.exists():
                actual_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
                if sha256.lower() != actual_sha256:
                    errors.append(f"final bundle manifest sha256 mismatch: {path}")

        if not (
            isinstance(source_lanes, list)
            and source_lanes
            and all(isinstance(source_lane, str) and source_lane for source_lane in source_lanes)
        ):
            errors.append(
                f"output/bundle-manifest.json files[{index}].source_lanes must be non-empty list of strings"
            )
        elif any(source_lane not in FINAL_REQUIRED_LANES for source_lane in source_lanes):
            errors.append(f"output/bundle-manifest.json files[{index}].source_lanes contains unknown lane")

        _check_manifest_source_files(workspace, index, source_lanes, source_files, errors)

    for filename in FINAL_BUNDLE_FILES:
        path = f"output/{filename}"
        count = len(entries_by_path.get(path, []))
        if count == 0:
            errors.append(f"missing final bundle manifest entry: {path}")
        elif count > 1:
            errors.append(f"duplicate final bundle manifest entry: {path}")


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in HEX_DIGITS for character in value.lower())


def _check_manifest_source_files(
    workspace: Path, manifest_index: int, source_lanes: Any, source_files: Any, errors: list[str]
) -> None:
    if not isinstance(source_files, list) or not source_files:
        errors.append(f"output/bundle-manifest.json files[{manifest_index}].source_files must be non-empty list")
        return

    for source_index, source in enumerate(source_files):
        if not isinstance(source, dict):
            errors.append(f"output/bundle-manifest.json files[{manifest_index}].source_files[{source_index}] must be object")
            continue
        path = source.get("path")
        sha256 = source.get("sha256")
        if not isinstance(path, str) or not path.startswith("lanes/"):
            errors.append(
                f"output/bundle-manifest.json files[{manifest_index}].source_files[{source_index}].path must be lane path"
            )
            continue
        source_lane = path.split("/", 2)[1] if "/" in path else ""
        if isinstance(source_lanes, list) and source_lane not in source_lanes:
            errors.append(
                f"output/bundle-manifest.json files[{manifest_index}].source_files[{source_index}] lane not in source_lanes"
            )
            continue
        if not _is_sha256_hex(sha256):
            errors.append(
                f"output/bundle-manifest.json files[{manifest_index}].source_files[{source_index}].sha256 must be 64-char hex string"
            )
            continue
        source_path = workspace / path
        if not source_path.exists():
            errors.append(f"final bundle source file missing: {path}")
            continue
        actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if sha256.lower() != actual_sha256:
            errors.append(f"final bundle source file sha256 mismatch: {path}")


def _check_evidence_path(lane_dir: Path, evidence: Any) -> str | None:
    if not isinstance(evidence, str) or not evidence.strip():
        return "needs evidence path"
    evidence_path = Path(evidence)
    if evidence_path.is_absolute():
        return f"evidence path must be workspace-relative: {evidence}"
    if any(part == ".." for part in evidence_path.parts):
        return f"evidence path must stay inside workspace: {evidence}"
    if (
        len(evidence_path.parts) >= 2
        and evidence_path.parts[0] == "input"
        and evidence_path.parts[1] == "raw_private"
    ):
        return f"evidence path cannot use input/raw_private: {evidence}"
    workspace = lane_dir.parents[2]
    for candidate in (lane_dir / evidence_path, workspace / evidence_path):
        resolved = candidate.resolve(strict=False)
        if not _is_relative_to(resolved, workspace.resolve()):
            return f"evidence path must stay inside workspace: {evidence}"
        if _is_raw_private_path(resolved, workspace.resolve()):
            return f"evidence path cannot use input/raw_private: {evidence}"
        if resolved.exists():
            if not resolved.is_file():
                return f"evidence path must point to file: {evidence}"
            return None
    return f"evidence path missing: {evidence}"


def _is_raw_private_path(path: Path, workspace: Path) -> bool:
    try:
        relative = path.relative_to(workspace)
    except ValueError:
        return False
    return len(relative.parts) >= 2 and relative.parts[0] == "input" and relative.parts[1] == "raw_private"


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def import_survey_cmd(workspace: Path, survey_path: Path) -> None:
    output_dir = workspace / "input" / "surveys" / "analysis"
    analysis = survey_mod.import_survey(survey_path, output_dir, workspace=workspace)
    print(json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2))


def import_photos_cmd(workspace: Path) -> None:
    source_dir = workspace / "input" / "photos"
    output_dir = source_dir / "analysis"
    manifest = photos_mod.import_photos(source_dir, output_dir, workspace=workspace)
    print(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))


def import_rules_cmd(workspace: Path, files: list[Path]) -> None:
    report = rules_mod.import_rule_files(workspace, files)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


def mine_references_cmd(workspace: Path) -> None:
    source_dir = workspace / "input" / "references"
    output_dir = source_dir / "analysis"
    report = references_mod.mine_references(source_dir, output_dir)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


def research_background_cmd(workspace: Path, query: str | None, max_results: int, offline: bool) -> None:
    research = background_mod.run_background_research(
        workspace,
        query=query,
        max_results=max_results,
        offline=offline,
    )
    print(json.dumps(research.to_dict(), ensure_ascii=False, indent=2))


def draft_cmd(workspace: Path) -> None:
    written = draft_mod.generate_drafts(workspace)
    print(json.dumps({"drafted_lanes": written}, ensure_ascii=False, indent=2))


def run_lanes_cmd(workspace: Path, agent: str, lanes: list[str] | None, execute: bool) -> int:
    manifest = run_lanes_mod.run_lanes(workspace, agent, lanes)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if not execute:
        return 0

    # Verify the agent CLI is installed and logged in before dispatching.
    status = agents_mod.check_agent(agent)
    print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
    if not status.installed:
        print(f"[run-lanes] {agent} 미설치로 실제 호출을 건너뜀.")
        return 1
    if status.login_status == agents_mod.STATUS_UNAUTHENTICATED:
        print(f"[run-lanes] {agent} 로그인되지 않아 실제 호출을 건너뜀. 먼저 로그인하세요.")
        return 1

    exit_code = 0
    for entry in manifest["lanes"]:
        result = agents_mod.run_agent_on_lane(workspace, agent, entry["lane"])
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        if not result.ok:
            exit_code = 1
    return exit_code


def build_hwpx_cmd(workspace: Path, output_path: Path | None, engine: str = "builtin") -> None:
    output_dir = workspace / "output"
    bundle_paths = [output_dir / name for name in FINAL_BUNDLE_FILES if name != "finalization-checklist.md"]
    existing = [path for path in bundle_paths if path.exists()]
    if not existing:
        raise SystemExit("no assembled bundle found; run `rch assemble` first")
    target = output_path or (output_dir / "report.hwpx")
    if engine == "kordoc":
        _build_hwpx_kordoc(workspace, existing, target)
        return
    result = hwpx_mod.build_hwpx_from_bundle(existing, target, images_root=workspace)
    summary = {
        "engine": "builtin",
        "hwpx": target.relative_to(workspace).as_posix() if target.is_relative_to(workspace) else str(target),
        "paragraphs": result.paragraph_count,
        "tables": result.table_count,
        "headings": result.heading_count,
        "images": result.image_count,
        "embedded_images": result.embedded_images,
        "missing_images": result.missing_images,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _build_hwpx_kordoc(workspace: Path, bundle_paths: list[Path], target: Path) -> None:
    """Render via the kordoc open-source converter (https://github.com/chrisryugj/kordoc).

    kordoc's markdown→HWPX path ships Korean report presets and renders
    much closer to Hancom's native look than the builtin structural
    renderer. Requires Node 18+; command overridable with RCH_KORDOC_CMD
    (default: `npx -y kordoc`)."""
    merged = workspace / "output" / "report-merged.md"
    merged.write_text(
        "\n\n".join(path.read_text(encoding="utf-8", errors="replace") for path in bundle_paths),
        encoding="utf-8",
    )
    base_cmd = shlex.split(os.environ.get("RCH_KORDOC_CMD", "npx -y kordoc"))
    cmd = [*base_cmd, "generate", str(merged), "-o", str(target), "--preset", "보고서"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    except FileNotFoundError:
        raise SystemExit(
            f"kordoc 실행 실패: {base_cmd[0]} 없음. Node 18+ 설치 후 재시도하거나 "
            "`rch build-hwpx --engine builtin`으로 폴백하세요."
        ) from None
    except subprocess.TimeoutExpired:
        raise SystemExit("kordoc 실행 시간 초과. `--engine builtin`으로 폴백하세요.") from None
    if proc.returncode != 0 or not target.exists():
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise SystemExit(
            "kordoc 렌더 실패 (exit={code}): {msg}\n`rch build-hwpx --engine builtin`으로 폴백하세요.".format(
                code=proc.returncode, msg=detail[0] if detail else "원인 미상"
            )
        )
    print(
        json.dumps(
            {
                "engine": "kordoc",
                "hwpx": target.relative_to(workspace).as_posix() if target.is_relative_to(workspace) else str(target),
                "merged_markdown": merged.relative_to(workspace).as_posix(),
                "note": "rch render-check로 구조 검증 후 한컴에서 확인하세요.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def diagnose_cmd(workspace: Path) -> int:
    """Inspect a workspace's output folder and explain why the report looks wrong."""
    import zipfile

    from rch import pipeline as pipeline_mod_local

    output_dir = workspace / "output"
    signals: list[str] = []
    info: dict[str, Any] = {"workspace": str(workspace)}

    if not workspace.exists():
        print(json.dumps({"ok": False, "signals": [f"workspace missing: {workspace}"]}, ensure_ascii=False))
        return 1

    # 1. Legacy skeleton detection: `rch go` leaves missing-inputs.md and
    #    placeholder tables — that path produces scaffolding, not a finished report.
    if (output_dir / "missing-inputs.md").exists():
        signals.append(
            "레거시 `rch go` 스켈레톤 산출물 흔적(output/missing-inputs.md). 이 경로는 placeholder 표 중심의 "
            "골격만 만듭니다 — 완성 보고서는 에이전트 autopilot(계획 승인 → rch next 루프)으로 다시 생성하세요."
        )
    draft_path = output_dir / "report-draft.md"
    if draft_path.exists():
        draft_text = draft_path.read_text(encoding="utf-8", errors="replace")
        if "확정한다.]" in draft_text or "harness-draft" in draft_text:
            signals.append(
                "본문이 파이썬 골격(harness-draft)입니다 — '[…확정한다.]' 자리표시 문단이 그대로 남아 있고 "
                "draft-writer 에이전트가 집필하지 않았습니다. autopilot으로 Phase 1~2부터 다시 실행하세요."
            )
    manifest = _read_json_safe(output_dir / "bundle-manifest.json")
    if isinstance(manifest, dict):
        sources = json.dumps(manifest, ensure_ascii=False)
        if "harness-draft" in sources or "harness-" in sources:
            signals.append(
                "bundle-manifest의 source lane이 harness-*(파이썬 생성기)입니다 — 에이전트 lane 산출물이 아닙니다."
            )

    # 2. Bundle / lanes state.
    if not (output_dir / "bundle-manifest.json").exists():
        signals.append("assemble 번들 없음(output/bundle-manifest.json) — lane 산출물이 조립되지 않았습니다.")
    lane_states: dict[str, str] = {}
    for lane in pipeline_mod_local.LANE_ROLES:
        status, _ = pipeline_mod_local._lane_status(workspace, lane)
        lane_states[lane] = status
    info["lanes"] = lane_states
    missing_lanes = [lane for lane, status in lane_states.items() if status == "missing"]
    if len(missing_lanes) >= 5:
        signals.append(
            f"lane 산출물 대부분 없음({len(missing_lanes)}개: {', '.join(missing_lanes[:6])}...). "
            "에이전트 파이프라인(Phase 1~4)이 돌지 않은 채 렌더만 실행된 것으로 보입니다."
        )

    # 3. Claim health.
    counts = {"real": 0, "derived": 0, "expected": 0, "placeholder": 0, "forbidden": 0}
    for path in workspace.glob("lanes/*/*/claim-ledger.json"):
        data = _read_json_safe(path)
        for claim in (data or {}).get("claims", []) if isinstance(data, dict) else []:
            status = claim.get("status") if isinstance(claim, dict) else None
            if status in counts:
                counts[status] += 1
    info["claims"] = counts
    if counts["placeholder"] > 0:
        signals.append(f"placeholder claim {counts['placeholder']}건 — 최종 반영 불가 상태의 자리표시자가 남아 있습니다.")

    # 4. HWPX inspection.
    hwpx_path = output_dir / "report.hwpx"
    if not hwpx_path.exists():
        signals.append("output/report.hwpx 없음.")
    else:
        try:
            with zipfile.ZipFile(hwpx_path) as archive:
                section = archive.read("Contents/section0.xml").decode("utf-8", errors="replace")
            if "<hp:tbl" in section and "cellSz" not in section:
                signals.append(
                    "구버전 렌더러로 빌드된 HWPX(표에 hp:cellSz/hp:sz 크기 정보 없음 → 한컴에서 표가 붕괴되어 보임). "
                    "최신 하네스로 업데이트(git pull) 후 `rch build-hwpx`를 다시 실행하세요."
                )
            if "hp:pagePr" not in section:
                signals.append("페이지 정의(hp:pagePr) 없음 → 한컴에서 빈 문서. `rch build-hwpx` 재실행 필요.")
        except zipfile.BadZipFile:
            signals.append("report.hwpx가 유효한 zip이 아님 — 손으로 조립된 파일로 보입니다. `rch build-hwpx`/`rch hwpx-pack`만 사용하세요.")
        toc_path = output_dir / "toc.md"
        check = render_check_mod.render_check(hwpx_path, toc_path=toc_path if toc_path.exists() else None)
        info["render_check"] = check.to_dict()
        signals.extend(f"render-check: {err}" for err in check.errors)

    if not signals:
        signals.append("결정적 문제 신호 없음 — 한컴 화면 캡처와 함께 output/diagnose.json을 공유하면 더 파고들 수 있습니다.")

    result = {"ok": True, "signals": signals, **info}
    output_dir.mkdir(exist_ok=True)
    (output_dir / "diagnose.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 진단 결과", ""] + [f"- {signal}" for signal in signals] + [""]
    (output_dir / "diagnose.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _read_json_safe(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def hwpx_unpack_cmd(workspace: Path, hwpx_path: Path | None, target_dir: Path | None) -> None:
    source = hwpx_path or (workspace / "output" / "report.hwpx")
    target = target_dir or (workspace / "output" / "hwpx-src")
    names = hwpx_edit_mod.unpack_hwpx(source, target)
    print(
        json.dumps(
            {
                "unpacked_to": str(target),
                "members": names,
                "note": "Contents/header.xml·section0.xml을 편집한 뒤 `rch hwpx-pack`으로 재조립+검증하세요.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def hwpx_pack_cmd(workspace: Path, source_dir: Path | None, output_path: Path | None) -> int:
    source = source_dir or (workspace / "output" / "hwpx-src")
    target = output_path or (workspace / "output" / "report.hwpx")
    hwpx_edit_mod.pack_hwpx(source, target)
    toc_path = workspace / "output" / "toc.md"
    check = render_check_mod.run_render_check(
        target,
        workspace / "output",
        toc_path=toc_path if toc_path.exists() else None,
        page_limit=render_check_mod.DEFAULT_PAGE_LIMIT,
    )
    print(
        json.dumps(
            {"packed": str(target), "render_check": check.to_dict()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if check.ok else 1


def render_check_cmd(workspace: Path, hwpx_path: Path | None, page_limit: int, min_pages: int = 0) -> int:
    target = hwpx_path or (workspace / "output" / "report.hwpx")
    toc_path = workspace / "output" / "toc.md"
    check = render_check_mod.run_render_check(
        target,
        workspace / "output",
        toc_path=toc_path if toc_path.exists() else None,
        page_limit=page_limit,
        min_pages=min_pages,
    )
    print(json.dumps(check.to_dict(), ensure_ascii=False, indent=2))
    return 0 if check.ok else 1


def revise_loop_cmd(workspace: Path) -> None:
    backlog = revise_mod.run_revise_loop(workspace)
    print(json.dumps(backlog.to_dict(), ensure_ascii=False, indent=2))


def brainstorm_cmd(
    workspace: Path,
    answers_path: Path | None,
    agent: str | None,
    research_background: bool = False,
    competition_name: str | None = None,
    field_answers: dict[str, str] | None = None,
) -> None:
    answers: dict[str, str] | None = None
    if answers_path is not None:
        loaded = json.loads(answers_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise SystemExit("--answers 파일은 JSON 객체여야 합니다.")
        answers = {str(key): str(value) for key, value in loaded.items()}
    if competition_name:
        answers = answers or {}
        answers["competition_name"] = competition_name
    # Per-field flags let an agent pass interview answers directly, no file.
    if field_answers:
        answers = answers or {}
        answers.update({key: value for key, value in field_answers.items() if value})
    bundle = brainstorm_mod.run_brainstorm(workspace, answers=answers, agent=agent)
    research_written: list[str] = []
    research_source_count = 0
    if research_background:
        research = background_mod.run_background_research(workspace)
        research_written = ["input/research/background-research.json", "input/research/04-background-research.md"]
        research_source_count = len(research.sources)
    summary = {
        "competition_name": bundle.answers.get("competition_name", ""),
        "major": bundle.answers.get("major", ""),
        "core_competencies_2022": bundle.core_competencies,
        "recommended_topic": bundle.recommended_topic,
        "recommended_title": bundle.titles[0] if bundle.titles else "",
        "topic_count": len(bundle.topics),
        "agent_augmented": bundle.agent_augmented,
        "ideas_written": [f"input/ideas/{name}" for name in (
            "00-interview.md", "01-trend-research.md", "02-research-topics.md", "03-title-candidates.md", "brainstorm.json"
        )],
        "research_written": research_written,
        "research_source_count": research_source_count,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _workspace_needs_init(workspace: Path) -> bool:
    return not workspace.exists() or not any(workspace.iterdir())


def _load_answers(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit("--answers 파일은 JSON 객체여야 합니다.")
    return {str(key): str(value) for key, value in loaded.items()}


def _answers_from_options(args: argparse.Namespace) -> dict[str, str]:
    answers = {
        "competition_name": args.competition_name or "",
        "major": args.major or "",
        "level": args.level or "",
        "class_context": args.class_context or "",
        "interests": args.interests or "",
        "tools": args.tools or "",
        "competency": args.competency or "",
        "constraints": args.constraints or "",
    }
    return {key: value for key, value in answers.items() if value}


def _find_survey_file(workspace: Path) -> Path | None:
    survey_dir = workspace / "input" / "surveys"
    if not survey_dir.exists():
        return None
    for path in sorted(survey_dir.rglob("*")):
        if not path.is_file():
            continue
        if "analysis" in path.relative_to(survey_dir).parts:
            continue
        if path.suffix.lower() in SURVEY_SUFFIXES:
            return path
    return None


def _write_missing_inputs_report(workspace: Path, missing_inputs: list[dict[str, Any]]) -> None:
    output_dir = workspace / "output"
    output_dir.mkdir(exist_ok=True)
    lines = ["# 입력자료 보강표", ""]
    if not missing_inputs:
        lines.append("현재 자동 실행에서 보강 필요 입력이 발견되지 않았다.")
        lines.append("")
    else:
        lines += ["| 자료 | 필요한 조치 | 경로 |", "| --- | --- | --- |"]
        for item in missing_inputs:
            lines.append(f"| {item['kind']} | {item['action']} | `{item['path']}` |")
        lines.append("")
    (output_dir / "missing-inputs.md").write_text("\n".join(lines), encoding="utf-8")
    (output_dir / "missing-inputs.json").write_text(
        json.dumps({"missing_inputs": missing_inputs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_system_lane(
    workspace: Path,
    lane: str,
    markdown_text: str,
    summary: str,
    status: str,
    claims: list[dict[str, Any]] | None = None,
    agent: str = "harness-go",
) -> None:
    lane_dir = workspace / "lanes" / lane / agent
    lane_dir.mkdir(parents=True, exist_ok=True)
    (lane_dir / "evidence").mkdir(exist_ok=True)
    (lane_dir / "lane-output.md").write_text(markdown_text, encoding="utf-8")
    (lane_dir / "lane-output.json").write_text(
        json.dumps(
            {"lane": lane, "agent": agent, "summary": summary, "artifacts": ["output/missing-inputs.md"]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (lane_dir / "claim-ledger.json").write_text(
        json.dumps({"claims": claims or []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (lane_dir / "verdict.json").write_text(
        json.dumps({"status": status, "reason": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_critic_rubric(lane_dir: Path, missing_inputs: list[dict[str, Any]]) -> None:
    score = 14 if missing_inputs else 18
    items = [
        {
            "criterion": criterion,
            "score": score,
            "max_score": 20,
            "evidence": "자동 실행 산출물과 입력자료 보강표",
            "risk": "입력자료 누락 시 최종 심사 감점",
            "fix": "missing-inputs.md 항목 보강 후 재실행",
        }
        for criterion in ("연구 필요성", "수업 설계", "실행 충실도", "학생 변화 근거", "일반화 가능성")
    ]
    (lane_dir / "rubric-score.json").write_text(
        json.dumps(
            {"total_score": score * len(items), "max_score": 100, "items": items},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _seed_go_review_lanes(workspace: Path, missing_inputs: list[dict[str, Any]]) -> None:
    status = "needs-work" if missing_inputs else "pass"
    if missing_inputs:
        rows = ["| 자료 | 보강 |", "| --- | --- |"]
        rows += [f"| {item['kind']} | {item['action']} |" for item in missing_inputs]
        body = "\n".join(["# 자동 점검", "", *rows, ""])
        claims = [
            {
                "id": f"missing-{index}",
                "text": f"{item['kind']} 보강 필요: {item['action']}",
                "status": "placeholder",
                "notes": item["path"],
            }
            for index, item in enumerate(missing_inputs, 1)
        ]
        summary = "입력자료 보강 필요."
    else:
        body = "# 자동 점검\n\n자동 실행 필수 입력 확인 완료.\n"
        claims = []
        summary = "자동 실행 점검 통과."
    _write_system_lane(workspace, "critic", body, summary, status, claims)
    _write_critic_rubric(workspace / "lanes" / "critic" / "harness-go", missing_inputs)
    _write_system_lane(workspace, "finalizer", body, summary, status, claims)


def go_workspace(
    workspace: Path,
    answers: dict[str, str] | None = None,
    rule_files: list[Path] | None = None,
    survey_path: Path | None = None,
    offline_research: bool = False,
    survey_items: int = survey_mod.DEFAULT_REQUIRED_SURVEY_ITEMS,
    photo_count: int = photos_mod.DEFAULT_REQUIRED_PHOTOS,
    build_hwpx: bool = True,
) -> dict[str, Any]:
    summary: dict[str, Any] = {"workspace": str(workspace), "steps": []}
    missing_inputs: list[dict[str, Any]] = []

    if _workspace_needs_init(workspace):
        init_workspace(workspace)
        summary["steps"].append("init")
    else:
        _ensure_input_dirs(workspace)

    if rule_files:
        imported = rules_mod.import_rule_files(workspace, rule_files)
        summary["rule_files"] = imported.to_dict()
        summary["steps"].append("import-rules")

    brainstorm_json = workspace / "input" / "ideas" / "brainstorm.json"
    if not brainstorm_json.exists():
        bundle = brainstorm_mod.run_brainstorm(workspace, answers=answers)
        summary["steps"].append("brainstorm")
        summary["recommended_title"] = bundle.titles[0] if bundle.titles else ""
    else:
        summary["steps"].append("brainstorm:skipped-existing")

    research = background_mod.run_background_research(workspace, offline=offline_research)
    summary["steps"].append("research-background")
    summary["research_fallback"] = research.fallback_used

    survey_source = survey_path or _find_survey_file(workspace)
    if survey_source and survey_source.exists():
        analysis = survey_mod.import_survey(
            survey_source,
            workspace / "input" / "surveys" / "analysis",
            workspace=workspace,
        )
        summary["survey"] = {"source": str(survey_source), "respondents": analysis.respondents}
    else:
        survey_mod.write_missing_survey_placeholder(workspace, item_count=survey_items)
        missing_inputs.append(
            {
                "kind": "설문",
                "action": f"동일 문항 {survey_items}문항 사전·사후 설문 CSV/XLSX 필요",
                "path": "input/surveys/",
            }
        )
        summary["survey"] = {"source": "", "respondents": 0, "placeholder": True}
    summary["steps"].append("survey")

    manifest = photos_mod.import_photos(
        workspace / "input" / "photos",
        workspace / "input" / "photos" / "analysis",
        workspace=workspace,
        placeholder_if_empty=True,
        required_count=photo_count,
    )
    if manifest.missing_required:
        missing_inputs.append(
            {
                "kind": "사진",
                "action": f"수업사진 {photo_count}장 첨부 및 개인정보 블러 필요",
                "path": "input/photos/",
            }
        )
    summary["photos"] = {"count": manifest.count, "placeholder": manifest.missing_required}
    summary["steps"].append("photos")

    references_mod.mine_references(workspace / "input" / "references", workspace / "input" / "references" / "analysis")
    summary["steps"].append("mine-references")

    draft_mod.generate_drafts(workspace)
    summary["steps"].append("draft")

    _write_missing_inputs_report(workspace, missing_inputs)
    _seed_go_review_lanes(workspace, missing_inputs)

    assemble_workspace(workspace)
    summary["steps"].append("assemble")
    check = check_workspace(workspace, final=False)
    summary["check"] = check.to_dict()
    summary["steps"].append("check")

    if build_hwpx:
        target = workspace / "output" / "report.hwpx"
        hwpx_mod.build_hwpx_from_bundle(
            [workspace / "output" / name for name in FINAL_BUNDLE_FILES if name != "finalization-checklist.md"],
            target,
            images_root=workspace,
        )
        summary["hwpx"] = str(target)
        render = render_check_mod.run_render_check(
            target,
            workspace / "output",
            toc_path=workspace / "output" / "toc.md",
        )
        summary["render_check"] = render.to_dict()
        summary["steps"].extend(["build-hwpx", "render-check"])

    backlog = revise_mod.run_revise_loop(workspace)
    summary["revision_tasks"] = len(backlog.tasks)
    summary["missing_inputs"] = missing_inputs
    summary["steps"].append("revise-loop")
    return summary


def go_cmd(
    workspace: Path,
    answers_path: Path | None,
    option_answers: dict[str, str],
    rule_files: list[Path] | None,
    survey_path: Path | None,
    offline_research: bool,
    survey_items: int,
    photo_count: int,
    skip_hwpx: bool,
) -> None:
    loaded_answers = _load_answers(answers_path) or {}
    answers = {**loaded_answers, **{key: value for key, value in option_answers.items() if value}} or None
    summary = go_workspace(
        workspace,
        answers=answers,
        rule_files=rule_files,
        survey_path=survey_path,
        offline_research=offline_research,
        survey_items=survey_items,
        photo_count=photo_count,
        build_hwpx=not skip_hwpx,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def agents_list_cmd() -> None:
    registry = {
        name: {
            "bin": spec.default_bin,
            "version_args": spec.version_args,
            "auth_args": spec.auth_args,
            "run_args": spec.run_args,
        }
        for name, spec in agents_mod.AGENT_REGISTRY.items()
    }
    print(json.dumps(registry, ensure_ascii=False, indent=2))


def agents_preflight_cmd(workspace: Path, agents: list[str] | None, strict: bool) -> int:
    report = agents_mod.run_preflight(workspace, agents)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if strict and not report.all_ready():
        return 1
    return 0


def agents_run_cmd(workspace: Path, agent: str, lanes: list[str], timeout: int) -> int:
    exit_code = 0
    for lane in lanes:
        result = agents_mod.run_agent_on_lane(workspace, agent, lane, timeout=timeout)
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        if not result.ok:
            exit_code = 1
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="create a clean competition workspace")
    init_p.add_argument("workspace")
    init_p.add_argument("--brainstorm", action="store_true", help="run the brainstorm interview right after init")
    init_p.add_argument("--research-background", action="store_true", help="after brainstorm, run public-route background research")

    brainstorm_p = sub.add_parser("brainstorm", help="interview → trend research → topic/title → input/ideas/")
    brainstorm_p.add_argument("workspace")
    brainstorm_p.add_argument("--answers", help="JSON file of interview answers (non-interactive)")
    brainstorm_p.add_argument("--competition-name", help="참가 예정 연구대회명")
    brainstorm_p.add_argument("--agent", choices=tuple(agents_mod.AGENT_REGISTRY), help="augment trend research via an agent CLI")
    brainstorm_p.add_argument("--research-background", action="store_true", help="run public-route theory/prior-research collection after topic selection")
    # Per-field flags so an agent can pass interview answers directly, no file.
    brainstorm_p.add_argument("--major", help="전공 교과/분야 (필수)")
    brainstorm_p.add_argument("--level", help="학교급/학년")
    brainstorm_p.add_argument("--class-context", dest="class_context", help="학급/수업 상황")
    brainstorm_p.add_argument("--interests", help="관심 트렌드/키워드")
    brainstorm_p.add_argument("--tools", help="활용 도구")
    brainstorm_p.add_argument("--competency", help="목표 역량")
    brainstorm_p.add_argument("--constraints", help="기타 제약 조건")

    go_p = sub.add_parser("go", help="short autopilot: brainstorm → research → placeholders → draft → hwpx")
    go_p.add_argument("workspace")
    go_p.add_argument("--answers", help="JSON file of interview answers (non-interactive)")
    go_p.add_argument("--competition-name", default="", help="참가 예정 연구대회명")
    go_p.add_argument("--major", help="전공 교과")
    go_p.add_argument("--level", default="", help="학교급/학년")
    go_p.add_argument("--class-context", default="", help="학급/수업 상황")
    go_p.add_argument("--interests", default="", help="관심 트렌드/키워드")
    go_p.add_argument("--tools", default="", help="활용 도구")
    go_p.add_argument("--competency", default="", help="목표 역량")
    go_p.add_argument("--constraints", default="", help="제약 조건")
    go_p.add_argument("--rule-file", action="append", default=[], help="대회 공문/양식/심사표 파일 또는 폴더")
    go_p.add_argument("--survey", help="설문 CSV/TSV/XLSX 경로. 없으면 input/surveys에서 자동 탐색")
    go_p.add_argument("--survey-items", type=int, default=survey_mod.DEFAULT_REQUIRED_SURVEY_ITEMS)
    go_p.add_argument("--photo-count", type=int, default=photos_mod.DEFAULT_REQUIRED_PHOTOS)
    go_p.add_argument("--offline-research", action="store_true", help="network 없이 배경연구 fallback 사용")
    go_p.add_argument("--skip-hwpx", action="store_true", help="HWPX build/render-check 생략")
    go_p.add_argument(
        "--skeleton",
        action="store_true",
        help="레거시 골격 생성 확인 플래그. 없으면 실행 거부(완성 보고서는 autopilot 사용)",
    )

    lane_p = sub.add_parser("lane", help="create lane inbox for an agent")
    lane_p.add_argument("workspace")
    lane_p.add_argument("lane", choices=LANES)
    lane_p.add_argument("agent")

    boot_p = sub.add_parser("bootstrap-lanes", help="create all report-production lane inboxes")
    boot_p.add_argument("workspace")
    boot_p.add_argument("agent")

    assemble_p = sub.add_parser("assemble", help="assemble report, summary, toc, appendix, and finalization bundle")
    assemble_p.add_argument("workspace")

    check_p = sub.add_parser("check", help="validate lane contracts and claim ledger")
    check_p.add_argument("workspace")
    check_p.add_argument("--final", action="store_true", help="enforce final-candidate rules")
    check_p.add_argument(
        "--allow-expected",
        action="store_true",
        help="final에서 라벨링된 예상값(status=expected) 주장을 허용 (교체 목록을 output/expected-claims.md에 기록)",
    )

    next_p = sub.add_parser(
        "next", help="autopilot: 다음에 할 작업(위임/명령)을 결정적으로 판정해 JSON으로 출력"
    )
    next_p.add_argument("workspace")

    survey_p = sub.add_parser("import-survey", help="analyze a pre/post survey CSV/TSV/XLSX")
    survey_p.add_argument("workspace")
    survey_p.add_argument("survey", help="path to the survey file")

    photos_p = sub.add_parser("import-photos", help="build photo manifest + privacy checklist")
    photos_p.add_argument("workspace")

    rules_p = sub.add_parser("import-rules", help="copy competition notice/rubric/form files into input/rules")
    rules_p.add_argument("workspace")
    rules_p.add_argument("files", nargs="+", help="대회 공문/양식/심사표 파일 또는 폴더")

    refs_p = sub.add_parser("mine-references", help="extract structure from reference reports")
    refs_p.add_argument("workspace")

    background_p = sub.add_parser("research-background", help="collect theory/background/prior research with public adaptive routes")
    background_p.add_argument("workspace")
    background_p.add_argument("--query", help="override topic/query instead of reading brainstorm output")
    background_p.add_argument("--max-results", type=int, default=8)
    background_p.add_argument("--offline", action="store_true", help="skip network routes and write verification-needed fallback")

    draft_p = sub.add_parser("draft", help="generate body/summary/toc/appendix drafts")
    draft_p.add_argument("workspace")

    run_lanes_p = sub.add_parser("run-lanes", help="generate per-lane prompt bundles for external agents")
    run_lanes_p.add_argument("workspace")
    run_lanes_p.add_argument("agent")
    run_lanes_p.add_argument("--lanes", nargs="*", choices=LANES, help="subset of lanes")
    run_lanes_p.add_argument(
        "--execute", action="store_true", help="preflight login then actually call the agent CLI"
    )

    hwpx_p = sub.add_parser("build-hwpx", help="build a .hwpx from the assembled bundle")
    hwpx_p.add_argument("workspace")
    hwpx_p.add_argument("--output", help="output .hwpx path")
    hwpx_p.add_argument(
        "--engine",
        choices=("builtin", "kordoc"),
        default="builtin",
        help="렌더 엔진: builtin(결정적 구조 렌더러) 또는 kordoc(오픈소스 한국형 보고서 프리셋, Node 18+ 필요)",
    )

    diagnose_p = sub.add_parser(
        "diagnose", help="output 폴더를 검진해 보고서가 왜 이상하게 나왔는지 신호를 찾는다"
    )
    diagnose_p.add_argument("workspace")

    icons_p = sub.add_parser(
        "render-icons", help="render input/icons/icon-spec.json into flat PNG icons (pure stdlib)"
    )
    icons_p.add_argument("workspace")

    unpack_p = sub.add_parser("hwpx-unpack", help="unpack a .hwpx zip for design-iteration XML editing")
    unpack_p.add_argument("workspace")
    unpack_p.add_argument("--hwpx", help="path to the .hwpx (default output/report.hwpx)")
    unpack_p.add_argument("--dir", help="target directory (default output/hwpx-src)")

    pack_p = sub.add_parser("hwpx-pack", help="repack an unpacked hwpx dir and validate with render-check")
    pack_p.add_argument("workspace")
    pack_p.add_argument("--dir", help="unpacked directory (default output/hwpx-src)")
    pack_p.add_argument("--output", help="output .hwpx path (default output/report.hwpx)")

    render_p = sub.add_parser("render-check", help="validate a built .hwpx structure")
    render_p.add_argument("workspace")
    render_p.add_argument("--hwpx", help="path to the .hwpx (default output/report.hwpx)")
    render_p.add_argument("--page-limit", type=int, default=render_check_mod.DEFAULT_PAGE_LIMIT)
    render_p.add_argument(
        "--min-pages", type=int, default=0, help="본문 분량 하한(추정). 미만이면 경고(예: 22)"
    )

    revise_p = sub.add_parser("revise-loop", help="collect critic/check/render feedback into a backlog")
    revise_p.add_argument("workspace")

    agent_names = tuple(agents_mod.AGENT_REGISTRY)
    agents_p = sub.add_parser("agents", help="detect, verify login, and run external agent CLIs")
    agents_sub = agents_p.add_subparsers(dest="agents_cmd", required=True)

    agents_list_p = agents_sub.add_parser("list", help="show the agent CLI registry and defaults")

    agents_pre_p = agents_sub.add_parser("preflight", help="check install + login for each agent CLI")
    agents_pre_p.add_argument("workspace")
    agents_pre_p.add_argument("--agents", nargs="*", choices=agent_names, help="subset of agents")
    agents_pre_p.add_argument("--strict", action="store_true", help="exit 1 if any agent is not authenticated")

    agents_run_p = agents_sub.add_parser("run", help="dispatch lane prompts to an agent CLI")
    agents_run_p.add_argument("workspace")
    agents_run_p.add_argument("agent", choices=agent_names)
    agents_run_p.add_argument("--lanes", nargs="+", required=True, choices=LANES)
    agents_run_p.add_argument("--timeout", type=int, default=agents_mod.RUN_TIMEOUT)

    args = parser.parse_args(argv)

    if args.cmd == "init":
        if args.research_background and not args.brainstorm:
            raise SystemExit("--research-background requires --brainstorm during init")
        init_workspace(Path(args.workspace))
        if args.brainstorm:
            brainstorm_cmd(Path(args.workspace), None, None, research_background=args.research_background)
        return 0
    if args.cmd == "brainstorm":
        field_answers = {
            key: getattr(args, key)
            for key in ("major", "level", "class_context", "interests", "tools", "competency", "constraints")
            if getattr(args, key, None)
        }
        brainstorm_cmd(
            Path(args.workspace),
            Path(args.answers) if args.answers else None,
            args.agent,
            research_background=args.research_background,
            competition_name=args.competition_name,
            field_answers=field_answers,
        )
        return 0
    if args.cmd == "go":
        if not args.skeleton:
            raise SystemExit(
                "거부: `rch go`는 레거시 스켈레톤 자동화입니다(본문이 '[…확정한다.]' placeholder 골격으로 "
                "채워지며 완성 보고서가 아닙니다). 완성 보고서는 에이전트 autopilot"
                "(AGENTS.md — deep-interview → 계획 승인 → rch next 루프)을 사용하세요. "
                "골격이 정말 필요하면 `rch go <ws> --skeleton`으로 다시 실행하세요."
            )
        print(
            "경고: `rch go`는 레거시 스켈레톤 자동화입니다(placeholder 표 중심, 완성 품질 아님). "
            "완성 보고서는 에이전트 autopilot(AGENTS.md — 인터뷰 → 계획 승인 → rch next 루프)을 사용하세요.",
            file=sys.stderr,
        )
        go_cmd(
            Path(args.workspace),
            Path(args.answers) if args.answers else None,
            _answers_from_options(args),
            [Path(path) for path in args.rule_file],
            Path(args.survey) if args.survey else None,
            args.offline_research,
            args.survey_items,
            args.photo_count,
            args.skip_hwpx,
        )
        return 0
    if args.cmd == "lane":
        create_lane(Path(args.workspace), args.lane, args.agent)
        return 0
    if args.cmd == "bootstrap-lanes":
        bootstrap_lanes(Path(args.workspace), args.agent)
        return 0
    if args.cmd == "assemble":
        assemble_workspace(Path(args.workspace))
        return 0
    if args.cmd == "check":
        result = check_workspace(
            Path(args.workspace), final=args.final, allow_expected=args.allow_expected
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    if args.cmd == "next":
        plan = pipeline_mod.run_next(Path(args.workspace), final_check=check_workspace)
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "import-survey":
        import_survey_cmd(Path(args.workspace), Path(args.survey))
        return 0
    if args.cmd == "import-photos":
        import_photos_cmd(Path(args.workspace))
        return 0
    if args.cmd == "import-rules":
        import_rules_cmd(Path(args.workspace), [Path(path) for path in args.files])
        return 0
    if args.cmd == "mine-references":
        mine_references_cmd(Path(args.workspace))
        return 0
    if args.cmd == "research-background":
        research_background_cmd(Path(args.workspace), args.query, args.max_results, args.offline)
        return 0
    if args.cmd == "draft":
        draft_cmd(Path(args.workspace))
        return 0
    if args.cmd == "run-lanes":
        return run_lanes_cmd(Path(args.workspace), args.agent, args.lanes, args.execute)
    if args.cmd == "build-hwpx":
        build_hwpx_cmd(Path(args.workspace), Path(args.output) if args.output else None, engine=args.engine)
        return 0
    if args.cmd == "diagnose":
        return diagnose_cmd(Path(args.workspace))
    if args.cmd == "render-icons":
        report = icons_mod.render_icons(Path(args.workspace))
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if not report.errors else 1
    if args.cmd == "hwpx-unpack":
        hwpx_unpack_cmd(
            Path(args.workspace),
            Path(args.hwpx) if args.hwpx else None,
            Path(args.dir) if args.dir else None,
        )
        return 0
    if args.cmd == "hwpx-pack":
        return hwpx_pack_cmd(
            Path(args.workspace),
            Path(args.dir) if args.dir else None,
            Path(args.output) if args.output else None,
        )
    if args.cmd == "render-check":
        return render_check_cmd(
            Path(args.workspace), Path(args.hwpx) if args.hwpx else None, args.page_limit, args.min_pages
        )
    if args.cmd == "revise-loop":
        revise_loop_cmd(Path(args.workspace))
        return 0
    if args.cmd == "agents":
        if args.agents_cmd == "list":
            agents_list_cmd()
            return 0
        if args.agents_cmd == "preflight":
            return agents_preflight_cmd(Path(args.workspace), args.agents, args.strict)
        if args.agents_cmd == "run":
            return agents_run_cmd(Path(args.workspace), args.agent, args.lanes, args.timeout)
        raise AssertionError(args.agents_cmd)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
