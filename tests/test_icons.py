from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from rch.cli import main
from rch.icons import MOTIFS, render_icon, render_icons


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


class IconRenderTests(unittest.TestCase):
    def test_every_motif_renders_valid_png(self) -> None:
        for motif in MOTIFS:
            data = render_icon(motif, "circle", "#1F4E79", "#FFFFFF")
            self.assertEqual(_png_size(data), (128, 128), motif)
            # IDAT payload must decompress (raw RGBA scanlines with filter bytes).
            idat_start = data.index(b"IDAT") + 4
            idat_len = struct.unpack(">I", data[data.index(b"IDAT") - 4 : data.index(b"IDAT")])[0]
            raw = zlib.decompress(data[idat_start : idat_start + idat_len])
            self.assertEqual(len(raw), 128 * (128 * 4 + 1), motif)

    def test_unknown_motif_rejected(self) -> None:
        with self.assertRaises(ValueError):
            render_icon("dragon", "circle", "#1F4E79", "#FFFFFF")

    def test_render_icons_from_spec_writes_pngs_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            icons_dir = workspace / "input" / "icons"
            icons_dir.mkdir(parents=True)
            (icons_dir / "icon-spec.json").write_text(
                json.dumps(
                    {
                        "icons": [
                            {"name": "ch1-need", "motif": "target", "usage": "I장"},
                            {"name": "task1", "motif": "note", "plate": "rounded", "bg": "#2E75B6"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            code = main(["render-icons", str(workspace)])
            self.assertEqual(code, 0)
            self.assertTrue((icons_dir / "rendered" / "ch1-need.png").exists())
            self.assertTrue((icons_dir / "rendered" / "task1.png").exists())
            manifest = (icons_dir / "icon-manifest.md").read_text(encoding="utf-8")
            self.assertIn("ch1-need", manifest)
            self.assertIn("target", manifest)

    def test_render_icons_without_spec_reports_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            report = render_icons(workspace)
            self.assertTrue(report.errors)


if __name__ == "__main__":
    unittest.main()
