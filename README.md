# 연구대회 보고서 제작 하네스

여러 종류의 연구대회 보고서를 AI 에이전트와 함께 만들기 위한 로컬 우선 하네스입니다.

목표는 대회 공문·보고서 양식·심사표, 아이디어, 사진, 설문결과, 레퍼런스 보고서, 증빙 자료를 한 작업공간에 넣고, lane별 지침을 따라 보고서 본문·요약서·목차·부록·최종화 체크리스트까지 통제된 markdown bundle로 만드는 것입니다.

## 현재 하네스가 하는 일

- 새 연구대회 작업공간 생성
- 아이디어, 배경연구, 공문·양식·심사표, 레퍼런스, 증빙, 사진, 설문, raw_private 입력 폴더 생성
- 참가 대회명과 대회 프로필 저장
- 에이전트 앱에 첨부한 대회 양식 파일을 `input/rules/`에 저장
- 14개 lane별 한국어 작업 지침 생성
- 각 lane의 산출물 계약 고정
- claim-ledger로 허위 주장, placeholder, 증거 누락 차단
- lane output을 모아 아래 최종 bundle 생성
  - `output/report-draft.md`
  - `output/summary-sheet.md`
  - `output/toc.md`
  - `output/appendix.md`
  - `output/finalization-checklist.md`
  - `output/bundle-manifest.json`
- `check --final`로 14개 production lane 완료, final bundle 누락, missing source lane, 금지 문구를 검사
- final evidence 경로가 workspace 내부이고 `input/raw_private/`를 직접 쓰지 않는지 검사
- critic의 `rubric-score.json`으로 심사표 기준 점수화와 85% 이상 final target을 검사

## 생성 엔진 · 렌더 엔진 · 품질 루프

이제 하네스만으로 자료 → 분석 → 초안 → HWPX → 검증 → 수정까지 돌 수 있습니다.

