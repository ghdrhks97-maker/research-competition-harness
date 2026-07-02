from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from rch import rules as rules_mod

SURVEY_SOURCE_SUFFIXES: Final = {".csv", ".tsv", ".tab", ".xlsx", ".xlsm"}
PHOTO_SOURCE_SUFFIXES: Final = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"}
REQUIRED_OUTPUTS: Final = (
    "bundle-manifest.json",
    "report-draft.md",
    "summary-sheet.md",
    "toc.md",
    "appendix.md",
    "finalization-checklist.md",
    "report.hwpx",
)


def input_state(workspace: Path) -> dict[str, Any]:
    return {
        "competition": rules_mod.load_competition_profile(workspace),
        "rules": _rules_manifest(workspace),
        "brainstorm": _file_state(workspace, "input/ideas/brainstorm.json"),
        "evidence": {"files": _list_files(workspace, "input/evidence")},
        "survey": _survey_state(workspace),
        "photos": _photos_state(workspace),
        "reference": _reference_state(workspace),
        "final_bundle": {"files": _list_files(workspace, "output"), "hwpx": _file_state(workspace, "output/report.hwpx")},
    }


def missing_inputs(state: dict[str, Any]) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    competition_name = str(state["competition"].get("competition_name", "")).strip()
    if not competition_name or competition_name == "연구대회":
        missing.append(_missing("competition", "참가 연구대회명", "대회명과 연도·분야를 수집·확정", "input/rules/competition-profile.json"))
    if not state["rules"].get("files"):
        missing.append(_missing("rules", "공문·양식·심사표", "rch import-rules로 원본 파일 보존", "input/rules/"))
    if not state["evidence"]["files"]:
        missing.append(_missing("evidence", "수업 증거", "활동지·산출물·관찰 기록을 익명화해 수집", "input/evidence/"))
    if not state["survey"]["files"]:
        missing.append(_missing("survey", "설문 원자료/분석", "사전·사후 설문 CSV/XLSX 또는 분석표 수집", "input/surveys/"))
    if not state["photos"]["files"]:
        missing.append(_missing("photos", "수업 사진", "개인정보 검토 가능한 수업 장면 파일 수집", "input/photos/"))
    if not state["reference"]["files"] and not _has_readable_reference_analysis(state["reference"]["analysis_json"]):
        missing.append(_missing("reference", "우수 보고서 구조 참고", "레퍼런스 보고서 또는 구조 분석 파일 수집", "input/references/"))
    return missing


def final_check(workspace: Path) -> dict[str, Any]:
    from rch.cli import check_workspace

    return check_workspace(workspace, final=True).to_dict()


def final_candidate_ready(workspace: Path, missing: list[dict[str, str]], check: dict[str, Any]) -> bool:
    return (
        not missing
        and all((workspace / "output" / name).exists() for name in REQUIRED_OUTPUTS)
        and bool(check.get("ok"))
    )


def readiness(is_ready: bool, missing: list[dict[str, str]], check: dict[str, Any]) -> dict[str, Any]:
    if is_ready:
        return {"verdict": "ready_for_hancom_hop_gate", "reason": "필수 입력과 최종 bundle/HWPX가 존재한다."}
    if missing:
        return {"verdict": "blocked_collect_inputs", "reason": "필수 입력이 없어 최종 후보로 판정하지 않는다."}
    if not check.get("ok"):
        error_count = len(check.get("errors", []))
        return {"verdict": "blocked_run_final_gates", "reason": f"입력은 있으나 final check 오류 {error_count}건이 남아 있다."}
    return {"verdict": "blocked_run_final_gates", "reason": "입력은 있으나 최종 bundle/HWPX gate가 남아 있다."}


def collection_kit(missing: list[dict[str, str]]) -> list[dict[str, str]]:
    source = missing or [_missing("final-gates", "최종 gate", "check/build/render gate 실행", "output/")]
    return [{"step": str(index), **item} for index, item in enumerate(source, 1)]


def _survey_state(workspace: Path) -> dict[str, Any]:
    return {
        "files": _list_files(workspace, "input/surveys", exclude_dirs={"analysis"}, suffixes=SURVEY_SOURCE_SUFFIXES),
        "analysis": _file_state(workspace, "input/surveys/analysis/survey-summary.md"),
        "analysis_json": _json_file_state(workspace, "input/surveys/analysis/survey-analysis.json"),
        "claim_ledger": _claim_ledger_state(workspace, "input/surveys/analysis/claim-ledger.json"),
        "lane_verdicts": _lane_verdicts(workspace, "survey-analyzer"),
    }


