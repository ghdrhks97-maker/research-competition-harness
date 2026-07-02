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

import json
from pathlib import Path
from typing import Any

from rch import background as background_mod
from rch import brainstorm as brainstorm_mod
from rch import draft as draft_mod
from rch import hwpx as hwpx_mod
from rch import photos as photos_mod
from rch import pipeline as pipeline_mod
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
        "competition_name": bundle.answers.get("competition_name", ""),
        "core_competencies_2022": bundle.core_competencies,
        "recommended_topic": bundle.recommended_topic,
        "recommended_title": bundle.titles[0] if bundle.titles else "",
        "titles": bundle.titles,
        "topics": [{"topic": topic.title_seed, "core_competency": topic.core_competency} for topic in bundle.topics],
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


def op_check(workspace: str, final: bool = False, allow_expected: bool = False) -> dict[str, Any]:
    path = _ws(workspace)
    result = check_workspace(path, final=final, allow_expected=allow_expected)
    return result.to_dict()


def op_next(workspace: str) -> dict[str, Any]:
    path = _ws(workspace)
    plan = pipeline_mod.run_next(path, final_check=check_workspace)
    return plan.to_dict()


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
        "한국 연구대회 보고서 제작 하네스(에이전트 우선). 판단·리서치·집필·비평은 전부 "
        "당신(에이전트)이 AGENTS.md의 역할 정의대로 직접 수행하고, 이 서버의 도구는 결정적 작업에만 쓴다: "
        "init(골격)·import_rules(양식 저장)·import_survey(설문 통계)·next(다음 작업 판정 루프)·"
        "check(검증 게이트)·assemble(조립)·build_hwpx(렌더)·render_check(렌더 검증)·revise_loop(수정 백로그)·"
        "diagnose(산출물 검진). 흐름: deep-interview(대화) → 계획 승인 → next를 반복 호출해 done까지. "
        "경고: go/brainstorm/draft/mine_references/research_background/import_photos는 레거시 파이썬 "
        "콘텐츠 생성기라서 placeholder 골격만 나온다 — 절대 호출하지 말 것(내용은 당신이 직접 쓴다). "
        "증거 없는 수치·학생 발화·사진 금지, 예상값은 '예상값(가상)' 라벨+expected."
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
        skeleton: bool = False,
    ) -> dict[str, Any]:
        """[레거시 — 완성 보고서용 아님] placeholder 표 중심의 스켈레톤을 빠르게 만든다.
        skeleton=True를 명시하지 않으면 실행을 거부한다. 완성 보고서는 이 도구가 아니라
        에이전트 autopilot(deep-interview → 계획 승인 → next 루프, AGENTS.md 참고)으로
        만들어야 한다. 에이전트는 이 도구를 호출하지 말 것."""
        if not skeleton:
            return {
                "ok": False,
                "refused": True,
                "reason": (
                    "go는 레거시 스켈레톤 생성기입니다(placeholder 골격, 완성 보고서 아님). "
                    "완성 보고서는 deep-interview → 계획 승인 → next 루프(autopilot)로 만드세요. "
                    "골격이 정말 필요하면 사용자 확인 후 skeleton=true로 다시 호출하세요."
                ),
            }
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
        """[레거시 — 호출 금지] 파이썬 템플릿으로 주제·제목을 만든다(품질 낮음). 주제·제목은
        에이전트가 deep-interview + brainstorm 역할(1등급 작명 공식)로 직접 만들어 input/ideas에 쓴다."""
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
        """[레거시 — 호출 금지] 파일명 휴리스틱 점검표만 만든다. 사진 개인정보 판정은
        photo-curator 역할이 실제 픽셀을 보고 직접 수행한다."""
        return op_import_photos(workspace)

    @app.tool()
    def mine_references(workspace: str) -> dict[str, Any]:
        """[레거시 — 호출 금지] 제목 개수 휴리스틱 추출(부정확). 레퍼런스 구조 분석은
        reference-miner 역할이 원본을 직접 읽고 수행한다."""
        return op_mine_references(workspace)

    @app.tool()
    def research_background(
        workspace: str,
        query: str = "",
        max_results: int = 8,
        offline: bool = False,
    ) -> dict[str, Any]:
        """[레거시 — 호출 금지] 기계 질의라 무관한 소스가 섞인다. 배경·선행연구는
        background-researcher 역할이 insane-search v2(4트랙 질의 매트릭스)로 직접 조사한다."""
        return op_research_background(workspace, query=query, max_results=max_results, offline=offline)

    @app.tool()
    def draft(workspace: str) -> dict[str, Any]:
        """[레거시 — 호출 금지] 대괄호 placeholder 골격만 만든다("[…확정한다.]" 문단).
        본문은 draft-writer 역할이 규정 분량을 채워 직접 집필한다."""
        return op_draft(workspace)

    @app.tool()
    def assemble(workspace: str) -> dict[str, Any]:
        """lane 산출물을 하나의 markdown 번들로 조립한다."""
        return op_assemble(workspace)

    @app.tool()
    def check(workspace: str, final: bool = False, allow_expected: bool = False) -> dict[str, Any]:
        """lane 계약·claim-ledger·금지어를 검증한다. final=True면 최종 후보 규칙.
        allow_expected=True면 라벨링된 예상값(status=expected) 주장을 final에서 허용한다."""
        return op_check(workspace, final=final, allow_expected=allow_expected)

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

    @app.tool()
    def diagnose(workspace: str) -> dict[str, Any]:
        """output 폴더를 검진해 보고서가 왜 이상하게 나왔는지(레거시 go 흔적, 표 크기 누락,
        lane 미실행, placeholder 잔존 등) 신호를 돌려준다."""
        from rch.cli import diagnose_cmd  # lazy: avoids duplicating the inspection logic

        path = _ws(workspace)
        diagnose_cmd(path)
        report = (path / "output" / "diagnose.json").read_text(encoding="utf-8")
        return json.loads(report)

    @app.tool()
    def next(workspace: str) -> dict[str, Any]:
        """autopilot: 다음에 할 작업(위임/명령)을 결정적으로 판정한다.
        needs_user가 비어 있으면 actions를 실행하고 다시 next를 호출하는 식으로
        done=true까지 반복한다."""
        return op_next(workspace)

    return app


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
