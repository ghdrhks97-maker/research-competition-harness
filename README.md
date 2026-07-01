# 연구대회 보고서 제작 하네스

수업혁신사례 연구대회 보고서를 여러 AI 에이전트와 함께 만들기 위한 로컬 우선 하네스입니다.

목표는 아이디어, 수업사진, 설문결과, 레퍼런스 보고서, 증빙 자료를 한 작업공간에 넣고, lane별 지침을 따라 보고서 본문·요약서·목차·부록·최종화 체크리스트까지 통제된 markdown bundle로 만드는 것입니다.

## 현재 하네스가 하는 일

- 새 연구대회 작업공간 생성
- 아이디어, 공문, 레퍼런스, 증빙, 사진, 설문, raw_private 입력 폴더 생성
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
- `check --final`로 final bundle 누락, missing source lane, 금지 문구를 검사

## 생성 엔진 · 렌더 엔진 · 품질 루프

이제 하네스만으로 자료 → 분석 → 초안 → HWPX → 검증 → 수정까지 돌 수 있습니다.

| 명령 | 하는 일 | 산출물 |
| --- | --- | --- |
| `rch brainstorm <ws>` | 전공 인터뷰 → 교육 트렌드 리서치 → 연구 주제·제목 자동 생성. 사람이 ideas 파일을 직접 쓰지 않음 | `input/ideas/` + brainstorm lane |
| `rch import-survey <ws> <file>` | 사전·사후 설문 CSV/TSV/XLSX 익명 분석(평균·변화량·Cohen's d·t검정 p값·자유응답 요약·소표본 한계) | `input/surveys/analysis/` |
| `rch import-photos <ws>` | 사진 매니페스트 + 개인정보 점검표(본문/요약/부록/제외 분류, 블러 지시) | `input/photos/analysis/` |
| `rch mine-references <ws>` | 레퍼런스 보고서에서 목차·표 밀도·부록 패턴 등 **구조만** 추출 | `input/references/analysis/` |
| `rch draft <ws>` | 분석 결과로 I~V장 본문·요약서·목차·부록 초안 생성(claim 태그 부착) | 쓰기 lane 4종 |
| `rch run-lanes <ws> <agent>` | lane별 프롬프트 번들 생성(외부 에이전트 배정용). `--execute` 시 로그인 확인 후 실제 호출 | `prompts/<agent>/` |
| `rch agents preflight <ws>` | Codex/Antigravity/Claude/Gemini CLI 설치·로그인 자동 확인 | `output/agent-preflight.{json,md}` |
| `rch agents run <ws> <agent> --lanes ...` | 프롬프트를 에이전트 CLI로 실제 호출해 응답 수집 | `lanes/<lane>/<agent>/agent-response.md` |
| `rch build-hwpx <ws>` | 조립된 bundle → HWPX(OWPML zip) 렌더 | `output/report.hwpx` |
| `rch render-check <ws>` | HWPX 구조·XML·페이지 추정·목차-본문 일치·표 무결성 검증 | `output/render-check.{json,md}` |
| `rch revise-loop <ws>` | critic·check·render-check 피드백을 우선순위 수정 백로그로 통합 | `output/revision-tasks.{json,md}` |

한 번에 도는 흐름:

```bash
rch init 2026-competition
rch brainstorm 2026-competition            # 전공 인터뷰 → 트렌드 → 주제·제목 → input/ideas/ 자동 작성
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

## 시작: 브레인스토밍으로 주제·제목 자동 생성

하네스를 시작하면 사람이 `input/ideas/`에 파일을 직접 쓰지 않습니다. `rch brainstorm`이 인터뷰 → 트렌드 리서치 → 주제·제목까지 만들어 넣습니다.

```bash
rch init 2026-competition
rch brainstorm 2026-competition                 # 대화형 인터뷰
rch init 2026-competition --brainstorm          # init 직후 인터뷰까지 한 번에
rch brainstorm 2026-competition --answers answers.json   # 비대화형(자동화/재현)
rch brainstorm 2026-competition --agent gemini  # 트렌드 리서치를 실제 에이전트로 보강
```

인터뷰 항목: 전공 교과(필수), 학교급/학년, 학급 상황, 관심 트렌드, 활용 도구, 목표 역량, 제약. 답변만 하면 하네스가 다음을 자동 작성합니다.

- `input/ideas/00-interview.md` — 인터뷰 기록
- `input/ideas/01-trend-research.md` — 전공 적합도로 정렬한 교육 트렌드 리서치
- `input/ideas/02-research-topics.md` — 점수 매긴 연구 주제 후보(추천 표시)
- `input/ideas/03-title-candidates.md` — 알파벳 약어형·한글 스토리형 제목 후보 5개
- `input/ideas/brainstorm.json` — 기계 판독용 번들

추천 제목은 `brainstorm` lane에도 자동 반영되어 이후 `rch draft`의 보고서 제목으로 이어집니다. 생성된 주제·제목은 `placeholder` claim으로 들어가며, 심사기준 대조와 최종 선택은 사람이 확정합니다.

비대화형 답변 파일 예시(`answers.json`):

```json
{"major":"과학","level":"중학교 2학년","class_context":"28명","interests":"AI, 탐구","tools":"AI 챗봇, 태블릿","competency":"탐구력","constraints":"총 12차시"}
```

## 에이전트 자동 호출 · 로그인 확인

하네스는 외부 에이전트 CLI(Codex, Antigravity, Claude, Gemini)를 **실제로 실행**해 설치 여부와 **로그인 상태를 자동 확인**하고, lane 프롬프트를 에이전트에 직접 넘겨 응답을 수집합니다.

```bash
# 1) 초기 사전 점검: 설치 + 로그인 확인
rch agents preflight 2026-competition
rch agents preflight 2026-competition --agents codex claude --strict  # 미로그인 시 exit 1

# 2) 프롬프트 번들 생성 후 로그인 확인과 함께 실제 호출까지 한 번에
rch run-lanes 2026-competition codex --lanes survey-analyzer draft-writer --execute

# 3) 이미 만든 번들을 특정 에이전트로 실행
rch agents run 2026-competition gemini --lanes critic
```

로그인 상태는 **실제 프로세스 종료 코드**로 판정합니다(꾸며내지 않음). 판정값: `authenticated` / `unauthenticated` / `not_installed` / `unknown`(확인 명령 미설정).

CLI마다 하위 명령이 달라 각 에이전트의 실행 명령을 환경변수로 조정할 수 있습니다(내장 기본값은 best-effort 추정치):

| 환경변수 | 뜻 | 예 |
| --- | --- | --- |
| `RCH_AGENT_<NAME>_BIN` | 실행 파일 경로/이름 | `RCH_AGENT_CODEX_BIN=/usr/local/bin/codex` |
| `RCH_AGENT_<NAME>_VERSION_ARGS` | 설치 확인 인자 | `--version` |
| `RCH_AGENT_<NAME>_AUTH_ARGS` | 로그인 확인 인자(종료코드 0=로그인) | `login status` |
| `RCH_AGENT_<NAME>_RUN_ARGS` | 프롬프트 전달 인자(`{prompt}`/`{prompt_file}` 치환) | `exec {prompt}` |

`<NAME>`은 `CODEX`, `CLAUDE`, `GEMINI`, `ANTIGRAVITY`. 기본 레지스트리는 `rch agents list`로 확인합니다.

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
cd /Users/hongtaekwan/research-competition-harness
PYTHONPATH=src python3 -m rch.cli init my-competition
PYTHONPATH=src python3 -m rch.cli bootstrap-lanes my-competition codex
PYTHONPATH=src python3 -m rch.cli check my-competition
```

설치형 CLI:

```bash
cd /Users/hongtaekwan/research-competition-harness
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
9. 각 lane의 `lane-input.md`를 Codex, Antigravity, Claude/Gemini, 사람에게 배정
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
cd /Users/hongtaekwan/research-competition-harness
PYTHONPATH=src python3 -m unittest discover -s tests
```

## GitHub

```bash
git add .
git commit -m "feat: add report production lane workflow"
git push
```

Repo: `https://github.com/ghdrhks97-maker/research-competition-harness`
