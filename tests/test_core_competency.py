from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rch import brainstorm
from rch.cli import init_workspace, main


BASE = {
    "competition_name": "교실수업개선 실천사례 연구대회",
    "major": "음악",
    "interests": "AI, 에듀테크",
    "tools": "아이패드, 개러지밴드",
    "competency": "음악적 창의융합 역량",
    "constraints": "총 12차시",
}


class CoreCompetencyLinkageTests(unittest.TestCase):
    def test_always_links_even_with_empty_answers(self) -> None:
        self.assertTrue(brainstorm.link_core_competencies({}))

    def test_maps_phrase_to_2022_competency(self) -> None:
        # "창의융합" → 창의적 사고, "음악" → 심미적 감성.
        linked = brainstorm.link_core_competencies({"competency": "음악적 창의융합 역량"})
        self.assertIn("창의적 사고 역량", linked)

    def test_bundle_topics_and_titles_carry_competency(self) -> None:
        bundle = brainstorm.build_bundle(dict(BASE))
        self.assertTrue(bundle.core_competencies)
        self.assertTrue(all(topic.core_competency for topic in bundle.topics))
        self.assertIn("2022 개정", bundle.topics[0].research_question)
        self.assertTrue(any("역량" in title for title in bundle.titles))


class BrainstormFlagTests(unittest.TestCase):
    def test_cli_flags_fill_ideas_without_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            code = main([
                "brainstorm", str(workspace),
                "--competition-name", "창의교육 연구대회",
                "--major", "음악",
                "--competency", "음악적 창의융합 역량",
                "--tools", "아이패드, 개러지밴드",
            ])
            self.assertEqual(code, 0)
            topics_md = (workspace / "input" / "ideas" / "02-research-topics.md").read_text(encoding="utf-8")
            self.assertIn("2022 개정", topics_md)
            self.assertIn("창의교육 연구대회", topics_md)


if __name__ == "__main__":
    unittest.main()
