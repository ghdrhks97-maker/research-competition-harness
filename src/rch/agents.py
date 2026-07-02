"""External agent runner (`rch agents ...`).

Actually shells out to the external agent CLIs — Codex, Claude,
Antigravity — to (1) confirm each is installed, (2) verify the user is
logged in, and (3) dispatch a lane prompt to a chosen agent and capture
its response.

The harness cannot know every CLI's exact subcommands (they change), so
each agent's binary and its version / auth / run arguments are configurable
through environment variables. The built-in defaults are best-effort
guesses; when a check cannot be run the harness reports `unknown` instead
of pretending. Nothing here fabricates a login state — every status comes
from a real process exit code.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 20
RUN_TIMEOUT = 600


@dataclass
class AgentSpec:
    name: str
    default_bin: str
    version_args: list[str]
    # Empty auth_args means "no known login-check command"; status -> unknown.
    auth_args: list[str]
    run_args: list[str]  # may contain the {prompt} placeholder


# Best-effort defaults. Override per environment with, e.g.,
#   RCH_AGENT_CODEX_BIN, RCH_AGENT_CODEX_AUTH_ARGS, RCH_AGENT_CODEX_RUN_ARGS
AGENT_REGISTRY: dict[str, AgentSpec] = {
    "codex": AgentSpec("codex", "codex", ["--version"], ["login", "status"], ["exec", "{prompt}"]),
    "claude": AgentSpec("claude", "claude", ["--version"], [], ["-p", "{prompt}"]),
    "antigravity": AgentSpec("antigravity", "antigravity", ["--version"], [], ["{prompt}"]),
}

STATUS_NOT_INSTALLED = "not_installed"
STATUS_AUTHENTICATED = "authenticated"
STATUS_UNAUTHENTICATED = "unauthenticated"
STATUS_UNKNOWN = "unknown"

# Usage isolation: when the harness itself is running inside an agent app,
# LLM work must stay on that app's own quota. Cross-calling a *different*
# agent CLI is refused unless the user opts in with RCH_ALLOW_CROSS_AGENT=1.
HOST_RUNTIME_ENV = "RCH_HOST_RUNTIME"
ALLOW_CROSS_AGENT_ENV = "RCH_ALLOW_CROSS_AGENT"
_HOST_ENV_HINTS: dict[str, tuple[str, ...]] = {
    "claude": ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT"),
    "codex": ("CODEX_SANDBOX", "CODEX_HOME", "CODEX_THREAD_ID", "CODEX_PROXY_PORT"),
    "antigravity": ("ANTIGRAVITY", "ANTIGRAVITY_HOME", "ANTIGRAVITY_AGENT"),
}


def detect_host_runtime() -> str | None:
    """Best-effort detection of the agent app this process is running inside."""
    override = os.environ.get(HOST_RUNTIME_ENV, "").strip().lower()
    if override in AGENT_REGISTRY:
        return override
    if override == "none":
        return None
    for runtime, hints in _HOST_ENV_HINTS.items():
        if any(os.environ.get(hint) for hint in hints):
            return runtime
    return None


def cross_agent_refusal(agent: str) -> str | None:
    """Return a refusal message when calling `agent` would spend another app's quota."""
    if os.environ.get(ALLOW_CROSS_AGENT_ENV, "").strip().lower() in {"1", "true", "yes"}:
        return None
    host = detect_host_runtime()
    if host is None or agent == host:
        return None
    return (
        f"사용량 격리: 현재 {host} 런타임 안에서 실행 중이므로 {agent} CLI 교차 호출을 막았습니다. "
        f"LLM 작업은 구동 런타임({host})의 서브에이전트로 수행하세요. "
        f"정말 교차 호출하려면 {ALLOW_CROSS_AGENT_ENV}=1 로 실행하세요."
    )


@dataclass
class AgentStatus:
    agent: str
    bin: str
    installed: bool
    version: str
    login_status: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreflightReport:
    agents: list[AgentStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"agents": [status.to_dict() for status in self.agents]}

    def all_ready(self) -> bool:
        return bool(self.agents) and all(
            status.login_status == STATUS_AUTHENTICATED for status in self.agents
        )


def _env(agent: str, key: str) -> str | None:
    return os.environ.get(f"RCH_AGENT_{agent.upper()}_{key}")


def _resolve_bin(spec: AgentSpec) -> str:
    return _env(spec.name, "BIN") or spec.default_bin


def _resolve_args(spec: AgentSpec, key: str, default: list[str]) -> list[str]:
    override = _env(spec.name, key)
    if override is None:
        return default
    return override.split()


