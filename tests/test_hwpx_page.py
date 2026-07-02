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
            # First H1 is the large centered document title; later H1s are chapter headings.
            self.assertIn('charPrIDRef="5"', section)
            self.assertIn('charPrIDRef="1"', section)
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
