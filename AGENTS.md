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

**`rch go`(및 MCP `go`)는 절대 호출 금지** — placeholder 표 중심의 레거시 스켈레톤 자동화라서 완성 보고서가 아니라 골격이 나온다. 완성 보고서는 반드시 deep-interview → 계획 승인 → autopilot 루프로 만든다. 산출물이 이상하면 `rch diagnose <ws>`로 원인 신호를 먼저 확인한다.

## 런타임 적응: 실행하는 앱이 자기 서브에이전트로 돌린다

- **Claude Code** — `.claude/agents/`의 서브에이전트를 Task로 스폰한다. 독립 lane은 한 번에 여러 Task로 **병렬** 실행.
- **Antigravity (AGY)** — AGY의 에이전트 매니저로 서브에이전트를 켠다. 각 역할 브리핑은 `.claude/agents/<역할>.md`.
- **Codex** — Codex의 병렬 태스크로 역할을 분배한다. 병렬이 없으면 아래 의존성 순서대로 순차 수행.

어느 앱이든 역할 정의는 `.claude/agents/<역할>.md` 하나를 공유한다.

## 파이프라인 (의존성 = 병렬 그룹)

### Phase 0 — 대화형 인터뷰 (deep-interview, 필수 선행)
사용자가 정보를 미리 다 입력하게 하지 않는다. **한 번에 하나씩** 대화로 물어보며 함께 구체화한다(가재코드 deep-interview 방식). 순서: 참가 연구대회 → 대상 학급/학생 → 전공 교과 → 연구 주제 → 제목 → 목표 역량·도구·제약 → 보유 자료.
- 선택지가 있는 질문(대회 종류, 주제 후보, 제목 후보)은 **승인창/선택 UI**로 제시한다. Claude Code는 `AskUserQuestion` 도구, 그 UI가 없는 앱(Codex/AGY)은 선택지를 나열해 한 턴씩 묻는다.
- **연구 주제가 없으면** `brainstorm` 에이전트가 전공·트렌드·2022 핵심역량 기반 **주제 후보 3~4개를 제안**하고, 사용자가 고르거나 수정하게 한다. 제목도 후보를 제시해 확정. 주제·제목은 2022 개정 6대 핵심역량 중 하나 이상과 반드시 연계.
- **제목·수업 모형은 1등급 작명 공식으로 짓는다**(상세: `.claude/agents/brainstorm.md`): ① 독창적 영문 약어 프로젝트명(각 글자=수업 단계, 예: L.E.A.P./W.A.R.M./SPIN) ② 감성 캐치프레이즈·언어유희(예: 내.일.을 잡아, 어_깨_동_무) ③ 방법론(PBL·SEL)+목표 역량(심미적 감성·소통) 명시. 후보는 약어형 3 + 언어유희형 2.
- 양식 파일 경로가 있으면 `rch import-rules`. 확정 사항은 `input/ideas/`·`input/rules/competition-profile.json`에 기록.
- 인터뷰 후 **보고서 계획을 요약해 승인**을 받는다(ralplan). 승인 전에는 Phase 1 이하를 시작하지 않는다.
- **승인되면 `input/rules/competition-profile.json`에 `"plan_approved": true`를 기록하고 즉시 아래 autopilot 루프를 시작한다.** 이 승인이 마지막 질문이다 — 이후 단계에서 다시 허락을 구하지 않는다.
상세 절차는 `.claude/skills/deep-interview/SKILL.md`.

### Phase 1 — 분석·리서치 (병렬)
아래는 서로 독립이라 **동시에** 돌린다:
- **`reference-miner`** — 우수 보고서 원본을 직접 읽고 목차·표·부록 구조 설계.
- **`background-researcher`** — insane 리서치로 이론적 배경·선행연구 조사(공개 학술·웹, 인용 날조 금지).
- **`photo-curator`** — 사진 개인정보 실제 검토·분류.
- **`evidence-curator`** — 주장↔증거 연결, claim 상태.
- 설문: 실제 CSV가 있으면 **`rch import-survey <ws> <csv>`**(파이썬 통계) 실행 → **`survey-analyst`** 가 그 수치를 해석. **실제 설문이 없으면** `survey-analyst`가 "바라는 결과"에 근거한 **예상 설문값(가상)** 을 만들어 보고서를 완성하고, 실제값 교체용 CSV 템플릿을 남긴다.

### Phase 2 — 본문 집필 (에이전트)
**`draft-writer`** 가 Phase 1 산출물을 모두 읽고 I~V장 본문을 집필(표 중심·최종 진술형). 설문 수치는 `input/surveys/analysis/`에서만 인용.

