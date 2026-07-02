"""HWPX finalizer (hwp/hwpx-finalizer-skill / `rch build-hwpx`).

Turns the assembled markdown bundle into a `.hwpx` package. HWPX is an
OWPML zip (a mimetype entry plus header/section XML), and this writer emits
a structurally complete skeleton: headings mapped to paragraph shapes,
body paragraphs, GFM tables mapped to `hp:tbl`, lists, and a generated
table of contents. Images are copied into `BinData/` and referenced with a
caption paragraph.

The first paragraph of the section carries the page/section definition
(`hp:secPr` with an A4 `hp:pagePr`). Without it Hancom opens the file but
renders a blank document — the text has no page to lay out on.

This produces a valid OWPML container. Because the harness cannot run
Hancom, `render-check` validates the structure (including that the page
definition exists) and the finalizer/human still confirm the visual result
in Hancom — the harness never conflates "structure valid" with "renders
correctly in Hancom".
"""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
from xml.sax.saxutils import escape

from rch.docmodel import Block, parse_markdown, strip_inline_markup

MIMETYPE = "application/hwp+zip"
HEAD_NS = "http://www.hancom.co.kr/hwpml/2011/head"
PARA_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
SECTION_NS = "http://www.hancom.co.kr/hwpml/2011/section"

# Paragraph-shape ids used in header.xml; index == heading level, 0 == body.
BODY_PARA = 0
HEADING_PARA = {1: 1, 2: 2, 3: 3, 4: 3, 5: 3, 6: 3}
HEADING_CHAR = {1: 1, 2: 2, 3: 3, 4: 3, 5: 3, 6: 3}
# Report styling: the first H1 becomes a large centered title, chapter H1s
# render as accent-filled bars (도비라), table header rows get an
# accent-colored bold face on a shaded fill, and :::box directives become
# shaded callout boxes.
TITLE_PARA = 4
TITLE_CHAR = 5
TABLE_HEADER_PARA = 4  # centered
TABLE_HEADER_CHAR = 4
CHAPTER_BAR_CHAR = 6  # white bold on the accent bar
ACCENT_COLOR = "#1F4E79"
TABLE_HEADER_FILL = "#D9E2F3"
BOX_FILL = "#EEF3FA"
BOX_BORDER_FILL_ID = 3
CHAPTER_BAR_FILL_ID = 4
# A4 body width in HWPUNIT (page 59528 minus 8504 margins each side).
# Tables must carry explicit hp:sz/hp:cellSz geometry — without cell widths
# Hancom cannot lay the table out and it renders collapsed.
BODY_WIDTH = 42520
ROW_HEIGHT = 1700

# Monotonic paragraph-id counter.  secPr carrier uses id="0", so body
# paragraphs start at 1.  Must be reset before each build invocation.
_para_id_counter = 0

def _next_para_id() -> int:
    global _para_id_counter
    _para_id_counter += 1
    return _para_id_counter



@dataclass
class BuildResult:
    hwpx_path: Path
    paragraph_count: int
    table_count: int
    heading_count: int
    image_count: int
    section_count: int = 1
    section_files: list[str] = field(default_factory=list)
    embedded_images: list[str] = field(default_factory=list)
    missing_images: list[str] = field(default_factory=list)


# Hancom's bundled fonts (함초롬 계열) have no emoji glyphs, so emoji render
# as empty boxes both in Hancom and in the rhwp PDF renderer. Strip them at
# the XML boundary; geometric shapes (■/▶/●, U+25A0–25FF) and arrows
# (U+2190–21FF) survive because the fonts do cover those.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # emoji & pictographs (astral plane)
    "☀-➿"  # misc symbols + dingbats (☀ ✅ ❓ ✂ …)
    "⬀-⯿"  # misc symbols and arrows (⭐ ⬆ …)
    "︀-️"  # variation selectors
    "‍"  # zero-width joiner
    "⃣"  # combining enclosing keycap
    "]+"
)


