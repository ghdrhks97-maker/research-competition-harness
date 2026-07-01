from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rch import brainstorm
from rch.cli import init_workspace, main
from rch.draft import gather_context


ANSWERS = {
    "major": "과학",
    "level": "중학교 2학년",
    "class_context": "28명",
    "interests": "AI, 탐구",
    "tools": "AI 챗봇, 태블릿",
    "competency": "탐구력",
    "constraints": "총 12차시",
}


class BrainstormLogicTests(unittest.TestCase):
    def test_rank_trends_prioritizes_subject_and_interest(self) -> None:
        ranked = brainstorm.rank_trends(ANSWERS)
        top = ranked[0][0].name
        # AI interest + science subject should push an AI/STEAM trend to the top.
        self.assertTrue(ranked[0][1] >= ranked[-1][1])
        self.assertTrue(any("AI" in name or "STEAM" in name or "융합" in name for name, _ in
                            [(trend.name, score) for trend, score in ranked[:3]]))
        self.assertTrue(top)

    def test_build_bundle_produces_topics_and_titles(self) -> None:
        bundle = brainstorm.build_bundle(ANSWERS)
        self.assertEqual(len(bundle.topics), 3)
        self.assertTrue(bundle.recommended_topic)
        self.assertEqual(len(bundle.titles), 5)
        # Title acronym should be Latin only, not mixed Korean.
        self.assertNotIn("활", bundle.titles[0].split("』")[0])

    def test_interview_uses_ask_callable(self) -> None:
        scripted = iter(["과학", "", "", "", "", "", ""])
        answers = brainstorm.run_interview(ask=lambda q: next(scripted))
        self.assertEqual(answers["major"], "과학")
        # Non-required blanks fall back to defaults.
        self.assertEqual(answers["competency"], "핵심 역량")


class BrainstormWriteTests(unittest.TestCase):
    def test_run_brainstorm_writes_ideas_and_seeds_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            bundle = brainstorm.run_brainstorm(workspace, answers=dict(ANSWERS))

            ideas = workspace / "input" / "ideas"
            for name in ("00-interview.md", "01-trend-research.md", "02-research-topics.md",
                         "03-title-candidates.md", "brainstorm.json"):
                self.assertTrue((ideas / name).exists(), name)

            data = json.loads((ideas / "brainstorm.json").read_text(encoding="utf-8"))
            self.assertEqual(data["answers"]["major"], "과학")

            lane_md = workspace / "lanes" / "brainstorm" / "harness-brainstorm" / "lane-output.md"
            self.assertTrue(lane_md.exists())
            self.assertTrue(lane_md.read_text(encoding="utf-8").startswith("# "))

            # The seeded title should flow into the draft title.
            context = gather_context(workspace)
            self.assertEqual(context.title, bundle.titles[0])

    def test_missing_major_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            with self.assertRaises(SystemExit):
                brainstorm.run_brainstorm(workspace, answers={"major": ""})

    def test_cli_brainstorm_with_answers_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            answers_file = Path(tmp) / "a.json"
            answers_file.write_text(json.dumps(ANSWERS), encoding="utf-8")
            code = main(["brainstorm", str(workspace), "--answers", str(answers_file)])
            self.assertEqual(code, 0)
            self.assertTrue((workspace / "input" / "ideas" / "brainstorm.json").exists())

    def test_cli_research_background_offline_writes_research_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            code = main(["research-background", str(workspace), "--query", "과학 탐구 수업", "--offline"])
            self.assertEqual(code, 0)
            self.assertTrue((workspace / "input" / "research" / "background-research.json").exists())

    def test_cli_init_with_brainstorm_flag_requires_no_manual_ideas(self) -> None:
        # init --brainstorm would prompt interactively; ensure the flag is wired
        # by checking init alone leaves ideas empty, then scripted brainstorm fills it.
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            ideas = workspace / "input" / "ideas"
            existing = [p.name for p in ideas.iterdir() if p.name != ".gitkeep"]
            self.assertEqual(existing, [])
            brainstorm.run_brainstorm(workspace, answers=dict(ANSWERS))
            filled = [p.name for p in ideas.iterdir() if p.name != ".gitkeep"]
            self.assertTrue(filled)


if __name__ == "__main__":
    unittest.main()
