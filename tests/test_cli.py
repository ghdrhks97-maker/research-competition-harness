from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rch.cli import assemble_workspace, bootstrap_lanes, check_workspace, create_lane, init_workspace
from rch.lane_specs import LANE_SPECS


class CliTests(unittest.TestCase):
    def _write_final_ready_lanes(self, workspace: Path) -> dict[str, str]:
        samples = {
            "draft-writer": "보고서 본문 샘플",
            "summary-sheet": "요약서 샘플",
            "toc-builder": "목차 샘플",
            "appendix-builder": "부록 샘플",
            "critic": "비평 점검 샘플",
            "finalizer": "최종 점검 샘플",
        }
        for lane, content in samples.items():
            lane_dir = workspace / "lanes" / lane / "codex"
            (lane_dir / "evidence").mkdir(exist_ok=True)
            (lane_dir / "evidence" / "source.md").write_text(f"evidence for {lane}", encoding="utf-8")
            (lane_dir / "lane-output.md").write_text(content, encoding="utf-8")
            (lane_dir / "lane-output.json").write_text(
                json.dumps({"lane": lane, "agent": "codex", "summary": content, "artifacts": []}),
                encoding="utf-8",
            )
            (lane_dir / "claim-ledger.json").write_text(
                json.dumps(
                    {"claims": [{"id": f"{lane}-1", "text": content, "status": "real", "evidence": "evidence/source.md"}]}
                ),
                encoding="utf-8",
            )
            (lane_dir / "verdict.json").write_text(
                json.dumps({"status": "pass", "reason": "synthetic"}), encoding="utf-8"
            )
        return samples

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

    def test_bootstrap_lanes_writes_report_production_guides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")

            self.assertIn("survey-analyzer", LANE_SPECS)
            self.assertIn("photo-curator", LANE_SPECS)
            self.assertIn("toc-builder", LANE_SPECS)
            self.assertIn("appendix-builder", LANE_SPECS)

            for lane in LANE_SPECS:
                lane_input = workspace / "lanes" / lane / "codex" / "lane-input.md"
                self.assertTrue(lane_input.exists(), lane)

            survey_input = (workspace / "lanes" / "survey-analyzer" / "codex" / "lane-input.md").read_text(
                encoding="utf-8"
            )
            photo_input = (workspace / "lanes" / "photo-curator" / "codex" / "lane-input.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("설문", survey_input)
            self.assertIn("사진", photo_input)
            self.assertIn("학생 개인정보", photo_input)

    def test_assemble_workspace_creates_final_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)

            assemble_workspace(workspace)

            expected = {
                "report-draft.md": "보고서 본문 샘플",
                "summary-sheet.md": "요약서 샘플",
                "toc.md": "목차 샘플",
                "appendix.md": "부록 샘플",
                "finalization-checklist.md": "최종 점검 샘플",
            }
            for filename, content in expected.items():
                path = workspace / "output" / filename
                self.assertTrue(path.exists(), filename)
                self.assertIn(content, path.read_text(encoding="utf-8"))

            result = check_workspace(workspace, final=True)
            self.assertTrue(result.ok, result.errors)

    def test_final_check_rejects_stale_bundle_manifest_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            assemble_workspace(workspace)

            manifest_path = workspace / "output" / "bundle-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("sha256 mismatch" in err for err in result.errors), result.errors)

    def test_final_check_rejects_missing_evidence_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            assemble_workspace(workspace)

            (workspace / "lanes" / "draft-writer" / "codex" / "evidence" / "source.md").unlink()

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("evidence path missing" in err for err in result.errors), result.errors)

    def test_final_check_rejects_stale_source_lane_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            assemble_workspace(workspace)

            (workspace / "lanes" / "draft-writer" / "codex" / "lane-output.md").unlink()

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("source file missing" in err for err in result.errors), result.errors)

    def test_final_check_requires_assembled_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            lane = workspace / "lanes" / "draft-writer" / "codex"

            (lane / "evidence" / "source.md").write_text("source", encoding="utf-8")
            (lane / "lane-output.md").write_text("final-ready claim", encoding="utf-8")
            (lane / "lane-output.json").write_text(
                json.dumps({"lane": "draft-writer", "agent": "codex", "summary": "s", "artifacts": []}),
                encoding="utf-8",
            )
            (lane / "claim-ledger.json").write_text(
                json.dumps({"claims": [{"id": "c1", "text": "final-ready claim", "status": "real", "evidence": "evidence/source.md"}]}),
                encoding="utf-8",
            )
            (lane / "verdict.json").write_text(json.dumps({"status": "pass", "reason": "synthetic"}), encoding="utf-8")

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("missing final bundle file" in err for err in result.errors))
