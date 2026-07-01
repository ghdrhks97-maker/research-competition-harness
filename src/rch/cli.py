from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rch.lane_specs import FINAL_BUNDLE_FILES, LANE_SPECS, render_lane_input

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "next_competition_workspace"

LANES = tuple(LANE_SPECS)
INPUT_DIRS = ("ideas", "rules", "references", "evidence", "photos", "surveys", "raw_private")
FINAL_OUTPUT_MAP = {
    "report-draft.md": ("draft-writer",),
    "summary-sheet.md": ("summary-sheet",),
    "toc.md": ("toc-builder",),
    "appendix.md": ("appendix-builder",),
    "finalization-checklist.md": ("finalizer", "critic"),
}

FINAL_FORBIDDEN = ("예정", "추후", "보완 예정", "초안", "미정", "TODO")
CLAIM_STATUSES = {"real", "placeholder", "derived", "forbidden"}
FINAL_ALLOWED_STATUSES = {"real", "derived"}
FINAL_REQUIRED_LANES = frozenset(lane for lanes in FINAL_OUTPUT_MAP.values() for lane in lanes)
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

    if final:
        _check_final_bundle(workspace, errors)

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
        evidence = claim.get("evidence")
        if status in FINAL_ALLOWED_STATUSES and not evidence:
            errors.append(f"{lane_dir}: claim {index} needs evidence path")
        elif final and status in FINAL_ALLOWED_STATUSES and not _evidence_exists(lane_dir, evidence):
            errors.append(f"{lane_dir}: claim {index} evidence path missing: {evidence}")


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


def _evidence_exists(lane_dir: Path, evidence: Any) -> bool:
    if not isinstance(evidence, str) or not evidence.strip():
        return False
    evidence_path = Path(evidence)
    if evidence_path.is_absolute():
        return evidence_path.exists()
    workspace = lane_dir.parents[2]
    return (lane_dir / evidence_path).exists() or (workspace / evidence_path).exists()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="create a clean competition workspace")
    init_p.add_argument("workspace")

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

    args = parser.parse_args(argv)

    if args.cmd == "init":
        init_workspace(Path(args.workspace))
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
        result = check_workspace(Path(args.workspace), final=args.final)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