| 명령 | 하는 일 | 산출물 |
| --- | --- | --- |
| `rch agent-harness <ws>` | Codex/Claude/AGY가 대회를 지휘하도록 현재 입력·누락자료·lane 순서·검증 gate·금지 규칙을 conductor pack으로 생성 | `output/agent-harness.json`, `output/agent-harness.md`, `prompts/conductor/agent-harness.md` |
| `rch go <ws> --skeleton` | 레거시 골격 생성. 완성 보고서용 아님. 기본 호출은 거부 | placeholder 중심 skeleton + 보강표 |
| `rch import-rules <ws> <files...>` | 대회 공문·심사표·보고서 양식을 `input/rules/`에 복사하고 manifest 생성 | `input/rules/rules-manifest.json` |
| `rch brainstorm <ws>` | 대회명 → 분야/교과 인터뷰 → 연구 동향 리서치 → 연구 주제·제목 자동 생성. 사람이 ideas 파일을 직접 쓰지 않음 | `input/ideas/` + `input/rules/competition-profile.json` |
| `rch research-background <ws>` | insane-search 방식의 public-route scheduler로 이론적 배경·선행연구 후보 수집(OpenAlex/CrossRef/arXiv/Jina route → fallback) | `input/research/` + reference-miner lane |
| `rch import-survey <ws> <file>` | 사전·사후 설문 CSV/TSV/XLSX 익명 분석(평균·변화량·Cohen's d·t검정 p값·자유응답 요약·소표본 한계) | `input/surveys/analysis/` |
| `rch import-photos <ws>` | 사진 매니페스트 + 개인정보 점검표(본문/요약/부록/제외 분류, 블러 지시) | `input/photos/analysis/` |
| `rch mine-references <ws>` | 레퍼런스 보고서에서 목차·표 밀도·부록 패턴 등 **구조만** 추출 | `input/references/analysis/` |
| `rch draft <ws>` | 분석 결과로 I~V장 본문·요약서·목차·부록 초안 생성(claim 태그 부착) | 쓰기 lane 4종 |
| `rch next <ws>` | **autopilot 드라이버**. 작업공간 상태를 보고 다음 작업(위임할 lane/실행할 명령)을 결정적으로 판정 | `output/next-plan.{json,md}` |
| `rch run-lanes <ws> <agent>` | lane별 프롬프트 번들 생성(외부 에이전트 배정용). `--execute` 시 로그인 확인 후 실제 호출 | `prompts/<agent>/` |
| `rch agents preflight <ws>` | Codex/Antigravity/Claude CLI 설치·로그인 자동 확인 | `output/agent-preflight.{json,md}` |
| `rch agents run <ws> <agent> --lanes ...` | 프롬프트를 에이전트 CLI로 실제 호출해 응답 수집 | `lanes/<lane>/<agent>/agent-response.md` |
| `rch render-icons <ws>` | icon-artist가 설계한 `icon-spec.json`을 실제 PNG 아이콘으로 렌더(의존성 0) | `input/icons/rendered/` |
| `rch build-hwpx <ws>` | `check --final` 통과 bundle만 HWPX로 렌더. `--engine kordoc`으로 한국형 보고서 프리셋 렌더(Node 18+) | `output/report.hwpx` |
| `rch render-check <ws>` | HWPX 구조·XML·페이지 추정·목차-본문 일치·표 무결성 검증. `--page-limit`(상한)·`--min-pages`(하한, 규정 분량 채움 검사) | `output/render-check.{json,md}` |
| `rch revise-loop <ws>` | critic·check·render-check 피드백을 우선순위 수정 백로그로 통합 | `output/revision-tasks.{json,md}` |
| `rch diagnose <ws>` | 보고서가 이상하게 나왔을 때 output 폴더를 검진(레거시 go 흔적·표 크기 누락·lane 미실행·placeholder 잔존) | `output/diagnose.{json,md}` |

에이전트 앱으로 장기 실행할 때 먼저 conductor pack을 만듭니다.

```bash
rch agent-harness 2026-competition --agent codex --agent claude --offline-research
```

`rch go`는 완성 보고서 경로가 아닙니다. `--skeleton`을 붙인 중간 골격 생성에서만 씁니다. 설문·사진이 없으면 placeholder 표를 만들 수 있지만 final gate와 `build-hwpx`가 기본 차단합니다.

- 설문 없음: `동일 문항 5문항 사전·사후 설문 필요` 표를 `input/surveys/analysis/survey-summary.md`와 본문 결과 섹션에 삽입
- 사진 없음: `사진첨부필요_01...` 배치표를 `input/photos/analysis/privacy-checklist.md`와 부록에 삽입
- 보강 목록: `output/missing-inputs.md`
- 최종 안전장치: placeholder claim과 `needs-work` verdict가 남아 `rch check --final` 통과는 막음

세부 단계 직접 실행:

```bash
rch init 2026-competition
rch import-rules 2026-competition ~/Downloads/보고서_양식.hwpx ~/Downloads/심사표.pdf
rch brainstorm 2026-competition            # 대회명 → 분야/교과 → 주제·제목 → input/ideas/ 자동 작성
rch research-background 2026-competition   # 이론적 배경·선행연구 후보 수집
rch agents preflight 2026-competition
# input/rules, input/references, input/surveys, input/photos, input/evidence 채우기 (ideas는 brainstorm이 채움)
rch import-survey 2026-competition input/surveys/pre-post.csv
rch import-photos 2026-competition
rch mine-references 2026-competition
rch draft 2026-competition
rch assemble 2026-competition
rch check 2026-competition --final
rch build-hwpx 2026-competition
rch render-check 2026-competition
rch revise-loop 2026-competition
```

각 명령은 `skills/` 아래 스킬 팩(`survey-analysis-skill` 등)으로 문서화되어 있습니다.

## 어디서 쓰든 작동: Codex · Claude Code · Antigravity

이 저장소는 **에이전트 우선(agent-first)** 하네스입니다. 판단·분석·집필은 전부 에이전트가 하고, 파이썬(`rch`)은 **LLM이 오히려 부정확한 세 가지에만** 씁니다.

| 파이썬(`rch`)이 하는 일 | 이유 |
| --- | --- |
| `import-survey` — 설문 통계(평균·효과크기·p값) | LLM은 산술에서 틀림 |
| `build-hwpx` — HWPX(OWPML zip) 생성 | LLM은 유효 바이너리를 못 만듦 |
| `assemble`/`check --final`/`render-check` — 조립·검증 게이트 | 결정적 규칙 검사 |

그 외 — 레퍼런스 구조 분석, insane 리서치(배경·선행연구), 브레인스토밍, 사진 개인정보, 본문 집필, 표 편집, 요약·목차·부록, 비평, 최종화 — 는 **전부 에이전트**가 합니다. (과거 파이썬 콘텐츠 명령 `brainstorm/mine-references/research-background/draft/import-photos`는 정확도가 낮아 콘텐츠 생성에 쓰지 않습니다.)

세 앱 모두에서 같은 오케스트레이션이 돌도록 진입점 파일을 제공합니다.

| 앱 | 자동 인식하는 진입점 | 한 번만 하는 셋업 |
| --- | --- | --- |
| **Claude Code** | `.claude/skills/report-orchestrator/` + `.claude/agents/` | 없음. 작업공간에서 `claude` 실행 |
| **Codex** | 루트 `AGENTS.md` | 없음. 작업공간에서 `codex` 실행 |
| **Antigravity** | `AGENTS.md` / `GEMINI.md` | MCP 서버 `rch-mcp` 등록(아래) + `AGENTS.md`를 규칙으로 지정 |

공통 셋업:

```bash
pip install -e ".[mcp]"     # rch + rch-mcp(MCP 서버) 설치
```

각 앱은 **자기 서브에이전트/병렬 방식**으로 역할을 돌립니다(역할 정의 `.claude/agents/<이름>.md`는 공유).
- **Claude Code**: `claude` 실행 → `report-orchestrator` 스킬이 트리거되어 `.claude/agents/`를 Task로 **병렬 스폰**.
- **Antigravity**: `AGENTS.md`/`GEMINI.md`를 규칙으로 지정 + MCP `rch-mcp` 등록 → AGY 에이전트 매니저로 서브에이전트 스폰.
- **Codex**: `codex` 실행 → 루트 `AGENTS.md`를 읽고 병렬 태스크로 역할 분배(없으면 순차). MCP는 `~/.codex/config.toml`에 `[mcp_servers.rch] command = "rch-mcp"`.

정보를 미리 다 적을 필요 없이, 그냥 이렇게 시작해도 됩니다:

```text
연구대회 보고서 만들어줘
```

그러면 하네스가 가재코드처럼 **대화형 인터뷰(`deep-interview`)** 로 이어집니다 — **한 번에 하나씩 승인창(질문 UI)** 을 띄워:
참가 연구대회 → 대상 학급/학생 → 전공 교과 → 연구 주제(없으면 에이전트가 **후보 3~4개 제안** → 선택) → 제목 후보 선택 → 역량·도구·제약 → 보유 자료. 확정 사항을 요약해 **계획 승인**을 받은 뒤에야 본문 생성을 시작합니다.

제목·수업 모형은 **1등급 수상작 작명 공식**으로 짓습니다: ① 독창적 영문 약어 프로젝트명(각 글자=수업 단계, 예: L.E.A.P., W.A.R.M., SPIN) ② 감성 캐치프레이즈·언어유희(예: 내.일.을 잡아, 어_깨_동_무) ③ 방법론(PBL·SEL)+목표 역량(심미적 감성·소통) 명시 — 후보는 약어형 3개+언어유희형 2개(상세: `.claude/agents/brainstorm.md`).

이미 정보가 있으면 한 줄로 넣어도 됩니다(인터뷰는 빠진 부분만 물어봄):

```text
교실수업개선 실천사례 연구대회, 음악, 중2, AI·에듀테크, 음악적 창의융합 역량 중심으로
연구보고서 만들어줘. 설문은 survey.csv, 사진은 photos/ 에 있어.
```

### 파이프라인 (의존성 = 병렬 그룹)

인터뷰 → `brainstorm` → **[병렬]** `reference-miner`·`background-researcher`·`photo-curator`·`evidence-curator`·`survey-analyst`(+`rch import-survey`) → `draft-writer` → `table-layout`→`summary-sheet`/`toc-builder`/`appendix-builder` → `critic`+`rch check`/`revise-loop` → `finalizer`+`rch assemble`/`build-hwpx`/`render-check`. 상세는 [`AGENTS.md`](AGENTS.md), [`docs/agent-orchestration.md`](docs/agent-orchestration.md).

### Autopilot: 계획 승인 후에는 질문 없이 완주

인터뷰에서 **계획 승인이 나면**(`competition-profile.json`의 `plan_approved: true`) 에이전트는 더 묻지 않고 `rch next <ws>` 루프로 Phase 1~5를 연속 실행해 `output/report.hwpx`까지 만듭니다.

```text
rch next <ws> → done?        → 종료 보고 (한컴 확인 + expected-claims.md 안내)
             → needs_user?  → 그 항목만 사용자에게 질문 (동의·개인정보·blocked verdict)
             → actions      → run(rch 명령) / delegate(서브에이전트, parallel이면 동시) → 다시 rch next
```

`rch next`는 lane verdict·산출물 존재·final 게이트를 결정적으로 검사해 다음 작업을 JSON으로 내놓는 상태 머신입니다(LLM 호출 없음, `output/next-plan.json`). 품질 문제(critic 지적·check 오류·render 실패)는 사용자에게 묻지 않고 해당 lane 재위임으로 해소하며, 멈추는 경우는 `needs_user`·개인정보 위험·같은 phase 3회 연속 실패뿐입니다.

### 에이전트별 사용법 (15종)

각 에이전트는 자기 lane의 계약 파일 4종(`lane-output.md`, `lane-output.json`, `claim-ledger.json`, `verdict.json`)을 **진짜 내용**으로 채웁니다. 상세 지침은 `.claude/agents/<이름>.md`.

| 에이전트 | 단계 | 하는 일 |
| --- | --- | --- |
| `brainstorm` | 0 | 주제·제목·수업모형·실천과제 확정(2022 핵심역량 연계) |
| `reference-miner` | 1(병렬) | 우수 보고서 **원본을 직접 읽고** 목차·표·부록 구조 설계 |
| `background-researcher` | 1(병렬) | **insane 리서치** — 이론적 배경·선행연구 조사(인용 날조 금지) |
| `photo-curator` | 1(병렬) | 사진 **실제 검토**로 개인정보 판정·배치 분류 |
| `survey-analyst` | 1(병렬) | `rch import-survey` 수치를 해석·서술(숫자 안 만듦) |
| `evidence-curator` | 1(병렬) | 주장↔증거 연결, claim 상태 확정 |
| `draft-writer` | 2(핵심) | I~V장 본문 집필(표 중심·최종 진술형) |
| `table-layout` | 3 | 표·카드 재편, 25쪽 압축 |
| `summary-sheet` | 3 | 요약서 |
| `toc-builder` | 3 | 목차·페이지·제목 일관성 |
| `appendix-builder` | 3 | 과정안·루브릭·활동지·부록 |
| `icon-artist` | 3 | 문맥 맞는 아이콘 시스템 설계 + `rch render-icons`로 PNG 생성 + 글리프 규칙 배포 |
| `critic` | 4 | 심사자 관점 비평 → `machine-feedback.json` |
| `finalizer` | 5 | 정합화·HWPX 조립·렌더 검증 지휘 |
| `hwpx-designer` | 6 | 검증된 HWPX에 수상작급 디자인(표지·도비라·색 박스·아이콘) 반복 적용 |

Claude Code는 이들을 서브에이전트로 자동 스폰(병렬), Antigravity는 AGY 에이전트 매니저, Codex는 병렬 태스크로 돌립니다. 병렬 스폰이 없으면 `AGENTS.md`의 의존성 순서대로 수행합니다.

### 사용량

LLM 작업(집필·추론)은 **구동하는 런타임의 사용량**만 씁니다(Antigravity→Antigravity, Codex→Codex, Claude Code→Claude). 서브에이전트도 구동 런타임의 방식으로만 스폰합니다. `rch`의 결정적 명령(통계·렌더·검증)과 `research-background`(공개 API)는 **AI 사용량을 쓰지 않습니다.**

`rch agents run`/`run-lanes --execute`는 다른 에이전트 CLI를 교차 호출하는 명령이지만, 하네스가 구동 런타임(Claude Code/Codex/Antigravity)을 감지하면 **다른 CLI 호출을 기본 차단**합니다. 정말 교차 호출하려면 `RCH_ALLOW_CROSS_AGENT=1`을 명시해야 하며, 런타임 감지를 바로잡으려면 `RCH_HOST_RUNTIME=claude|codex|antigravity|none`으로 지정할 수 있습니다.

## 시작: 브레인스토밍으로 주제·제목 자동 생성

하네스를 시작하면 사람이 `input/ideas/`에 파일을 직접 쓰지 않습니다. `rch brainstorm`이 참가 대회명 → 분야/교과 인터뷰 → 동향 리서치 → 주제·제목까지 만들어 넣습니다.

```bash
rch init 2026-competition
rch brainstorm 2026-competition                 # 대화형 인터뷰. 첫 질문은 참가 연구대회명
rch init 2026-competition --brainstorm          # init 직후 인터뷰까지 한 번에
rch brainstorm 2026-competition --answers answers.json   # 비대화형(자동화/재현)
rch brainstorm 2026-competition --competition-name "과학전람회"
rch brainstorm 2026-competition --agent claude  # 트렌드 리서치를 실제 에이전트로 보강
rch brainstorm 2026-competition --research-background  # 주제 선정 직후 배경연구까지 실행
```

인터뷰 항목: 참가 연구대회명, 전공/분야(필수), 학교급/학년, 상황, 관심 트렌드, 활용 도구, 목표 역량, 제약. 답변만 하면 하네스가 다음을 자동 작성합니다.

- `input/ideas/00-interview.md` — 인터뷰 기록
- `input/ideas/01-trend-research.md` — 전공 적합도로 정렬한 교육 트렌드 리서치
- `input/ideas/02-research-topics.md` — 점수 매긴 연구 주제 후보(추천 표시)
- `input/ideas/03-title-candidates.md` — 알파벳 약어형·한글 스토리형 제목 후보 5개
- `input/ideas/brainstorm.json` — 기계 판독용 번들
- `input/rules/competition-profile.json` — 참가 대회명·분야 프로필

## 대회 양식·공문·심사표 넣기

대회마다 양식과 규정이 다르므로, 파일을 먼저 `input/rules/`에 넣습니다.

```bash
rch import-rules 2026-competition ~/Downloads/공문.pdf ~/Downloads/보고서_양식.hwpx ~/Downloads/심사표.xlsx
```

에이전트 앱에서 첨부한 파일도 로컬 path만 알면 MCP로 저장할 수 있습니다.

```text
첨부한 공문, 심사표, 보고서 양식 파일을 rch import_rules로 input/rules에 저장하고, rch agent_harness와 rch next 루프로 완성 보고서까지 진행해줘.
```

저장 위치:

```text
input/rules/forms/      보고서 양식, 서식
input/rules/rubrics/    심사표, 평가표
input/rules/notices/    공문, 요강, 규정
input/rules/templates/  그 외 참고 양식
```

추천 제목은 `brainstorm` lane에도 자동 반영되어 이후 `rch draft`의 보고서 제목으로 이어집니다. 생성된 주제·제목은 `placeholder` claim으로 들어가며, 심사기준 대조와 최종 선택은 사람이 확정합니다.

## 배경지식·선행연구 리서치

`rch research-background`는 `insane-search` 방식에서 가져온 원칙을 보고서용 리서치에 적용합니다.

- 한 번의 fetch 성공으로 끝내지 않고 route log를 남깁니다.
- Phase 0: OpenAlex, CrossRef, arXiv 같은 공개 API를 먼저 씁니다.
- Phase 1: Jina public search reader route를 시도합니다.
- 실패하면 local curated fallback을 쓰되 `needs-work`로 표시합니다.
- 로그인·페이월·개인자료 접근은 하지 않습니다.
- 공개 웹 본문은 untrusted source material로 취급하고, 보고서에는 요약·근거 후보로만 반영합니다.

산출물:

```text
input/research/background-research.json
input/research/04-background-research.md
lanes/reference-miner/harness-background/
```

`rch draft`는 이 결과를 읽어 본문에 `II. 이론적 배경 및 선행연구` 섹션을 자동 삽입합니다. live public source가 있으면 `derived` claim으로, fallback뿐이면 `placeholder`로 남겨 final 반영을 막습니다.

비대화형 답변 파일 예시(`answers.json`):

```json
{"major":"과학","level":"중학교 2학년","class_context":"28명","interests":"AI, 탐구","tools":"AI 챗봇, 태블릿","competency":"탐구력","constraints":"총 12차시"}
```

## 에이전트 자동 호출 · 로그인 확인

하네스는 외부 에이전트 CLI(Codex, Antigravity, Claude)를 **실제로 실행**해 설치 여부와 **로그인 상태를 자동 확인**하고, lane 프롬프트를 에이전트에 직접 넘겨 응답을 수집합니다.

```bash
# 1) 초기 사전 점검: 설치 + 로그인 확인
rch agents preflight 2026-competition
rch agents preflight 2026-competition --agents codex claude --strict  # 미로그인 시 exit 1

# 2) 프롬프트 번들 생성 후 로그인 확인과 함께 실제 호출까지 한 번에
rch run-lanes 2026-competition codex --lanes survey-analyzer draft-writer --execute

# 3) 이미 만든 번들을 특정 에이전트로 실행
rch agents run 2026-competition claude --lanes critic
```

로그인 상태는 **실제 프로세스 종료 코드**로 판정합니다(꾸며내지 않음). 판정값: `authenticated` / `unauthenticated` / `not_installed` / `unknown`(확인 명령 미설정).

CLI마다 하위 명령이 달라 각 에이전트의 실행 명령을 환경변수로 조정할 수 있습니다(내장 기본값은 best-effort 추정치):

| 환경변수 | 뜻 | 예 |
| --- | --- | --- |
| `RCH_AGENT_<NAME>_BIN` | 실행 파일 경로/이름 | `RCH_AGENT_CODEX_BIN=/usr/local/bin/codex` |
| `RCH_AGENT_<NAME>_VERSION_ARGS` | 설치 확인 인자 | `--version` |
| `RCH_AGENT_<NAME>_AUTH_ARGS` | 로그인 확인 인자(종료코드 0=로그인) | `login status` |
| `RCH_AGENT_<NAME>_RUN_ARGS` | 프롬프트 전달 인자(`{prompt}`/`{prompt_file}` 치환) | `exec {prompt}` |

`<NAME>`은 `CODEX`, `CLAUDE`, `ANTIGRAVITY`. 기본 레지스트리는 `rch agents list`로 확인합니다.

에이전트가 남긴 응답(`agent-response.md`)은 자유 서술이므로, 에이전트는 이어서 lane 계약 파일(`lane-output.json`, `claim-ledger.json`, `verdict.json`)을 채워야 `check`/`assemble` 파이프라인에 반영됩니다.

## 여전히 사람이 확정하는 일

- 각 에이전트 CLI의 설치와 최초 로그인(하네스는 로그인 여부를 확인·차단하지만 로그인 자체는 사용자가 수행)
- 사진 픽셀의 얼굴·이름·학번 노출 최종 확인
- Hancom/HOP에서 실제로 열어 페이지 수·목차 번호·표 흐름·이미지 겹침 최종 확인
- 자유응답 인용의 학생 동의·익명화 확정

`build-hwpx`는 구조적으로 유효한 OWPML 컨테이너를 만들지만, 구조 통과가 Hancom 실제 표시를 보장하지는 않습니다. 렌더 품질의 최종 판정은 사람이 Hancom에서 확인합니다.

### 렌더 엔진 우선순위 (수상작 외형에 가깝게)

빌트인 렌더러는 구조 보장용입니다(제목 색·크기, 표 헤더 음영, 양쪽 정렬 정도의 기본 스타일). 1등급 수상작 같은 외형이 필요하면 finalizer가 순서대로 시도합니다:

1. **대회 공식 양식 채우기** — `input/rules/forms/*.hwpx`가 있고 [kordoc](https://github.com/chrisryugj/kordoc)이 설치돼 있으면 `npx -y kordoc fill 양식.hwpx -j values.json -o output/report.hwpx` (원본 서식 100% 유지)
2. **kordoc 보고서 프리셋** — `rch build-hwpx <ws> --engine kordoc` (내부에서 `npx -y kordoc generate ... --preset 보고서` 실행, `RCH_KORDOC_CMD`로 명령 조정)
3. **빌트인** — `rch build-hwpx <ws>` (의존성 없음, 항상 유효한 HWPX)

어느 경로든 `rch render-check`로 검증합니다.

### 디자인 반복 루프 (hwpx-designer)

구조 검증을 통과한 뒤에는 **`hwpx-designer` 에이전트**가 수상작 수준 디자인(표지, 장 도비라 바, 색 박스, 아이콘 글리프, 카드형 요약서)을 반복적으로 입힙니다:

```bash
rch hwpx-unpack <ws>    # output/report.hwpx → output/hwpx-src/ (XML 편집 가능)
# Contents/header.xml·section0.xml 편집 (에이전트)
rch hwpx-pack <ws>      # 재조립(mimetype 규칙 준수) + render-check 자동 실행
```

pack이 검증에 실패하면 그 편집은 폐기하고 더 작은 단위로 재시도합니다. 반복본은 `output/iterations/report_v<NN>.hwpx`로 쌓입니다. 본문 마크다운 단계에서도 `:::box 제목` ... `:::` 지시문으로 색 박스를, ▶ ◆ ■ 글리프로 아이콘 리듬을 쓸 수 있고, 장 제목(H1)은 자동으로 액센트 도비라 바로 렌더됩니다.

XLSX 분석에는 `openpyxl`이 필요합니다(`pip install .[xlsx]`). CSV/TSV는 추가 의존성 없이 동작합니다.

## 설치 없이 실행

```bash
cd research-competition-harness
PYTHONPATH=src python3 -m rch.cli init my-competition
PYTHONPATH=src python3 -m rch.cli bootstrap-lanes my-competition codex
PYTHONPATH=src python3 -m rch.cli check my-competition
```

설치형 CLI:

```bash
cd research-competition-harness
python3 -m pip install -e .
rch init my-competition
rch bootstrap-lanes my-competition codex
rch check my-competition
```

## 작업공간 구조

```text
my-competition/
  input/
    ideas/        # 아이디어, 제목 후보, 수업 모형 메모
    research/     # 배경지식, 선행연구, 이론적 배경 리서치
    rules/        # 공문, 규격, 심사표
    references/   # 우수 보고서
    evidence/     # 익명화된 수업 증빙
    photos/       # 개인정보 검토 또는 블러 처리된 사진
    surveys/      # 익명화된 설문 표와 요약 지표
    raw_private/  # 원자료. commit 금지
  lanes/
  output/
```

## Lane 목록

| Lane | 역할 |
| --- | --- |
| `intake` | 입력 자료 분류, 개인정보 위험, 누락 질문 |
| `brainstorm` | 제목, 연구 질문, 수업 모형, 실천과제 |
| `reference-miner` | 우수 보고서 구조·표·부록 패턴 추출 |
| `evidence-curator` | 주장과 실제 증거 연결 |
| `survey-analyzer` | 사전·사후 설문, 자유응답, 소표본 한계 분석 |
| `photo-curator` | 수업사진 privacy/action/placement manifest |
| `draft-writer` | claim-tagged 보고서 본문 |
| `table-layout` | 표 중심 편집, 페이지 흐름, 캡션 |
| `summary-sheet` | 요약서 구성 |
| `toc-builder` | 목차, 제목 일관성, 페이지 번호 가정 |
| `appendix-builder` | 과정안, 루브릭, 활동지, 설문지, 산출물 부록 |
| `icon-visual` | 아이콘, 도식, 시각자료 manifest |
| `critic` | 심사자 관점 리뷰, 개인정보, 허위 주장, AI 티 점검 |
| `finalizer` | 최종 bundle/HWPX 조립 전 체크리스트 |

## Lane 산출물 계약

각 lane은 아래 파일을 채웁니다.

```text
lanes/<lane>/<agent>/
  lane-input.md       # 하네스가 생성하는 작업 지침
  lane-output.md      # 사람이 읽는 산출물
  lane-output.json    # 기계가 읽는 요약
  claim-ledger.json   # 주장과 근거 상태
  verdict.json        # pass / needs-work / blocked
  evidence/           # 해당 lane에서 쓴 보조 근거
```

`critic` lane은 추가로 `rubric-score.json`을 채웁니다.

```json
{
  "total_score": 90,
  "max_score": 100,
  "items": [
    {
      "criterion": "학생 변화 근거",
      "score": 18,
      "max_score": 20,
      "evidence": "설문·산출물 근거",
      "risk": "수치 과장 시 감점",
      "fix": "소표본 한계 명시"
    }
  ]
}
```

`claim-ledger.json` status:

| Status | 뜻 | final 반영 |
| --- | --- | --- |
| `real` | 실제 증빙으로 직접 확인 | 가능 |
| `derived` | 실제 증빙에서 계산/도출, 방법 기록 | 가능 |
| `expected` | "예상값(가상)" 라벨이 붙은 예상 결과(설문 미실시 등) | `check --final --allow-expected`에서만 가능 |
| `placeholder` | 초안용 자리표시자(아직 못 채운 구멍) | 불가 |
| `forbidden` | 보고서 반영 금지 | 불가 |

`expected` claim은 text/notes에 "예상"/"가상" 라벨이 없으면 `check`가 거부합니다. `--allow-expected`로 final을 통과하면 교체 목록이 `output/expected-claims.md`에 남고, 실제 자료가 생기면 교체 후 플래그 없는 `check --final`로 재검증합니다.

## 추천 운영 흐름

```bash
rch init 2026-competition
```

1. `input/rules/`에 공문, 심사표, 양식 넣기
2. `input/references/`에 우수 보고서 넣기
3. `input/ideas/`에 수업 아이디어와 제목 후보 넣기
4. `input/evidence/`에 익명화된 수업 증빙 넣기
5. `input/photos/`에 개인정보 검토된 사진 넣기
6. `input/surveys/`에 익명화된 설문 결과 넣기
7. `input/raw_private/`에는 원자료를 임시 보관하되 commit하지 않기
8. `rch bootstrap-lanes 2026-competition codex`
9. 각 lane의 `lane-input.md`를 Codex, Antigravity, Claude, 사람에게 배정
10. 각 agent가 lane 계약 파일 작성
11. `rch check 2026-competition`
12. `rch assemble 2026-competition`
13. `rch check 2026-competition --final`
14. finalizer가 bundle을 바탕으로 HWPX 조립
15. Hancom/HOP 렌더, 목차 페이지, 표 흐름, 개인정보를 사람이 최종 검증

## Assemble

```bash
PYTHONPATH=src python3 -m rch.cli assemble my-competition
```

생성 파일:

```text
output/report-draft.md
output/summary-sheet.md
output/toc.md
output/appendix.md
output/finalization-checklist.md
output/bundle-manifest.json
```

`bundle-manifest.json`에는 각 파일 SHA-256과 source lane이 남습니다. source lane이 비면 `check --final`에서 실패합니다.

`check --final` 추가 규칙:

- 모든 production lane은 최소 1개 agent output이 완성되어야 합니다.
- 모든 required lane의 `verdict.status`는 `pass`여야 합니다.
- final claim evidence는 workspace-relative path여야 합니다.
- final claim evidence는 `input/raw_private/`를 직접 가리킬 수 없습니다.
- critic `rubric-score.json`은 5개 이상 criterion과 85% 이상 총점을 가져야 합니다.
- 기본은 `real`/`derived` claim만 허용. **설문 미실시 등으로 예상값(가상)을 넣은 완성본은 `--allow-expected`를 붙여** 라벨링된 `expected` claim까지 허용합니다(`placeholder`는 계속 차단).

## 금지선

- 증거 없는 학생 발화 금지
- 증거 없는 설문 수치 금지
- 증거 없는 수업 결과 금지
- 확정되지 않은 확산 실적 금지
- AI 생성 이미지나 목업을 실제 증빙처럼 사용 금지
- 학생 얼굴, 이름, 학번, 개인 화면이 남은 사진 final 반영 금지
- 레퍼런스 보고서 문장 복사 금지
- 여러 에이전트의 동시 `.hwpx` 수정 금지

final 문구 금지:

```text
예정
추후
보완 예정
초안
미정
TODO
```

## 테스트

```bash
cd research-competition-harness
PYTHONPATH=src python3 -m unittest discover -s tests
```

## GitHub

```bash
git add .
git commit -m "feat: add report production lane workflow"
git push
```

Repo: `https://github.com/ghdrhks97-maker/research-competition-harness`

## 라이선스

MIT License. 자세한 내용은 [`LICENSE`](LICENSE) 참고.
