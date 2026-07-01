# 연구대회 보고서 제작 하네스

여러 AI 에이전트가 병렬로 아이디어, 레퍼런스 분석, 원고, 표 구성, 요약서, 아이콘/시각자료, 비평을 만들되 최종 `.hwpx`는 한 finalizer만 조립하게 하는 로컬 우선 하네스입니다.

핵심 목표는 다음번 연구대회에서 같은 시행착오를 줄이는 것입니다.

- 보고서 아이디어 브레인스토밍
- 레퍼런스 보고서 구조 추출
- 내 보고서용 표 중심 원고화
- 요약서 작성
- 아이콘/시각자료 목록화
- 근거 없는 주장 차단
- 최종 HWPX 조립 전 검증

## 핵심 원리

에이전트는 병렬로 일하지만 같은 `.hwpx`를 동시에 수정하지 않습니다.

각 에이전트는 자기 lane 폴더에 정해진 계약 파일만 남깁니다.

```text
lane-output.md
lane-output.json
claim-ledger.json
verdict.json
evidence/
```

conductor는 lane 산출물을 모아 주장 근거, 형식, 금지 문구를 검사합니다. 그 뒤 finalizer 하나만 HWPX를 만들고 렌더링/Hancom 검증으로 넘깁니다.

## 저장소 구성

```text
research-competition-harness/
  src/rch/cli.py                         # init, lane, check CLI
  schemas/                               # lane 산출물 JSON 형식
  templates/next_competition_workspace/  # 새 연구대회 작업공간 뼈대
  docs/architecture.md                   # conductor + lane 구조
  docs/lane-contract.md                  # lane 산출물 계약
  examples/synthetic/                    # 가짜 예시 데이터
  tests/test_cli.py                      # CLI 핵심 테스트
```

이 저장소에는 실제 보고서, 학생 자료, 사진, 증빙, PDF, HWPX를 넣지 않습니다. 하네스 코드, 템플릿, 스키마, 문서, synthetic 예시만 둡니다.

## 빠른 시작

설치 없이 로컬에서 바로 실행:

```bash
cd /Users/hongtaekwan/research-competition-harness
PYTHONPATH=src python3 -m rch.cli init my-competition
PYTHONPATH=src python3 -m rch.cli lane my-competition brainstorm codex
PYTHONPATH=src python3 -m rch.cli check my-competition
```

CLI 명령어로 쓰고 싶으면 editable install:

```bash
cd /Users/hongtaekwan/research-competition-harness
python3 -m pip install -e .
rch init my-competition
rch lane my-competition brainstorm codex
rch check my-competition
```

## 작업공간 구조

`rch init my-competition` 실행 뒤 생성되는 구조:

```text
my-competition/
  input/
    rules/        # 대회 공문, 규격, 심사표
    references/   # 레퍼런스 보고서
    evidence/     # 실제 수업 증빙
  lanes/          # 에이전트별 작업함
  output/         # 검사 결과, 최종 조립 산출물
```

실제 연구대회마다 새 작업공간을 만들고, 이 저장소에는 그 작업공간의 민감 자료를 commit하지 않습니다.

## Lane 종류

| Lane | 추천 담당 | 역할 |
| --- | --- | --- |
| `brainstorm` | Antigravity / Codex | 주제, 제목, 연구 질문, 심사 기준 적합성 |
| `reference-miner` | Claude / Gemini / Codex | 우수 보고서 구조, 표 패턴, 흐름 추출 |
| `draft-writer` | Codex / Claude | claim-tagged 원고 작성 |
| `table-layout` | Codex | 표 중심 보고서 지도 작성 |
| `summary-sheet` | Codex / Antigravity | 요약서 구성 |
| `icon-visual` | Codex / Antigravity | 아이콘, 차트, 시각자료 manifest |
| `critic` | Claude / Gemini / Codex | 심사표, 형식, 익명성, 허위 주장 점검 |
| `finalizer` | Codex | HWPX 조립, package/render/Hancom 검증 |

lane 생성 예시:

```bash
PYTHONPATH=src python3 -m rch.cli lane my-competition reference-miner antigravity
```

생성 결과:

