---
name: survey-analysis-skill
description: 사전·사후 설문 CSV/TSV/XLSX를 익명 분석해 평균, 변화량, 효과크기, t-검정 p값, 자유응답 요약, 소표본 한계를 만든다. 원자료 없는 수치를 real로 만들지 않는다.
backing_command: rch import-survey <workspace> <survey-file>
---

# survey-analysis-skill

## 언제 쓰나
`input/surveys/`에 사전·사후 설문 원자료(CSV/TSV/XLSX)가 있을 때. 보고서 IV장 결과와 요약서 핵심 결과를 채우기 전에 실행한다.

## 무엇을 하나
- 개인정보 열(이름/학번/연락처 등)을 자동 제외하고 목록으로 보고한다.
- `문항_사전`/`문항_사후` 쌍을 감지해 평균, 평균차, 대응표본 Cohen's d, 두쪽 t-검정 p값을 계산한다.
- 단일 문항은 기술통계(평균/표준편차)만 낸다.
- 자유응답은 상위 키워드와 대표 응답을 뽑되 동의·익명화 확인 전까지 `placeholder`로 둔다.
- 표본이 30 미만이면 소표본 한계를 자동으로 명시한다.

## 실행
```bash
rch import-survey my-competition input/surveys/2026-pre-post.csv
```

산출물: `input/surveys/analysis/survey-analysis.json`, `survey-summary.md`, `claim-ledger.json`.

## 금지선
- 원자료·계산식 없는 숫자는 `real`이 아니라 `derived`(방법 기록) 또는 배제.
- 유의하지 않은 결과도 그대로 보고한다. 과장 해석 금지.
- 자유응답 인용은 사람 검토로 동의·익명화를 확정한 뒤에만 승격한다.