def _run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def check_agent(agent: str) -> AgentStatus:
    if agent not in AGENT_REGISTRY:
        raise SystemExit(f"unknown agent: {agent}")
    spec = AGENT_REGISTRY[agent]
    binary = _resolve_bin(spec)

    resolved = shutil.which(binary)
    if resolved is None:
        return AgentStatus(
            agent=agent,
            bin=binary,
            installed=False,
            version="",
            login_status=STATUS_NOT_INSTALLED,
            detail=f"'{binary}' PATH에 없음. 설치 후 다시 실행하거나 RCH_AGENT_{agent.upper()}_BIN으로 경로 지정.",
        )

    version_args = _resolve_args(spec, "VERSION_ARGS", spec.version_args)
    _, version_out, _ = _run([binary, *version_args], DEFAULT_TIMEOUT)
    version = version_out.splitlines()[0] if version_out else ""

    auth_args = _resolve_args(spec, "AUTH_ARGS", spec.auth_args)
    if not auth_args:
        return AgentStatus(
            agent=agent,
            bin=binary,
            installed=True,
            version=version,
            login_status=STATUS_UNKNOWN,
            detail=f"로그인 확인 명령 미설정. RCH_AGENT_{agent.upper()}_AUTH_ARGS로 지정하면 자동 확인.",
        )

    code, out, err = _run([binary, *auth_args], DEFAULT_TIMEOUT)
    if code == 0:
        status = STATUS_AUTHENTICATED
        detail = out.splitlines()[0] if out else "로그인 확인됨."
    elif code in {124, 127}:
        status = STATUS_UNKNOWN
        detail = err or "확인 실패."
    else:
        status = STATUS_UNAUTHENTICATED
        detail = (out or err or "로그인되지 않음.").splitlines()[0]
    return AgentStatus(
        agent=agent,
        bin=binary,
        installed=True,
        version=version,
        login_status=status,
        detail=detail,
    )


def preflight(agents: list[str] | None = None) -> PreflightReport:
    selected = agents or list(AGENT_REGISTRY)
    report = PreflightReport()
    for agent in selected:
        report.agents.append(check_agent(agent))
    return report


def render_preflight_markdown(report: PreflightReport) -> str:
    lines = [
        "# 에이전트 사전 점검",
        "",
        "| 에이전트 | 설치 | 버전 | 로그인 | 비고 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for status in report.agents:
        lines.append(
            f"| {status.agent} | {'예' if status.installed else '아니오'} | {status.version or '-'} "
            f"| {status.login_status} | {status.detail} |"
        )
    lines.append("")
    lines.append("환경변수로 명령을 조정할 수 있습니다: "
                 "`RCH_AGENT_<NAME>_BIN`, `_VERSION_ARGS`, `_AUTH_ARGS`, `_RUN_ARGS`.")
    lines.append("")
    return "\n".join(lines)


def run_preflight(workspace: Path, agents: list[str] | None = None) -> PreflightReport:
    report = preflight(agents)
    output_dir = workspace / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "agent-preflight.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "agent-preflight.md").write_text(
        render_preflight_markdown(report), encoding="utf-8"
    )
    return report


@dataclass
class RunResult:
    agent: str
    lane: str
    ok: bool
    response_path: str
    detail: str


def run_agent_on_lane(
    workspace: Path, agent: str, lane: str, timeout: int = RUN_TIMEOUT
) -> RunResult:
    if agent not in AGENT_REGISTRY:
        raise SystemExit(f"unknown agent: {agent}")
    refusal = cross_agent_refusal(agent)
    if refusal:
        return RunResult(agent, lane, False, "", refusal)
    spec = AGENT_REGISTRY[agent]
    binary = _resolve_bin(spec)

    prompt_path = workspace / "prompts" / agent / f"{lane}.md"
    if not prompt_path.exists():
        raise SystemExit(f"prompt not found: {prompt_path}. `rch run-lanes` 먼저 실행.")

    status = check_agent(agent)
    if not status.installed:
        return RunResult(agent, lane, False, "", status.detail)
    if status.login_status == STATUS_UNAUTHENTICATED:
        return RunResult(agent, lane, False, "", "로그인되지 않음. 먼저 로그인하세요.")

    prompt_text = prompt_path.read_text(encoding="utf-8")
    run_args = _resolve_args(spec, "RUN_ARGS", spec.run_args)
    cmd = [binary] + [
        arg.replace("{prompt}", prompt_text).replace("{prompt_file}", str(prompt_path))
        for arg in run_args
    ]
    code, out, err = _run(cmd, timeout)

    lane_dir = workspace / "lanes" / lane / agent
    lane_dir.mkdir(parents=True, exist_ok=True)
    response_path = lane_dir / "agent-response.md"
    stderr_block = f"\n\nSTDERR:\n{err}" if err else ""
    response_path.write_text(
        f"# {agent} / {lane} 응답\n\n(exit={code})\n\n{out}{stderr_block}\n",
        encoding="utf-8",
    )
    ok = code == 0
    detail = "응답 저장됨. 에이전트가 lane 계약 파일(lane-output.json/claim-ledger.json/verdict.json)을 채워야 함." if ok else (err or "실행 실패")
    return RunResult(agent, lane, ok, response_path.relative_to(workspace).as_posix(), detail)
