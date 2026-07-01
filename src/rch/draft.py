"""Draft generator (report-draft-writer-skill / `rch draft`).

Composes first drafts of the report body, summary sheet, table of
contents, and appendix from whatever the harness already knows: the
recommended outline from `mine-references`, the survey analysis from
`import-survey`, the photo manifest from `import-photos`, and any filled
upstream lane outputs (brainstorm, evidence-curator, ...).

Output lands in the four writing lanes under a synthetic agent so the
existing `assemble` step can pick it up. Every generated section carries a
claim ledger: survey-backed statements are `derived`, and anything the
harness cannot verify is an explicit `placeholder` for a human to resolve.
The draft is deliberately not final-clean — that is the quality loop's job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DRAFT_AGENT = "harness-draft"

DEFAULT_OUTLINE = [
    "I. 연구의 필요성 및 목적",
    "II. 연구의 준비 및 실태 분석",
    "III. 수업 설계 및 실천 과제",
    "IV. 실천 과정 및 결과",
    "V. 결론 및 제언",
]


@dataclass
class DraftContext:
    title: str
    outline: list[str]
    survey_summary_md: str
    survey_claims: list[dict[str, Any]]
    photo_body: list[str]
    photo_appendix: list[str]
    brainstorm_md: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _first_lane_output(workspace: Path, lane: str) -> str:
    for path in sorted((workspace / "lanes" / lane).glob("*/lane-output.md")):
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            return text
    return ""


def _strip_title(markdown_text: str) -> str:
    lines = markdown_text.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def gather_context(workspace: Path) -> DraftContext:
    outline_report = _read_json(workspace / "input" / "references" / "analysis" / "reference-pattern.json")
    outline = DEFAULT_OUTLINE
    if isinstance(outline_report, dict) and outline_report.get("recommended_outline"):
        outline = [str(item) for item in outline_report["recommended_outline"]]

    survey_summary = _strip_title(_read_text(workspace / "input" / "surveys" / "analysis" / "survey-summary.md"))
    survey_ledger = _read_json(workspace / "input" / "surveys" / "analysis" / "claim-ledger.json")
    survey_claims = survey_ledger.get("claims", []) if isinstance(survey_ledger, dict) else []

    photo_manifest = _read_json(workspace / "input" / "photos" / "analysis" / "photo-manifest.json")
    photo_body: list[str] = []
    photo_appendix: list[str] = []
    if isinstance(photo_manifest, dict):
        for photo in photo_manifest.get("photos", []):
            placement = photo.get("suggested_placement")
            entry = f"{photo.get('file')} ({photo.get('privacy_risk')})"
            if placement == "body":
                photo_body.append(entry)
            elif placement == "appendix":
                photo_appendix.append(entry)

    brainstorm = _first_lane_output(workspace, "brainstorm")
    title = _extract_title(brainstorm) or "연구대회 보고서 제목(확정 필요)"

    return DraftContext(
        title=title,
        outline=outline,
        survey_summary_md=survey_summary,
        survey_claims=survey_claims,
        photo_body=photo_body,
        photo_appendix=photo_appendix,
        brainstorm_md=brainstorm,
    )


def _extract_title(brainstorm_md: str) -> str:
    for line in brainstorm_md.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _section_body(heading: str, context: DraftContext) -> tuple[str, list[dict[str, Any]]]:
    claims: list[dict[str, Any]] = []
    lines = [f"## {heading}", ""]
    lower = heading
    if "결과" in lower or "IV" in heading or "V." in heading and "결과" in heading:
        if context.survey_summary_md:
            lines.append("실천 과정에서 수집한 사전·사후 설문 결과는 다음과 같다.")
            lines.append("")
            lines.append(context.survey_summary_md)
            lines.append("")
            claims.extend(context.survey_claims)
        else:
            lines.append("실천 결과는 설문 분석(`rch import-survey`) 결과로 채운다.")
            claims.append(_placeholder(f"{heading}-결과", "설문/증거 분석 결과로 대체 필요"))
    else:
        lines.append(f"[{heading}의 서술은 lane 산출물과 증거로 확정한다.]")
        claims.append(_placeholder(f"{heading}", "본문 서술 확정 필요"))
    lines.append("")
    return "\n".join(lines), claims


def _placeholder(claim_id: str, note: str) -> dict[str, Any]:
    return {"id": _slug(claim_id), "text": note, "status": "placeholder", "notes": note}


def _slug(text: str) -> str:
    return "draft-" + "".join(ch if ch.isalnum() else "-" for ch in text).strip("-").lower()


def build_report_body(context: DraftContext) -> tuple[str, list[dict[str, Any]]]:
    lines = [f"# {context.title}", ""]
    claims: list[dict[str, Any]] = []
    for heading in context.outline:
        if heading.startswith("부록"):
            continue
        body, section_claims = _section_body(heading, context)
        lines.append(body)
        claims.extend(section_claims)
    return "\n".join(lines).rstrip() + "\n", claims


def build_summary(context: DraftContext) -> tuple[str, list[dict[str, Any]]]:
    lines = [
        "# 요약서",
        "",
        f"- 제목: {context.title}",
        "- 문제의식: [한 줄로 확정]",
        "- 수업 모형: [brainstorm lane 결과로 확정]",
        "- 실천 과제: [3~5개로 확정]",
        "",
    ]
    claims: list[dict[str, Any]] = []
    if context.survey_summary_md:
        lines.append("## 핵심 결과")
        lines.append("")
        lines.append(context.survey_summary_md)
        lines.append("")
        claims.extend(context.survey_claims)
    else:
        claims.append(_placeholder("summary-result", "핵심 결과를 설문/증거로 확정"))
    return "\n".join(lines).rstrip() + "\n", claims


def build_toc(context: DraftContext) -> tuple[str, list[dict[str, Any]]]:
    lines = ["# 목차", ""]
    for heading in context.outline:
        lines.append(f"- {heading}")
    lines.append("")
    claims = [_placeholder("toc-pages", "인쇄 페이지 번호는 build-hwpx/render-check 후 확정")]
    return "\n".join(lines).rstrip() + "\n", claims


def build_appendix(context: DraftContext) -> tuple[str, list[dict[str, Any]]]:
    lines = ["# 부록", "", "본문을 보강하는 자료만 남긴다.", ""]
    claims: list[dict[str, Any]] = []
    if context.photo_appendix:
        lines.append("## 수업사진 (부록 배치 후보)")
        lines.append("")
        for entry in context.photo_appendix:
            lines.append(f"- {entry}")
        lines.append("")
        claims.append(_placeholder("appendix-photos", "사진 개인정보 확인 후 반영"))
    lines.append("## 구성 항목")
    lines.append("")
    for item in ["교수학습 과정안", "평가 루브릭", "활동지", "설문지", "대표 산출물"]:
        lines.append(f"- {item} [확정 필요]")
    lines.append("")
    claims.append(_placeholder("appendix-items", "부록 실제 자료 첨부 필요"))
    return "\n".join(lines).rstrip() + "\n", claims


LANE_BUILDERS = {
    "draft-writer": build_report_body,
    "summary-sheet": build_summary,
    "toc-builder": build_toc,
    "appendix-builder": build_appendix,
}


def _write_lane(workspace: Path, lane: str, markdown_text: str, claims: list[dict[str, Any]]) -> None:
    lane_dir = workspace / "lanes" / lane / DRAFT_AGENT
    (lane_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (lane_dir / "lane-output.md").write_text(markdown_text, encoding="utf-8")
    (lane_dir / "lane-output.json").write_text(
        json.dumps(
            {"lane": lane, "agent": DRAFT_AGENT, "summary": f"{lane} 자동 초안", "artifacts": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (lane_dir / "claim-ledger.json").write_text(
        json.dumps({"claims": claims}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    has_placeholder = any(claim.get("status") == "placeholder" for claim in claims)
    (lane_dir / "verdict.json").write_text(
        json.dumps(
            {
                "status": "needs-work" if has_placeholder else "pass",
                "reason": "harness 자동 초안. 사람/에이전트 검토 후 placeholder 해소 필요."
                if has_placeholder
                else "harness 자동 초안. 근거 확인됨.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def generate_drafts(workspace: Path) -> dict[str, int]:
    if not workspace.exists():
        raise SystemExit(f"workspace missing: {workspace}")
    context = gather_context(workspace)
    written: dict[str, int] = {}
    for lane, builder in LANE_BUILDERS.items():
        markdown_text, claims = builder(context)
        _write_lane(workspace, lane, markdown_text, claims)
        written[lane] = len(claims)
    return written
