---
name: hwpx-finalizer-skill
description: 조립된 markdown bundle을 HWPX(OWPML zip)로 렌더한다. 제목 스타일, 표, 이미지, 목차 문단을 삽입한다. 한 주체만 조립한다.
backing_command: rch build-hwpx <workspace> [--output path.hwpx]
---

# hwp/hwpx-finalizer-skill

## 언제 쓰나
`assemble`로 최종 bundle이 만들어지고 `check --final`을 통과할 상태일 때. HWPX 조립은 한 주체만 수행한다.

## 무엇을 하나
- `output/report-draft.md`, `summary-sheet.md`, `toc.md`, `appendix.md`를 하나의 HWPX로 렌더한다.
- markdown 블록을 OWPML로 매핑한다: 제목 → 문단 모양(paraPr) 스타일, 문단 → 본문, GFM 표 → `hp:tbl`, 목록 → 불릿 문단.
- 이미지 파일은 `BinData/`에 넣고 캡션 문단으로 참조한다.
- `mimetype`을 zip 첫 항목·무압축으로 저장하고 `Contents/header.xml`에 폰트/글자/문단/테두리 참조를 정의한다.

## 실행
```bash
rch build-hwpx my-competition --output my-competition/output/report.hwpx
```

## 경계
- 이 스킬은 구조적으로 유효한 OWPML 컨테이너를 만든다. Hancom 실제 표시는 `render-check`와 사람이 Hancom/HOP에서 최종 확인한다.
- 여러 에이전트가 같은 HWPX를 동시에 수정하지 않는다.
