from __future__ import annotations

from typing import Final

PHASE_IDS: Final = ("intake", "research", "evidence", "reference", "draft", "design", "finalization", "hwpx")

ANTI_FABRICATION_RULES: Final = (
    "설문 수치, 향상도, p값, 효과크기는 원자료와 계산식 없이는 만들지 않는다.",
    "학생 발화·소감·면담 인용은 실제 익명 원문 없이는 만들지 않는다.",
    "수업 사진, 스크린샷, 산출물 이미지는 실제 파일 없이는 만들지 않는다.",
    "심사 점수, 수상 가능성, 확산 실적, 연수 실적은 증거 없이 확정하지 않는다.",
    "레퍼런스 보고서는 구조와 패턴만 추출하고 문장·표·캡션은 복사하지 않는다.",
    "최종 본문에는 미완성·보류 표시를 넣지 않는다. 확정 전 내용은 claim-ledger placeholder로 둔다.",
)


def phases() -> list[dict[str, str]]:
    titles = {
        "intake": "대회명·규정·입력 정리",
        "research": "배경연구 public-route 수집",
        "evidence": "claim-ledger와 실제 증거 연결",
        "reference": "우수 보고서 구조 추출",
        "draft": "본문·요약·목차·부록 초안",
        "design": "표·페이지·시각 구조 압축",
        "finalization": "금지어·placeholder·심사표 gate",
        "hwpx": "HWPX 생성과 Hancom/HOP 렌더 확인",
    }
    return [{"id": phase_id, "title": titles[phase_id]} for phase_id in PHASE_IDS]


def commands(agents: tuple[str, ...], offline_research: bool) -> list[dict[str, str]]:
    research_flag = " --offline" if offline_research else ""
    command_rows = [
        ("import-rules", "rch import-rules <workspace> <notice/rubric/form files...>", "공식 규정·양식 원본 보존"),
        ("brainstorm", "rch brainstorm <workspace>", "대회명부터 주제·제목 생성"),
        ("research", f"rch research-background <workspace>{research_flag}", "배경연구 후보 수집"),
        ("survey", "rch import-survey <workspace> <survey.csv>", "익명 설문 분석"),
        ("photos", "rch import-photos <workspace>", "사진 매니페스트와 개인정보 점검"),
        ("references", "rch mine-references <workspace>", "레퍼런스 보고서 구조만 추출"),
    ]
    for agent in agents:
        command_rows.append((f"lanes-{agent}", f"rch run-lanes <workspace> {agent}", f"{agent} lane 프롬프트 생성"))
    command_rows += [
        ("draft", "rch draft <workspace>", "분석 결과를 보고서 bundle lane으로 전환"),
        ("assemble", "rch assemble <workspace>", "markdown 최종 bundle 조립"),
        ("check", "rch check <workspace> --final", "claim-ledger·금지어·rubric final gate"),
        ("hwpx", "rch build-hwpx <workspace> && rch render-check <workspace>", "HWPX 생성 후 구조 점검"),
    ]
    return [{"id": command_id, "command": command, "purpose": purpose} for command_id, command, purpose in command_rows]


def quality_gates() -> list[dict[str, str]]:
    return [
        {"id": "rules", "name": "Competition rules gate", "check": "input/rules 원본 경로와 rules-manifest hash를 보존한다."},
        {"id": "claims", "name": "Claim ledger gate", "check": "final claim은 real/derived와 workspace-relative evidence만 허용한다."},
        {"id": "fabrication", "name": "Anti-fabrication gate", "check": "설문·학생발화·사진·점수는 실제 원자료 없이는 final 반영 금지."},
        {"id": "page-budget", "name": "Page budget before visual polish", "check": "page budget을 먼저 맞춘 뒤 아이콘·표·이미지 polish를 한다."},
        {"id": "hancom-hop", "name": "Hancom/HOP render truth", "check": "최종 판정은 Hancom/HOP에서 output/report.hwpx를 열어 페이지·목차·표 흐름을 확인한다."},
    ]
