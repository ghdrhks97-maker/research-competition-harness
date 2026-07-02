from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VisualCheck:
    hwpx_path: str
    ok: bool = False
    skipped: bool = False
    renderer: str = ""
    pdf_path: str = ""
    pages_dir: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_renderer() -> str:
    env = os.environ.get("RCH_RHWP_RENDER", "").strip()
    if env:
        return env
    candidates = [
        Path("/Users/hongtaekwan/연구대회_자동화/scripts/render_hwpx_with_rhwp.sh"),
        Path("/Users/hongtaekwan/연구대회_자동화/_transfer_windows_report_history_20260602/scripts/render_hwpx_with_rhwp.sh"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def _command(renderer: str, hwpx_path: Path, pdf_path: Path) -> list[str]:
    parts = shlex.split(renderer)
    if any("{input}" in part or "{output}" in part for part in parts):
        return [part.replace("{input}", str(hwpx_path)).replace("{output}", str(pdf_path)) for part in parts]
    return [*parts, str(hwpx_path), str(pdf_path)]


def run_visual_check(
    hwpx_path: Path,
    output_dir: Path,
    renderer: str | None = None,
    timeout: int = 900,
) -> VisualCheck:
    check = VisualCheck(hwpx_path=str(hwpx_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    if not hwpx_path.exists():
        check.errors.append(f"hwpx not found: {hwpx_path}")
        _write_reports(check, output_dir)
        return check

    renderer_cmd = _default_renderer() if renderer is None else renderer.strip()
    check.renderer = renderer_cmd
    if not renderer_cmd:
        check.skipped = True
        check.warnings.append("RHWP/Hancom visual renderer not configured. Set RCH_RHWP_RENDER.")
        _write_reports(check, output_dir)
        return check

    pdf_path = output_dir / "visual-check.pdf"
    cmd = _command(renderer_cmd, hwpx_path, pdf_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        check.errors.append(f"visual renderer not found: {cmd[0]}")
        _write_reports(check, output_dir)
        return check
    except subprocess.TimeoutExpired:
        check.errors.append("visual renderer timeout")
        _write_reports(check, output_dir)
        return check
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        check.errors.append(f"visual renderer failed(exit={proc.returncode}): {detail[0] if detail else 'unknown'}")
        _write_reports(check, output_dir)
        return check
    if not pdf_path.exists():
        check.errors.append(f"visual renderer produced no pdf: {pdf_path}")
        _write_reports(check, output_dir)
        return check

    check.pdf_path = str(pdf_path)
    pages_dir = output_dir / "visual-check-pages"
    pages_dir.mkdir(exist_ok=True)
    check.pages_dir = str(pages_dir)
    _rasterize_pdf(pdf_path, pages_dir, check)
    if any(pages_dir.glob("page-*.png")):
        check.metrics = _image_metrics(pages_dir, check)
    check.ok = not check.errors
    _write_reports(check, output_dir)
    return check


def _rasterize_pdf(pdf_path: Path, pages_dir: Path, check: VisualCheck) -> None:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        check.warnings.append("pdftoppm not found; PDF evidence only.")
        return
    for old in pages_dir.glob("page-*.png"):
        old.unlink()
    proc = subprocess.run(
        [pdftoppm, "-png", "-r", "120", str(pdf_path), str(pages_dir / "page")],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        check.warnings.append(f"pdftoppm failed(exit={proc.returncode}): {detail[0] if detail else 'unknown'}")


def _image_metrics(pages_dir: Path, check: VisualCheck) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops
    except ImportError:
        check.warnings.append("Pillow not installed; page coverage metrics skipped.")
        return {}

    rows = []
    for page in sorted(pages_dir.glob("page-*.png")):
        image = Image.open(page).convert("RGB")
        diff = ImageChops.difference(image, Image.new("RGB", image.size, "white"))
        bbox = diff.getbbox()
        if not bbox:
            rows.append({"page": page.stem, "coverage": 0, "top": 0, "bottom": 0, "status": "blank"})
            continue
        left, top, right, bottom = bbox
        coverage = (right - left) * (bottom - top) / (image.width * image.height)
        bottom_ratio = bottom / image.height
        status = "ok"
        if bottom_ratio < 0.72:
            status = "underfilled"
        elif bottom_ratio < 0.80:
            status = "thin"
        rows.append(
            {
                "page": page.stem,
                "coverage": round(coverage, 3),
                "top": round(top / image.height, 3),
                "bottom": round(bottom_ratio, 3),
                "status": status,
            }
        )
    return {
        "pages": len(rows),
        "underfilled": [row["page"] for row in rows if row["status"] == "underfilled"],
        "thin": [row["page"] for row in rows if row["status"] == "thin"],
        "rows": rows,
    }


def _write_reports(check: VisualCheck, output_dir: Path) -> None:
    (output_dir / "visual-check.json").write_text(
        json.dumps(check.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# 시각 검증 결과",
        "",
        f"- 대상: `{check.hwpx_path}`",
        f"- 판정: {'통과' if check.ok else '보류' if check.skipped else '실패'}",
        f"- renderer: `{check.renderer or 'none'}`",
    ]
    if check.pdf_path:
        lines.append(f"- PDF: `{check.pdf_path}`")
    if check.metrics:
        lines.append(f"- raster pages: {check.metrics.get('pages', 0)}")
        lines.append(f"- underfilled: {len(check.metrics.get('underfilled', []))}")
        lines.append(f"- thin: {len(check.metrics.get('thin', []))}")
    if check.errors:
        lines += ["", "## 오류", "", *[f"- {error}" for error in check.errors]]
    if check.warnings:
        lines += ["", "## 경고", "", *[f"- {warning}" for warning in check.warnings]]
    (output_dir / "visual-check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
