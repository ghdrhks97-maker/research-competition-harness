"""Context-matched report icons (`rch render-icons`).

The icon-artist agent designs an icon *system* for the report (which motif
represents each chapter / practice task, on which accent color) and writes
`input/icons/icon-spec.json`. This module deterministically rasterizes that
spec into real PNG files — pure stdlib (zlib + struct), no Pillow — so the
same icons render on any machine. Agents never draw pixels themselves and
never fabricate binary files by hand; they only pick motifs and colors.

Icons are flat, geometric, and drawn from a fixed motif vocabulary, which
keeps them legible at report size and consistent across the document. The
PNGs go to `input/icons/rendered/` for the appendix, hwpx-designer
placement, or manual Hancom placement; in-body text keeps using glyph icons
(▶ ◆ ■) which render safely everywhere.
"""

from __future__ import annotations

import json
import math
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SIZE = 128  # output pixels; rendered with 2x supersampling
SS = 2
SPEC_FILE = "icon-spec.json"
RENDER_DIR = "rendered"
DEFAULT_BG = "#1F4E79"
DEFAULT_FG = "#FFFFFF"

Point = tuple[float, float]
Predicate = Callable[[float, float], bool]


@dataclass
class IconResult:
    name: str
    motif: str
    path: str


@dataclass
class RenderReport:
    icons: list[IconResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "icons": [icon.__dict__ for icon in self.icons],
            "errors": self.errors,
        }


def _hex_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid color: {color}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


# --- geometry predicates (coordinates normalized to [-1, 1]) ---------------


def _circle(cx: float, cy: float, r: float) -> Predicate:
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _ring(cx: float, cy: float, r_outer: float, r_inner: float) -> Predicate:
    outer = _circle(cx, cy, r_outer)
    inner = _circle(cx, cy, r_inner)
    return lambda x, y: outer(x, y) and not inner(x, y)


def _rect(x0: float, y0: float, x1: float, y1: float) -> Predicate:
    return lambda x, y: x0 <= x <= x1 and y0 <= y <= y1


def _segment(a: Point, b: Point, width: float) -> Predicate:
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy or 1e-9

    def inside(x: float, y: float) -> bool:
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length_sq))
        px, py = ax + t * dx, ay + t * dy
        return (x - px) ** 2 + (y - py) ** 2 <= width * width

    return inside


def _triangle(a: Point, b: Point, c: Point) -> Predicate:
    def sign(p: Point, q: Point, x: float, y: float) -> float:
        return (x - q[0]) * (p[1] - q[1]) - (p[0] - q[0]) * (y - q[1])

    def inside(x: float, y: float) -> bool:
        d1 = sign(a, b, x, y)
        d2 = sign(b, c, x, y)
        d3 = sign(c, a, x, y)
        has_neg = d1 < 0 or d2 < 0 or d3 < 0
        has_pos = d1 > 0 or d2 > 0 or d3 > 0
        return not (has_neg and has_pos)

    return inside


def _diamond(cx: float, cy: float, r: float) -> Predicate:
    return lambda x, y: abs(x - cx) + abs(y - cy) <= r


def _star(cx: float, cy: float, r: float) -> Predicate:
    # 5-point star via angular radius modulation.
    def inside(x: float, y: float) -> bool:
        dx, dy = x - cx, y - cy
        dist = math.hypot(dx, dy)
        if dist > r:
            return False
        angle = math.atan2(dy, dx)
        # radius shrinks between the 5 points
        wave = 0.5 + 0.5 * math.cos(5 * (angle + math.pi / 2))
        return dist <= r * (0.45 + 0.55 * wave)

    return inside


# --- motif vocabulary --------------------------------------------------------

MOTIFS: dict[str, list[Predicate]] = {
    # 음표 — 음악 교과
    "note": [_circle(-0.15, 0.35, 0.28), _rect(0.08, -0.55, 0.22, 0.4), _segment((0.15, -0.55), (0.5, -0.4), 0.1)],
    # 과녁 — 목표·필요성
    "target": [_ring(0, 0, 0.75, 0.55), _ring(0, 0, 0.38, 0.2), _circle(0, 0, 0.1)],
    # 상승 막대 — 성장·결과
    "growth": [_rect(-0.65, 0.15, -0.3, 0.65), _rect(-0.15, -0.15, 0.2, 0.65), _rect(0.35, -0.5, 0.7, 0.65)],
    # 체크 — 실천·완료
    "check": [_segment((-0.5, 0.05), (-0.12, 0.45), 0.14), _segment((-0.12, 0.45), (0.55, -0.35), 0.14)],
    # 연결 고리 — 협력·소통
    "link": [_ring(-0.28, 0, 0.42, 0.24), _ring(0.28, 0, 0.42, 0.24)],
    # 책 — 이론·배경
    "book": [_rect(-0.65, -0.45, -0.05, 0.5), _rect(0.05, -0.45, 0.65, 0.5), _rect(-0.05, -0.45, 0.05, 0.55)],
    # 돋보기 — 탐구·분석
    "magnifier": [_ring(-0.15, -0.15, 0.45, 0.28), _segment((0.18, 0.18), (0.6, 0.6), 0.12)],
    # 별 — 핵심 성과
    "star": [_star(0, 0, 0.75)],
    # 하트 — 정서·SEL
    "heart": [
        _circle(-0.26, -0.18, 0.32),
        _circle(0.26, -0.18, 0.32),
        _triangle((-0.55, 0.0), (0.55, 0.0), (0.0, 0.68)),
    ],
    # 말풍선 — 소통·발표
    "speech": [_circle(0, -0.08, 0.55), _triangle((-0.1, 0.3), (0.35, 0.3), (0.45, 0.68))],
    # 사람 — 학생·공동체
    "person": [_circle(0, -0.35, 0.25), _triangle((-0.5, 0.65), (0.5, 0.65), (0.0, -0.15))],
    # 톱니 — 방법·도구
    "gear": [
        _ring(0, 0, 0.5, 0.22),
        _rect(-0.1, -0.75, 0.1, -0.4),
        _rect(-0.1, 0.4, 0.1, 0.75),
        _rect(-0.75, -0.1, -0.4, 0.1),
        _rect(0.4, -0.1, 0.75, 0.1),
    ],
    # 화살표 — 확산·다음 단계
    "arrow": [_rect(-0.6, -0.14, 0.15, 0.14), _triangle((0.1, -0.4), (0.1, 0.4), (0.65, 0.0))],
    # 다이아 — 항목 불릿
    "diamond": [_diamond(0, 0, 0.6)],
}

