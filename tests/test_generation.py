from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from rch.background import run_background_research
from rch import stats
from rch.cli import assemble_workspace, init_workspace
from rch.docmodel import parse_markdown
from rch.draft import generate_drafts
from rch.hwpx import build_hwpx
from rch.photos import import_photos
from rch.references import mine_references
from rch.render_check import render_check
from rch.revise import run_revise_loop
from rch.run_lanes import run_lanes
from rch.survey import analyze_table, import_survey


class StatsTests(unittest.TestCase):
    def test_paired_test_matches_known_values(self) -> None:
        pre = [3, 2, 3, 4, 2]
        post = [5, 4, 5, 5, 4]
        result = stats.paired_test(pre, post)
        self.assertEqual(result.n, 5)
        self.assertAlmostEqual(result.mean_diff, 1.8, places=6)
        self.assertAlmostEqual(result.t, 9.0, places=3)
        # Two-sided p for t=9, df=4 is ~0.00083.
        self.assertLess(result.p_value, 0.01)
        self.assertGreater(result.cohens_d, 0.8)

    def test_t_two_sided_p_symmetric(self) -> None:
        self.assertAlmostEqual(stats.t_two_sided_p(2.0, 10), stats.t_two_sided_p(-2.0, 10), places=9)
        self.assertAlmostEqual(stats.t_two_sided_p(0.0, 10), 1.0, places=6)


class DocModelTests(unittest.TestCase):
    def test_parse_headings_tables_lists(self) -> None:
        blocks = parse_markdown("# 제목\n\n본문 문단\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n- 항목1\n- 항목2\n")
        kinds = [block.kind for block in blocks]
        self.assertEqual(kinds, ["heading", "paragraph", "table", "list"])
        table = blocks[2]
        self.assertEqual(table.rows, [["a", "b"], ["1", "2"]])
        self.assertTrue(blocks[3].items == ["항목1", "항목2"])


