from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

RULE_AGENT = "harness-rules"
PROFILE_JSON = "competition-profile.json"
PROFILE_MD = "competition-profile.md"
MANIFEST_JSON = "rules-manifest.json"
SUMMARY_MD = "rules-summary.md"


@dataclass
class RuleFile:
    source: str
    stored_path: str
    sha256: str
    bytes: int
    kind: str


@dataclass
class RulesImport:
    workspace: str
    files: list[RuleFile] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def rules_root(workspace: Path) -> Path:
    root = workspace / "input" / "rules"
    for name in ("forms", "rubrics", "notices", "templates"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def load_competition_profile(workspace: Path) -> dict[str, Any]:
    path = workspace / "input" / "rules" / PROFILE_JSON
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_competition_profile(workspace: Path, profile: dict[str, Any]) -> dict[str, Any]:
    root = rules_root(workspace)
    current = load_competition_profile(workspace)
    merged = {**current}
    for key, value in profile.items():
        if value not in ("", None, [], {}):
            merged[str(key)] = value
    (root / PROFILE_JSON).write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / PROFILE_MD).write_text(render_profile_markdown(merged), encoding="utf-8")
    return merged


def render_profile_markdown(profile: dict[str, Any]) -> str:
    lines = ["# 연구대회 프로필", ""]
    if not profile:
        lines.append("- 대회명: 미기재")
        lines.append("")
        return "\n".join(lines)
    labels = {
        "competition_name": "대회명",
        "competition_year": "연도",
        "competition_type": "대회 유형",
        "major": "분야/교과",
        "level": "대상/학교급",
    }
    for key, label in labels.items():
        if profile.get(key):
            lines.append(f"- {label}: {profile[key]}")
    extra = sorted(key for key in profile if key not in labels and profile.get(key))
    for key in extra:
        lines.append(f"- {key}: {profile[key]}")
    lines.append("")
    return "\n".join(lines)


def import_rule_files(workspace: Path, paths: list[Path]) -> RulesImport:
    root = rules_root(workspace)
    report = RulesImport(workspace=str(workspace))
    for source in _expand_sources(paths):
        if not source.exists():
            report.missing.append(str(source))
            continue
        if not source.is_file():
            continue
        kind = _kind_for(source)
        target_dir = root / kind
        target_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_target(target_dir / _safe_name(source.name))
        if source.resolve(strict=False) != target.resolve(strict=False):
            shutil.copy2(source, target)
        data = target.read_bytes()
        report.files.append(
            RuleFile(
                source=str(source),
                stored_path=target.relative_to(workspace).as_posix(),
                sha256=hashlib.sha256(data).hexdigest(),
                bytes=len(data),
                kind=kind,
            )
        )
    _write_rules_outputs(workspace, report)
    return report


def render_rules_summary(report: RulesImport) -> str:
    lines = ["# 대회 규정·양식 파일", ""]
    if report.files:
        lines += ["| 종류 | 저장 경로 | 원본 | bytes | sha256 |", "| --- | --- | --- | --- | --- |"]
        for item in report.files:
            lines.append(
                f"| {item.kind} | `{item.stored_path}` | `{item.source}` | {item.bytes} | `{item.sha256}` |"
            )
        lines.append("")
    else:
        lines.append("저장된 규정·양식 파일이 없다.")
        lines.append("")
    if report.missing:
        lines += ["## 찾지 못한 파일", ""]
        lines += [f"- `{path}`" for path in report.missing]
        lines.append("")
    lines.append("양식·공문·심사표는 문장 복사 대상이 아니라 형식, 분량, 제출 조건, 심사 기준의 근거로만 사용한다.")
    lines.append("")
    return "\n".join(lines)


def _write_rules_outputs(workspace: Path, report: RulesImport) -> None:
    root = rules_root(workspace)
    summary = render_rules_summary(report)
    (root / MANIFEST_JSON).write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (root / SUMMARY_MD).write_text(summary, encoding="utf-8")
    lane_dir = workspace / "lanes" / "intake" / RULE_AGENT
    lane_dir.mkdir(parents=True, exist_ok=True)
    (lane_dir / "evidence").mkdir(exist_ok=True)
    (lane_dir / "lane-output.md").write_text(summary, encoding="utf-8")
    (lane_dir / "lane-output.json").write_text(
        json.dumps(
            {
                "lane": "intake",
                "agent": RULE_AGENT,
                "summary": "대회 규정·양식 파일 저장",
                "artifacts": ["input/rules/rules-manifest.json", "input/rules/rules-summary.md"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    claims = [
        {
            "id": f"rule-file-{index}",
            "text": f"대회 규정·양식 파일 저장: {item.stored_path}",
            "status": "real",
            "evidence": item.stored_path,
        }
        for index, item in enumerate(report.files, 1)
    ]
    (lane_dir / "claim-ledger.json").write_text(
        json.dumps({"claims": claims}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    status = "pass" if report.files and not report.missing else "needs-work"
    reason = "규정·양식 파일 저장 완료." if status == "pass" else "규정·양식 파일 확인 필요."
    (lane_dir / "verdict.json").write_text(
        json.dumps({"status": status, "reason": reason}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _expand_sources(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        source = path.expanduser()
        if source.is_dir():
            expanded.extend(sorted(child for child in source.rglob("*") if child.is_file()))
        else:
            expanded.append(source)
    return expanded


def _kind_for(path: Path) -> str:
    name = path.name.lower()
    if any(token in name for token in ("심사", "rubric", "평가")):
        return "rubrics"
    if any(token in name for token in ("공문", "notice", "요강", "규정")):
        return "notices"
    if any(token in name for token in ("양식", "서식", "template", "form")):
        return "forms"
    return "templates"


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[/\\:\0]+", "_", name).strip()
    return cleaned or "rule-file"


def _unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    index = 2
    while True:
        candidate = parent / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
