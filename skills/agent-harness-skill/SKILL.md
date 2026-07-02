---
name: agent-harness-skill
description: Codex/Claude/AGY가 다음 연구대회 보고서 제작을 지휘하도록 conductor pack을 만든다.
backing_command: rch agent-harness <workspace> --agent codex --agent claude
---

# agent-harness-skill

## 언제 쓰나
새 연구대회 작업공간을 만들었거나, 대회 양식·증거·레퍼런스가 뒤섞여 있어 에이전트가 어디서 시작해야 할지 정해야 할 때 쓴다.

## 무엇을 하나
- 현재 workspace 입력 상태를 읽는다.
- 누락된 대회명, 규정, 증거, 설문, 사진, 레퍼런스를 collection kit로 정리한다.
- lane 실행 순서와 CLI 명령을 conductor prompt로 만든다.
- claim-ledger, 심사표, page budget, Hancom/HOP render gate를 품질 gate로 고정한다.
- 설문 수치, 학생 인용, 사진, 점수, 확산 실적을 꾸며내지 못하게 anti-fabrication rule을 함께 넣는다.

## 실행
```bash
rch agent-harness my-competition --agent codex --agent claude --offline-research
```

산출물:

```text
output/agent-harness.json
output/agent-harness.md
prompts/conductor/agent-harness.md
```

## 경계
이 스킬은 지휘 표면을 만든다. 누락 자료를 대신 만들지 않는다. `final_candidate_ready=false`가 나오면 먼저 collection kit를 채운다.
