---
name: hancom-render-qa-skill
description: 빌드된 HWPX를 검증한다. OWPML 구조, section 분리, XML 적합성, 페이지 추정, 목차 번호, 표 흐름, 이미지 참조, 선택적 visual evidence를 확인한다.
backing_command: rch render-check <workspace> [--hwpx path] [--page-limit N] [--min-pages N] && rch visual-check <workspace>
---

# hancom-render-qa-skill

## 언제 쓰나
`build-hwpx` 직후. 최종 판정 전에 구조와 분량을 점검한다.

## 무엇을 하나
- `mimetype` 위치·무압축, 필수 OWPML 항목 존재, 모든 XML 파트의 적합성을 검사한다.
- `Contents/section*.xml` 전체를 검사해 표지·요약·목차·본문·부록 분리 여부를 본다.
- 제목/문단/표 수를 세고, 페이지 수를 추정해 제한(기본 25쪽)과 비교한다.
- 표의 행별 열 수 일관성, `rowCnt`, `colCnt` 일치를 확인한다.
- `output/toc.md`의 목차 항목을 본문 제목과 정규화 대조해 불일치를 보고한다.
- 가능하면 `visual-check`로 PDF/page evidence와 coverage metrics를 남긴다.

## 실행
```bash
rch render-check my-competition --page-limit 25 --min-pages 22
rch visual-check my-competition
```

산출물: `output/render-check.json`, `render-check.md`, `output/visual-check.json`, `visual-check.md`.

## 경계
- 구조 통과는 Hancom 실제 표시를 보장하지 않는다. 페이지 수는 추정치다.
- `visual-check`가 renderer 미설정으로 skipped면 최종 확인을 생략한 것이 아니다.
- 최종 확인은 사람이 Hancom/HOP에서 열어 페이지 수, 목차 번호, 표 흐름, 이미지 겹침을 직접 본다.
