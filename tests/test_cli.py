from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rch.cli import assemble_workspace, bootstrap_lanes, check_workspace, create_lane, init_workspace, main
from rch.lane_specs import LANE_SPECS
from rch.render_check import render_check


class CliTests(unittest.TestCase):
    def _write_final_ready_lanes(self, workspace: Path) -> dict[str, str]:
        samples = {lane: f"{spec['title']} 샘플" for lane, spec in LANE_SPECS.items()}
        samples.update(
            {
            "draft-writer": "보고서 본문 샘플",
            "summary-sheet": "요약서 샘플",
            "toc-builder": "목차 샘플",
            "appendix-builder": "부록 샘플",
            "critic": "비평 점검 샘플",
            "finalizer": "최종 점검 샘플",
            }
        )
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
            if lane == "critic":
                self._write_passing_rubric_score(lane_dir)
        return samples

    def _write_passing_rubric_score(self, lane_dir: Path) -> None:
        items = [
            {
                "criterion": "연구 필요성",
                "score": 18,
                "max_score": 20,
                "evidence": "심사표와 본문 필요성 대응",
                "risk": "근거 연결 약화 시 감점",
                "fix": "필요성과 수업 증거 연결 유지",
            },
            {
                "criterion": "수업 설계",
                "score": 18,
                "max_score": 20,
                "evidence": "수업 모형과 실천과제 대응",
                "risk": "단계 설명 부족 시 감점",
                "fix": "표 중심으로 단계 보강",
            },
            {
                "criterion": "실행 충실도",
                "score": 18,
                "max_score": 20,
                "evidence": "차시 운영 증빙",
                "risk": "증빙 누락 시 감점",
                "fix": "활동지와 사진 근거 유지",
            },
            {
                "criterion": "학생 변화 근거",
                "score": 18,
                "max_score": 20,
                "evidence": "설문과 산출물 근거",
                "risk": "수치 과장 시 감점",
                "fix": "소표본 한계 명시",
            },
            {
                "criterion": "일반화 가능성",
                "score": 18,
                "max_score": 20,
                "evidence": "확산 계획과 적용 조건",
                "risk": "미확정 실적 표현 시 감점",
                "fix": "확정 사실만 유지",
            },
        ]
        (lane_dir / "rubric-score.json").write_text(
            json.dumps({"total_score": 90, "max_score": 100, "items": items}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_low_rubric_score(self, lane_dir: Path) -> None:
        items = [
            {
                "criterion": criterion,
                "score": 14,
                "max_score": 20,
                "evidence": "근거 부족",
                "risk": "감점 위험",
                "fix": "보강 필요",
            }
            for criterion in ("연구 필요성", "수업 설계", "실행 충실도", "학생 변화 근거", "일반화 가능성")
        ]
        (lane_dir / "rubric-score.json").write_text(
            json.dumps({"total_score": 70, "max_score": 100, "items": items}, ensure_ascii=False),
            encoding="utf-8",
        )

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

    def _set_expected_survey_claim(self, workspace: Path, text: str, notes: str = "") -> None:
        lane = workspace / "lanes" / "survey-analyzer" / "codex"
        claim: dict[str, str] = {"id": "survey-1", "text": text, "status": "expected"}
        if notes:
            claim["notes"] = notes
        (lane / "claim-ledger.json").write_text(
            json.dumps({"claims": [claim]}, ensure_ascii=False), encoding="utf-8"
        )

    def test_expected_claim_requires_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            self._set_expected_survey_claim(workspace, "탐구 흥미가 오를 것이다")

            result = check_workspace(workspace)
            self.assertFalse(result.ok)
            self.assertTrue(any("label" in err for err in result.errors), result.errors)

    def test_final_check_rejects_expected_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            self._set_expected_survey_claim(workspace, "탐구 흥미 사전 3.1 → 사후 4.0 (예상값·가상)")
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("--allow-expected" in err for err in result.errors), result.errors)

    def test_final_check_allows_labeled_expected_with_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            self._set_expected_survey_claim(
                workspace,
                "탐구 흥미 사전 3.1 → 사후 4.0 (예상값·가상)",
                notes="실제 설문 후 교체",
            )
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True, allow_expected=True)
            self.assertTrue(result.ok, result.errors)
            self.assertTrue(any("expected" in warn for warn in result.warnings), result.warnings)
            report = workspace / "output" / "expected-claims.md"
            self.assertTrue(report.exists())
            self.assertIn("탐구 흥미", report.read_text(encoding="utf-8"))

    def test_final_check_allow_expected_still_rejects_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            lane = workspace / "lanes" / "survey-analyzer" / "codex"
            (lane / "claim-ledger.json").write_text(
                json.dumps({"claims": [{"id": "s1", "text": "빈 구멍", "status": "placeholder"}]}),
                encoding="utf-8",
            )
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True, allow_expected=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("not allowed: placeholder" in err for err in result.errors), result.errors)

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

    def test_final_check_requires_upstream_lane_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            (workspace / "lanes" / "survey-analyzer" / "codex" / "lane-output.md").unlink()
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("survey-analyzer" in err for err in result.errors), result.errors)

    def test_final_check_rejects_non_pass_required_lane_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            verdict_path = workspace / "lanes" / "survey-analyzer" / "codex" / "verdict.json"
            verdict_path.write_text(json.dumps({"status": "needs-work", "reason": "review pending"}), encoding="utf-8")
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("verdict.status must be pass" in err for err in result.errors), result.errors)

    def test_final_check_rejects_absolute_evidence_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            claim_path = workspace / "lanes" / "draft-writer" / "codex" / "claim-ledger.json"
            claim_ledger = json.loads(claim_path.read_text(encoding="utf-8"))
            claim_ledger["claims"][0]["evidence"] = str(
                workspace / "lanes" / "draft-writer" / "codex" / "evidence" / "source.md"
            )
            claim_path.write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("workspace-relative" in err for err in result.errors), result.errors)

    def test_final_check_rejects_raw_private_evidence_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            raw_private = workspace / "input" / "raw_private" / "secret.md"
            raw_private.write_text("raw student data", encoding="utf-8")
            claim_path = workspace / "lanes" / "draft-writer" / "codex" / "claim-ledger.json"
            claim_ledger = json.loads(claim_path.read_text(encoding="utf-8"))
            claim_ledger["claims"][0]["evidence"] = "input/raw_private/secret.md"
            claim_path.write_text(json.dumps(claim_ledger, ensure_ascii=False), encoding="utf-8")
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("input/raw_private" in err for err in result.errors), result.errors)

    def test_final_check_requires_critic_rubric_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            (workspace / "lanes" / "critic" / "codex" / "rubric-score.json").unlink()
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("rubric-score.json" in err for err in result.errors), result.errors)

    def test_final_check_rejects_low_critic_rubric_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            bootstrap_lanes(workspace, "codex")
            self._write_final_ready_lanes(workspace)
            self._write_low_rubric_score(workspace / "lanes" / "critic" / "codex")
            assemble_workspace(workspace)

            result = check_workspace(workspace, final=True)
            self.assertFalse(result.ok)
            self.assertTrue(any("below final target" in err for err in result.errors), result.errors)

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

    def test_go_finishes_with_missing_survey_and_photos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            rule_file = Path(tmp) / "2026_보고서_양식.hwpx"
            rule_file.write_bytes(b"fake hwpx template")
            answers = Path(tmp) / "answers.json"
            answers.write_text(
                json.dumps(
                    {
                        "competition_name": "창의교육 연구대회",
                        "major": "과학",
                        "level": "중학교 2학년",
                        "class_context": "28명",
                        "interests": "AI, 탐구",
                        "tools": "AI 챗봇",
                        "competency": "탐구력",
                        "constraints": "총 12차시",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            # Without --skeleton the legacy path refuses (agents kept off it).
            with self.assertRaises(SystemExit) as ctx:
                main(["go", str(workspace), "--answers", str(answers)])
            self.assertIn("skeleton", str(ctx.exception))

            code = main(
                [
                    "go",
                    str(workspace),
                    "--skeleton",
                    "--answers",
                    str(answers),
                    "--rule-file",
                    str(rule_file),
                    "--offline-research",
                    "--survey-items",
                    "5",
                    "--photo-count",
                    "4",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue((workspace / "output" / "report.hwpx").exists())
            rendered = render_check(workspace / "output" / "report.hwpx")
            self.assertEqual(rendered.section_count, 5)
            self.assertTrue((workspace / "output" / "missing-inputs.md").exists())
            self.assertTrue((workspace / "input" / "rules" / "forms" / "2026_보고서_양식.hwpx").exists())
            report = (workspace / "output" / "report-draft.md").read_text(encoding="utf-8")
            appendix = (workspace / "output" / "appendix.md").read_text(encoding="utf-8")
            self.assertIn("동일 문항 5문항 사전·사후 설문", report)
            self.assertIn("사진첨부필요", appendix)
            check = json.loads((workspace / "output" / "harness-check.json").read_text(encoding="utf-8"))
            self.assertTrue(check["ok"], check)

    def test_import_rules_copies_template_to_rules_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "competition"
            init_workspace(workspace)
            form = Path(tmp) / "보고서_양식.hwp"
            form.write_bytes(b"form")
            code = main(["import-rules", str(workspace), str(form)])
            self.assertEqual(code, 0)
            self.assertTrue((workspace / "input" / "rules" / "forms" / "보고서_양식.hwp").exists())
            manifest = json.loads((workspace / "input" / "rules" / "rules-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["files"][0]["kind"], "forms")