```text
my-competition/lanes/reference-miner/antigravity/
  lane-input.md
  evidence/
```

에이전트는 `lane-input.md`를 읽고 같은 폴더에 required output을 채웁니다.

## Lane 산출물 계약

모든 lane은 아래 파일을 만들어야 합니다.

```text
lane-output.md       # 사람이 읽는 결과
lane-output.json     # 기계가 읽는 요약
claim-ledger.json    # 주장과 근거 상태
verdict.json         # pass / needs-work / blocked
evidence/            # 해당 lane이 사용한 증빙
```

`claim-ledger.json` claim status:

| Status | 뜻 | 최종 반영 |
| --- | --- | --- |
| `real` | 실제 증빙으로 직접 확인 | 가능 |
| `derived` | 실제 증빙에서 계산/도출 | 가능 |
| `placeholder` | draft용 자리표시자 | 불가 |
| `forbidden` | 보고서에 들어가면 안 됨 | 불가 |

최종 후보(`--final`)는 `real`, `derived`만 통과합니다. 둘 다 evidence path가 필요합니다.

## 검사 명령

일반 검사:

```bash
PYTHONPATH=src python3 -m rch.cli check my-competition
```

최종 후보 검사:

```bash
PYTHONPATH=src python3 -m rch.cli check my-competition --final
```

검사 결과는 콘솔과 아래 파일에 남습니다.

```text
my-competition/output/harness-check.json
```

현재 검사하는 것:

- lane 필수 파일 존재 여부
- JSON parse 가능 여부
- `verdict.status` 값 유효성
- `claim-ledger.json`의 `claims[]` 존재 여부
- claim status 유효성
- 최종 후보에서 `placeholder`, `forbidden` claim 차단
- `real`, `derived` claim의 evidence path 누락 차단
- 최종 후보에서 금지 문구 차단

## 금지선

최종 보고서 본문에는 아래를 넣지 않습니다.

- 지어낸 학생 발화
- 지어낸 설문 수치
- 지어낸 수업 결과
- 지어낸 확산/공유 실적
- 출처 없는 사진/스크린샷
- 레퍼런스 보고서 문장 복사
- 여러 에이전트의 동시 HWPX 수정

최종 후보 검사에서 아래 문구도 막습니다.

```text
예정
추후
보완 예정
초안
미정
TODO
```

## 추천 운영 흐름

1. `rch init <workspace>`로 새 대회 작업공간 생성
2. `input/rules/`에 공문, 규격, 심사표 저장
3. `input/references/`에 우수 보고서 저장
4. `input/evidence/`에 실제 수업 증빙 저장
5. lane별 inbox 생성
6. Codex, Antigravity, Claude/Gemini가 자기 lane만 채움
7. `rch check`로 중간 점검
8. `rch check --final`로 최종 후보 점검
9. finalizer가 하나의 HWPX로 조립
10. package/render/Hancom 검증 뒤 최종본 확정

## Antigravity/Codex 병렬 사용 방식

Antigravity나 다른 도구가 직접 이 Python CLI를 몰라도 됩니다. 파일 계약만 지키면 됩니다.

예:

```text
lanes/brainstorm/antigravity/lane-input.md
```

이 파일을 Antigravity에 주고, 결과를 같은 폴더에 아래처럼 저장하게 합니다.

```text
lanes/brainstorm/antigravity/lane-output.md
lanes/brainstorm/antigravity/lane-output.json
lanes/brainstorm/antigravity/claim-ledger.json
lanes/brainstorm/antigravity/verdict.json
```

Codex는 finalizer나 검사 자동화처럼 파일 시스템과 검증에 강한 일을 맡깁니다. Antigravity는 아이디어, 구조 제안, 시각 방향처럼 발산 작업에 쓰면 좋습니다.

## 테스트

```bash
cd /Users/hongtaekwan/research-competition-harness
PYTHONPATH=src python3 -m unittest discover -s tests
```

## GitHub 사용

변경 후 push:

```bash
cd /Users/hongtaekwan/research-competition-harness
git add .
git commit -m "docs: translate README to Korean"
git push
```

현재 remote:

```text
https://github.com/ghdrhks97-maker/research-competition-harness
```

private repo입니다.