def _strip_unrenderable(text: str) -> str:
    text = _EMOJI_RE.sub("", text)
    return re.sub(r"  +", " ", text)


def _x(text: str) -> str:
    return escape(_strip_unrenderable(strip_inline_markup(text)))


def _run(text: str, char_id: int = 0) -> str:
    return f'<hp:run charPrIDRef="{char_id}"><hp:t>{_x(text)}</hp:t></hp:run>'


# Zero-height lineseg marker. Layout-cache honouring consumers (rhwp, and
# Hancom's PDF export) need one lineseg per paragraph: rhwp's HWPX parser
# leaves `line_segs` empty when the array is missing and then renders the
# whole paragraph as a single unwrapped line, so text overlaps. A single
# all-zero lineseg instead triggers rhwp's automatic reflow
# (`len == 1 && vertsize == 0`), which recomputes wrapping and heights from
# CharPr/ParaPr at load time.
LINESEG_RECALC = (
    "<hp:linesegarray>"
    '<hp:lineseg textpos="0" vertpos="0" vertsize="0" textheight="0"'
    ' baseline="0" spacing="0" horzpos="0" horzsize="0" flags="393216"/>'
    "</hp:linesegarray>"
)


def _paragraph(text: str, para_id: int = BODY_PARA, char_id: int = 0) -> str:
    pid = _next_para_id()
    return (
        f'<hp:p id="{pid}" paraPrIDRef="{para_id}" styleIDRef="0"'
        f' pageBreak="0" columnBreak="0" merged="0">'
        f'{_run(text, char_id)}{LINESEG_RECALC}</hp:p>'
    )


# Geometry estimation. These tables are anchored `treatAsChar` and layout
# consumers (Hancom's TAC line height, rhwp's measured layout) size the host
# line from the DECLARED hp:sz/hp:cellSz geometry — a lowballed height makes
# following text overlap the table and clips cell content. So the producer
# must declare realistic heights: estimate wrapped line counts from
# character widths (10pt body: hangul ≈ full width 1000 HWPUNIT, latin ≈ 520).
CELL_H_PADDING = 282  # top+bottom cellMargin (141 each)
CELL_W_PADDING = 1020  # left+right cellMargin (510 each)
LINE_BLOCK = 1600  # one 10pt text line incl. 160% line spacing, in HWPUNIT
MIN_COL_WIDTH = 3200


def _text_units(text: str) -> int:
    """Approximate rendered width of `text` at 10pt, in HWPUNIT."""
    units = 0
    for ch in text:
        units += 1000 if ord(ch) >= 0x2E80 else 520
    return units


