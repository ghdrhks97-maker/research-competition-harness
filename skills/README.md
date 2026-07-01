# 스킬 팩

각 스킬은 lane 지침을 실제 동작하는 하네스 명령으로 뒷받침합니다. 하네스만으로 완성형 보고서까지 가는 파이프라인 순서:

| 단계 | 스킬 | 명령 |
| --- | --- | --- |
| 1 | input-intake-skill | `rch run-lanes` (intake) |
| 2 | survey-analysis-skill | `rch import-survey` |
| 3 | photo-privacy-curator-skill | `rch import-photos` |
| 4 | reference-report-miner-skill | `rch mine-references` |
| 5 | evidence-ledger-skill | `rch check` |
| 6 | report-draft-writer-skill | `rch draft` |
| 7 | summary-toc-appendix-skill | `rch draft` + `rch assemble` |
| 8 | table-layout-compressor-skill | `rch render-check` 신호 |
| 9 | hwp/hwpx-finalizer-skill | `rch build-hwpx` |
| 10 | hancom-render-qa-skill | `rch render-check` |
| 루프 | (품질 루프) | `rch revise-loop` |

## 한 번에 도는 흐름

```bash
rch init 2026-competition
# 자료 채우기: input/rules, input/references, input/ideas, input/surveys, input/photos, input/evidence
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

생성 엔진(import-*/draft) → 렌더 엔진(build-hwpx) → 품질 루프(check/render-check/revise-loop)가 하나로 붙어 있습니다.
