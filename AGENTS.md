# AGENTS.md — 에이전트 우선 연구보고서 하네스

이 저장소는 **에이전트 우선(agent-first)** 하네스다. 판단·분석·집필은 전부 에이전트가 하고, 파이썬(`rch`)은 LLM이 오히려 부정확한 **세 가지에만** 쓴다.

이 파일은 모든 에이전트 앱(Claude Code, Antigravity, Codex, Gemini) 공용 진입점이다. 작업공간에서 "연구보고서 만들어줘" 요청을 받으면 아래를 따른다.

## 파이썬은 딱 3가지만 (그 외 전부 에이전트)

| 파이썬(`rch`)이 하는 일 | 이유 |
| --- | --- |
| `rch import-survey` — 설문 통계(평균·효과크기·t검정 p값) | LLM은 산술에서 틀린다. 파이썬이 정확. |
| `rch build-hwpx` — HWPX(OWPML zip) 생성 | LLM은 유효한 바이너리 문서를 못 만든다. |
| `rch assemble` / `check --final` / `render-check` — 조립·검증 게이트 | 결정적 규칙 검사. |

부수적으로 `rch init`(폴더 골격), `rch import-rules`(양식 파일 복사)만 더 쓴다.

**그 외 — 레퍼런스 구조 분석, insane 리서치(배경·선행연구), 브레인스토밍, 사진 개인정보, 본문 집필, 표 편집, 요약·목차·부록, 비평, 최종화 — 는 전부 에이전트가 한다.** 과거 파이썬 명령(`rch brainstorm/mine-references/research-background/draft/import-photos`)은 정확도가 낮아 **더 이상 콘텐츠 생성에 쓰지 않는다**(에이전트가 대체).

## 런타임 적응: 실행하는 앱이 자기 서브에이전트로 돌린다

- **Claude Code** — `.claude/agents/`의 서브에이전트를 Task로 스폰한다. 독립 lane은 한 번에 여러 Task로 **병렬** 실행.
- **Antigravity (AGY)** — AGY의 에이전트 매니저로 서브에이전트를 켠다. 각 역할 브리핑은 `.claude/agents/<역할>.md`.
- **Codex** — Codex의 병렬 태스크로 역할을 분배한다. 병렬이 없으면 아래 의존성 순서대로 순차 수행.

어느 앱이든 역할 정의는 `.claude/agents/<역할>.md` 하나를 공유한다.

## 파이프라인 (의존성 = 병렬 그룹)

### Phase 0 — 인터뷰·주제 (에이전트)
대화로 물어본다(파일 요구 금지): 참가 대회명, 전공 교과, 학교급/학년, 학급 상황, 관심 트렌드, 활용 도구, 목표 역량, 제약. 양식 파일 경로 있으면 `rch import-rules`.
→ **`brainstorm` 에이전트**가 주제·제목·수업모형·실천과제를 확정(2022 개정 6대 핵심역량 중 하나 이상 반드시 연계). `input/ideas/`에 기록.

### Phase 1 — 분석·리서치 (병렬)
아래는 서로 독립이라 **동시에** 돌린다:
- **`reference-miner`** — 우수 보고서 원본을 직접 읽고 목차·표·부록 구조 설계.
- **`background-researcher`** — insane 리서치로 이론적 배경·선행연구 조사(공개 학술·웹, 인용 날조 금지).
- **`photo-curator`** — 사진 개인정보 실제 검토·분류.
- **`evidence-curator`** — 주장↔증거 연결, claim 상태.
- 설문: 오케스트레이터가 먼저 **`rch import-survey <ws> <csv>`**(파이썬 통계) 실행 → **`survey-analyst`** 에이전트가 그 수치를 해석·서술(숫자 안 만듦).

### Phase 2 — 본문 집필 (에이전트)
**`draft-writer`** 가 Phase 1 산출물을 모두 읽고 I~V장 본문을 집필(표 중심·최종 진술형). 설문 수치는 `input/surveys/analysis/`에서만 인용.

### Phase 3 — 편집·부속 (draft 이후, 일부 병렬)
**`table-layout`** → 그 뒤 **`summary-sheet`**·**`toc-builder`**·**`appendix-builder`**(병렬).

### Phase 4 — 비평·검증 루프
**`critic`** 가 심사자 관점 검토 → `lanes/critic/agent/machine-feedback.json`. 이어서 `rch check <ws>` → `rch revise-loop <ws>`. 지적사항을 해당 에이전트에 다시 위임해 고친다. `rch check <ws> --final` 통과까지 반복(최대 3~4회).

### Phase 5 — 조립·렌더
**`finalizer`** 지휘로 `rch assemble` → `rch check --final`(통과 필수) → `rch build-hwpx` → `rch render-check`. 완료 시 `output/report.hwpx`와 남은 확인사항 제시, "한컴에서 최종 확인" 안내.

## 에이전트 역할 (13)

`brainstorm`, `reference-miner`, `background-researcher`, `photo-curator`, `survey-analyst`, `evidence-curator`, `draft-writer`, `table-layout`, `summary-sheet`, `toc-builder`, `appendix-builder`, `critic`, `finalizer`. 각 에이전트는 `lanes/<lane>/agent/`에 계약 파일 4종(`lane-output.md`, `lane-output.json`, `claim-ledger.json`, `verdict.json`)을 **진짜 내용**으로 채운다.

## 안전 규칙 (전 역할 강제)

- 증거 없는 설문 수치·학생 발화·수업 결과·확산 실적·인용을 **지어내지 않는다.** 불확실하면 `placeholder`.
- 설문 수치는 `rch import-survey`가 낸 `input/surveys/analysis/` 값만 인용.
- `unreviewed`/`high` 위험 사진은 본문·부록에 넣지 않는다.
- 레퍼런스·웹 문장을 복사하지 않는다(구조·근거 후보만).
- 최종 본문에 예정/추후/초안/미정/TODO 금지.
- HWPX 조립은 finalizer 한 번만. 구조 통과(render-check) ≠ Hancom 실제 표시(사람이 한컴에서 확인).

## 사용량

LLM 작업은 **구동 런타임 사용량**만 쓴다(AGY→AGY, Codex→Codex, Claude Code→Claude). `rch`의 통계·렌더·검증은 AI 사용량 0. `rch agents run`/`run-lanes --execute`만 다른 CLI를 교차 호출한다(에이전트 우선 모드에서는 쓰지 않는다).
