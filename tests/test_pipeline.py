from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from rch.cli import init_workspace
from rch.pipeline import PHASE1_LANES, PHASE3B_LANES, compute_next, run_next


@dataclass
class FakeCheck:
    ok: bool
    errors: list[str] = field(default_factory=list)


def _approve_plan(workspace: Path) -> None:
    profile = workspace / "input" / "rules" / "competition-profile.json"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(json.dumps({"competition_name": "테스트 대회", "plan_approved": True}), encoding="utf-8")


def _pass_lane(workspace: Path, lane: str, status: str = "pass", claim_status: str = "real") -> None:
    lane_dir = workspace / "lanes" / lane / "agent"
    (lane_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (lane_dir / "evidence" / "source.md").write_text("evidence", encoding="utf-8")
    (lane_dir / "lane-output.md").write_text(f"{lane} 산출물", encoding="utf-8")
    (lane_dir / "lane-output.json").write_text(
        json.dumps({"lane": lane, "agent": "agent", "summary": lane, "artifacts": []}),
        encoding="utf-8",
    )
    claim: dict[str, str] = {"id": f"{lane}-1", "text": f"{lane} 주장", "status": claim_status}
    if claim_status in {"real", "derived"}:
        claim["evidence"] = "evidence/source.md"
    else:
        claim["text"] = f"{lane} 예상값(가상) 주장"
    (lane_dir / "claim-ledger.json").write_text(json.dumps({"claims": [claim]}), encoding="utf-8")
    (lane_dir / "verdict.json").write_text(
        json.dumps({"status": status, "reason": "synthetic"}), encoding="utf-8"
    )
    if lane == "critic":
        (lane_dir / "rubric-score.json").write_text(
            json.dumps({"total_score": 90, "max_score": 100, "items": []}), encoding="utf-8"
        )


def _pass_through_critic(workspace: Path) -> None:
    for lane in (*PHASE1_LANES, "draft-writer", "table-layout", *PHASE3B_LANES, "critic"):
        _pass_lane(workspace, lane)


def _finalize_outputs(workspace: Path) -> None:
    _pass_lane(workspace, "finalizer")
    output = workspace / "output"
    output.mkdir(exist_ok=True)
    (output / "bundle-manifest.json").write_text("{}", encoding="utf-8")
    (output / "report.hwpx").write_bytes(b"PK")
    (output / "render-check.json").write_text(json.dumps({"ok": True}), encoding="utf-8")


class PipelineTests(unittest.TestCase):
    def test_missing_workspace_needs_init(self) -> None:
        plan = compute_next(Path("/nonexistent/workspace-xyz"))
        self.assertEqual(plan.phase, "setup")
        self.assertEqual(plan.actions[0]["kind"], "run")

    def test_interview_required_before_anything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "interview")
            self.assertTrue(plan.needs_user)

    def test_phase1_parallel_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            _approve_plan(workspace)
            (workspace / "input" / "surveys" / "pre-post.csv").write_text("a,b\n1,2\n", encoding="utf-8")

            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "phase1-analysis")
            self.assertTrue(plan.parallel)
            delegated = {action["lane"] for action in plan.actions if action["kind"] == "delegate"}
            self.assertEqual(delegated, set(PHASE1_LANES))
            commands = [action["command"] for action in plan.actions if action["kind"] == "run"]
            self.assertTrue(any("import-survey" in cmd for cmd in commands), commands)

    def test_blocked_verdict_escalates_to_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            _approve_plan(workspace)
            _pass_lane(workspace, "photo-curator", status="blocked")

            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "blocked")
            self.assertTrue(any("photo-curator" in item for item in plan.needs_user))

    def test_phase_order_draft_layout_companions_critic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            _approve_plan(workspace)
            for lane in PHASE1_LANES:
                _pass_lane(workspace, lane)

            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "phase2-draft")

            _pass_lane(workspace, "draft-writer")
            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "phase3-layout")

            _pass_lane(workspace, "table-layout")
            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "phase3-companions")
            self.assertTrue(plan.parallel)

            for lane in PHASE3B_LANES:
                _pass_lane(workspace, lane)
            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "phase4-critic")

    def test_finalize_then_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            _approve_plan(workspace)
            _pass_through_critic(workspace)

            plan = compute_next(workspace)
            self.assertEqual(plan.phase, "phase5-finalize")
            self.assertEqual(plan.actions[0]["lane"], "finalizer")

            _finalize_outputs(workspace)
            plan = compute_next(workspace, final_check=lambda ws, **kw: FakeCheck(ok=True))
            self.assertTrue(plan.done)
            self.assertEqual(plan.phase, "done")

    def test_failed_final_gate_goes_to_revise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            _approve_plan(workspace)
            _pass_through_critic(workspace)
            _finalize_outputs(workspace)

            plan = compute_next(
                workspace, final_check=lambda ws, **kw: FakeCheck(ok=False, errors=["금지어 발견"])
            )
            self.assertEqual(plan.phase, "revise")
            self.assertFalse(plan.done)
            self.assertTrue(any("revise-loop" in a.get("command", "") for a in plan.actions))
            self.assertIn("금지어 발견", plan.notes)

    def test_expected_claims_switch_gate_to_allow_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            _approve_plan(workspace)
            _pass_through_critic(workspace)
            _pass_lane(workspace, "survey-analyzer", claim_status="expected")
            _finalize_outputs(workspace)

            captured: dict[str, bool] = {}

            def final_check(ws: Path, **kwargs: bool) -> FakeCheck:
                captured.update(kwargs)
                return FakeCheck(ok=True)

            plan = compute_next(workspace, final_check=final_check)
            self.assertTrue(plan.done)
            self.assertTrue(captured.get("allow_expected"))

    def test_run_next_writes_plan_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            run_next(workspace)
            self.assertTrue((workspace / "output" / "next-plan.json").exists())
            self.assertTrue((workspace / "output" / "next-plan.md").exists())


if __name__ == "__main__":
    unittest.main()
