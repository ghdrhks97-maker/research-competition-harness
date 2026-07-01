---
name: reference-report-miner-skill
description: 우수 보고서(md/txt/hwpx)에서 목차, 표 밀도, 결과 제시 방식, 부록 패턴을 추출한다. 문장 복사 금지, 구조만 추출.
backing_command: rch mine-references <workspace>
---

# reference-report-miner-skill

## 언제 쓰나
`input/references/`에 우수 보고서를 넣은 뒤. 본문 골격을 세우기 전.

## 무엇을 하나
- 텍스트 추출 가능한 레퍼런스(`.md`, `.txt`, `.hwpx` 섹션 텍스트)를 읽는다.
- 목차 후보, 제목 수, 표 행 수, 그림 언급, 결과 신호, 부록 유무 같은 **구조 지표**만 뽑는다.
- 레퍼런스들의 제목 밀도·부록 유무로 권장 목차를 제안한다.
- PDF는 텍스트로 export 후 다시 실행하도록 안내한다(추측하지 않음).

## 실행
```bash
rch mine-references my-competition
```

산출물: `input/references/analysis/reference-pattern.json`, `recommended-outline.md`.

## 금지선
- 레퍼런스 문장·캡션·표 내용을 복사하지 않는다. 목차·표 밀도·부록 구성 같은 구조만 참고한다.
- 확인 불가한 추출 내용은 읽지 못함으로 표시한다.
