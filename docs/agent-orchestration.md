# 에이전트 우선 오케스트레이션

이 하네스는 **에이전트 우선(agent-first)** 이다. 판단·분석·집필은 전부 에이전트가 하고, 파이썬(`rch`)은 LLM이 오히려 부정확한 **세 가지에만** 쓴다. 실행하는 앱(Claude Code / Antigravity / Codex)이 자기 서브에이전트/병렬 방식으로 돌린다.

## 파이썬 경계 (딱 3가지)

| `rch`가 하는 일 | 이유 |
| --- | --- |
| `import-survey` — 설문 통계(평균·효과크기·p값) | LLM은 산술에서 틀린다 |
| `build-hwpx` — HWPX(OWPML zip) 생성 | LLM은 유효 바이너리를 못 만든다 |
| `assemble`/`check --final`/`render-check` — 조립·검증 게이트 | 결정적 규칙 검사 |

(+ `init` 폴더 골격, `import-rules` 양식 복사)

**그 외 전부 에이전트.** 레퍼런스 구조 분석, insane 리서치, 브레인스토밍, 사진 개인정보, 본문 집필, 표 편집, 요약·목차·부록, 비평, 최종화. 과거 파이썬 콘텐츠 명령(`brainstorm/mine-references/research-background/draft/import-photos`)은 정확도가 낮아 **더 이상 쓰지 않는다**(에이전트가 대체).

## 구성

```
AGENTS.md                              # 앱 공용 진입점(Codex/AGY/Gemini)
GEMINI.md                              # AGENTS.md 포인터
.claude/
  skills/report-orchestrator/SKILL.md  # Claude Code 진입점
  agents/                              # 13개 전문 서브에이전트
    brainstorm · reference-miner · background-researcher · photo-curator
    survey-analyst · evidence-curator · draft-writer · table-layout
    summary-sheet · toc-builder · appendix-builder · critic · finalizer
```

## 런타임 적응

| 앱 | 서브에이전트 실행 | 진입점 |
| --- | --- | --- |
| Claude Code | `.claude/agents/`를 Task로 병렬 스폰 | `.claude/skills/report-orchestrator/` |
| Antigravity | AGY 에이전트 매니저로 스폰 | `AGENTS.md` + MCP `rch-mcp` |
| Codex | 병렬 태스크로 역할 분배(없으면 순차) | `AGENTS.md` |

역할 정의(`.claude/agents/<역할>.md`)는 세 앱이 공유한다.

## 파이프라인

인터뷰 → `brainstorm` → **[병렬]** `reference-miner`·`background-researcher`·`photo-curator`·`evidence-curator`·`survey-analyst`(+`rch import-survey`) → `draft-writer` → `table-layout`→`summary-sheet`/`toc-builder`/`appendix-builder` → `critic`+`rch check`/`revise-loop` → `finalizer`+`rch assemble`/`build-hwpx`/`render-check`.

## 안전

증거 없는 수치·발화·성과·인용 금지(→placeholder), 설문 수치는 `rch import-survey` 결과만, 위험 사진 배제, 레퍼런스·웹 복사 금지, 최종 금지어 없음, HWPX 조립 1회. `rch check --final`이 최종 게이트. 구조 통과 ≠ Hancom 실제 표시(사람이 한컴 확인).