def _cell_line_count(text: str, cell_width: int) -> int:
    avail = max(cell_width - CELL_W_PADDING, 600)
    plain = strip_inline_markup(text)
    return max(1, -(-_text_units(plain) // avail))  # ceil division


# Extra headroom on declared heights. Underestimating clips cell text in
# lineseg-honouring renderers; overestimating only adds whitespace (Hancom
# treats the declared height as a minimum), so err on the tall side.
HEIGHT_SLACK = 600


def _row_height(cells: list[str], widths: list[int]) -> int:
    lines = 1
    for index, cell in enumerate(cells):
        width = widths[index] if index < len(widths) else widths[-1]
        lines = max(lines, _cell_line_count(cell, width))
    return lines * LINE_BLOCK + CELL_H_PADDING + HEIGHT_SLACK


def _col_widths(col_count: int, rows: list[list[str]] | None = None) -> list[int]:
    if not rows:
        base = BODY_WIDTH // col_count
        widths = [base] * col_count
        widths[-1] += BODY_WIDTH - base * col_count
        return widths
    # Distribute the body width by each column's content weight so long-text
    # columns wrap less; every column keeps a readable minimum.
    weights = [1] * col_count
    for row in rows:
        for index in range(col_count):
            cell = row[index] if index < len(row) else ""
            weights[index] = max(weights[index], _text_units(strip_inline_markup(cell)))
    weights = [max(w, MIN_COL_WIDTH) for w in weights]
    total = sum(weights)
    widths = [max(MIN_COL_WIDTH, BODY_WIDTH * w // total) for w in weights]
    widths[-1] += BODY_WIDTH - sum(widths)
    if widths[-1] < MIN_COL_WIDTH:  # rebalance if the tail column got squeezed
        deficit = MIN_COL_WIDTH - widths[-1]
        widths[-1] = MIN_COL_WIDTH
        widest = max(range(col_count - 1), key=lambda i: widths[i], default=0)
        widths[widest] -= deficit
    return widths


def _tbl_open(row_cnt: int, col_cnt: int, border_fill: int, total_height: int) -> str:
    return (
        f'<hp:tbl id="0" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{row_cnt}" colCnt="{col_cnt}" cellSpacing="0" borderFillIDRef="{border_fill}" noAdjust="0">'
        f'<hp:sz width="{BODY_WIDTH}" widthRelTo="ABSOLUTE" height="{total_height}" '
        f'heightRelTo="ABSOLUTE" protect="0"/>'
        # treatAsChar="0" (자리차지): a char-anchored table cannot split across
        # pages in Hancom, so a tall table gets pushed wholesale to the next
        # page leaving a large gap. Non-TAC + pageBreak="CELL" splits by row,
        # matching how Hancom-authored reports (v203) anchor their tables.
        '<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        'vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="141" bottom="141"/>'
        '<hp:inMargin left="510" right="510" top="141" bottom="141"/>'
    )


def _tc(paragraphs: str, col: int, row: int, width: int, fill: int, height: int = ROW_HEIGHT) -> str:
    return (
        f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" '
        f'borderFillIDRef="{fill}">'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
        f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" '
        f'hasNumRef="0">{paragraphs}</hp:subList>'
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{height}"/>'
        '<hp:cellMargin left="510" right="510" top="141" bottom="141"/>'
        "</hp:tc>"
    )


def _table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    col_count = max(len(row) for row in rows)
    widths = _col_widths(col_count, rows)
    row_heights = [_row_height(row, widths) for row in rows]
    parts = [_tbl_open(len(rows), col_count, 1, sum(row_heights))]
    for row_index, row in enumerate(rows):
        parts.append("<hp:tr>")
        for col_index in range(col_count):
            cell = row[col_index] if col_index < len(row) else ""
            header = row_index == 0
            fill_id = 2 if header else 1  # header row sits on a shaded fill
            para = _paragraph(
                cell,
                TABLE_HEADER_PARA if header else BODY_PARA,
                TABLE_HEADER_CHAR if header else 0,
            )
            parts.append(
                _tc(para, col_index, row_index, widths[col_index], fill_id, row_heights[row_index])
            )
        parts.append("</hp:tr>")
    parts.append("</hp:tbl>")
    # A table object lives inside a paragraph run in OWPML.
    return (
        f'<hp:p paraPrIDRef="{BODY_PARA}" styleIDRef="0"><hp:run charPrIDRef="0">'
        f'{"".join(parts)}</hp:run>{LINESEG_RECALC}</hp:p>'
    )


def _single_cell_table(paragraphs: str, fill_id: int, height: int = ROW_HEIGHT) -> str:
    return (
        f'<hp:p paraPrIDRef="{BODY_PARA}" styleIDRef="0"><hp:run charPrIDRef="0">'
        f"{_tbl_open(1, 1, fill_id, height)}<hp:tr>"
        f"{_tc(paragraphs, 0, 0, BODY_WIDTH, fill_id, height)}"
        f"</hp:tr></hp:tbl></hp:run>{LINESEG_RECALC}</hp:p>"
    )


def _chapter_bar(text: str, level: int) -> str:
    # Chapter heading on an accent-filled full-width bar; the inner paragraph
    # keeps the heading paraPr id so toc matching still sees it as a heading.
    heading = _paragraph(text, HEADING_PARA.get(level, 3), CHAPTER_BAR_CHAR)
    # 16pt bar text: one line ≈ 16pt * 160% = 2560 HWPUNIT plus cell padding.
    return _single_cell_table(heading, CHAPTER_BAR_FILL_ID, 2560 + CELL_H_PADDING)


def _callout_box(title: str, lines: list[str]) -> str:
    paragraphs: list[str] = []
    height = CELL_H_PADDING
    if title:
        paragraphs.append(_paragraph(title, BODY_PARA, 2))
        # Box titles use the 13pt char shape → 13pt * 160% ≈ 2080 per line.
        height += _cell_line_count(title, BODY_WIDTH) * 2080
    for line in lines:
        paragraphs.append(_paragraph(line, BODY_PARA, 0))
        height += _cell_line_count(line, BODY_WIDTH) * LINE_BLOCK
    if not paragraphs:
        return ""
    return _single_cell_table("".join(paragraphs), BOX_BORDER_FILL_ID, height + HEIGHT_SLACK)


def _blocks_to_section(blocks: list[Block], images_root: Path, result: BuildResult) -> str:
    body: list[str] = []
    bin_index = 0
    title_pending = True  # the first H1 renders as the document title
    for block in blocks:
        if block.kind == "heading":
            if block.level == 1 and title_pending:
                body.append(_paragraph(block.text, TITLE_PARA, TITLE_CHAR))
                title_pending = False
            elif block.level == 1:
                body.append(_chapter_bar(block.text, block.level))
            else:
                body.append(
                    _paragraph(block.text, HEADING_PARA.get(block.level, 3), HEADING_CHAR.get(block.level, 3))
                )
            result.heading_count += 1
        elif block.kind == "paragraph":
            body.append(_paragraph(block.text))
        elif block.kind == "table":
            body.append(_table(block.rows))
            result.table_count += 1
        elif block.kind == "box":
            rendered = _callout_box(block.text, block.items)
            if rendered:
                body.append(rendered)
        elif block.kind == "list":
            for item in block.items:
                prefix = "• "
                body.append(_paragraph(f"{prefix}{item}"))
        elif block.kind == "image":
            bin_index += 1
            caption = block.text or Path(block.src).name
            body.append(_paragraph(f"[사진: {caption}]"))
            result.image_count += 1
            _maybe_embed_image(block.src, images_root, result)
        elif block.kind == "hr":
            body.append(_paragraph("────────"))
    result.paragraph_count += len(body)
    return "".join(body)


def _maybe_embed_image(src: str, images_root: Path, result: BuildResult) -> None:
    candidate = (images_root / src).resolve()
    if candidate.exists() and candidate.is_file():
        result.embedded_images.append(src)
    else:
        result.missing_images.append(src)


def _header_xml(section_count: int = 1) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<hh:head xmlns:hh="{HEAD_NS}" version="1.4" secCnt="{section_count}">'
        "<hh:refList>"
        '<hh:fontfaces itemCnt="7">'
        + "".join(
            f'<hh:fontface lang="{lang}" fontCnt="1">'
            '<hh:font id="0" face="함초롬돋움" type="TTF" isEmbedded="0"/></hh:fontface>'
            for lang in ("HANGUL", "LATIN", "HANJA", "JAPANESE", "OTHER", "SYMBOL", "USER")
        )
        + "</hh:fontfaces>"
        '<hh:charProperties itemCnt="7">'
        + "".join(
            _char_property(index, height, bold, color)
            for index, (height, bold, color) in enumerate(
                [
                    (1000, 0, "#000000"),  # 0 body
                    (1600, 1, ACCENT_COLOR),  # 1 H1 장 제목
                    (1300, 1, ACCENT_COLOR),  # 2 H2 / box title
                    (1100, 1, "#000000"),  # 3 H3+
                    (1000, 1, ACCENT_COLOR),  # 4 table header
                    (2000, 1, ACCENT_COLOR),  # 5 document title
                    (1600, 1, "#FFFFFF"),  # 6 chapter bar (white on accent)
                ]
            )
        )
        + "</hh:charProperties>"
        '<hh:paraProperties itemCnt="5">'
        + "".join(
            _para_property(index, align)
            for index, align in enumerate(("JUSTIFY", "CENTER", "LEFT", "LEFT", "CENTER"))
        )
        + "</hh:paraProperties>"
        '<hh:styles itemCnt="1"><hh:style id="0" type="PARA" name="바탕글" engName="Normal" '
        'paraPrIDRef="0" charPrIDRef="0" nextStyleIDRef="0"/></hh:styles>'
        '<hh:borderFills itemCnt="5">'
        '<hh:borderFill id="0" threeD="0" shadow="0"/>'
        '<hh:borderFill id="1" threeD="0" shadow="0">'
        '<hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        "</hh:borderFill>"
        '<hh:borderFill id="2" threeD="0" shadow="0">'
        '<hh:leftBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hh:rightBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hh:topBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hh:bottomBorder type="SOLID" width="0.12 mm" color="#000000"/>'
        f'<hh:fillBrush><hh:winBrush faceColor="{TABLE_HEADER_FILL}" hatchColor="{ACCENT_COLOR}" alpha="0"/></hh:fillBrush>'
        "</hh:borderFill>"
        f'<hh:borderFill id="{BOX_BORDER_FILL_ID}" threeD="0" shadow="0">'
        f'<hh:leftBorder type="SOLID" width="0.4 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:rightBorder type="SOLID" width="0.4 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:topBorder type="SOLID" width="0.4 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:bottomBorder type="SOLID" width="0.4 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:fillBrush><hh:winBrush faceColor="{BOX_FILL}" hatchColor="{ACCENT_COLOR}" alpha="0"/></hh:fillBrush>'
        "</hh:borderFill>"
        f'<hh:borderFill id="{CHAPTER_BAR_FILL_ID}" threeD="0" shadow="0">'
        f'<hh:leftBorder type="SOLID" width="0.12 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:rightBorder type="SOLID" width="0.12 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:topBorder type="SOLID" width="0.12 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:bottomBorder type="SOLID" width="0.12 mm" color="{ACCENT_COLOR}"/>'
        f'<hh:fillBrush><hh:winBrush faceColor="{ACCENT_COLOR}" hatchColor="{ACCENT_COLOR}" alpha="0"/></hh:fillBrush>'
        "</hh:borderFill>"
        "</hh:borderFills>"
        "</hh:refList></hh:head>"
    )


def _char_property(index: int, height: int, bold: int, color: str = "#000000") -> str:
    bold_tag = "<hh:bold/>" if bold else ""
    return (
        f'<hh:charPr id="{index}" height="{height}" textColor="{color}" shadeColor="none"'
        f' useFontSpace="0" useKerning="0" symMark="NONE" borderFillIDRef="0">'
        f'<hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        f'<hh:spacing hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        f'<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f'<hh:underline type="NONE" shape="SOLID" color="#000000"/>'
        f'<hh:strikeout shape="NONE" color="#000000"/>'
        f'<hh:outline type="NONE"/>'
        f'<hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/>'
        f"{bold_tag}</hh:charPr>"
    )


def _para_property(index: int, align: str = "LEFT") -> str:
    return (
        f'<hh:paraPr id="{index}" tabPrIDRef="0" condense="0" fontLineHeight="1" '
        f'snapToGrid="1" suppressLineNumbers="0" checked="0">'
        f'<hh:align horizontal="{align}" vertical="BASELINE"/>'
        f'<hh:lineSpacing type="PERCENT" value="160"/>'
        f"</hh:paraPr>"
    )


# A4 page in HWPUNIT (1/7200 inch): 210mm x 297mm with report margins.
def _sec_pr() -> str:
    return (
        '<hp:secPr id="" textDirection="HORIZONTAL" spaceColumns="1134" tabStop="8000" '
        'tabStopVal="4000" tabStopUnit="HWPUNIT" outlineShapeIDRef="0" memoShapeIDRef="0" '
        'textVerticalWidthHead="0" masterPageCnt="0">'
        '<hp:grid lineGrid="0" charGrid="0" wonggojiFormat="0" strtnum="0"/>'
        '<hp:startNum pageStartsOn="BOTH" page="0" pic="0" tbl="0" equation="0"/>'
        '<hp:visibility hideFirstHeader="0" hideFirstFooter="0" hideFirstMasterPage="0" '
        'border="SHOW_ALL" fill="SHOW_ALL" hideFirstPageNum="0" hideFirstEmptyLine="0" showLineNumber="0"/>'
        '<hp:lineNumberShape restartType="0" countBy="0" distance="0" startNumber="0"/>'
        '<hp:pagePr landscape="0" width="59528" height="84188" gutterType="LEFT_ONLY">'
        '<hp:margin header="4252" footer="4252" gutter="0" left="8504" right="8504" top="5668" bottom="4252"/>'
        "</hp:pagePr>"
        '<hp:footNotePr>'
        '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
        '<hp:noteLine length="5666" type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>'
        '<hp:numbering type="CONTINUOUS" newNum="1"/>'
        '<hp:placement place="EACH_COLUMN" beneathText="0"/>'
        "</hp:footNotePr>"
        '<hp:endNotePr>'
        '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar=")" supscript="0"/>'
        '<hp:noteLine length="14692" type="SOLID" width="0.12 mm" color="#000000"/>'
        '<hp:noteSpacing betweenNotes="0" belowLine="567" aboveLine="850"/>'
        '<hp:numbering type="CONTINUOUS" newNum="1"/>'
        '<hp:placement place="END_OF_DOCUMENT" beneathText="0"/>'
        "</hp:endNotePr>"
        '<hp:pageBorderFill type="BOTH" borderFillIDRef="0" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">'
        '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/></hp:pageBorderFill>'
        '<hp:pageBorderFill type="EVEN" borderFillIDRef="0" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">'
        '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/></hp:pageBorderFill>'
        '<hp:pageBorderFill type="ODD" borderFillIDRef="0" textBorder="PAPER" headerInside="0" footerInside="0" fillArea="PAPER">'
        '<hp:offset left="1417" right="1417" top="1417" bottom="1417"/></hp:pageBorderFill>'
        "</hp:secPr>"
    )


def _secpr_paragraph() -> str:
    # The first paragraph of a section carries the page/section definition.
    # Without it Hancom opens the file but has no page to render text onto.
    return (
        f'<hp:p id="0" paraPrIDRef="{BODY_PARA}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="0">{_sec_pr()}</hp:run>'
        f'<hp:run charPrIDRef="0"><hp:t></hp:t></hp:run>'
        f"{LINESEG_RECALC}</hp:p>"
    )


def _section_xml(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<hs:sec xmlns:hs="{SECTION_NS}" xmlns:hp="{PARA_NS}">'
        f"{_secpr_paragraph()}{body}"
        "</hs:sec>"
    )


def _version_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hv:HCFVersion xmlns:hv="http://www.hancom.co.kr/hwpml/2011/version" '
        'tagetApplication="WORDPROCESSOR" major="5" minor="1" micro="1" buildNumber="0" os="1" '
        'application="research-competition-harness"/>'
    )


def _container_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<ocf:container xmlns:ocf="urn:oasis:names:tc:opendocument:xmlns:container" '
        'xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf">'
        '<ocf:rootfiles><ocf:rootfile full-path="Contents/content.hpf" '
        'media-type="application/hwpml-package+xml"/></ocf:rootfiles></ocf:container>'
    )


def _content_hpf(section_files: list[str] | None = None) -> str:
    section_files = section_files or ["Contents/section0.xml"]
    manifest_items = [
        '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>',
    ]
    spine_items = []
    for index, section_file in enumerate(section_files):
        section_id = f"section{index}"
        manifest_items.append(
            f'<opf:item id="{section_id}" href="{section_file}" media-type="application/xml"/>'
        )
        spine_items.append(f'<opf:itemref idref="{section_id}" linear="yes"/>')
    return "".join(
        [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n',
            '<hpf:package xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" ',
            'xmlns:opf="http://www.idpf.org/2007/opf/" version="">',
            "<opf:metadata><opf:title>연구대회 보고서</opf:title></opf:metadata>",
            "<opf:manifest>",
            "".join(manifest_items),
            "</opf:manifest>",
            "<opf:spine>",
            "".join(spine_items),
            "</opf:spine>",
            "</hpf:package>",
        ]
    )


def _manifest_xml(embedded_images: list[str], section_files: list[str] | None = None) -> str:
    section_files = section_files or ["Contents/section0.xml"]
    entries = [
        '<odf:file-entry full-path="/" media-type="application/hwp+zip"/>',
        '<odf:file-entry full-path="Contents/header.xml" media-type="application/xml"/>',
    ]
    for section_file in section_files:
        entries.append(f'<odf:file-entry full-path="{section_file}" media-type="application/xml"/>')
    for index, _ in enumerate(embedded_images):
        entries.append(f'<odf:file-entry full-path="BinData/image{index}" media-type="image/*"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<odf:manifest xmlns:odf="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
        + "".join(entries)
        + "</odf:manifest>"
    )


def _settings_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<ha:HWPApplicationSetting xmlns:ha="http://www.hancom.co.kr/hwpml/2011/app"/>'
    )


