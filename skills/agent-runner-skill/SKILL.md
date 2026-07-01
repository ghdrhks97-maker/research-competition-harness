---
name: agent-runner-skill
description: 외부 에이전트 CLI(Codex/Antigravity/Claude/Gemini)를 실제로 실행해 설치·로그인을 자동 확인하고 lane 프롬프트를 호출한다.
backing_command: rch agents preflight <workspace> · rch agents run <workspace> <agent> --lanes ...
---

# agent-runner-skill

## 언제 쓰나
하네스를 돌리는 초기 단계. lane을 외부 에이전트에 배정하기 전에 설치·로그인을 확인하고, 확인되면 실제로 호출한다.

## 무엇을 하나
- 각 에이전트 CLI의 설치 여부(`shutil.which`)와 버전을 확인한다.
- 로그인 확인 명령을 실행하고 **실제 종료 코드**로 상태를 판정한다: `authenticated`/`unauthenticated`/`not_installed`/`unknown`.
- `run-lanes`가 만든 프롬프트를 에이전트 CLI로 넘겨 응답(`agent-response.md`)을 수집한다.
- 로그인되지 않은 에이전트로는 호출을 차단한다.

## 실행
```bash
rch agents preflight my-competition --strict          # 미로그인 시 exit 1
rch run-lanes my-competition codex --lanes draft-writer --execute
rch agents run my-competition gemini --lanes critic
rch agents list                                        # 기본 레지스트리 확인
```

## 설정
CLI마다 하위 명령이 다르므로 환경변수로 조정한다(기본값은 best-effort 추정치):
`RCH_AGENT_<NAME>_BIN`, `_VERSION_ARGS`, `_AUTH_ARGS`(종료코드 0=로그인), `_RUN_ARGS`(`{prompt}`/`{prompt_file}` 치환).

## 경계
- 로그인 상태를 꾸며내지 않는다. 확인 명령이 없으면 `unknown`으로 보고한다.
- 에이전트 응답은 자유 서술이다. lane 계약 파일(`lane-output.json`/`claim-ledger.json`/`verdict.json`)은 에이전트가 이어서 채워야 파이프라인에 반영된다.
