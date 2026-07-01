"""Brainstorming engine (brainstorm-skill / `rch brainstorm`).

The harness starts here. Instead of asking a human to hand-author files in
`input/ideas/`, this runs a short structured interview (major/subject,
school level, class context, tools, target competency, constraints),
researches current education trends relevant to that subject, synthesizes
ranked research-topic candidates, brainstorms report titles, and writes
everything into `input/ideas/` as structured files. It also seeds the
`brainstorm` lane so the chosen title flows into `draft`.

Two modes:
- interactive: prompts on stdin (the default when a person runs it),
- scripted: pass an answers dict / `--answers file.json` for automation
  and tests.

If an external agent CLI is configured and logged in, the trend research
and topic synthesis can be augmented by a live agent; otherwise a
deterministic, subject-aware trend catalog is used. Nothing is fabricated
as verified fact — generated ideas enter as `placeholder`/`derived` claims
for a human to confirm.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

BRAINSTORM_AGENT = "harness-brainstorm"

# Interview script. key, question, required, default (used in scripted mode).
INTERVIEW: list[dict[str, Any]] = [
    {"key": "major", "q": "전공 교과가 무엇입니까? (예: 과학, 국어, 수학, 영어, 사회, 미술, 체육, 초등)", "required": True, "default": ""},
    {"key": "level", "q": "학교급/학년은? (예: 중학교 2학년)", "required": False, "default": "미기재"},
    {"key": "class_context", "q": "학급/수업 상황을 한 줄로? (인원, 특징)", "required": False, "default": "미기재"},
    {"key": "interests", "q": "관심 있는 교육 트렌드나 키워드가 있다면? (쉼표로, 없으면 Enter)", "required": False, "default": ""},
    {"key": "tools", "q": "활용 가능한 도구/환경은? (예: AI 챗봇, 태블릿, 실험실)", "required": False, "default": "미기재"},
    {"key": "competency", "q": "학생에게 가장 기르고 싶은 역량은? (예: 탐구력, 비판적 사고, 협업)", "required": False, "default": "핵심 역량"},
    {"key": "constraints", "q": "제약 조건은? (예: 총 12차시, 1학기 운영)", "required": False, "default": "미기재"},
]


@dataclass
class Trend:
    name: str
    summary: str
    subjects: tuple[str, ...]  # applicable subjects; ("공통",) = all
    keywords: tuple[str, ...]


# Current Korean K-12 education trends, subject-tagged for relevance scoring.
TREND_CATALOG: list[Trend] = [
    Trend("AI 활용 맞춤형 학습", "AI 디지털교과서와 생성형 AI로 학생별 수준·속도에 맞춘 개별화 수업을 설계한다.", ("공통",), ("ai", "인공지능", "맞춤형", "개별화", "챗봇", "디지털교과서")),
    Trend("하이터치 하이테크(HTHT)", "기술로 지식 전달을 효율화하고 교사는 고차원 상호작용·정서 지원에 집중한다.", ("공통",), ("htht", "하이터치", "에듀테크", "플립러닝")),
    Trend("학생 주도성(에이전시)", "학생이 학습 목표·과정·평가에 주도적으로 참여하는 자기주도 학습을 강화한다.", ("공통",), ("주도성", "에이전시", "자기주도", "선택", "자율")),
    Trend("과정중심·개념기반 탐구", "결과 점수 대신 학습 과정을 평가하고 핵심 개념 중심의 탐구로 전이를 돕는다.", ("공통",), ("과정중심", "개념기반", "탐구", "ib", "평가", "루브릭")),
    Trend("디지털 시민성·미디어 리터러시", "정보 판별, 저작권, 디지털 윤리와 안전한 온라인 소통 역량을 기른다.", ("공통", "국어", "사회", "도덕"), ("디지털시민", "미디어", "리터러시", "팩트체크", "윤리")),
    Trend("생태전환·기후환경 교육", "기후위기 대응과 지속가능성 실천을 교과와 연계한다.", ("공통", "과학", "사회", "실과"), ("생태", "기후", "환경", "지속가능", "탄소")),
    Trend("융합교육(STEAM)·메이커", "과학·기술·공학·예술·수학을 실물 제작과 문제해결로 융합한다.", ("과학", "수학", "기술", "미술", "실과", "초등"), ("steam", "융합", "메이커", "제작", "문제해결")),
    Trend("사회정서학습(SEL)", "정서 인식·관계·자기조절 역량으로 회복적 학급 문화를 만든다.", ("공통", "도덕", "체육"), ("sel", "정서", "관계", "회복", "공감")),
    Trend("프로젝트 기반 학습(PBL)", "실제 맥락의 과제를 장기 프로젝트로 해결하며 역량을 통합한다.", ("공통",), ("pbl", "프로젝트", "실생활", "산출물")),
    Trend("데이터·컴퓨팅 사고", "데이터 해석과 컴퓨팅 사고로 문제를 구조화하고 해결한다.", ("수학", "과학", "정보", "사회"), ("데이터", "컴퓨팅", "코딩", "sw", "통계")),
]


@dataclass
class TopicCandidate:
    trend: str
    title_seed: str
    research_question: str
    practical_tasks: list[str]
    score: int
    rationale: str


@dataclass
class BrainstormBundle:
    answers: dict[str, str]
    trends: list[dict[str, Any]]
    topics: list[TopicCandidate]
    recommended_topic: str
    titles: list[str]
    agent_augmented: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def _default_ask(question: str) -> str:
    try:
        return input(f"{question}\n> ").strip()
    except EOFError:
        return ""


def run_interview(ask: Callable[[str], str] | None = None) -> dict[str, str]:
    ask = ask or _default_ask
    answers: dict[str, str] = {}
    for item in INTERVIEW:
        value = ask(item["q"])
        while item["required"] and not value:
            value = ask(f"(필수) {item['q']}")
        answers[item["key"]] = value or item["default"]
    return answers


def _tokens(text: str) -> set[str]:
    return {token.strip().lower() for token in text.replace(",", " ").split() if token.strip()}


def rank_trends(answers: dict[str, str]) -> list[tuple[Trend, int]]:
    major = answers.get("major", "").strip()
    interest_tokens = _tokens(answers.get("interests", "")) | _tokens(answers.get("competency", "")) | _tokens(answers.get("tools", ""))
    ranked: list[tuple[Trend, int]] = []
    for trend in TREND_CATALOG:
        score = 1  # baseline relevance
        if major and (major in trend.subjects):
            score += 3
        if "공통" in trend.subjects:
            score += 1
        for keyword in trend.keywords:
            if any(keyword in token or token in keyword for token in interest_tokens):
                score += 2
        ranked.append((trend, score))
    ranked.sort(key=lambda pair: (-pair[1], pair[0].name))
    return ranked


def synthesize_topics(answers: dict[str, str], ranked: list[tuple[Trend, int]], limit: int = 3) -> list[TopicCandidate]:
    major = answers.get("major", "").strip() or "교과"
    competency = answers.get("competency", "").strip() or "핵심 역량"
    tools = answers.get("tools", "").strip()
    topics: list[TopicCandidate] = []
    for trend, score in ranked[:limit]:
        tool_clause = f" {tools}을(를) 활용해" if tools and tools != "미기재" else ""
        topics.append(
            TopicCandidate(
                trend=trend.name,
                title_seed=f"{trend.name} 기반 {major} 수업",
                research_question=f"{trend.name}을(를) 적용한{tool_clause} {major} 수업이 학생의 {competency} 신장에 어떤 영향을 주는가?",
                practical_tasks=[
                    f"실천1: {trend.name}에 맞춘 {major} 수업 모형 설계",
                    f"실천2: 수업 단계별 {competency} 중심 활동·평가 개발",
                    f"실천3: 사전·사후 변화 측정과 결과 일반화",
                ],
                score=score,
                rationale=f"{trend.summary} 전공({major})·역량({competency}) 적합도 점수 {score}.",
            )
        )
    return topics


def brainstorm_titles(topic: TopicCandidate, answers: dict[str, str]) -> list[str]:
    major = answers.get("major", "").strip() or "교과"
    competency = answers.get("competency", "").strip() or "핵심 역량"
    trend = topic.trend
    acronym = _acronym(trend, competency)
    return [
        f"『{acronym}』: {trend}으로 {competency}을(를) 키우는 {major} 수업 실천",
        f"{trend}을(를) 만난 {major}: {competency} 신장을 위한 수업 설계와 실천",
        f"{major} 교실의 전환 — {trend} 기반 {competency} 중심 수업 연구",
        f"묻고 만들고 나누다: {major} 속 {trend}로 기르는 {competency}",
        f"{competency}을(를) 위한 {trend} 수업 모형 개발과 적용: {major} 사례",
    ]


def _acronym(trend: str, competency: str) -> str:
    # Prefer a Latin acronym already present in the trend name (AI, STEAM, PBL…).
    latin = re.findall(r"[A-Za-z]+", trend)
    if latin:
        return "".join(latin).upper()[:5]
    return "STEP"


def build_bundle(answers: dict[str, str]) -> BrainstormBundle:
    ranked = rank_trends(answers)
    topics = synthesize_topics(answers, ranked)
    recommended = topics[0] if topics else None
    titles = brainstorm_titles(recommended, answers) if recommended else []
    return BrainstormBundle(
        answers=answers,
        trends=[{"name": trend.name, "summary": trend.summary, "score": score} for trend, score in ranked[:5]],
        topics=topics,
        recommended_topic=recommended.title_seed if recommended else "",
        titles=titles,
    )


# --- rendering ------------------------------------------------------------

def render_interview_md(bundle: BrainstormBundle) -> str:
    lines = ["# 브레인스토밍 인터뷰 기록", ""]
    label = {item["key"]: item["q"] for item in INTERVIEW}
    for key, value in bundle.answers.items():
        lines.append(f"- **{label.get(key, key)}**: {value}")
    lines.append("")
    return "\n".join(lines)


def render_trend_md(bundle: BrainstormBundle) -> str:
    lines = ["# 교육 트렌드 리서치", "", f"전공: {bundle.answers.get('major', '')}", "",
             "| 트렌드 | 적합도 | 요약 |", "| --- | --- | --- |"]
    for trend in bundle.trends:
        lines.append(f"| {trend['name']} | {trend['score']} | {trend['summary']} |")
    lines.append("")
    if bundle.agent_augmented:
        lines.append("> 외부 에이전트 리서치로 보강됨.")
    else:
        lines.append("> 내장 트렌드 카탈로그 기반. 최신 동향은 `rch brainstorm --agent <name>`으로 보강 가능.")
    lines.append("")
    return "\n".join(lines)


def render_topics_md(bundle: BrainstormBundle) -> str:
    lines = ["# 연구 주제 후보", ""]
    for index, topic in enumerate(bundle.topics, 1):
        mark = " (추천)" if topic.title_seed == bundle.recommended_topic else ""
        lines += [
            f"## {index}. {topic.title_seed}{mark}",
            "",
            f"- 트렌드: {topic.trend}",
            f"- 연구 질문: {topic.research_question}",
            f"- 적합도 점수: {topic.score}",
            f"- 근거: {topic.rationale}",
            "- 실천 과제:",
        ]
        lines += [f"  - {task}" for task in topic.practical_tasks]
        lines.append("")
    return "\n".join(lines)


def render_titles_md(bundle: BrainstormBundle) -> str:
    lines = ["# 보고서 제목 후보", ""]
    for index, title in enumerate(bundle.titles, 1):
        lines.append(f"{index}. {title}")
    lines.append("")
    lines.append("> 1번을 기본 추천 제목으로 brainstorm lane에 반영. 확정 전 사람이 최종 선택.")
    lines.append("")
    return "\n".join(lines)


def _seed_brainstorm_lane(workspace: Path, bundle: BrainstormBundle) -> None:
    if not bundle.titles:
        return
    lane_dir = workspace / "lanes" / "brainstorm" / BRAINSTORM_AGENT
    (lane_dir / "evidence").mkdir(parents=True, exist_ok=True)
    title = bundle.titles[0]
    topic = bundle.topics[0]
    body = [
        f"# {title}",
        "",
        f"- 연구 주제: {topic.title_seed}",
        f"- 연구 질문: {topic.research_question}",
        "- 실천 과제:",
        *[f"  - {task}" for task in topic.practical_tasks],
        "",
        "## 제목 후보",
        "",
        *[f"{i}. {t}" for i, t in enumerate(bundle.titles, 1)],
        "",
    ]
    (lane_dir / "lane-output.md").write_text("\n".join(body), encoding="utf-8")
    (lane_dir / "lane-output.json").write_text(
        json.dumps({"lane": "brainstorm", "agent": BRAINSTORM_AGENT, "summary": "브레인스토밍 초안", "artifacts": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (lane_dir / "claim-ledger.json").write_text(
        json.dumps(
            {"claims": [
                {"id": "brainstorm-title", "text": f"추천 제목: {title}", "status": "placeholder", "notes": "사람 최종 선택 필요"},
                {"id": "brainstorm-topic", "text": f"추천 주제: {topic.title_seed}", "status": "placeholder", "notes": "심사기준 대조 후 확정"},
            ]},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    (lane_dir / "verdict.json").write_text(
        json.dumps({"status": "needs-work", "reason": "브레인스토밍 자동 초안. 주제·제목 사람 확정 필요."}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_ideas(workspace: Path, bundle: BrainstormBundle) -> list[str]:
    ideas_dir = workspace / "input" / "ideas"
    ideas_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "00-interview.md": render_interview_md(bundle),
        "01-trend-research.md": render_trend_md(bundle),
        "02-research-topics.md": render_topics_md(bundle),
        "03-title-candidates.md": render_titles_md(bundle),
        "brainstorm.json": json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2),
    }
    written: list[str] = []
    for name, content in files.items():
        (ideas_dir / name).write_text(content, encoding="utf-8")
        written.append(f"input/ideas/{name}")
    _seed_brainstorm_lane(workspace, bundle)
    return written


def run_brainstorm(
    workspace: Path,
    answers: dict[str, str] | None = None,
    ask: Callable[[str], str] | None = None,
    agent: str | None = None,
) -> BrainstormBundle:
    if not workspace.exists():
        raise SystemExit(f"workspace missing: {workspace}")
    if answers is None:
        answers = run_interview(ask)
    if not answers.get("major"):
        raise SystemExit("전공 교과(major)는 필수입니다.")
    bundle = build_bundle(answers)
    if agent:
        _augment_with_agent(workspace, agent, bundle)
    write_ideas(workspace, bundle)
    return bundle


def _augment_with_agent(workspace: Path, agent: str, bundle: BrainstormBundle) -> None:
    """Best-effort: run a live agent to enrich trend research. Never fails hard."""
    try:
        from rch import agents as agents_mod
    except ImportError:
        return
    status = agents_mod.check_agent(agent)
    if not status.installed or status.login_status == agents_mod.STATUS_UNAUTHENTICATED:
        return
    prompt = (
        f"전공 교과 '{bundle.answers.get('major')}' 관련 최신 한국 교육 트렌드 3가지와 "
        f"연구대회에 적합한 수업혁신 연구 주제를 간단히 제안해줘. 사실만."
    )
    prompt_dir = workspace / "prompts" / agent
    prompt_dir.mkdir(parents=True, exist_ok=True)
    lane_file = prompt_dir / "brainstorm.md"
    lane_file.write_text(prompt, encoding="utf-8")
    try:
        result = agents_mod.run_agent_on_lane(workspace, agent, "brainstorm")
    except (SystemExit, OSError):
        return
    bundle.agent_augmented = bool(result.ok)
