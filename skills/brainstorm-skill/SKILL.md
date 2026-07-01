---
name: brainstorm-skill
description: 하네스 시작 시 전공 교과를 묻고 교육 트렌드를 리서치해 가장 적합한 연구 주제와 보고서 제목을 브레인스토밍해 input/ideas/에 자동 작성한다. 사람이 ideas 파일을 직접 쓰지 않는다.
backing_command: rch brainstorm <workspace> [--answers file.json] [--agent <name>]
---

# brainstorm-skill

## 언제 쓰나
`rch init` 직후, 가장 먼저. 사람이 아이디어 파일을 손으로 만들 필요가 없도록 주제·제목을 자동 생성한다.

## 무엇을 하나
1. **인터뷰**: 전공 교과(필수), 학교급/학년, 학급 상황, 관심 트렌드, 활용 도구, 목표 역량, 제약을 묻는다.
2. **트렌드 리서치**: 전공 적합도·관심 키워드로 현재 한국 교육 트렌드를 정렬한다(AI 맞춤형, HTHT, 학생 주도성, 과정중심·개념기반, 디지털 시민성, 생태전환, STEAM, SEL, PBL, 데이터·컴퓨팅 등). `--agent`로 실제 에이전트 리서치 보강 가능.
3. **주제 합성**: 상위 트렌드 × 전공 × 역량으로 연구 주제 후보 3개를 점수와 함께 만들고 추천을 표시한다.
4. **제목 브레인스토밍**: 알파벳 약어형·한글 스토리형 제목 후보 5개를 만든다.
5. **자동 작성**: `input/ideas/`에 인터뷰·트렌드·주제·제목 파일과 `brainstorm.json`을 쓰고, 추천 제목을 `brainstorm` lane에 반영한다.
6. **선택 배경연구**: `--research-background`를 붙이면 주제 선정 직후 `rch research-background`를 이어 실행한다.

## 실행
```bash
rch brainstorm my-competition                      # 대화형
rch init my-competition --brainstorm               # init 직후 실행
rch brainstorm my-competition --answers a.json     # 비대화형(자동화/테스트)
rch brainstorm my-competition --agent claude       # 트렌드 리서치 보강
rch brainstorm my-competition --research-background # 주제 선정 후 이론적 배경·선행연구 수집
```

## 금지선
- 생성된 주제·제목은 확정 사실이 아니다. `placeholder` claim으로 들어가며 심사기준 대조·최종 선택은 사람이 한다.
- 멋진 제목보다 증거로 설명 가능한 구조를 우선한다.
- 트렌드 요약을 확인되지 않은 성과로 과장하지 않는다.
