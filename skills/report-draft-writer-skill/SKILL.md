---
name: report-draft-writer-skill
description: lane 산출물과 분석 결과로 I~V장 보고서 본문 초안을 표 중심으로 생성한다. 최종 진술형, 금지어 없음, 미확정 내용은 placeholder claim으로 표시.
backing_command: rch draft <workspace>
---

# report-draft-writer-skill

## 언제 쓰나
`import-survey`, `import-photos`, `mine-references`, brainstorm lane이 채워진 뒤. 본문·요약서·목차·부록 초안을 한 번에 만든다.

## 무엇을 하나
- `mine-references`의 권장 목차로 I~V장 골격을 세운다.
- IV장 결과에 설문 분석 표를 그대로 삽입하고, 해당 수치를 `derived` claim으로 연결한다.
- 확인할 수 없는 서술은 `placeholder` claim으로 명시해 사람/에이전트가 채우게 한다.
- 결과를 네 개 쓰기 lane(`draft-writer`, `summary-sheet`, `toc-builder`, `appendix-builder`)에 `harness-draft` 에이전트로 기록해 `assemble`이 바로 집게 한다.

## 실행
```bash
rch draft my-competition
rch assemble my-competition
rch check my-competition
```

## 금지선
- 본문에 예정/추후/초안/미정/TODO를 쓰지 않는다.
- 표가 말하고 본문이 해석하는 구조를 유지한다.
- 초안은 일부러 final-clean이 아니다. placeholder 해소는 품질 루프(`revise-loop`)가 담당한다.
