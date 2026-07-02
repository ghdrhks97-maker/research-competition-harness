from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rch import agent_harness
from rch import mcp_server
from rch.brainstorm import run_brainstorm
from rch.cli import init_workspace, main
from rch.rules import import_rule_files


class AgentHarnessTests(unittest.TestCase):
    def test_empty_workspace_harness_is_honest_about_missing_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)

            result = agent_harness.generate_agent_harness(
                workspace,
                agents=("codex", "claude"),
                offline_research=True,
            )

            data = json.loads((workspace / "output" / "agent-harness.json").read_text(encoding="utf-8"))
            missing = {item["id"] for item in data["missing_inputs"]}

            self.assertEqual(result.json_path, "output/agent-harness.json")
            self.assertFalse(data["final_candidate_ready"])
            self.assertEqual(data["readiness"]["verdict"], "blocked_collect_inputs")
            self.assertGreaterEqual(
                missing,
                {"competition", "rules", "evidence", "survey", "photos", "reference"},
            )
            self.assertIn("수집", data["collection_kit"][0]["action"])
            self.assertTrue(any("설문 수치" in rule for rule in data["anti_fabrication_rules"]))
            self.assertTrue(any("학생 발화" in rule for rule in data["anti_fabrication_rules"]))
            self.assertTrue(any("사진" in rule for rule in data["anti_fabrication_rules"]))

    def test_cli_agent_harness_writes_pack_for_requested_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)

            exit_code = main(
                [
                    "agent-harness",
                    str(workspace),
                    "--agent",
                    "codex",
                    "--agent",
                    "claude",
                    "--offline-research",
                ]
            )

            data = json.loads((workspace / "output" / "agent-harness.json").read_text(encoding="utf-8"))
            prompt = (workspace / "prompts" / "conductor" / "agent-harness.md").read_text(encoding="utf-8")

            self.assertEqual(exit_code, 0)
            self.assertEqual(data["agents"], ["codex", "claude"])
            self.assertTrue((workspace / "output" / "agent-harness.md").exists())
            self.assertIn("--offline", " ".join(command["command"] for command in data["commands"]))
            self.assertIn("conductor", prompt.lower())
            self.assertIn("직접 가짜 증거를 만들지 않는다", prompt)
            for forbidden in ("예정", "추후", "보완 예정", "초안", "미정", "TODO"):
                self.assertNotIn(forbidden, prompt)

    def test_rule_and_brainstorm_workspace_preserves_inputs_and_render_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            rule = Path(tmp) / "심사표.pdf"
            rule.write_bytes(b"rubric")
            import_rule_files(workspace, [rule])
            run_brainstorm(
                workspace,
                answers={
                    "competition_name": "창의교육 연구대회",
                    "major": "과학",
                    "level": "중학교 2학년",
                    "interests": "AI, 탐구",
                    "competency": "탐구력",
                },
            )

            agent_harness.generate_agent_harness(workspace, agents=("codex",), offline_research=False)
            data = json.loads((workspace / "output" / "agent-harness.json").read_text(encoding="utf-8"))

            phase_ids = {phase["id"] for phase in data["phases"]}
            rule_paths = [item["stored_path"] for item in data["input_state"]["rules"]["files"]]
            gates = "\n".join(gate["name"] + " " + gate["check"] for gate in data["quality_gates"])

            self.assertGreaterEqual(
                phase_ids,
                {"intake", "research", "evidence", "reference", "draft", "design", "finalization", "hwpx"},
            )
            self.assertIn("input/rules/rubrics/심사표.pdf", rule_paths)
            self.assertEqual(data["input_state"]["competition"]["competition_name"], "창의교육 연구대회")
            self.assertIn("Hancom/HOP", gates)
            self.assertIn("page budget", gates)
            self.assertFalse(data["final_candidate_ready"])
            self.assertTrue(any(item["id"] == "evidence" for item in data["missing_inputs"]))

    def test_go_placeholders_do_not_satisfy_agent_harness_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            rule = Path(tmp) / "심사표.pdf"
            rule.write_bytes(b"rubric")

            exit_code = main(
                [
                    "go",
                    str(workspace),
                    "--competition-name",
                    "창의교육 연구대회",
                    "--major",
                    "과학",
                    "--rule-file",
                    str(rule),
                    "--offline-research",
                    "--survey-items",
                    "4",
                    "--photo-count",
                    "2",
                    "--skeleton",
                ]
            )
            result = agent_harness.generate_agent_harness(workspace, agents=("codex",), offline_research=True)
            data = json.loads((workspace / "output" / "agent-harness.json").read_text(encoding="utf-8"))
            missing = {item["id"] for item in data["missing_inputs"]}

            self.assertEqual(exit_code, 0)
            self.assertFalse(result.final_candidate_ready)
            self.assertFalse(data["final_candidate_ready"])
            self.assertFalse(data["final_check"]["ok"])
            self.assertIn("survey", missing)
            self.assertIn("photos", missing)
            self.assertEqual(data["input_state"]["survey"]["files"], [])
            self.assertEqual(data["input_state"]["photos"]["files"], [])
            self.assertTrue(data["input_state"]["survey"]["analysis"]["exists"])
            self.assertTrue(data["input_state"]["photos"]["manifest"]["data"]["missing_required"])

    def test_output_files_alone_do_not_make_final_candidate_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            rule = Path(tmp) / "심사표.pdf"
            rule.write_bytes(b"rubric")
            import_rule_files(workspace, [rule])
            run_brainstorm(
                workspace,
                answers={
                    "competition_name": "창의교육 연구대회",
                    "major": "과학",
                },
            )
            (workspace / "input" / "evidence" / "artifact.md").write_text("real artifact", encoding="utf-8")
            (workspace / "input" / "surveys" / "survey.csv").write_text("문항1_사전,문항1_사후\n3,4\n", encoding="utf-8")
            (workspace / "input" / "photos" / "photo.png").write_bytes(b"not-a-real-png")
            (workspace / "input" / "references" / "reference.md").write_text("# I. 구조\n", encoding="utf-8")
            output = workspace / "output"
            output.mkdir(exist_ok=True)
            for name in (
                "report-draft.md",
                "summary-sheet.md",
                "toc.md",
                "appendix.md",
                "finalization-checklist.md",
            ):
                (output / name).write_text("# filled\n", encoding="utf-8")
            (output / "bundle-manifest.json").write_text('{"files": [], "missing_sources": ["draft-writer"]}', encoding="utf-8")
            (output / "report.hwpx").write_bytes(b"placeholder-hwpx")

            agent_harness.generate_agent_harness(workspace, agents=("codex",), offline_research=False)
            data = json.loads((workspace / "output" / "agent-harness.json").read_text(encoding="utf-8"))

            self.assertEqual(data["missing_inputs"], [])
            self.assertFalse(data["final_candidate_ready"])
            self.assertFalse(data["final_check"]["ok"])
            self.assertEqual(data["readiness"]["verdict"], "blocked_run_final_gates")

    def test_mcp_op_agent_harness_returns_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp) / "ws")
            mcp_server.op_init(workspace)

            result = mcp_server.op_agent_harness(
                workspace,
                agents="codex,claude",
                offline_research=True,
            )

            self.assertFalse(result["final_candidate_ready"])
            missing = {item["id"] for item in result["missing_inputs"]}
            self.assertIn("survey", missing)
            self.assertIn("photos", missing)
            self.assertEqual(result["json_path"], "output/agent-harness.json")
            self.assertEqual(result["markdown_path"], "output/agent-harness.md")
            self.assertEqual(result["prompt_path"], "prompts/conductor/agent-harness.md")


if __name__ == "__main__":
    unittest.main()
