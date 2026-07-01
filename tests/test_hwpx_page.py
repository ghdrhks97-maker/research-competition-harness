from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
