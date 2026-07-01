---
name: table-layout-compressor-skill
description: 긴 문단을 표·카드·비교표로 바꾸고 25쪽 제한 기준으로 압축한다. 표 잘림/중복/빈말을 제거한다.
backing_command: rch render-check <workspace> --page-limit 25 (분량 신호) + table-layout lane
---

# table-layout-compressor-skill

## 언제 쓰나
본문 초안이 길어졌을 때, 그리고 HWPX 빌드 후 분량이 제한을 넘을 때.

## 무엇을 하나
- 긴 설명을 3~5열 표나 단계 카드로 바꾸되, 표가 페이지 하단에서 잘리지 않게 한다.
- 표 바로 뒤에 해석 문단을 붙여 흐름이 끊기지 않게 한다.
- 표 제목/캡션/번호 규칙을 통일하고 빈 수식어를 줄인다.
- `render-check`의 페이지 추정과 표 무결성 경고를 압축 목표로 삼는다.

## 실행
```bash
rch build-hwpx my-competition
rch render-check my-competition --page-limit 25   # 추정 페이지 초과 시 경고
```
경고를 `revise-loop`로 모아 `table-layout` lane에서 압축을 반영한다.

## 금지선
- 표를 늘려 독해를 방해하지 않는다.
- 표/그림 분할, orphan heading, 하단 잘림을 finalizer에 떠넘기지 않는다.
