# MCP 서버로 Claude Code / Codex에서 쓰기

하네스를 CLI로 직접 돌리는 대신, **Claude Code나 Codex가 하네스 기능을 도구(tool)로 호출**하게 하려면 MCP 서버를 씁니다. 제어 방향이 바뀝니다.

```
Claude Code / Codex  ──MCP 도구 호출──▶  rch 엔진(brainstorm/import_survey/draft/build_hwpx…)
```

## 설치

```bash
pip install -e ".[mcp]"     # mcp 패키지 포함 설치
# 확인: rch-mcp 이 PATH에 생김 (stdio MCP 서버)
```

## 노출되는 도구

| 도구 | 하는 일 |
| --- | --- |
| `init(workspace)` | 작업공간 생성 |
| `brainstorm(workspace, major, level?, class_context?, interests?, tools?, competency?, constraints?)` | 인터뷰 답 → 트렌드·주제·제목 → input/ideas |
| `research_background(workspace, query?, max_results?, offline?)` | 공개 route scheduler로 이론적 배경·선행연구 후보 수집 |
| `import_survey(workspace, survey_path)` | 사전·사후 설문 익명 분석 |
| `import_photos(workspace)` | 사진 개인정보 점검표 |
| `mine_references(workspace)` | 레퍼런스 구조 추출 |
| `draft(workspace)` | I~V장 본문·요약·목차·부록 초안 |
| `assemble(workspace)` | 번들 조립 |
| `check(workspace, final?)` | 계약·증거·금지어 검증 |
| `build_hwpx(workspace, output?)` | HWPX 렌더 |
| `render_check(workspace, hwpx?, page_limit?)` | HWPX 구조·페이지 검증 |
| `revise_loop(workspace)` | 피드백 백로그 통합 |

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

> "`2026-대회` 작업공간 만들고, 전공은 과학, 관심은 AI·탐구로 브레인스토밍해줘. 배경지식과 선행연구도 리서치하고, 그다음 `~/survey.csv` 설문 분석하고 초안까지 만들어줘."

에이전트가 순서대로 `init → brainstorm → research_background → import_survey → draft → assemble → check`를 도구로 호출합니다.

## 참고

- MCP 서버는 CLI(`rch ...`)와 **같은 엔진**을 공유합니다. 둘 중 편한 쪽을 쓰면 됩니다.
- 증거 없는 수치·학생 발화·사진 차단 등 안전 규칙은 도구 안에서도 그대로 적용됩니다.
- 이 모델에서는 하네스가 외부 AI를 부르지 않습니다(운전자는 Claude Code/Codex). 따라서 `rch agents ...`(하네스가 AI를 호출하는 기능)는 헤드리스 자동화용으로만 남습니다.
