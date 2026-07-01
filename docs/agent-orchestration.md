# 에이전트 오케스트레이션 모드 (Claude Code)

로컬 우선 `rch` CLI는 **결정적 골격**만 만듭니다(placeholder). 실제 보고서 문장·종합·비평은 LLM이 써야 합니다. 이 모드는 웹툰 하네스처럼 **Claude Code가 런타임이 되어 lane별 전문 서브에이전트를 조율**해 실제 내용을 채웁니다.

## 구성

```
.claude/
  skills/
    report-orchestrator/SKILL.md   # 진입점. "연구보고서 만들어줘"에서 자동 트리거
  agents/                          # lane별 전문 서브에이전트
    brainstorm.md
    reference-miner.md
    survey-analyst.md
    evidence-curator.md
    draft-writer.md                # I~V장 본문 집필 (가장 중요)
    table-layout.md
    summary-sheet.md
    toc-builder.md
    appendix-builder.md
    critic.md
    finalizer.md
```

## 하이브리드 원칙

| 역할 | 담당 | 예 |
| --- | --- | --- |
| 결정적 분석·렌더·검증 | `rch` (파이썬) | 설문 통계, HWPX 렌더, check, 개인정보 스캔 |
| 실제 글쓰기·종합·비평 | 서브에이전트 (LLM) | 본문 집필, 결과 해석, 요약서, 심사자 비평 |

`rch`는 숫자를 만들지 않고, 에이전트는 숫자를 지어내지 않는다(분석 결과만 인용). 두 층이 합쳐져야 완성형 보고서가 나온다.

## 쓰는 법

작업공간 폴더에서 **Claude Code**를 열고 자연어로 요청합니다.

```
claude
> 2026-음악대회 작업공간으로 교실수업개선 실천사례 연구대회, 음악, 중2, AI·에듀테크,
  음악적 창의융합 역량 중심으로 연구보고서 만들어줘. 설문은 survey.csv, 사진은 photos/ 에 있어.
```

`report-orchestrator` 스킬이 트리거되어:
1. Phase 0 인터뷰·`rch brainstorm`
2. Phase 1 `rch import-survey/import-photos/mine-references/research-background`
3. Phase 2 `draft-writer`·`survey-analyst` 등 서브에이전트가 실제 집필
4. Phase 3 `critic` + `rch check`/`revise-loop` 루프
5. Phase 4 `rch assemble`/`build-hwpx`/`render-check`

## CLI만 쓰는 헤드리스 대안

Claude Code 없이 돌리려면, `rch run-lanes <ws> <agent> --execute` 또는 `rch agents run`이 외부 에이전트 CLI(codex/claude/antigravity)에 lane 프롬프트를 던져 채우게 할 수 있습니다. 다만 오케스트레이션·품질 루프는 위 Claude Code 모드가 더 매끄럽습니다.

## 안전

모든 에이전트는 동일 안전 규칙을 따릅니다: 증거 없는 수치·학생 발화·성과 금지, 설문 수치는 분석 결과만, 개인정보 사진 배제, 레퍼런스 복사 금지, 최종 금지어 없음, HWPX 동시 편집 금지. `rch check --final`이 최종 게이트입니다.
