# AGENTS.md — 연구대회 보고서 하네스 오케스트레이션 지침

이 파일은 **모든 에이전트 앱(Codex, Claude Code, Antigravity, Gemini 등)** 공용 지침이다. 이 저장소가 설치된 작업공간에서 "연구보고서 만들어줘" 같은 요청을 받으면 아래 절차를 따른다.

Claude Code는 `.claude/skills/report-orchestrator/`와 `.claude/agents/`를 자동 인식한다. Codex/Antigravity/Gemini는 이 `AGENTS.md`를 진입점으로 삼는다.

## 이 저장소는 무엇인가

여러 종류의 연구대회 보고서를 만드는 하이브리드 하네스다.

- **`rch` (파이썬 CLI)** = 결정적 작업만. 설문 통계, HWPX 렌더, 검증, 개인정보 스캔, 골격 생성. **숫자를 만들지 않는다.**
- **에이전트 (당신, LLM)** = 실제 글쓰기·종합·비평. 각 lane의 산출물을 **진짜 내용**으로 채운다. **숫자를 지어내지 않는다**(설문 수치는 rch 분석 결과만 인용).

순수 파이썬은 placeholder 골격만 만든다. 실제 보고서 문장은 반드시 에이전트가 쓴다.

## 준비

`rch`가 설치돼 있어야 한다(`pip install -e .`). 명령은 `rch ...` 또는 `PYTHONPATH=src python3 -m rch.cli ...`.
MCP로 붙었다면 같은 기능이 `init/brainstorm/import_survey/draft/build_hwpx/render_check` 등 도구로 노출된다(`docs/mcp.md`).

## 6단계 파이프라인

### Phase 0 — 인터뷰·대회 세팅
사용자에게 대화로 물어본다(파일 요구 금지): 참가 대회명, 전공 교과, 학교급/학년, 학급 상황, 관심 트렌드, 활용 도구, 목표 역량, 제약.
- 대회 양식·공문·심사표 파일 경로가 있으면 `rch import-rules <ws> <files...>`.
- 답을 플래그로 바로 전달: `rch brainstorm <ws> --competition-name "..." --major ... --interests ... --competency ...` → `input/ideas/`에 주제·제목 생성(2022 개정 핵심역량 연계).

### Phase 1 — 자료 분석 (결정적, rch)
- 설문: `rch import-survey <ws> <file>` · 사진: `rch import-photos <ws>` · 레퍼런스: `rch mine-references <ws>` · 배경: `rch research-background <ws>`.
- 자료가 없으면 지어내지 말고 placeholder로 두고, 무엇을 넣으면 품질이 오르는지 사용자에게 안내.

### Phase 2 — 실제 집필 (에이전트 역할 수행)
`rch lane <ws> <lane> agent`로 lane 폴더를 만들고, 각 lane 역할을 수행해 `lanes/<lane>/agent/`에 계약 파일 4종(`lane-output.md`, `lane-output.json`, `claim-ledger.json`, `verdict.json`)을 **진짜 내용**으로 작성한다.
- 서브에이전트 스폰이 되는 앱(Claude Code)은 `.claude/agents/`의 전문 에이전트에 위임한다.
- 서브에이전트가 없는 앱(Codex/Antigravity)은 아래 역할을 **순서대로 직접 수행**한다.
- 의존성: `survey-analyst`·`evidence-curator`·`reference-miner`(병렬 가능) → `draft-writer` → `table-layout` → `summary-sheet`/`toc-builder`/`appendix-builder`.

### Phase 3 — 비평·검증 루프
1. `critic` 역할로 심사자 관점 검토 → `lanes/critic/agent/machine-feedback.json` 작성.
2. `rch check <ws>` → `rch revise-loop <ws>`로 수정 백로그 통합.
3. 지적사항을 해당 lane에서 고치고 `rch check <ws> --final`이 통과할 때까지 반복(최대 3~4회).

### Phase 4 — 조립·렌더
`rch assemble <ws>` → `rch check <ws> --final`(통과 필수) → `rch build-hwpx <ws>` → `rch render-check <ws>`.
완료 시 `output/report.hwpx`와 남은 확인사항을 제시하고, "한컴오피스에서 열어 최종 확인"을 안내한다.

## 에이전트(lane) 역할

각 역할의 상세 지침은 `.claude/agents/<이름>.md`에 있다. 서브에이전트가 없는 앱은 그 파일을 읽고 해당 역할을 직접 수행한다.

| 역할 | 하는 일 | 산출 위치 |
| --- | --- | --- |
| `brainstorm` | 주제·제목·수업모형·실천과제 프레임 확정(2022 핵심역량 연계) | `lanes/brainstorm/agent/` |
| `reference-miner` | 레퍼런스 구조(목차·표·부록 패턴)만 추출·적용 | `lanes/reference-miner/agent/` |
| `survey-analyst` | rch 설문 분석 수치를 해석·서술(숫자 안 만듦) | `lanes/survey-analyzer/agent/` |
| `evidence-curator` | 주장↔증거 연결, claim 상태 확정 | `lanes/evidence-curator/agent/` |
| `draft-writer` | I~V장 본문 집필(표 중심·최종 진술형) | `lanes/draft-writer/agent/` |
| `table-layout` | 표·카드 중심 재편, 25쪽 압축 | `lanes/table-layout/agent/` |
| `summary-sheet` | 요약서 작성 | `lanes/summary-sheet/agent/` |
| `toc-builder` | 목차·페이지·제목 일관성 | `lanes/toc-builder/agent/` |
| `appendix-builder` | 과정안·루브릭·활동지·설문지·산출물 부록 | `lanes/appendix-builder/agent/` |
| `critic` | 심사자 관점 비평 → machine-feedback.json | `lanes/critic/agent/` |
| `finalizer` | 정합화·HWPX 조립·렌더 검증 지휘 | `lanes/finalizer/agent/` |

## 안전 규칙 (모든 역할 공통·강제)

- 증거 없는 설문 수치·학생 발화·수업 결과·확산 실적을 만들지 않는다. 불확실하면 `placeholder` claim.
- 설문 수치는 `input/surveys/analysis/`의 rch 분석 결과에서만 인용한다.
- `unreviewed`/`high` 위험 사진은 본문·부록에 넣지 않는다.
- 레퍼런스 문장·표 내용을 복사하지 않는다(구조만 참고).
- 최종 본문에 예정/추후/초안/미정/TODO 금지.
- 여러 에이전트가 같은 HWPX를 동시에 수정하지 않는다.
- 구조 통과(render-check)와 Hancom 실제 표시를 혼동하지 않는다 — 마지막은 사람이 한컴에서 확인.

## 사용량 참고

- LLM 작업(집필·추론)은 **당신을 구동하는 런타임의 사용량**을 쓴다(Codex→Codex, Antigravity→Antigravity, Claude Code→Claude).
- `rch`의 결정적 명령(통계·렌더·검증)과 `research-background`(공개 API)는 **AI 사용량을 쓰지 않는다.**
- `rch agents run` / `run-lanes --execute`만이 **다른** 에이전트 CLI를 불러내 그쪽 사용량을 쓴다. 교차 호출을 원치 않으면 이 명령을 쓰지 않는다.