def _prv_text(blocks: list[Block]) -> str:
    lines: list[str] = []
    for block in blocks:
        if block.kind in {"heading", "paragraph"}:
            lines.append(strip_inline_markup(block.text))
        elif block.kind == "list":
            lines.extend(strip_inline_markup(item) for item in block.items)
    return "\n".join(lines)


def _write_hwpx_package(
    sections: list[tuple[str, str]],
    output_path: Path,
    images_root: Path,
    result: BuildResult,
) -> BuildResult:
    global _para_id_counter
    _para_id_counter = 0
    section_files: list[str] = []
    section_xmls: list[tuple[str, str]] = []
    preview_blocks: list[Block] = []
    for index, (_name, markdown_text) in enumerate(sections):
        blocks = parse_markdown(markdown_text)
        preview_blocks.extend(blocks)
        body = _blocks_to_section(blocks, images_root, result)
        section_file = f"Contents/section{index}.xml"
        section_files.append(section_file)
        section_xmls.append((section_file, _section_xml(body)))
    result.section_count = len(section_files)
    result.section_files = section_files

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        # mimetype must be first and stored uncompressed.
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        archive.writestr(info, MIMETYPE)
        archive.writestr("version.xml", _version_xml())
        archive.writestr("settings.xml", _settings_xml())
        archive.writestr("META-INF/container.xml", _container_xml())
        archive.writestr("META-INF/manifest.xml", _manifest_xml(result.embedded_images, section_files))
        archive.writestr("Contents/content.hpf", _content_hpf(section_files))
        archive.writestr("Contents/header.xml", _header_xml(len(section_files)))
        for section_file, section_xml in section_xmls:
            archive.writestr(section_file, section_xml)
        archive.writestr("Preview/PrvText.txt", _prv_text(preview_blocks))
        for index, src in enumerate(result.embedded_images):
            data = (images_root / src).read_bytes()
            archive.writestr(f"BinData/image{index}", data)

    return result


