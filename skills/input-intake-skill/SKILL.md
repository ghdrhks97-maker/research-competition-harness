---
name: input-intake-skill
description: 공문, 심사표, 보고서 양식, 아이디어, 사진, 설문, 활동지를 자동 분류하고 개인정보 위험을 표시한다.
backing_command: rch run-lanes <workspace> <agent> --lanes intake
---

# input-intake-skill

## 언제 쓰나
새 자료를 `input/`에 넣은 직후. 이후 분석 스킬(import-survey/import-photos/mine-references)로 넘기기 전 분류·개인정보 점검.

## 무엇을 하나
- 자료를 report fact / student evidence / visual evidence / reference pattern / appendix candidate로 나눈다.
- 학생 이름·얼굴·학번·연락처·학교 외부 공개 위험을 표시한다.
- 확정 사실, 작성자 추정, 아이디어, 빈칸을 분리한다.
- 최종 반영 불가 자료는 `placeholder`/`forbidden`으로 표시한다.

## 실행
```bash
rch run-lanes my-competition codex --lanes intake   # intake 프롬프트 번들 생성
# 이어서 자동 분석:
rch import-rules my-competition input/rules/<file>.hwpx
rch import-survey my-competition input/surveys/<file>.csv
rch import-photos my-competition
rch mine-references my-competition
```

## 금지선
- 사진은 설명 가능성보다 개인정보 위험을 먼저 본다.
- 설문 숫자는 원자료·계산식 없으면 real로 두지 않는다.
