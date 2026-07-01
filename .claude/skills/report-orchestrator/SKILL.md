---
name: report-orchestrator
description: 연구대회 보고서를 완성하는 진입점. "연구보고서 만들어줘" 같은 요청에서 자동 트리거된다. 판단·분석·집필은 전부 서브에이전트에 위임하고, 파이썬 rch는 설문 통계·HWPX 렌더·검증에만 쓴다.
---

# report-orchestrator

에이전트 우선 지휘자다. 당신(Claude Code)이 런타임이 되어 각 단계를 `.claude/agents/`의 전문 서브에이전트에게 **Task로 위임**한다. 파이썬 `rch`는 LLM이 부정확한 세 가지에만 쓴다.

## 파이썬은 3가지만
- `rch import-survey` — 설문 통계(산술은 파이썬이 정확)
- `rch build-hwpx` — HWPX 바이너리 생성
- `rch assemble`/`check --final`/`render-check` — 조립·검증 게이트
- (+ `rch init` 폴더 골격, `rch import-rules` 양식 복사)

**그 외 전부 서브에이전트.** `rch brainstorm/mine-references/research-background/draft/import-photos`는 정확도가 낮으니 **쓰지 않는다** — 대신 아래 에이전트를 켠다.

## 실행

작업공간 확인/생성(`rch init <ws>`). 그다음 단계별로 서브에이전트를 스폰한다. **독립 lane은 한 응답에서 여러 Task를 동시에 호출해 병렬로 돌린다.**

### Phase 0 — 인터뷰·주제
대화로 8개 항목(대회명·교과·학년·상황·트렌드·도구·역량·제약)을 묻는다. 양식 파일 있으면 `rch import-rules`. → `brainstorm` 서브에이전트로 주제·제목·실천과제 확정(2022 개정 핵심역량 연계).

### Phase 1 — 분석·리서치 (병렬 스폰)
설문 CSV가 있으면 먼저 `rch import-survey <ws> <csv>`(통계). 그다음 아래를 **동시에** Task로:
- `reference-miner`(우수 보고서 구조 직접 분석)
- `background-researcher`(insane 리서치: 이론·선행연구)
- `photo-curator`(사진 개인정보 실제 검토)
- `evidence-curator`(주장↔증거)
- `survey-analyst`(rch 통계 해석)

### Phase 2 — 집필
`draft-writer` 서브에이전트가 Phase 1 결과를 모두 읽고 I~V장 본문 집필.

### Phase 3 — 편집·부속
`table-layout` → 그 뒤 `summary-sheet`·`toc-builder`·`appendix-builder`(병렬).

### Phase 4 — 비평·검증 루프
`critic` → `rch check <ws>` → `rch revise-loop <ws>`. 지적사항을 해당 서브에이전트에 다시 위임. `rch check <ws> --final` 통과까지 반복(≤4회).

### Phase 5 — 조립·렌더
`finalizer` 지휘: `rch assemble` → `rch check --final` → `rch build-hwpx` → `rch render-check`. 완료 시 `output/report.hwpx`와 남은 확인사항 제시, "한컴에서 최종 확인" 안내.

## 안전 (전 에이전트 강제)
증거 없는 수치·발화·성과·인용 금지(→placeholder), 설문 수치는 rch 분석만, 위험 사진 배제, 레퍼런스·웹 복사 금지, 최종 금지어 없음, HWPX 조립 1회. 상세는 `AGENTS.md`.

## 진행
각 Phase 시작·종료를 짧게 보고. 자료 부족·동의 필요·개인정보 위험은 멈추고 사용자 확인. 서브에이전트 산출물이 약하면 해당 에이전트를 재위임한다.
