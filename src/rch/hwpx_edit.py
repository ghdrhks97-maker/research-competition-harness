"""HWPX design-iteration loop (`rch hwpx-unpack` / `rch hwpx-pack`).

An HWPX file is an OWPML zip. The deterministic builder guarantees a valid
container but a plain look; award-level design (표지, 장 도비라, 색 박스,
아이콘, 카드형 요약) needs richer OWPML than a markdown renderer can carry.

These commands open the sanctioned path for that: an agent unpacks the
built HWPX, edits the XML parts (Contents/header.xml, Contents/section0.xml)
with full OWPML freedom, then packs — packing rebuilds the zip with the
correct member order (mimetype first, stored) and immediately validates the
result with render-check. Iterate unpack→edit→pack until the design goal is
met, keeping numbered iteration copies. Agents must never zip by hand;
`pack` is the only rebuild path so every iteration stays verifiable.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

MIMETYPE_NAME = "mimetype"
DEFAULT_MIMETYPE = "application/hwp+zip"


def unpack_hwpx(hwpx_path: Path, target_dir: Path) -> list[str]:
    """Extract every member of the HWPX zip into target_dir (replacing it)."""
    if not hwpx_path.exists():
        raise SystemExit(f"hwpx not found: {hwpx_path}")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)
    with zipfile.ZipFile(hwpx_path) as archive:
        names = archive.namelist()
        archive.extractall(target_dir)
    return names


def pack_hwpx(source_dir: Path, output_path: Path) -> Path:
    """Rebuild an HWPX zip from an unpacked directory.

    The OWPML container requires the `mimetype` entry to be the first zip
    member and stored uncompressed — this is why agents must not zip by
    hand."""
    if not source_dir.is_dir():
        raise SystemExit(f"unpacked hwpx directory not found: {source_dir}")
    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    if not files:
        raise SystemExit(f"unpacked hwpx directory is empty: {source_dir}")

    mimetype_path = source_dir / MIMETYPE_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(MIMETYPE_NAME)
        info.compress_type = zipfile.ZIP_STORED
        mimetype = (
            mimetype_path.read_text(encoding="utf-8").strip()
            if mimetype_path.exists()
            else DEFAULT_MIMETYPE
        )
        archive.writestr(info, mimetype)
        for path in files:
            name = path.relative_to(source_dir).as_posix()
            if name == MIMETYPE_NAME:
                continue
            archive.write(path, name)
    return output_path
