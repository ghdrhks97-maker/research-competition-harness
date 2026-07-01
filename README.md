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
| `rch go <ws>` | 짧은 전체 실행. 작업공간 생성 → 브레인스토밍 → 배경연구 → 설문/사진 placeholder → 레퍼런스 구조 → 초안 → 조립 → HWPX → 렌더 점검 | `output/report.hwpx` + 보강표 |
| `rch import-rules <ws> <files...>` | 대회 공문·심사표·보고서 양식을 `input/rules/`에 복사하고 manifest 생성 | `input/rules/rules-manifest.json` |
| `rch brainstorm <ws>` | 대회명 → 분야/교과 인터뷰 → 연구 동향 리서치 → 연구 주제·제목 자동 생성. 사람이 ideas 파일을 직접 쓰지 않음 | `input/ideas/` + `input/rules/competition-profile.json` |
| `rch research-background <ws>` | insane-search 방식의 public-route scheduler로 이론적 배경·선행연구 후보 수집(OpenAlex/CrossRef/arXiv/Jina route → fallback) | `input/research/` + reference-miner lane |
| `rch import-survey <ws> <file>` | 사전·사후 설문 CSV/TSV/XLSX 익명 분석(평균·변화량·Cohen's d·t검정 p값·자유응답 요약·소표본 한계) | `input/surveys/analysis/` |
| `rch import-photos <ws>` | 사진 매니페스트 + 개인정보 점검표(본문/요약/부록/제외 분류, 블러 지시) | `input/photos/analysis/` |
| `rch mine-references <ws>` | 레퍼런스 보고서에서 목차·표 밀도·부록 패턴 등 **구조만** 추출 | `input/references/analysis/` |
| `rch draft <ws>` | 분석 결과로 I~V장 본문·요약서·목차·부록 초안 생성(claim 태그 부착) | 쓰기 lane 4종 |
| `rch run-lanes <ws> <agent>` | lane별 프롬프트 번들 생성(외부 에이전트 배정용). `--execute` 시 로그인 확인 후 실제 호출 | `prompts/<agent>/` |
| `rch agents preflight <ws>` | Codex/Antigravity/Claude CLI 설치·로그인 자동 확인 | `output/agent-preflight.{json,md}` |
| `rch agents run <ws> <agent> --lanes ...` | 프롬프트를 에이전트 CLI로 실제 호출해 응답 수집 | `lanes/<lane>/<agent>/agent-response.md` |
| `rch build-hwpx <ws>` | 조립된 bundle → HWPX(OWPML zip) 렌더 | `output/report.hwpx` |
| `rch render-check <ws>` | HWPX 구조·XML·페이지 추정·목차-본문 일치·표 무결성 검증 | `output/render-check.{json,md}` |
| `rch revise-loop <ws>` | critic·check·render-check 피드백을 우선순위 수정 백로그로 통합 | `output/revision-tasks.{json,md}` |

한 번에 도는 흐름:

```bash
rch go 2026-competition --competition-name "창의교육 연구대회" --major 과학 --interests "AI, 탐구" --competency 탐구력
```

설문·사진이 아직 없어도 멈추지 않습니다. 이 경우 하네스가 다음 placeholder 표를 넣고 HWPX까지 만듭니다.

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

## Claude Code / Codex / AGY에서 MCP로 쓰기

CLI로 직접 돌리는 대신 **Claude Code, Codex, AGY가 하네스 기능을 도구로 호출**하게 하려면 MCP 서버를 씁니다.

```bash
pip install -e ".[mcp]"     # rch-mcp (stdio MCP 서버) 설치
```

Claude Code(`.mcp.json`) 또는 Codex(`~/.codex/config.toml`)에 `rch-mcp`를 등록하면 `go`, `init`, `import_rules`, `brainstorm`, `research_background`, `import_survey`, `draft`, `build_hwpx`, `render_check` 등이 도구로 노출됩니다. 이때는 에이전트가 운전자이므로 `rch agents ...`(하네스가 AI를 호출) 기능은 필요 없습니다. 설정과 예시는 [`docs/mcp.md`](docs/mcp.md) 참고.

모든 에이전트앱 공통 짧은 지시:

```text
rch go를 사용해 2026-competition 작업공간을 만들고 창의교육 연구대회, 과학, AI 탐구, 탐구력 중심으로 보고서 초안과 HWPX까지 생성해줘. 첨부한 보고서 양식 파일은 input/rules에 저장해서 참고해줘.
```

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
첨부한 공문, 심사표, 보고서 양식 파일을 rch import_rules로 input/rules에 저장하고, 그 양식을 기준으로 rch go를 실행해줘.
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
| `placeholder` | 초안용 자리표시자 | 불가 |
| `forbidden` | 보고서 반영 금지 | 불가 |

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