def build_hwpx(markdown_text: str, output_path: Path, images_root: Path) -> BuildResult:
    result = BuildResult(
        hwpx_path=output_path,
        paragraph_count=0,
        table_count=0,
        heading_count=0,
        image_count=0,
    )
    return _write_hwpx_package([("body", markdown_text)], output_path, images_root, result)


def build_hwpx_from_bundle(bundle_paths: list[Path], output_path: Path, images_root: Path) -> BuildResult:
    parts: list[str] = []
    for path in bundle_paths:
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return build_hwpx("\n\n".join(parts), output_path, images_root)


def _read_json_file(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", strip_inline_markup(text)).strip()


def _first_nonempty(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _cover_markdown(workspace: Path, preview: bool = False) -> str:
    profile = _read_json_file(workspace / "input" / "rules" / "competition-profile.json")
    brainstorm = _read_json_file(workspace / "input" / "ideas" / "brainstorm.json")
    title = _first_nonempty(
        profile.get("recommended_title"),
        brainstorm.get("recommended_title"),
        profile.get("title"),
        "연구대회 보고서",
    )
    competition = _first_nonempty(profile.get("competition_name"), profile.get("name"), "연구대회")
    major = _first_nonempty(profile.get("major"), profile.get("subject"), "교과")
    level = _first_nonempty(profile.get("level"), profile.get("class_context"))
    lines = [
        "# 연구대회 보고서",
        "",
        f"## {_plain(title)}",
        "",
        "| 항목 | 내용 |",
        "|---|---|",
        f"| 참가 대회 | {_plain(competition)} |",
        f"| 교과/분야 | {_plain(major)} |",
    ]
    if level:
        lines.append(f"| 대상 | {_plain(level)} |")
    lines += [
        "",
        ":::box 표지 확인",
        "대회 양식의 표지 서식이 있으면 최종 편집 단계에서 해당 양식 기준으로 재정렬한다.",
        ":::",
    ]
    if preview:
        lines += [
            "",
            ":::box 중간 확인본",
            "이 파일은 final gate 또는 build gate를 통과하지 않은 preview입니다. 제출용 최종본이 아닙니다.",
            ":::",
        ]
    return "\n".join(lines)


# `rch assemble` prefixes each bundle file with provenance scaffolding
# (`# summary-sheet.md`, `## draft-writer / antigravity`). Useful for lane
# traceability, but in the built report they render as fake titles and break
# the TOC↔heading match, so the finalizer drops them.
_SCAFFOLD_FILE_HEADING = re.compile(r"^#\s+[\w.-]+\.md\s*$")
_SCAFFOLD_LANE_HEADING = re.compile(r"^##\s+[\w-]+\s*/\s*[\w-]+\s*$")


def _strip_assembly_scaffold(text: str) -> str:
    lines = [
        line
        for line in text.splitlines()
        if not _SCAFFOLD_FILE_HEADING.match(line) and not _SCAFFOLD_LANE_HEADING.match(line)
    ]
    return "\n".join(lines).strip()


def _read_part(path: Path, fallback_title: str) -> str:
    if path.exists():
        text = _strip_assembly_scaffold(path.read_text(encoding="utf-8", errors="replace"))
        if text:
            return text
    return f"# {fallback_title}\n\n자료 없음"


def build_research_report_hwpx(
    workspace: Path,
    output_path: Path,
    *,
    images_root: Path | None = None,
    preview: bool = False,
) -> BuildResult:
    images_root = images_root or workspace
    output_dir = workspace / "output"
    sections = [
        ("cover", _cover_markdown(workspace, preview=preview)),
        ("summary", _read_part(output_dir / "summary-sheet.md", "요약서")),
        ("toc", _read_part(output_dir / "toc.md", "목차")),
        ("body", _read_part(output_dir / "report-draft.md", "본문")),
        ("appendix", _read_part(output_dir / "appendix.md", "부록")),
    ]
    result = BuildResult(
        hwpx_path=output_path,
        paragraph_count=0,
        table_count=0,
        heading_count=0,
        image_count=0,
    )
    return _write_hwpx_package(sections, output_path, images_root, result)
