# MCP 서버로 Claude Code / Codex / AGY에서 쓰기

하네스를 CLI로 직접 돌리는 대신, **Claude Code, Codex, AGY가 하네스 기능을 도구(tool)로 호출**하게 하려면 MCP 서버를 씁니다. 제어 방향이 바뀝니다.

```
Claude Code / Codex / AGY  ──MCP 도구 호출──▶  rch 엔진(agent_harness/next/check/build_hwpx…)
```

## 설치

```bash
pip install -e ".[mcp]"     # mcp 패키지 포함 설치
# 확인: rch-mcp 이 PATH에 생김 (stdio MCP 서버)
```

## 노출되는 도구

| 도구 | 하는 일 |
| --- | --- |
| `agent_harness(workspace, agents?, offline_research?)` | 에이전트 지휘용 conductor pack 생성 |
| `go(workspace, competition_name?, major?, rule_files?, ...)` | 레거시 skeleton 생성기. `skeleton=true` 없으면 거부. 완성 보고서용 아님 |
| `init(workspace)` | 작업공간 생성 |
| `import_rules(workspace, rule_files)` | 첨부/로컬 대회 공문·심사표·보고서 양식 파일을 `input/rules`에 저장 |
| `brainstorm(workspace, major, competition_name?, level?, class_context?, interests?, tools?, competency?, constraints?)` | 대회명·인터뷰 답 → 동향·주제·제목 → input/ideas |
| `research_background(workspace, query?, max_results?, offline?)` | 공개 route scheduler로 이론적 배경·선행연구 후보 수집 |
| `import_survey(workspace, survey_path)` | 사전·사후 설문 익명 분석 |
| `import_photos(workspace)` | 사진 개인정보 점검표 |
| `mine_references(workspace)` | 레퍼런스 구조 추출 |
| `draft(workspace)` | I~V장 본문·요약·목차·부록 초안 |
| `assemble(workspace)` | 번들 조립 |
| `check(workspace, final?, allow_expected?)` | 계약·증거·금지어 검증. `allow_expected`는 라벨링된 예상값(`expected`) 주장을 final에서 허용 |
| `build_hwpx(workspace, output?, force?)` | final gate와 품질 gate 통과 bundle만 HWPX 렌더. 중간 확인만 `force=true` |
| `render_check(workspace, hwpx?, page_limit?)` | HWPX 구조·페이지 검증 |
| `revise_loop(workspace)` | 피드백 백로그 통합 |
| `next(workspace)` | autopilot: 다음 작업(위임/명령)을 결정적으로 판정. `needs_user`가 비면 actions 실행 후 재호출, `done=true`까지 반복 |

모든 도구는 첫 인자로 작업공간 경로를 받고 JSON 결과를 돌려줍니다.

## Claude Code 등록

프로젝트 루트에 `.mcp.json`:

```json
{
  "mcpServers": {
    "rch": {
      "command": "rch-mcp"
    }
  }
}
```

또는 CLI로:

```bash
claude mcp add rch -- rch-mcp
```

전역 설치를 안 했다면 모듈 실행 형태로:

```json
{
  "mcpServers": {
    "rch": {
      "command": "python3",
      "args": ["-m", "rch.mcp_server"],
      "env": { "PYTHONPATH": "/path/to/research-competition-harness/src" }
    }
  }
}
```

## Codex 등록

`~/.codex/config.toml`:

```toml
[mcp_servers.rch]
command = "rch-mcp"

# 전역 설치를 안 했다면:
# command = "python3"
# args = ["-m", "rch.mcp_server"]
# env = { PYTHONPATH = "/path/to/research-competition-harness/src" }
```

## 사용 예 (에이전트 대화)

에이전트 지휘 실행:

> "`2026-대회` 작업공간을 만들고, 첨부한 공문·심사표·양식은 `import_rules`로 저장해. 그다음 `agent_harness`로 conductor pack을 만들고, 계획 승인 뒤 `next`를 반복 호출해서 done까지 진행해."

자료가 있는 경우 세부 실행:

> "`2026-대회` 작업공간 만들고, 참가 대회는 과학전람회, 전공은 과학, 관심은 AI·탐구로 브레인스토밍해줘. 첨부한 양식 파일은 `import_rules`로 저장하고, 배경지식과 선행연구도 리서치하고, 그다음 `~/survey.csv` 설문 분석하고 초안까지 만들어줘."

에이전트가 순서대로 `init/import_rules → agent_harness → next 루프 → assemble/check/build_hwpx/render_check`를 도구로 호출합니다. 리서치·사진 판정·본문 집필은 AGENTS.md 역할 정의대로 에이전트가 직접 수행합니다.

`go`는 레거시 skeleton 생성기입니다. `skeleton=true` 없이는 거부되며, 완성 보고서에는 쓰지 않습니다.

## 참고

- MCP 서버는 CLI(`rch ...`)와 **같은 엔진**을 공유합니다. 둘 중 편한 쪽을 쓰면 됩니다.
- 증거 없는 수치·학생 발화·사진 차단 등 안전 규칙은 도구 안에서도 그대로 적용됩니다.
- 이 모델에서는 하네스가 외부 AI를 부르지 않습니다(운전자는 Claude Code/Codex). 따라서 `rch agents ...`(하네스가 AI를 호출하는 기능)는 헤드리스 자동화용으로만 남습니다.