### Phase 3 — 편집·부속 (draft 이후, 일부 병렬)
**`table-layout`** → 그 뒤 **`summary-sheet`**·**`toc-builder`**·**`appendix-builder`**·**`icon-artist`**(병렬). icon-artist는 문맥 맞는 아이콘 시스템을 설계하고 `rch render-icons`로 실제 PNG를 생성, 글리프 사용 규칙을 배포한다.

### Phase 4 — 비평·검증 루프
**`critic`** 가 심사자 관점 검토 → `lanes/critic/agent/machine-feedback.json`. 이어서 `rch check <ws>` → `rch revise-loop <ws>`. 지적사항을 해당 에이전트에 다시 위임해 고친다. final 게이트 통과까지 반복(최대 3~4회). final 게이트는 두 모드다:
- 실제 자료만으로 완성: `rch check <ws> --final`
- 예상값(가상) 포함 완성본: `rch check <ws> --final --allow-expected` — 라벨링된 `expected` claim만 허용되고, 교체 목록이 `output/expected-claims.md`에 남는다. 라벨 없는 `expected`와 `placeholder`는 여전히 차단된다.

### Phase 5 — 조립·렌더
**`finalizer`** 지휘로 `rch assemble` → final 게이트(위 두 모드 중 해당하는 것, 통과 필수) → 렌더(엔진 우선순위: 대회 양식 kordoc fill → kordoc 프리셋 → `rch build-hwpx`) → `rch render-check`.

### Phase 6 — 디자인 마무리 (hwpx-designer)
구조 검증을 통과한 `report.hwpx`를 **`hwpx-designer`** 가 마무리한다: `rch hwpx-unpack` → XML 편집(표지·아이콘 PNG 배치·카드형 요약) → `rch hwpx-pack`(자동 render-check). 반복본은 `output/iterations/report_v<NN>.hwpx`. 완료 시 최종본과 남은 확인사항 제시(예상값 포함이면 `output/expected-claims.md` 교체 목록 안내), "한컴에서 최종 확인" 안내.

## 원패스 원칙 (반복 최소화)
디자인을 뒤로 미루지 않는다 — **집필 단계에서 이미 완성형에 가깝게** 쓴다: draft-writer·table-layout이 `:::box`·글리프·icon-artist의 아이콘 규칙을 본문에 직접 넣고, 장 제목(H1)은 렌더러가 자동으로 도비라 바로 만든다. 분량도 draft 단계에서 규정 상한까지 채운다(`render-check --min-pages`로 검사). 그래서 Phase 6의 hwpx-designer는 긴 반복이 아니라 **표지·아이콘 배치 등 1~3회 마무리 폴리시**가 기본이다(문제가 있을 때만 추가 반복).

## 시작 전 점검 (필수)
작업을 시작하기 전에 **하네스 저장소를 최신으로 당긴다**: `git -C <하네스 경로> pull`. 구버전 렌더러로 빌드하면 표 크기 정보가 빠져 한컴에서 표가 붕괴된다. 빌드 후에는 `rch diagnose <ws>`로 구버전·골격 신호를 확인한다.

## Autopilot 루프 (계획 승인 후 자동 발동 — 필수)

계획 승인(Phase 0) 이후에는 **질문이나 검토 요청 없이 Phase 1→5를 연속 실행해 `output/report.hwpx`까지 완주**한다. 각 Phase 사이에 "계속할까요?"를 묻지 않는다. 루프 드라이버는 결정적 상태 머신 **`rch next <ws>`** 다:

```
반복:
  rch next <ws>            # 다음 작업을 JSON으로 판정 (output/next-plan.json)
  ├─ done=true            → 종료. 결과 보고(한컴 확인 안내 + expected-claims.md 교체 목록)
  ├─ needs_user가 있으면   → 멈추고 사용자에게 그 항목만 질문
  └─ 아니면 actions 실행    → kind=run은 rch 명령 실행, kind=delegate는 해당 lane을
                             role의 서브에이전트로 위임(parallel=true면 동시에) → 다시 rch next
```

