---
name: evidence-ledger-skill
description: 모든 주장에 증거를 연결하고 real/derived/expected/placeholder/forbidden으로 판정한다. 증거 없는 수치·학생 발화가 최종본에 들어가는 것을 차단한다.
backing_command: rch check <workspace> [--final] [--allow-expected]
---

# evidence-ledger-skill

## 언제 쓰나
lane 산출물을 병합하기 전, 그리고 최종 후보를 확정하기 전 항상.

## 무엇을 하나
- 각 lane의 `claim-ledger.json`을 검사한다.
- claim 상태를 강제한다: `real`(직접 확인), `derived`(계산·도출, 방법 기록), `expected`(라벨링된 예상값·가상), `placeholder`(초안 구멍 전용), `forbidden`(반영 금지).
- `expected` claim은 text/notes에 "예상"/"가상" 라벨이 없으면 거부한다.
- `--final`에서는 `real`/`derived`만 허용하고, 각 claim의 evidence 경로 파일이 실제 존재하는지 확인한다.
- `--final --allow-expected`에서는 라벨링된 `expected`까지 허용하고, 교체 목록을 `output/expected-claims.md`에 남긴다. `placeholder`는 계속 차단한다.
- `bundle-manifest.json`의 SHA-256과 source lane 누락, final 금지어(예정/추후/초안/미정/TODO)를 검사한다.

## 실행
```bash
rch check my-competition                            # 상시 검사
rch check my-competition --final                    # 최종 후보 규칙 (실제 자료만)
rch check my-competition --final --allow-expected   # 예상값(가상) 포함 완성본
```

## 판정 규칙
- 증거 없는 학생 반응·설문 수치·수업 결과·확산 실적을 실제인 것처럼 만들지 않는다. 예상 결과는 "예상값(가상)" 라벨 + `expected`로만.
- 불확실한 내용은 TODO가 아니라 `placeholder` claim으로 둔다.
- final 후보에는 `real`/`derived`만(예상값 완성본은 `--allow-expected`로 `expected`까지), `real`/`derived` claim에는 존재하는 evidence 경로가 있어야 한다.
