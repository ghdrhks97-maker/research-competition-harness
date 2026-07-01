---
name: summary-toc-appendix-skill
description: 요약서, 목차, 부록을 자동 생성하고 본문 claim과 불일치를 검사한다.
backing_command: rch draft <workspace> && rch assemble <workspace>
---

# summary-toc-appendix-skill

## 언제 쓰나
본문 초안이 만들어진 뒤. 요약서/목차/부록을 본문과 정합적으로 맞춘다.

## 무엇을 하나
- 요약서: 제목, 문제의식, 수업 모형, 실천과제, 핵심 결과를 압축한다. 핵심 결과는 설문 분석 표를 재사용한다.
- 목차: 권장 목차로 I~V장 항목을 세우고, 페이지 번호는 `build-hwpx`/`render-check` 이후로 미룬다.
- 부록: 사진 매니페스트의 부록 배치 후보와 과정안/루브릭/활동지/설문지/산출물 항목을 정리한다.
- `render-check`가 목차 항목과 본문 제목을 정규화해 불일치를 보고한다.

## 실행
```bash
rch draft my-competition        # summary-sheet/toc-builder/appendix-builder 초안 생성
rch assemble my-competition     # output/summary-sheet.md, toc.md, appendix.md
rch render-check my-competition # 목차-본문 제목 일치 검사
```

## 금지선
- 요약서에 본문보다 센 주장을 쓰지 않는다.
- 확인 전(`unreviewed`)·고위험 사진을 부록에 넣지 않는다.
- 목차와 본문 제목이 다르면 최종 후보로 보내지 않는다.
