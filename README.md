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

## 아직 자동으로 하지 않는 일

- Codex, Antigravity, Claude, Gemini를 자동 호출하지 않음
- raw 설문 스프레드시트나 사진을 자동 분석하지 않음
- finished `.hwpx` 파일을 자동 생성하지 않음
- Hancom/HOP 렌더 기준 페이지 수를 이 CLI 안에서 직접 검증하지 않음

즉, 에이전트가 채워야 하는 `lane-output.md`, `claim-ledger.json`, `verdict.json`을 이 하네스가 대신 작성하지는 않습니다. 대신 “무엇을 어떻게 쓰고, 무엇을 쓰면 안 되는지”를 lane 지침으로 강하게 고정하고, 최종 병합 전 검사를 수행합니다.

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
