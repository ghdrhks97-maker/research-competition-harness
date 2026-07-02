from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from rch.cli import main
from rch.hwpx import build_hwpx
from rch.render_check import render_check


class HwpxPageDefinitionTests(unittest.TestCase):
    def test_section_has_page_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            build_hwpx("# 제목\n\n본문 문단\n", out, images_root=Path(tmp))
            with zipfile.ZipFile(out) as archive:
                section = archive.read("Contents/section0.xml").decode("utf-8")
            # Page geometry is required or Hancom renders a blank document.
            self.assertIn("<hp:secPr", section)
            self.assertIn("<hp:pagePr", section)
            self.assertIn('width="59528"', section)  # A4 width in HWPUNIT
            self.assertIn('height="84188"', section)  # A4 height in HWPUNIT

    def test_report_styling_title_headings_table_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            md = "# 문서 제목\n\n본문\n\n# 장 제목\n\n| 항목 | 값 |\n| --- | --- |\n| a | 1 |\n"
            build_hwpx(md, out, images_root=Path(tmp))
            with zipfile.ZipFile(out) as archive:
                section = archive.read("Contents/section0.xml").decode("utf-8")
                header = archive.read("Contents/header.xml").decode("utf-8")
            # First H1 is the large centered document title; later H1s render
            # as accent chapter bars (white bold text on filled cell).
            self.assertIn('charPrIDRef="5"', section)
            self.assertIn('charPrIDRef="6"', section)
            self.assertIn('borderFillIDRef="4"', section)
            # Table header row sits on the shaded borderFill with the accent char shape.
            self.assertIn('borderFillIDRef="2"', section)
            self.assertIn('charPrIDRef="4"', section)
            self.assertIn("#D9E2F3", header)
            self.assertIn("#1F4E79", header)
            self.assertIn('horizontal="JUSTIFY"', header)
            self.assertIn('horizontal="CENTER"', header)

    def test_render_check_flags_missing_page_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            build_hwpx("# 제목\n\n본문\n", out, images_root=Path(tmp))
            # Strip the page definition to simulate the old blank-render bug.
            data = {}
            with zipfile.ZipFile(out) as archive:
                for name in archive.namelist():
                    content = archive.read(name)
                    if name == "Contents/section0.xml":
                        text = content.decode("utf-8")
                        text = text[: text.index("<hp:p")] + text[text.index("<hp:p", text.index("</hp:p>")):]
                        content = text.encode("utf-8")
                    data[name] = content
            broken = Path(tmp) / "broken.hwpx"
            with zipfile.ZipFile(broken, "w") as archive:
                for name, content in data.items():
                    archive.writestr(name, content)
            check = render_check(broken)
            self.assertFalse(check.ok)
            self.assertTrue(any("pagePr" in error for error in check.errors))


class DesignRenderingTests(unittest.TestCase):
    def test_chapter_bar_and_callout_box(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            md = (
                "# 문서 제목\n\n"
                "# I. 연구의 필요성\n\n"
                ":::box 연구 질문\n"
                "▶ 어떻게 기를 것인가?\n"
                ":::\n"
            )
            build_hwpx(md, out, images_root=Path(tmp))
            with zipfile.ZipFile(out) as archive:
                section = archive.read("Contents/section0.xml").decode("utf-8")
                header = archive.read("Contents/header.xml").decode("utf-8")
            # Chapter H1 renders as a white-bold paragraph on an accent-filled bar.
            self.assertIn('borderFillIDRef="4"', section)
            self.assertIn('charPrIDRef="6"', section)
            # The :::box directive becomes a shaded callout cell with its content.
            self.assertIn('borderFillIDRef="3"', section)
            self.assertIn("연구 질문", section)
            self.assertIn("▶ 어떻게 기를 것인가?", section)
            self.assertIn("#EEF3FA", header)

    def test_min_pages_warning_when_underfilled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            build_hwpx("# 제목\n\n짧은 본문\n", out, images_root=Path(tmp))
            check = render_check(out, min_pages=22)
            self.assertTrue(check.ok)  # warning, not error
            self.assertTrue(any("하한" in warn for warn in check.warnings), check.warnings)

    def test_chapter_bar_headings_still_match_toc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.hwpx"
            build_hwpx("# 문서 제목\n\n# I. 연구의 필요성\n\n본문\n", out, images_root=Path(tmp))
            check = render_check(out)
            self.assertTrue(check.ok, check.errors)
            self.assertGreaterEqual(check.heading_count, 1)


class HwpxEditRoundtripTests(unittest.TestCase):
    def test_unpack_edit_pack_keeps_valid_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / "output").mkdir(parents=True)
            hwpx = workspace / "output" / "report.hwpx"
            build_hwpx("# 제목\n\n본문\n", hwpx, images_root=workspace)

            code = main(["hwpx-unpack", str(workspace)])
            self.assertEqual(code, 0)
            section = workspace / "output" / "hwpx-src" / "Contents" / "section0.xml"
            self.assertTrue(section.exists())
            section.write_text(
                section.read_text(encoding="utf-8").replace("본문", "디자인 반복 본문"),
                encoding="utf-8",
            )

            code = main(["hwpx-pack", str(workspace)])
            self.assertEqual(code, 0)
            with zipfile.ZipFile(hwpx) as archive:
                names = archive.namelist()
                # OWPML requires mimetype first and stored uncompressed.
                self.assertEqual(names[0], "mimetype")
                self.assertEqual(archive.getinfo("mimetype").compress_type, zipfile.ZIP_STORED)
                self.assertIn("디자인 반복 본문", archive.read("Contents/section0.xml").decode("utf-8"))
            self.assertTrue(render_check(hwpx).ok)


class KordocEngineTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("RCH_KORDOC_CMD", None)

    def test_build_hwpx_kordoc_engine_uses_configured_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / "output").mkdir(parents=True)
            (workspace / "output" / "report-draft.md").write_text("# 제목\n\n본문\n", encoding="utf-8")

            stub = Path(tmp) / "kordoc-stub.sh"
            stub.write_text(
                "#!/bin/sh\n"
                'out=""\n'
                'while [ $# -gt 0 ]; do\n'
                '  if [ "$1" = "-o" ]; then out="$2"; fi\n'
                "  shift\n"
                "done\n"
                'printf "PK" > "$out"\n',
                encoding="utf-8",
            )
            stub.chmod(0o755)
            os.environ["RCH_KORDOC_CMD"] = str(stub)

            code = main(["build-hwpx", str(workspace), "--engine", "kordoc"])
            self.assertEqual(code, 0)
            self.assertTrue((workspace / "output" / "report.hwpx").exists())
            self.assertTrue((workspace / "output" / "report-merged.md").exists())

    def test_build_hwpx_kordoc_engine_fails_clearly_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            (workspace / "output").mkdir(parents=True)
            (workspace / "output" / "report-draft.md").write_text("# 제목\n", encoding="utf-8")
            os.environ["RCH_KORDOC_CMD"] = "/nonexistent/kordoc-binary-xyz"

            with self.assertRaises(SystemExit) as ctx:
                main(["build-hwpx", str(workspace), "--engine", "kordoc"])
            self.assertIn("builtin", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
