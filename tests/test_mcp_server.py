from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rch import mcp_server


class McpOpsTests(unittest.TestCase):
    """Exercise the op_* functions directly (no mcp dependency required)."""

    def test_full_pipeline_ops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp) / "ws")

            self.assertTrue(mcp_server.op_init(workspace)["ok"])

            brain = mcp_server.op_brainstorm(
                workspace,
                "과학",
                competition_name="창의교육 연구대회",
                interests="AI, 탐구",
                competency="탐구력",
            )
            self.assertTrue(brain["recommended_title"])
            self.assertTrue((Path(workspace) / "input" / "ideas" / "brainstorm.json").exists())
            profile = Path(workspace) / "input" / "rules" / "competition-profile.json"
            self.assertIn("창의교육 연구대회", profile.read_text(encoding="utf-8"))

            form = Path(tmp) / "보고서_양식.hwpx"
            form.write_bytes(b"form")
            imported = mcp_server.op_import_rules(workspace, str(form))
            self.assertEqual(imported["files"][0]["kind"], "forms")

            survey = Path(tmp) / "s.csv"
            survey.write_text("문항_사전,문항_사후\n2,4\n3,5\n2,5\n", encoding="utf-8")
            result = mcp_server.op_import_survey(workspace, str(survey))
            self.assertEqual(result["respondents"], 3)

            mcp_server.op_import_photos(workspace)
            mcp_server.op_mine_references(workspace)
            background = mcp_server.op_research_background(workspace, query="과학 탐구 수업", offline=True)
            self.assertTrue(background["fallback_used"])

            drafted = mcp_server.op_draft(workspace)["drafted_lanes"]
            self.assertIn("draft-writer", drafted)

            mcp_server.op_assemble(workspace)
            self.assertTrue((Path(workspace) / "output" / "report-draft.md").exists())

            hwpx = mcp_server.op_build_hwpx(workspace)
            self.assertTrue(Path(hwpx["hwpx"]).exists())

            render = mcp_server.op_render_check(workspace)
            self.assertIn("estimated_pages", render)

            backlog = mcp_server.op_revise_loop(workspace)
            self.assertIn("tasks", backlog)

    def test_build_hwpx_requires_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp) / "ws")
            mcp_server.op_init(workspace)
            with self.assertRaises(ValueError):
                mcp_server.op_build_hwpx(workspace)

    def test_check_op_returns_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp) / "ws")
            mcp_server.op_init(workspace)
            result = mcp_server.op_check(workspace)
            self.assertIn("ok", result)
            self.assertIn("errors", result)

    def test_go_op_finishes_without_survey_or_photos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp) / "ws")
            result = mcp_server.op_go(
                workspace,
                competition_name="창의교육 연구대회",
                major="과학",
                interests="AI, 탐구",
                competency="탐구력",
                offline_research=True,
                survey_items=4,
                photo_count=2,
            )
            root = Path(workspace)
            self.assertIn("build-hwpx", result["steps"])
            self.assertTrue((root / "output" / "report.hwpx").exists())
            self.assertTrue(result["missing_inputs"])
            self.assertTrue((root / "input" / "surveys" / "analysis" / "survey-summary.md").exists())
            self.assertTrue((root / "input" / "photos" / "analysis" / "photo-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
