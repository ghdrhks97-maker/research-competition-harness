---
name: evidence-ledger-skill
description: 모든 주장에 증거를 연결하고 real/derived/placeholder/forbidden으로 판정한다. 증거 없는 수치·학생 발화가 최종본에 들어가는 것을 차단한다.
backing_command: rch check <workspace> [--final]
---

# evidence-ledger-skill

## 언제 쓰나
lane 산출물을 병합하기 전, 그리고 최종 후보를 확정하기 전 항상.

## 무엇을 하나
- 각 lane의 `claim-ledger.json`을 검사한다.
- claim 상태를 강제한다: `real`(직접 확인), `derived`(계산·도출, 방법 기록), `placeholder`(초안 전용), `forbidden`(반영 금지).
- `--final`에서는 `real`/`derived`만 허용하고, 각 claim의 evidence 경로 파일이 실제 존재하는지 확인한다.
- `bundle-manifest.json`의 SHA-256과 source lane 누락, final 금지어(예정/추후/초안/미정/TODO)를 검사한다.

## 실행
```bash
rch check my-competition          # 상시 검사
rch check my-competition --final  # 최종 후보 규칙
```

## 판정 규칙
- 증거 없는 학생 반응·설문 수치·수업 결과·확산 실적은 만들지 않는다.
- 불확실한 내용은 TODO가 아니라 `placeholder` claim으로 둔다.
- final 후보에는 `real`/`derived`만, 각 claim에 존재하는 evidence 경로가 있어야 한다.