- **멈추는 조건은 딱 세 가지**: ① `needs_user`(계획 미승인, verdict `blocked` — 동의·개인정보·자료 확보 등 사용자만 풀 수 있는 문제), ② 개인정보/동의 위험 발견, ③ 같은 phase가 3회 반복 실패(원인과 함께 사용자 보고).
- 그 외 품질 문제(critic 지적, check 오류, render 실패)는 사용자에게 묻지 말고 **해당 lane 재위임으로 스스로 해소**한다 — 그것이 Phase 4 루프다.
- 서브에이전트가 판단이 어려운 문제를 만나면 verdict를 `blocked`+이유로 남긴다. autopilot이 그걸 `needs_user`로 승격해 사용자에게 묻는다. 사소한 선택은 blocked로 만들지 말고 보수적 기본값으로 스스로 결정한 뒤 lane-output에 기록한다.
- `rch next`는 예상값(가상) claim이 있으면 final 게이트를 자동으로 `--allow-expected` 모드로 판정한다.

## 에이전트 역할 (15)

`brainstorm`, `reference-miner`, `background-researcher`, `photo-curator`, `survey-analyst`, `evidence-curator`, `draft-writer`, `table-layout`, `summary-sheet`, `toc-builder`, `appendix-builder`, `icon-artist`(icon-visual lane — 아이콘 시스템 설계 + `rch render-icons`), `critic`, `finalizer`, `hwpx-designer`(디자인 마무리 — lane 없음, finalizer lane evidence에 기록). 각 lane 에이전트는 `lanes/<lane>/agent/`에 계약 파일 4종(`lane-output.md`, `lane-output.json`, `claim-ledger.json`, `verdict.json`)을 **진짜 내용**으로 채운다.

## 완성 원칙: 자료가 없어도 예상값으로 완성한다

설문·사진이 없다고 멈추거나 대괄호 빈칸을 남기지 않는다. **"바라는 결과"에 근거한 예상값(가상)으로 보고서를 완성**하고, 나중에 실제값으로 교체할 수 있게 남긴다. 단 예상값은 아래 규칙을 지킨다.

## 안전 규칙 (전 역할 강제)

- **실제 조사 결과가 없는 수치·발화·인용은 지어내되 반드시 "예상값(가상)"으로 명확히 라벨링하고 `status: expected`로 둔다.** 절대 `real`/`derived`로 표시하거나 "측정되었다"처럼 실제인 것처럼 쓰지 않는다. 예상값은 교육적으로 보수적이어야 한다(과장 금지). `expected` claim은 text/notes에 "예상"/"가상" 라벨이 없으면 `rch check`가 거부한다. (`placeholder`는 아직 채우지 못한 초안 구멍 전용 — final 어느 모드에서도 통과 불가.)
- 실제 설문 수치는 `rch import-survey`가 낸 `input/surveys/analysis/` 값만 `derived`로 인용. 실제값이 들어오면 예상값을 교체한다.
- `unreviewed`/`high` 위험 사진은 본문·부록에 넣지 않는다. 사진이 없으면 "사진첨부필요" 자리표시로 진행한다.
- 레퍼런스·웹 문장을 복사하지 않는다(구조·근거 후보만). 존재하지 않는 논문·저자·DOI를 만들지 않는다.
- 최종 본문에 예정/추후/초안/미정/TODO 금지(단 "예상값(가상)" 라벨은 draft에서 허용).
- HWPX 조립은 finalizer 한 번만. **zip을 손으로 만들지 않는다** — 최초 생성은 `rch build-hwpx`(또는 kordoc), 이후 디자인 편집은 `hwpx-designer`가 `rch hwpx-unpack`→XML 편집→`rch hwpx-pack`(자동 검증) 루프 안에서만 한다. pack의 render-check 실패 = 그 편집 폐기. 구조 통과 ≠ Hancom 실제 표시(사람이 한컴에서 확인). 렌더 품질은 finalizer·hwpx-designer가 강하게 책임진다.

## 사용량

LLM 작업은 **구동 런타임 사용량**만 쓴다(AGY→AGY, Codex→Codex, Claude Code→Claude). 서브에이전트도 반드시 구동 런타임의 방식(Claude Code Task / AGY 에이전트 매니저 / Codex 병렬 태스크)으로만 스폰한다. `rch`의 통계·렌더·검증은 AI 사용량 0.

`rch agents run`/`run-lanes --execute`는 다른 CLI를 교차 호출하는 명령인데, **하네스가 구동 런타임을 감지하면 다른 CLI 호출을 기본 차단**한다(예: Claude Code 안에서 `rch agents run <ws> codex` → 거부). 정말 필요하면 사용자가 `RCH_ALLOW_CROSS_AGENT=1`로 명시 허용해야 한다. 에이전트는 이 우회를 스스로 켜지 않는다.
