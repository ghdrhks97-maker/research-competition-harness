from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rch.cli import check_workspace, create_lane, init_workspace


class CliTests(unittest.TestCase):
    def test_init_and_lane_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            create_lane(workspace, "brainstorm", "codex")
            lane = workspace / "lanes" / "brainstorm" / "codex"

            self.assertTrue((lane / "lane-input.md").exists())
            self.assertTrue((lane / "evidence").is_dir())

    def test_final_check_rejects_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            create_lane(workspace, "brainstorm", "codex")
            lane = workspace / "lanes" / "brainstorm" / "codex"

            (lane / "lane-output.md").write_text("draft", encoding="utf-8")
            (lane / "lane-output.json").write_text(
                json.dumps({"lane": "brainstorm", "agent": "codex", "summary": "s", "artifacts": []}),
                encoding="utf-8",
            )
            (lane / "claim-ledger.json").write_text(
                json.dumps({"claims": [{"id": "c1", "text": "unsupported", "status": "placeholder"}]}),
                encoding="utf-8",
            )
            (lane / "verdict.json").write_text(
                json.dumps({"status": "needs-work", "reason": "placeholder"}),
                encoding="utf-8",
            )

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("not allowed" in err for err in result.errors))