def _photos_state(workspace: Path) -> dict[str, Any]:
    return {
        "files": _list_files(workspace, "input/photos", exclude_dirs={"analysis"}, suffixes=PHOTO_SOURCE_SUFFIXES),
        "analysis": _file_state(workspace, "input/photos/analysis/photo-manifest.json"),
        "manifest": _json_file_state(workspace, "input/photos/analysis/photo-manifest.json"),
        "claim_ledger": _claim_ledger_state(workspace, "input/photos/analysis/claim-ledger.json"),
        "lane_verdicts": _lane_verdicts(workspace, "photo-curator"),
    }


def _reference_state(workspace: Path) -> dict[str, Any]:
    return {
        "files": _list_files(workspace, "input/references", exclude_dirs={"analysis"}),
        "analysis": _list_files(workspace, "input/references/analysis"),
        "analysis_json": _json_file_state(workspace, "input/references/analysis/reference-pattern.json"),
    }


def _rules_manifest(workspace: Path) -> dict[str, Any]:
    path = workspace / "input" / "rules" / rules_mod.MANIFEST_JSON
    if not path.exists():
        return {"files": [], "missing": []}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return loaded
    return {"files": [], "missing": []}


def _missing(identifier: str, item: str, action: str, path: str) -> dict[str, str]:
    return {"id": identifier, "item": item, "action": action, "path": path}


def _file_state(workspace: Path, relative_path: str) -> dict[str, Any]:
    path = workspace / relative_path
    return {"path": relative_path, "exists": path.exists()}


def _json_file_state(workspace: Path, relative_path: str) -> dict[str, Any]:
    path = workspace / relative_path
    state = _file_state(workspace, relative_path)
    if not path.exists():
        return {**state, "valid": False, "data": None}
    try:
        return {**state, "valid": True, "data": json.loads(path.read_text(encoding="utf-8"))}
    except json.JSONDecodeError as exc:
        return {**state, "valid": False, "data": None, "error": str(exc)}


def _claim_ledger_state(workspace: Path, relative_path: str) -> dict[str, Any]:
    state = _json_file_state(workspace, relative_path)
    data = state.get("data")
    claims = data.get("claims", []) if isinstance(data, dict) else []
    if not isinstance(claims, list):
        claims = []
    statuses = [str(claim.get("status")) for claim in claims if isinstance(claim, dict) and claim.get("status")]
    return {
        "path": relative_path,
        "exists": state["exists"],
        "valid": state["valid"],
        "claim_count": len(claims),
        "claim_statuses": statuses,
        "has_placeholder": any(status == "placeholder" for status in statuses),
    }


def _lane_verdicts(workspace: Path, lane: str) -> list[dict[str, str]]:
    lane_root = workspace / "lanes" / lane
    if not lane_root.exists():
        return []
    verdicts: list[dict[str, str]] = []
    for path in sorted(lane_root.glob("*/verdict.json")):
        data = _read_json_safely(path)
        verdicts.append(
            {
                "path": path.relative_to(workspace).as_posix(),
                "status": str(data.get("status", "invalid")) if isinstance(data, dict) else "invalid",
                "reason": str(data.get("reason", "")) if isinstance(data, dict) else "",
            }
        )
    return verdicts


def _has_readable_reference_analysis(state: dict[str, Any]) -> bool:
    data = state.get("data")
    if not isinstance(data, dict):
        return False
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        return False
    return any(isinstance(profile, dict) and profile.get("readable") for profile in profiles)


def _read_json_safely(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _list_files(
    workspace: Path,
    relative_dir: str,
    exclude_dirs: set[str] | None = None,
    suffixes: set[str] | None = None,
) -> list[str]:
    root = workspace / relative_dir
    if not root.exists():
        return []
    excluded = exclude_dirs or set()
    files: list[str] = []
    for path in sorted(root.rglob("*")):
        relative_parts = path.relative_to(root).parts
        if any(part in excluded for part in relative_parts[:-1]):
            continue
        if suffixes is not None and path.suffix.lower() not in suffixes:
            continue
        if path.is_file() and path.name != ".gitkeep":
            files.append(path.relative_to(workspace).as_posix())
    return files
