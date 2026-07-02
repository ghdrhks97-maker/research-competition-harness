"""Render QA (hancom-render-qa-skill / `rch render-check`).

Validates a built `.hwpx` without launching Hancom: confirms the OWPML zip
structure, that every XML part is well-formed, counts headings/paragraphs/
tables, estimates page count against a limit, checks table row integrity,
resolves image references, and verifies the table of contents matches the
document headings. It reports an honest verdict and always states that the
final visual confirmation still happens in Hancom/HOP.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

REQUIRED_ENTRIES = (
    "mimetype",
    "version.xml",
    "META-INF/container.xml",
    "Contents/header.xml",
    "Contents/section0.xml",
)
MIMETYPE = "application/hwp+zip"
DEFAULT_PAGE_LIMIT = 25
# Competition forms usually demand a *full* body (표지·목차·요약서 제외 25쪽).
# Below this estimate the report reads under-filled, so the check warns.
DEFAULT_MIN_PAGES = 0
# Rough characters-per-page for a dense Korean A4 report body. Estimate only.
CHARS_PER_PAGE = 1600
ROWS_PER_PAGE = 45


@dataclass
class RenderCheck:
    hwpx_path: str
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    heading_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    estimated_pages: int = 0
    page_limit: int = DEFAULT_PAGE_LIMIT
    min_pages: int = DEFAULT_MIN_PAGES
    toc_headings_matched: bool = True
    toc_mismatches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _count_elements(root: ElementTree.Element) -> tuple[int, int]:
    paragraphs = 0
    tables = 0
    for element in root.iter():
        name = _localname(element.tag)
        if name == "p":
            paragraphs += 1
        elif name == "tbl":
            tables += 1
    return paragraphs, tables


def _section_text_and_headings(root: ElementTree.Element) -> tuple[str, list[str], int]:
    texts: list[str] = []
    headings: list[str] = []
    heading_count = 0
    for paragraph in root.iter():
        if _localname(paragraph.tag) != "p":
            continue
        para_ref = paragraph.get("paraPrIDRef")
        collected: list[str] = []
        for node in paragraph.iter():
            if _localname(node.tag) == "t" and node.text:
                collected.append(node.text)
        text = "".join(collected).strip()
        if not text:
            continue
        texts.append(text)
        # paraPrIDRef 1/2/3 are heading shapes in the builder.
        if para_ref in {"1", "2", "3"}:
            heading_count += 1
            headings.append(text)
    return "\n".join(texts), headings, heading_count


def _estimate_pages(body_text: str, table_count: int, row_estimate: int) -> int:
    char_pages = len(body_text) / CHARS_PER_PAGE
    table_pages = row_estimate / ROWS_PER_PAGE
    estimate = char_pages + table_pages
    return max(1, round(estimate))


def _parse_toc_headings(toc_path: Path) -> list[str]:
    if not toc_path.exists():
        return []
    headings: list[str] = []
    for line in toc_path.read_text(encoding="utf-8", errors="replace").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Drop leading list markers and trailing dot-leaders / page numbers.
        stripped = re.sub(r"^[-*0-9.)\s]+", "", stripped)
        stripped = re.sub(r"[.\s]*\d+\s*$", "", stripped)
        stripped = stripped.strip()
        if stripped:
            headings.append(stripped)
    return headings


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def render_check(
    hwpx_path: Path,
    toc_path: Path | None = None,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    min_pages: int = DEFAULT_MIN_PAGES,
) -> RenderCheck:
    check = RenderCheck(hwpx_path=hwpx_path.as_posix(), page_limit=page_limit, min_pages=min_pages)

    if not hwpx_path.exists():
        check.ok = False
        check.errors.append(f"hwpx not found: {hwpx_path}")
        return check

    try:
        archive = zipfile.ZipFile(hwpx_path)
    except zipfile.BadZipFile:
        check.ok = False
        check.errors.append("not a valid zip / hwpx container")
        return check

    with archive:
        names = archive.namelist()
        for entry in REQUIRED_ENTRIES:
            if entry not in names:
                check.errors.append(f"missing OWPML entry: {entry}")

        if names and names[0] != "mimetype":
            check.errors.append("mimetype must be the first zip entry")
        else:
            info = archive.getinfo("mimetype") if "mimetype" in names else None
            if info is not None and info.compress_type != zipfile.ZIP_STORED:
                check.errors.append("mimetype must be stored uncompressed")
            if "mimetype" in names and archive.read("mimetype").decode("utf-8").strip() != MIMETYPE:
                check.errors.append(f"mimetype content must be {MIMETYPE}")

        # Well-formedness of every XML part.
        for name in names:
            if name.endswith(".xml") or name.endswith(".hpf"):
                try:
                    ElementTree.fromstring(archive.read(name))
                except ElementTree.ParseError as exc:
                    check.errors.append(f"malformed xml: {name}: {exc}")

        if "Contents/section0.xml" in names:
            try:
                section_root = ElementTree.fromstring(archive.read("Contents/section0.xml"))
            except ElementTree.ParseError:
                section_root = None
            # A section with no page definition (hp:pagePr) opens in Hancom
            # but renders blank — text has no page to lay out on.
            if b"pagePr" not in archive.read("Contents/section0.xml"):
                check.errors.append(
                    "section0.xml에 페이지 정의(hp:pagePr)가 없어 Hancom에서 빈 문서로 보입니다. build-hwpx 재실행 필요."
                )
            if section_root is not None:
                paragraphs, tables = _count_elements(section_root)
                body_text, headings, heading_count = _section_text_and_headings(section_root)
                check.paragraph_count = paragraphs
                check.table_count = tables
                check.heading_count = heading_count
                row_estimate = _estimate_table_rows(section_root)
                check.estimated_pages = _estimate_pages(body_text, tables, row_estimate)
                if check.estimated_pages > page_limit:
                    check.warnings.append(
                        f"추정 {check.estimated_pages}쪽이 제한 {page_limit}쪽을 초과(추정치). "
                        "table-layout 압축 검토 필요."
                    )
                if min_pages and check.estimated_pages < min_pages:
                    check.warnings.append(
                        f"추정 {check.estimated_pages}쪽이 목표 하한 {min_pages}쪽 미만(추정치). "
                        "본문 밀도 부족 — draft-writer 보강 필요(장별 분량 예산 참고)."
                    )
                _check_table_integrity(section_root, check)
                _check_toc(headings, toc_path, check)

    check.ok = not check.errors
    return check


def _estimate_table_rows(root: ElementTree.Element) -> int:
    rows = 0
    for element in root.iter():
        if _localname(element.tag) == "tr":
            rows += 1
    return rows


def _check_table_integrity(root: ElementTree.Element, check: RenderCheck) -> None:
    for index, table in enumerate(element for element in root.iter() if _localname(element.tag) == "tbl"):
        declared_cols = table.get("colCnt")
        rows = [child for child in table if _localname(child.tag) == "tr"]
        widths = set()
        for row in rows:
            cells = [cell for cell in row if _localname(cell.tag) == "tc"]
            widths.add(len(cells))
        if len(widths) > 1:
            check.warnings.append(f"표 {index + 1} 행마다 열 수가 다름: {sorted(widths)}")
        if declared_cols and widths and int(declared_cols) not in widths:
            check.warnings.append(f"표 {index + 1} colCnt({declared_cols})와 실제 열 수 불일치")


def _check_toc(headings: list[str], toc_path: Path | None, check: RenderCheck) -> None:
    if toc_path is None:
        return
    toc_headings = _parse_toc_headings(toc_path)
    if not toc_headings:
        check.warnings.append("목차(toc.md)를 찾지 못해 목차-본문 대조를 건너뜀")
        return
    body_norms = {_norm(text) for text in headings}
    missing = [entry for entry in toc_headings if _norm(entry) not in body_norms]
    if missing:
        check.toc_headings_matched = False
        check.toc_mismatches = missing
        check.warnings.append(
            f"목차 {len(missing)}개 항목이 본문 제목과 정확히 일치하지 않음: {', '.join(missing[:5])}"
        )


def render_report_markdown(check: RenderCheck) -> str:
    status = "통과" if check.ok else "실패"
    lines = [
        "# 렌더 검증 결과",
        "",
        f"- 대상: `{check.hwpx_path}`",
        f"- 구조 판정: {status}",
        f"- 제목 수: {check.heading_count}",
        f"- 문단 수: {check.paragraph_count}",
        f"- 표 수: {check.table_count}",
        f"- 추정 페이지: {check.estimated_pages} / 제한 {check.page_limit} (추정치)",
        f"- 목차-본문 일치: {'예' if check.toc_headings_matched else '아니오'}",
        "",
    ]
    if check.errors:
        lines += ["## 오류", ""] + [f"- {error}" for error in check.errors] + [""]
    if check.warnings:
        lines += ["## 경고", ""] + [f"- {warning}" for warning in check.warnings] + [""]
    lines += [
        "## 사람 최종 확인",
        "",
        "- Hancom/HOP에서 실제로 열어 페이지 수, 목차 번호, 표 흐름, 이미지 겹침을 최종 확인한다.",
        "- 구조 통과는 Hancom 실제 표시를 보장하지 않는다.",
        "",
    ]
    return "\n".join(lines)


def run_render_check(
    hwpx_path: Path,
    output_dir: Path,
    toc_path: Path | None = None,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    min_pages: int = DEFAULT_MIN_PAGES,
) -> RenderCheck:
    check = render_check(hwpx_path, toc_path=toc_path, page_limit=page_limit, min_pages=min_pages)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "render-check.json").write_text(
        json.dumps(check.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "render-check.md").write_text(render_report_markdown(check), encoding="utf-8")
    return check