PLATES: dict[str, Predicate | None] = {
    "circle": _circle(0, 0, 0.96),
    "rounded": lambda x, y: max(abs(x), abs(y)) <= 0.92 or _circle(math.copysign(0.72, x), math.copysign(0.72, y), 0.24)(x, y),
    "square": _rect(-0.92, -0.92, 0.92, 0.92),
    "none": None,
}


def _render_pixels(motif: str, plate: str, bg: str, fg: str) -> bytes:
    shapes = MOTIFS[motif]
    plate_fn = PLATES[plate]
    bg_rgb = _hex_rgb(bg)
    fg_rgb = _hex_rgb(fg)
    raw = bytearray()
    grid = SIZE * SS
    for py in range(SIZE):
        raw.append(0)  # PNG filter type 0 per scanline
        for px in range(SIZE):
            r = g = b = a = 0
            for sy in range(SS):
                for sx in range(SS):
                    x = ((px * SS + sx) + 0.5) / grid * 2 - 1
                    y = ((py * SS + sy) + 0.5) / grid * 2 - 1
                    if any(shape(x, y) for shape in shapes):
                        sr, sg, sb, sa = *fg_rgb, 255
                    elif plate_fn is not None and plate_fn(x, y):
                        sr, sg, sb, sa = *bg_rgb, 255
                    else:
                        sr = sg = sb = sa = 0
                    r += sr
                    g += sg
                    b += sb
                    a += sa
            n = SS * SS
            raw += bytes((r // n, g // n, b // n, a // n))
    return bytes(raw)


def _png_bytes(pixels: bytes) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(pixels, 9))
        + chunk(b"IEND", b"")
    )


def render_icon(motif: str, plate: str, bg: str, fg: str) -> bytes:
    if motif not in MOTIFS:
        raise ValueError(f"unknown motif: {motif}; expected one of: {', '.join(sorted(MOTIFS))}")
    if plate not in PLATES:
        raise ValueError(f"unknown plate: {plate}; expected one of: {', '.join(sorted(PLATES))}")
    return _png_bytes(_render_pixels(motif, plate, bg, fg))


def render_icons(workspace: Path) -> RenderReport:
    """Render every icon in input/icons/icon-spec.json to PNG files."""
    report = RenderReport()
    spec_path = workspace / "input" / "icons" / SPEC_FILE
    if not spec_path.exists():
        report.errors.append(
            f"icon spec not found: {spec_path}. icon-artist가 먼저 icon-spec.json을 작성해야 합니다."
        )
        return report
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.errors.append(f"invalid icon-spec.json: {exc}")
        return report
    icons = spec.get("icons") if isinstance(spec, dict) else None
    if not isinstance(icons, list) or not icons:
        report.errors.append("icon-spec.json must contain a non-empty icons[] list")
        return report

    out_dir = spec_path.parent / RENDER_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_lines = ["# 아이콘 매니페스트", "", "| 이름 | 모티프 | 용도 | 파일 |", "| --- | --- | --- | --- |"]
    for index, item in enumerate(icons):
        if not isinstance(item, dict) or not item.get("name"):
            report.errors.append(f"icons[{index}] must be an object with a name")
            continue
        name = str(item["name"]).strip().replace("/", "_")
        motif = str(item.get("motif", "diamond"))
        plate = str(item.get("plate", "circle"))
        bg = str(item.get("bg", DEFAULT_BG))
        fg = str(item.get("fg", DEFAULT_FG))
        try:
            data = render_icon(motif, plate, bg, fg)
        except ValueError as exc:
            report.errors.append(f"icons[{index}] ({name}): {exc}")
            continue
        target = out_dir / f"{name}.png"
        target.write_bytes(data)
        rel = target.relative_to(workspace).as_posix()
        report.icons.append(IconResult(name=name, motif=motif, path=rel))
        manifest_lines.append(
            f"| {name} | {motif} | {item.get('usage', '')} | `{rel}` |"
        )
    manifest_lines.append("")
    manifest_lines.append("본문 내 아이콘은 글리프(▶ ◆ ■)를 쓰고, PNG는 부록·hwpx-designer·한컴 수동 배치용이다.")
    manifest_lines.append("")
    (spec_path.parent / "icon-manifest.md").write_text("\n".join(manifest_lines), encoding="utf-8")
    return report
