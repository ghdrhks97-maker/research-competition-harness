"""MCP server wrapper (`rch-mcp`).

Exposes the harness engine as Model Context Protocol tools so Claude Code
or Codex can drive report production by calling tools (brainstorm, import
survey, draft, build hwpx, ...) instead of a human running the CLI.

Design: the actual work lives in plain ``op_*`` functions that reuse the
existing engine modules and need no MCP dependency (so they stay unit
testable). ``build_server()`` imports the MCP SDK lazily and registers
those ops as tools; ``main()`` runs the stdio server. This means importing
this module never requires ``mcp`` to be installed — only running the
server does (``pip install "research-competition-harness[mcp]"``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rch import background as background_mod
from rch import brainstorm as brainstorm_mod
from rch import draft as draft_mod
from rch import hwpx as hwpx_mod
from rch import photos as photos_mod
from rch import references as references_mod
from rch import render_check as render_check_mod
from rch import revise as revise_mod
from rch import rules as rules_mod
from rch import survey as survey_mod
from rch.cli import assemble_workspace, check_workspace, go_workspace, init_workspace
from rch.lane_specs import FINAL_BUNDLE_FILES

# Bundle files that carry renderable report content (checklist is meta).
_RENDER_BUNDLE = tuple(name for name in FINAL_BUNDLE_FILES if name != "finalization-checklist.md")

INTERVIEW_KEYS = (
    "competition_name",
    "major",
    "level",
    "class_context",
    "interests",
    "tools",
    "competency",
    "constraints",
)


def _ws(workspace: str) -> Path:
    path = Path(workspace).expanduser()
    return path


def op_init(workspace: str) -> dict[str, Any]:
    path = _ws(workspace)
    init_workspace(path)
    return {"ok": True, "workspace": str(path)}


def op_brainstorm(workspace: str, major: str, **answers: str) -> dict[str, Any]:
    path = _ws(workspace)
    payload = {"major": major}
    for key in INTERVIEW_KEYS:
        if key in answers and answers[key]:
            payload[key] = answers[key]
    bundle = brainstorm_mod.run_brainstorm(path, answers=payload)
    return {
        "recommended_topic": bundle.recommended_topic,
        "recommended_title": bundle.titles[0] if bundle.titles else "",
        "titles": bundle.titles,
        "topics": [topic.title_seed for topic in bundle.topics],
        "trends": bundle.trends,
        "ideas_dir": "input/ideas/",
    }


def op_import_rules(workspace: str, rule_files: str) -> dict[str, Any]:
    path = _ws(workspace)
    files = _split_paths(rule_files)
    report = rules_mod.import_rule_files(path, files)
    return report.to_dict()


def op_import_survey(workspace: str, survey_path: str) -> dict[str, Any]:
    path = _ws(workspace)
    analysis = survey_mod.import_survey(
        Path(survey_path).expanduser(),
        path / "input" / "surveys" / "analysis",
        workspace=path,
    )
    return analysis.to_dict()


def op_import_photos(workspace: str) -> dict[str, Any]:
    path = _ws(workspace)
    source = path / "input" / "photos"
    manifest = photos_mod.import_photos(source, source / "analysis", workspace=path)
    return manifest.to_dict()


def op_mine_references(workspace: str) -> dict[str, Any]:
    path = _ws(workspace)
    source = path / "input" / "references"
    report = references_mod.mine_references(source, source / "analysis")
    return report.to_dict()


def op_research_background(
    workspace: str,
    query: str = "",
    max_results: int = 8,
    offline: bool = False,
) -> dict[str, Any]:
    path = _ws(workspace)
    report = background_mod.run_background_research(
        path,
        query=query or None,
        max_results=max_results,
        offline=offline,
    )
    return report.to_dict()


def op_draft(workspace: str) -> dict[str, Any]:
    path = _ws(workspace)
    written = draft_mod.generate_drafts(path)
    return {"drafted_lanes": written}


def op_assemble(workspace: str) -> dict[str, Any]:
    path = _ws(workspace)
    assemble_workspace(path)
    manifest_path = path / "output" / "bundle-manifest.json"
    return {"ok": True, "manifest": manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else ""}


def op_check(workspace: str, final: bool = False) -> dict[str, Any]:
    path = _ws(workspace)
    result = check_workspace(path, final=final)
    return result.to_dict()


def op_build_hwpx(workspace: str, output: str | None = None) -> dict[str, Any]:
    path = _ws(workspace)
    output_dir = path / "output"
    bundle = [output_dir / name for name in _RENDER_BUNDLE if (output_dir / name).exists()]
    if not bundle:
        raise ValueError("no assembled bundle found; run assemble first")
    target = Path(output).expanduser() if output else output_dir / "report.hwpx"
    result = hwpx_mod.build_hwpx_from_bundle(bundle, target, images_root=path)
    return {
        "hwpx": str(target),
        "paragraphs": result.paragraph_count,
        "tables": result.table_count,
        "headings": result.heading_count,
        "images": result.image_count,
        "missing_images": result.missing_images,
    }


def op_render_check(workspace: str, hwpx: str | None = None, page_limit: int = 25) -> dict[str, Any]:
    path = _ws(workspace)
    target = Path(hwpx).expanduser() if hwpx else path / "output" / "report.hwpx"
    toc_path = path / "output" / "toc.md"
    check = render_check_mod.run_render_check(
        target, path / "output", toc_path=toc_path if toc_path.exists() else None, page_limit=page_limit
    )
    return check.to_dict()


def op_revise_loop(workspace: str) -> dict[str, Any]:
    path = _ws(workspace)
    backlog = revise_mod.run_revise_loop(path)
    return backlog.to_dict()


def op_go(
    workspace: str,
    competition_name: str = "연구대회",
    major: str = "교과",
    level: str = "",
    class_context: str = "",
    interests: str = "",
    tools: str = "",
    competency: str = "",
    constraints: str = "",
    rule_files: str = "",
    survey_path: str = "",
    offline_research: bool = False,
    survey_items: int = 5,
    photo_count: int = 4,
    build_hwpx: bool = True,
) -> dict[str, Any]:
    path = _ws(workspace)
    answers = {
        "competition_name": competition_name or "연구대회",
        "major": major or "교과",
        "level": level,
        "class_context": class_context,
        "interests": interests,
        "tools": tools,
        "competency": competency,
        "constraints": constraints,
    }
    return go_workspace(
        path,
        answers={key: value for key, value in answers.items() if value},
        rule_files=_split_paths(rule_files),
        survey_path=Path(survey_path).expanduser() if survey_path else None,
        offline_research=offline_research,
        survey_items=survey_items,
        photo_count=photo_count,
        build_hwpx=build_hwpx,
    )


def _split_paths(value: str) -> list[Path]:
    if not value:
        return []
    raw = value.replace("\n", ",").replace(";", ",").split(",")
    return [Path(item.strip()).expanduser() for item in raw if item.strip()]


def build_server() -> Any:
    """Create the FastMCP server with all tools registered."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - only hit without the extra
        raise SystemExit(
            'MCP 서버 실행에는 mcp 패키지가 필요합니다: pip install "research-competition-harness[mcp]"'
        ) from exc

    app = FastMCP("rch", instructions=(
        "한국 연구대회 보고서 제작 하네스. 빠른 시작은 go. 순서: init → brainstorm → "
        "research_background/import_survey/import_photos/mine_references → draft → assemble → check(final) → "
        "build_hwpx → render_check → revise_loop. 증거 없는 수치·학생 발화·사진은 금지."
    ))

    @app.tool()
    def go(
        workspace: str,
        competition_name: str = "연구대회",
        major: str = "교과",
        level: str = "",
        class_context: str = "",
        interests: str = "",
        tools: str = "",
        competency: str = "",
        constraints: str = "",
        rule_files: str = "",
        survey_path: str = "",
        offline_research: bool = False,
        survey_items: int = 5,
        photo_count: int = 4,
        build_hwpx: bool = True,
    ) -> dict[str, Any]:
        """브레인스토밍부터 HWPX 검증까지 자동 실행한다. 설문/사진 없으면 placeholder 표를 만든다."""
        return op_go(
            workspace,
            competition_name=competition_name,
            major=major,
            level=level,
            class_context=class_context,
            interests=interests,
            tools=tools,
            competency=competency,
            constraints=constraints,
            rule_files=rule_files,
            survey_path=survey_path,
            offline_research=offline_research,
            survey_items=survey_items,
            photo_count=photo_count,
            build_hwpx=build_hwpx,
        )

    @app.tool()
    def init(workspace: str) -> dict[str, Any]:
        """새 대회 작업공간을 생성한다."""
        return op_init(workspace)

    @app.tool()
    def brainstorm(
        workspace: str,
        major: str,
        competition_name: str = "",
        level: str = "",
        class_context: str = "",
        interests: str = "",
        tools: str = "",
        competency: str = "",
        constraints: str = "",
    ) -> dict[str, Any]:
        """전공 인터뷰 답을 받아 트렌드 리서치·연구 주제·제목을 만들어 input/ideas에 쓴다."""
        return op_brainstorm(
            workspace, major, competition_name=competition_name, level=level, class_context=class_context, interests=interests,
            tools=tools, competency=competency, constraints=constraints,
        )

    @app.tool()
    def import_rules(workspace: str, rule_files: str) -> dict[str, Any]:
        """대회 공문·심사표·보고서 양식 파일을 input/rules에 저장한다."""
        return op_import_rules(workspace, rule_files)

    @app.tool()
    def import_survey(workspace: str, survey_path: str) -> dict[str, Any]:
        """사전·사후 설문 CSV/TSV/XLSX를 익명 분석한다(평균·변화량·효과크기·p값)."""
        return op_import_survey(workspace, survey_path)

    @app.tool()
    def import_photos(workspace: str) -> dict[str, Any]:
        """input/photos 사진의 개인정보 점검표와 배치 매니페스트를 만든다."""
        return op_import_photos(workspace)

    @app.tool()
    def mine_references(workspace: str) -> dict[str, Any]:
        """레퍼런스 보고서에서 목차·표 밀도·부록 패턴 등 구조만 추출한다."""
        return op_mine_references(workspace)

    @app.tool()
    def research_background(
        workspace: str,
        query: str = "",
        max_results: int = 8,
        offline: bool = False,
    ) -> dict[str, Any]:
        """공개 route scheduler로 이론적 배경·선행연구 후보를 수집한다."""
        return op_research_background(workspace, query=query, max_results=max_results, offline=offline)

    @app.tool()
    def draft(workspace: str) -> dict[str, Any]:
        """분석 결과로 I~V장 본문·요약서·목차·부록 초안을 생성한다."""
        return op_draft(workspace)

    @app.tool()
    def assemble(workspace: str) -> dict[str, Any]:
        """lane 산출물을 하나의 markdown 번들로 조립한다."""
        return op_assemble(workspace)

    @app.tool()
    def check(workspace: str, final: bool = False) -> dict[str, Any]:
        """lane 계약·claim-ledger·금지어를 검증한다. final=True면 최종 후보 규칙."""
        return op_check(workspace, final=final)

    @app.tool()
    def build_hwpx(workspace: str, output: str = "") -> dict[str, Any]:
        """조립된 번들을 HWPX(OWPML) 파일로 렌더한다."""
        return op_build_hwpx(workspace, output or None)

    @app.tool()
    def render_check(workspace: str, hwpx: str = "", page_limit: int = 25) -> dict[str, Any]:
        """HWPX 구조·페이지 추정·목차 일치·표 무결성을 검증한다."""
        return op_render_check(workspace, hwpx or None, page_limit=page_limit)

    @app.tool()
    def revise_loop(workspace: str) -> dict[str, Any]:
        """critic·check·render-check 피드백을 우선순위 수정 백로그로 통합한다."""
        return op_revise_loop(workspace)

    return app


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
