---
name: photo-privacy-curator-skill
description: 수업사진의 얼굴/이름/학번/개인화면 위험을 점검하고 본문용/요약서용/부록용/제외용으로 분류한다. 필요 시 블러 지시.
backing_command: rch import-photos <workspace>
---

# photo-privacy-curator-skill

## 언제 쓰나
`input/photos/`에 사진을 넣은 뒤. 본문·부록에 사진을 배치하기 전.

## 무엇을 하나
- 사진 폴더를 스캔해 매니페스트(SHA-256, 크기)와 개인정보 점검표를 만든다.
- 하네스는 픽셀을 볼 수 없으므로 기본값은 안전 우선(`unreviewed`, 블러 필요, 사용 보류)이다.
- 파일명 신호로 위험도 힌트를 준다(얼굴/명단/이름 → high, 결과물/화면 → low).
- 배치를 제안한다: low → 본문, unreviewed → 부록, high → 제외.

## 실행
```bash
rch import-photos my-competition
```

산출물: `input/photos/analysis/photo-manifest.json`, `privacy-checklist.md`, `claim-ledger.json`.

## 금지선
- 확인 전(`unreviewed`)·고위험 사진은 본문/요약서/부록에 넣지 않는다.
- 사람이 얼굴·이름표·학번·개인화면 노출을 직접 확인하고 위험 사진은 블러·크롭 후 `low`로 갱신한다.
- 사진으로 확인되지 않는 수업 효과를 설명하지 않는다.
