# 스킬 팩

각 스킬은 lane 지침을 실제 동작하는 하네스 명령으로 뒷받침합니다. 하네스만으로 완성형 보고서까지 가는 파이프라인 순서:

| 단계 | 스킬 | 명령 |
| --- | --- | --- |
| 0 | agent-runner-skill | `rch agents preflight` / `rch agents run` |
| 1 | brainstorm-skill | `rch brainstorm` (전공 인터뷰 → 트렌드 → 주제·제목 → input/ideas) |
| 2 | research-background-skill | `rch research-background` |
| 3 | input-intake-skill | `rch run-lanes` (intake) |
| 4 | survey-analysis-skill | `rch import-survey` |
| 5 | photo-privacy-curator-skill | `rch import-photos` |
| 6 | reference-report-miner-skill | `rch mine-references` |
| 7 | evidence-ledger-skill | `rch check` |
| 8 | report-draft-writer-skill | `rch draft` |
| 9 | summary-toc-appendix-skill | `rch draft` + `rch assemble` |
| 10 | table-layout-compressor-skill | `rch render-check` 신호 |
| 11 | hwp/hwpx-finalizer-skill | `rch build-hwpx` |
| 12 | hancom-render-qa-skill | `rch render-check` |
| 루프 | (품질 루프) | `rch revise-loop` |

## 한 번에 도는 흐름

```bash
rch init 2026-competition
rch brainstorm 2026-competition              # 전공 인터뷰 → 트렌드 → 주제·제목 → input/ideas 자동 작성
rch research-background 2026-competition     # 이론적 배경·선행연구 후보 수집
rch agents preflight 2026-competition        # 에이전트 설치·로그인 확인
# 자료 채우기: input/rules, input/references, input/surveys, input/photos, input/evidence (ideas는 brainstorm이 채움)
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
