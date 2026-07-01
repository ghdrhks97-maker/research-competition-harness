"""Reference report miner (reference-report-miner-skill / `rch mine-references`).

Extracts *structure*, not sentences, from reference reports so a new
report can borrow the layout of strong entries without copying wording.
It reads text-extractable references (`.md`, `.txt`, and `.hwpx` section
text) and reports outline shape, table/figure density, result-presentation
signals, and appendix patterns. PDFs must be exported to text first; the
miner records them as unread rather than guessing.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {".md", ".txt", ".markdown"}
CHAPTER_RE = re.compile(r"^\s*(?:#+\s*)?((?:[IVX]+|[0-9]+)[.)]?)\s+(\S.*)$")
KOREAN_CHAPTER_RE = re.compile(r"^\s*(?:#+\s*)?(제?\s*[0-9IVX]+\s*[장절])\s*(.*)$")
APPENDIX_HINTS = ("부록", "붙임", "appendix", "별첨")
RESULT_HINTS = ("결과", "분석", "효과", "성과", "변화", "만족도", "사전", "사후")
FIGURE_HINTS = ("그림", "사진", "figure", "fig.", "표 ")


@dataclass
class ReferenceProfile:
    file: str
    readable: bool
    outline: list[str] = field(default_factory=list)
    heading_count: int = 0
    table_row_count: int = 0
    figure_mentions: int = 0
    result_signal: int = 0
    has_appendix: bool = False
    note: str = ""


@dataclass
class ReferenceReport:
    source_dir: str
    profiles: list[ReferenceProfile] = field(default_factory=list)
    recommended_outline: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_hwpx_text(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            parts = [
                archive.read(name).decode("utf-8", errors="replace")
                for name in archive.namelist()
                if name.startswith("Contents/section") and name.endswith(".xml")
            ]
    except (zipfile.BadZipFile, KeyError, OSError):
        return None
    if not parts:
        return None
    text = "\n".join(parts)
    # Strip XML tags; keep text nodes as coarse lines.
    text = re.sub(r"<[^>]+>", "\n", text)
    return text


def _read_reference(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".hwpx":
        return _extract_hwpx_text(path)
    return None


def _profile_text(name: str, text: str) -> ReferenceProfile:
    lines = [line.rstrip() for line in text.split("\n")]
    outline: list[str] = []
    heading_count = 0
    figure_mentions = 0
    result_signal = 0
    has_appendix = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        chapter = KOREAN_CHAPTER_RE.match(stripped) or CHAPTER_RE.match(stripped)
        if chapter and len(stripped) <= 60:
            heading_count += 1
            if len(outline) < 40:
                outline.append(stripped)
        low = stripped.lower()
        if any(hint in low for hint in FIGURE_HINTS):
            figure_mentions += 1
        if any(hint in stripped for hint in RESULT_HINTS):
            result_signal += 1
        if any(hint in low for hint in APPENDIX_HINTS):
            has_appendix = True

    table_row_count = sum(1 for line in lines if line.strip().startswith("|") and line.count("|") >= 2)

    return ReferenceProfile(
        file=name,
        readable=True,
        outline=outline,
        heading_count=heading_count,
        table_row_count=table_row_count,
        figure_mentions=figure_mentions,
        result_signal=result_signal,
        has_appendix=has_appendix,
        note="구조 지표만 추출. 문장·표 내용은 복사하지 않음.",
    )


def _recommend_outline(profiles: list[ReferenceProfile]) -> list[str]:
    # Default competition arc; enriched only when references confirm it.
    default = [
        "I. 연구의 필요성 및 목적",
        "II. 연구의 준비 및 실태 분석",
        "III. 수업 설계 및 실천 과제",
        "IV. 실천 과정 및 결과",
        "V. 결론 및 제언",
    ]
    readable = [profile for profile in profiles if profile.readable]
    if not readable:
        return default
    avg_headings = sum(profile.heading_count for profile in readable) / len(readable)
    has_appendix = any(profile.has_appendix for profile in readable)
    outline = list(default)
    if avg_headings >= 10:
        outline = [
            "I. 연구의 필요성 및 목적",
            "II. 이론적 배경 및 실태 분석",
            "III. 연구 설계",
            "IV. 실천 과제별 전개",
            "V. 연구 결과 및 분석",
            "VI. 결론 및 제언",
        ]
    if has_appendix:
        outline.append("부록: 과정안·루브릭·활동지·설문지·산출물")
    return outline


def mine_references(source_dir: Path, output_dir: Path) -> ReferenceReport:
    report = ReferenceReport(source_dir=source_dir.as_posix())
    if source_dir.exists():
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in TEXT_SUFFIXES and suffix != ".hwpx":
                if suffix == ".pdf":
                    report.profiles.append(
                        ReferenceProfile(
                            file=path.relative_to(source_dir).as_posix(),
                            readable=False,
                            note="PDF는 텍스트로 export 후 다시 mine-references 실행.",
                        )
                    )
                continue
            text = _read_reference(path)
            name = path.relative_to(source_dir).as_posix()
            if text is None:
                report.profiles.append(
                    ReferenceProfile(file=name, readable=False, note="텍스트 추출 실패.")
                )
                continue
            report.profiles.append(_profile_text(name, text))

    report.recommended_outline = _recommend_outline(report.profiles)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reference-pattern.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "recommended-outline.md").write_text(
        render_outline_markdown(report), encoding="utf-8"
    )
    return report


def render_outline_markdown(report: ReferenceReport) -> str:
    lines = ["# 레퍼런스 구조 추출", "", f"- 원본 폴더: `{report.source_dir}`", ""]
    lines += ["## 권장 목차 (구조만 참고)", ""]
    lines += [f"{index}. {item}" for index, item in enumerate(report.recommended_outline, 1)]
    lines.append("")
    lines += ["## 레퍼런스별 구조 지표", "", "| 파일 | 읽음 | 제목수 | 표행 | 그림언급 | 결과신호 | 부록 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for profile in report.profiles:
        lines.append(
            f"| `{profile.file}` | {'예' if profile.readable else '아니오'} | {profile.heading_count} "
            f"| {profile.table_row_count} | {profile.figure_mentions} | {profile.result_signal} "
            f"| {'예' if profile.has_appendix else '아니오'} |"
        )
    lines.append("")
    lines.append("> 문장·표 내용·캡션은 복사하지 않는다. 목차·표 밀도·부록 구성 같은 구조만 참고한다.")
    lines.append("")
    return "\n".join(lines)