class SurveyTests(unittest.TestCase):
    def test_analyze_detects_pairs_and_pii(self) -> None:
        headers = ["이름", "문항1_사전", "문항1_사후", "자유응답"]
        rows = [["김", "3", "5", "좋았다"], ["이", "2", "4", "재미"], ["박", "3", "5", "유익"]]
        analysis = analyze_table(headers, rows, "t.csv")
        self.assertIn("이름", analysis.dropped_pii_columns)
        self.assertEqual(len(analysis.paired_items), 1)
        item = analysis.paired_items[0]
        self.assertEqual(item.item, "문항1")
        self.assertEqual(item.n, 3)
        self.assertEqual(len(analysis.free_responses), 1)

    def test_import_survey_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            survey = Path(tmp) / "s.csv"
            survey.write_text("문항_사전,문항_사후\n2,4\n3,5\n2,5\n", encoding="utf-8")
            out = Path(tmp) / "analysis"
            analysis = import_survey(survey, out)
            self.assertTrue((out / "survey-analysis.json").exists())
            self.assertTrue((out / "survey-summary.md").exists())
            ledger = json.loads((out / "claim-ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["claims"][0]["status"], "derived")
            self.assertEqual(analysis.respondents, 3)


class PhotoTests(unittest.TestCase):
    def test_import_photos_flags_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "photos"
            source.mkdir()
            (source / "학생_얼굴.png").write_bytes(b"x")
            (source / "결과물_화면.png").write_bytes(b"y")
            manifest = import_photos(source, source / "analysis")
            risks = {photo.file: photo.privacy_risk for photo in manifest.photos}
            self.assertEqual(risks["학생_얼굴.png"], "high")
            self.assertEqual(risks["결과물_화면.png"], "low")
            self.assertTrue((source / "analysis" / "privacy-checklist.md").exists())


class ReferenceTests(unittest.TestCase):
    def test_mine_references_extracts_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "refs"
            source.mkdir()
            (source / "r.md").write_text(
                "# I. 필요성\n## II. 실태\n| a | b |\n| --- | --- |\n부록 항목\n", encoding="utf-8"
            )
            report = mine_references(source, source / "analysis")
            self.assertTrue(report.recommended_outline)
            profile = report.profiles[0]
            self.assertTrue(profile.readable)
            self.assertTrue(profile.has_appendix)

    def test_pdf_recorded_as_unread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "refs"
            source.mkdir()
            (source / "r.pdf").write_bytes(b"%PDF-1.4 fake")
            report = mine_references(source, source / "analysis")
            self.assertFalse(report.profiles[0].readable)


class BackgroundResearchTests(unittest.TestCase):
    def test_background_research_writes_public_sources_and_seeds_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)

            def fake_fetch(url: str) -> str:
                if "api.openalex.org" in url:
                    return json.dumps(
                        {
                            "results": [
                                {
                                    "display_name": "Formative assessment and student agency in science classrooms",
                                    "doi": "https://doi.org/10.1000/example",
                                    "publication_year": 2024,
                                    "authorships": [{"author": {"display_name": "A. Researcher"}}],
                                    "abstract_inverted_index": {
                                        "Formative": [0],
                                        "assessment": [1],
                                        "supports": [2],
                                        "agency": [3],
                                    },
                                }
                            ]
                        }
                    )
                if "api.crossref.org" in url:
                    return json.dumps({"message": {"items": []}})
                if "export.arxiv.org" in url:
                    return "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"
                if "s.jina.ai" in url:
                    return "[Public background note](https://example.org/background)"
                raise AssertionError(url)

            research = run_background_research(
                workspace,
                query="AI 활용 과학 탐구 수업",
                fetcher=fake_fetch,
                max_results=3,
            )

            self.assertFalse(research.fallback_used)
            self.assertTrue((workspace / "input" / "research" / "background-research.json").exists())
            self.assertTrue((workspace / "input" / "research" / "04-background-research.md").exists())
            self.assertTrue((workspace / "lanes" / "reference-miner" / "harness-background" / "lane-output.md").exists())

    def test_draft_uses_background_research_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)

            def fake_fetch(url: str) -> str:
                if "api.openalex.org" in url:
                    return json.dumps(
                        {
                            "results": [
                                {
                                    "display_name": "Inquiry learning theory for science education",
                                    "id": "https://openalex.org/W1",
                                    "publication_year": 2023,
                                    "abstract_inverted_index": {"Inquiry": [0], "learning": [1], "supports": [2]},
                                }
                            ]
                        }
                    )
                if "api.crossref.org" in url:
                    return json.dumps({"message": {"items": []}})
                if "export.arxiv.org" in url:
                    return "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"
                return ""

            run_background_research(workspace, query="과학 탐구 수업", fetcher=fake_fetch)
            generate_drafts(workspace)
            report = (workspace / "lanes" / "draft-writer" / "harness-draft" / "lane-output.md").read_text(
                encoding="utf-8"
            )
            ledger = json.loads(
                (workspace / "lanes" / "draft-writer" / "harness-draft" / "claim-ledger.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("이론적 배경 및 선행연구", report)
            self.assertTrue(any(claim["id"] == "background-research-used" for claim in ledger["claims"]))


class HwpxTests(unittest.TestCase):
    def test_build_hwpx_is_valid_owpml_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            result = build_hwpx(
                "# 제목\n\n본문\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n",
                out,
                images_root=Path(tmp),
            )
            self.assertTrue(out.exists())
            self.assertEqual(result.table_count, 1)
            with zipfile.ZipFile(out) as archive:
                names = archive.namelist()
                self.assertEqual(names[0], "mimetype")
                self.assertEqual(archive.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
                self.assertEqual(archive.read("mimetype").decode("utf-8"), "application/hwp+zip")
                self.assertIn("Contents/section0.xml", names)
                self.assertIn("Contents/header.xml", names)


class RenderCheckTests(unittest.TestCase):
    def test_render_check_passes_and_flags_toc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            build_hwpx("# 서론\n\n본문 문단\n", out, images_root=Path(tmp))
            toc = Path(tmp) / "toc.md"
            toc.write_text("- 서론\n- 없는장\n", encoding="utf-8")
            check = render_check(out, toc_path=toc)
            self.assertTrue(check.ok, check.errors)
            self.assertFalse(check.toc_headings_matched)
            self.assertIn("없는장", check.toc_mismatches)

    def test_render_check_rejects_bad_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.hwpx"
            bad.write_text("not a zip", encoding="utf-8")
            check = render_check(bad)
            self.assertFalse(check.ok)


class DraftAndLoopTests(unittest.TestCase):
    def test_draft_assemble_and_revise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            written = generate_drafts(workspace)
            self.assertIn("draft-writer", written)
            self.assertTrue((workspace / "lanes" / "draft-writer" / "harness-draft" / "lane-output.md").exists())
            assemble_workspace(workspace)
            self.assertTrue((workspace / "output" / "report-draft.md").exists())

            # Seed critic machine feedback and confirm revise-loop collects it.
            critic_dir = workspace / "lanes" / "critic" / "codex"
            critic_dir.mkdir(parents=True, exist_ok=True)
            (critic_dir / "machine-feedback.json").write_text(
                json.dumps({"issues": [{"severity": "blocking", "instruction": "표 잘림", "auto_fixable": False}]}),
                encoding="utf-8",
            )
            backlog = run_revise_loop(workspace)
            self.assertTrue(any(task.source == "critic" for task in backlog.tasks))
            self.assertEqual(backlog.tasks[0].severity, "blocking")

    def test_run_lanes_writes_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            init_workspace(workspace)
            manifest = run_lanes(workspace, "codex", ["survey-analyzer"])
            self.assertEqual(manifest["agent"], "codex")
            self.assertTrue((workspace / "prompts" / "codex" / "survey-analyzer.md").exists())


if __name__ == "__main__":
    unittest.main()
