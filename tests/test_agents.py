from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from rch import agents
from rch.cli import main


def _clear_env() -> None:
    for key in list(os.environ):
        if key.startswith("RCH_AGENT_"):
            del os.environ[key]
    for key in (agents.HOST_RUNTIME_ENV, agents.ALLOW_CROSS_AGENT_ENV):
        os.environ.pop(key, None)


class AgentPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_env()

    def tearDown(self) -> None:
        _clear_env()

    def test_not_installed_when_binary_missing(self) -> None:
        os.environ["RCH_AGENT_CODEX_BIN"] = "definitely-not-a-real-binary-xyz"
        status = agents.check_agent("codex")
        self.assertFalse(status.installed)
        self.assertEqual(status.login_status, agents.STATUS_NOT_INSTALLED)

    def test_authenticated_when_auth_command_succeeds(self) -> None:
        os.environ["RCH_AGENT_CODEX_BIN"] = "python3"
        os.environ["RCH_AGENT_CODEX_AUTH_ARGS"] = "-c pass"
        status = agents.check_agent("codex")
        self.assertTrue(status.installed)
        self.assertEqual(status.login_status, agents.STATUS_AUTHENTICATED)

    def test_unauthenticated_when_auth_command_fails(self) -> None:
        os.environ["RCH_AGENT_CODEX_BIN"] = "python3"
        os.environ["RCH_AGENT_CODEX_AUTH_ARGS"] = "-c raise SystemExit(1)"
        status = agents.check_agent("codex")
        self.assertTrue(status.installed)
        self.assertEqual(status.login_status, agents.STATUS_UNAUTHENTICATED)

    def test_unknown_when_no_auth_command(self) -> None:
        os.environ["RCH_AGENT_CLAUDE_BIN"] = "python3"
        # claude default auth_args is empty -> unknown
        status = agents.check_agent("claude")
        self.assertEqual(status.login_status, agents.STATUS_UNKNOWN)

    def test_preflight_writes_report_and_strict_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            os.environ["RCH_AGENT_CODEX_BIN"] = "python3"
            os.environ["RCH_AGENT_CODEX_AUTH_ARGS"] = "-c pass"
            code = main(["agents", "preflight", str(workspace), "--agents", "codex", "--strict"])
            self.assertEqual(code, 0)
            self.assertTrue((workspace / "output" / "agent-preflight.json").exists())
            self.assertTrue((workspace / "output" / "agent-preflight.md").exists())

    def test_strict_exit_nonzero_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["RCH_AGENT_CODEX_BIN"] = "definitely-not-a-real-binary-xyz"
            code = main(["agents", "preflight", tmp, "--agents", "codex", "--strict"])
            self.assertEqual(code, 1)


class AgentRunTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_env()
        # The test process may itself run inside an agent app (e.g. Claude
        # Code sets CLAUDECODE); pin detection off so cross-agent runs work.
        os.environ[agents.HOST_RUNTIME_ENV] = "none"

    def tearDown(self) -> None:
        _clear_env()

    def test_run_agent_captures_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            prompt_dir = workspace / "prompts" / "codex"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "survey-analyzer.md").write_text("do the analysis", encoding="utf-8")

            stub = workspace / "stub.sh"
            stub.write_text(
                '#!/bin/sh\nif [ "$1" = "auth-ok" ]; then exit 0; fi\necho "STUB RESPONSE"\n',
                encoding="utf-8",
            )
            stub.chmod(0o755)
            os.environ["RCH_AGENT_CODEX_BIN"] = str(stub)
            os.environ["RCH_AGENT_CODEX_AUTH_ARGS"] = "auth-ok"
            os.environ["RCH_AGENT_CODEX_RUN_ARGS"] = "run {prompt}"

            result = agents.run_agent_on_lane(workspace, "codex", "survey-analyzer")
            self.assertTrue(result.ok)
            response = (workspace / "lanes" / "survey-analyzer" / "codex" / "agent-response.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("STUB RESPONSE", response)

    def test_detect_host_runtime_override(self) -> None:
        os.environ[agents.HOST_RUNTIME_ENV] = "codex"
        self.assertEqual(agents.detect_host_runtime(), "codex")
        os.environ[agents.HOST_RUNTIME_ENV] = "none"
        self.assertIsNone(agents.detect_host_runtime())

    def test_cross_agent_run_is_refused_inside_another_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            prompt_dir = workspace / "prompts" / "codex"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "survey-analyzer.md").write_text("prompt", encoding="utf-8")
            os.environ[agents.HOST_RUNTIME_ENV] = "claude"

            result = agents.run_agent_on_lane(workspace, "codex", "survey-analyzer")
            self.assertFalse(result.ok)
            self.assertIn("사용량 격리", result.detail)
            self.assertFalse((workspace / "lanes" / "survey-analyzer" / "codex" / "agent-response.md").exists())

    def test_cross_agent_run_allowed_with_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            prompt_dir = workspace / "prompts" / "codex"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "survey-analyzer.md").write_text("prompt", encoding="utf-8")

            stub = workspace / "stub.sh"
            stub.write_text(
                '#!/bin/sh\nif [ "$1" = "auth-ok" ]; then exit 0; fi\necho "STUB RESPONSE"\n',
                encoding="utf-8",
            )
            stub.chmod(0o755)
            os.environ["RCH_AGENT_CODEX_BIN"] = str(stub)
            os.environ["RCH_AGENT_CODEX_AUTH_ARGS"] = "auth-ok"
            os.environ["RCH_AGENT_CODEX_RUN_ARGS"] = "run {prompt}"
            os.environ[agents.HOST_RUNTIME_ENV] = "claude"
            os.environ[agents.ALLOW_CROSS_AGENT_ENV] = "1"

            result = agents.run_agent_on_lane(workspace, "codex", "survey-analyzer")
            self.assertTrue(result.ok, result.detail)

    def test_run_blocks_when_unauthenticated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            prompt_dir = workspace / "prompts" / "codex"
            prompt_dir.mkdir(parents=True)
            (prompt_dir / "survey-analyzer.md").write_text("prompt", encoding="utf-8")
            os.environ["RCH_AGENT_CODEX_BIN"] = "python3"
            os.environ["RCH_AGENT_CODEX_AUTH_ARGS"] = "-c raise SystemExit(1)"
            result = agents.run_agent_on_lane(workspace, "codex", "survey-analyzer")
            self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
