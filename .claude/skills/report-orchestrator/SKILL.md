---
name: report-orchestrator
description: 연구대회 보고서를 실제로 완성하는 진입점. "연구보고서 만들어줘", "이 대회 보고서 초안 써줘" 같은 요청에서 자동 트리거되어, rch 하네스(결정적 분석·렌더·검증)와 lane별 전문 서브에이전트(실제 글쓰기)를 단계별로 조율한다.
---

# report-orchestrator

연구대회 보고서를 처음부터 끝까지 완성하는 지휘자다. 웹툰 하네스처럼, 당신(Claude Code)이 런타임이 되어 각 단계를 전문 서브에이전트에게 위임하고, 결정적 작업은 `rch` CLI에 맡긴다.

## 핵심 원칙: 하이브리드

- **`rch` (파이썬)** = 결정적 작업만. 설문 통계, HWPX 렌더, 검증, 개인정보 스캔, 골격 생성. 숫자를 만들지 않는다.
- **서브에이전트 (LLM)** = 실제 글쓰기·종합·비평. 각 lane의 `lane-output.md`와 계약 파일을 **진짜 내용**으로 채운다.

순수 파이썬은 골격(placeholder)만 만든다. 실제 보고서 문장은 반드시 서브에이전트가 쓴다.

## 준비

`rch`가 설치돼 있어야 한다. 없으면 `pip install -e .` 안내. 명령은 `PYTHONPATH=src python3 -m rch.cli ...` 또는 설치형 `rch ...`.

작업공간 경로를 사용자에게 확인한다(예: `2026-음악대회`). 없으면 `rch init <ws>`.

## 6단계 파이프라인

### Phase 0 — 인터뷰·대회 세팅
1. 사용자에게 대화로 물어본다(파일 요구 금지): 참가 대회명, 전공 교과, 학교급/학년, 학급 상황, 관심 트렌드, 활용 도구, 목표 역량, 제약.
2. 대회 양식·공문·심사표 파일 경로가 있으면 `rch import-rules <ws> <files...>`.
3. 받은 답을 플래그로 바로 넘겨 실행:
   `rch brainstorm <ws> --competition-name "..." --major ... --interests ... --competency ...`
   → `input/ideas/`에 주제·제목 생성(2022 개정 핵심역량 연계). 필요하면 `brainstorm` 서브에이전트로 후보를 다듬는다.

### Phase 1 — 자료 분석 (결정적, rch)
- 설문 CSV 있으면 `rch import-survey <ws> <file>` → 평균·효과크기·p값.
- 사진 있으면 `rch import-photos <ws>` → 개인정보 점검표.
- 레퍼런스 있으면 `rch mine-references <ws>` → 목차·표 구조.
- 인터넷 가능하면 `rch research-background <ws>` → 선행연구 후보.
- 자료가 없으면 그 사실을 기록하고 placeholder로 두되, 사용자에게 "무엇을 넣으면 품질이 올라가는지" 안내.

### Phase 2 — 실제 집필 (서브에이전트, 병렬 가능)
각 lane 폴더를 준비: `rch lane <ws> <lane> agent` (lane-input.md 생성).
그다음 Task로 서브에이전트를 위임한다. 각 에이전트는 자기 lane의 계약 파일 4종을 **진짜 내용**으로 채운다.

- `survey-analyst` — rch 설문 분석 수치를 해석·서술(수치는 분석 결과에서만).
- `evidence-curator` — 주장↔증거 연결, claim-ledger 확정.
- `reference-miner` — 레퍼런스 구조를 참고해 목차·표 전략 서술(문장 복사 금지).
- `draft-writer` — I~V장 본문 집필(표 중심, 최종 진술형).  ← 가장 중요
- `table-layout` → `summary-sheet` → `toc-builder` → `appendix-builder` (draft 이후)
- `icon-visual` — 시각 언어(선택)

의존성: survey-analyst·evidence-curator·reference-miner를 먼저(병렬) → draft-writer → 나머지.

### Phase 3 — 비평·검증 루프
1. `critic` 서브에이전트가 심사자 관점으로 검토 → `lanes/critic/agent/machine-feedback.json` 작성.
2. `rch check <ws>` 로 계약·claim·금지어 검사.
3. `rch revise-loop <ws>` 로 수정 백로그 통합.
4. 지적사항을 해당 lane 에이전트에게 다시 위임해 고친다. `rch check <ws> --final` 이 통과할 때까지 반복(최대 3~4회). placeholder claim이 남아 있으면 통과 못 한다.

### Phase 4 — 조립·렌더
1. `rch assemble <ws>` → markdown 번들.
2. `rch check <ws> --final` (통과 필수).
3. `rch build-hwpx <ws>` → `output/report.hwpx` (A4 페이지 정의 포함).
4. `rch render-check <ws>` → 구조·페이지·목차 검증. 경고는 revise 루프로.
5. 사용자에게 "한컴오피스에서 열어 최종 확인" 안내.

## 안전 규칙 (모든 에이전트에 강제)

- 증거 없는 설문 수치·학생 발화·수업 결과·확산 실적을 **만들지 않는다**. 불확실하면 `placeholder` claim.
- 설문 수치는 `input/surveys/analysis/`의 rch 분석 결과에서만 인용한다.
- 사진은 `unreviewed`/`high` 위험이면 본문·부록에 넣지 않는다.
- 레퍼런스 문장·표 내용을 복사하지 않는다. 구조만 참고.
- 최종 본문에 예정/추후/초안/미정/TODO 금지.
- 여러 에이전트가 같은 HWPX를 동시에 수정하지 않는다(조립은 한 번만).

## 진행 방식

각 Phase 시작·종료를 사용자에게 짧게 보고한다. 자료 부족·동의 필요·개인정보 위험은 진행을 멈추고 사용자에게 확인한다. 완료 시 `output/report.hwpx`와 남은 확인사항 목록을 제시한다.
