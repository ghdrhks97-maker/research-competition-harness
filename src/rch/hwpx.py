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


@dataclass
class BuildResult:
    hwpx_path: Path
    paragraph_count: int
    table_count: int
    heading_count: int
    image_count: int
    embedded_images: list[str] = field(default_factory=list)
    missing_images: list[str] = field(default_factory=list)


def _x(text: str) -> str:
    return escape(strip_inline_markup(text))


def _run(text: str, char_id: int = 0) -> str:
    return f'<hp:run charPrIDRef="{char_id}"><hp:t>{_x(text)}</hp:t></hp:run>'


def _paragraph(text: str, para_id: int = BODY_PARA, char_id: int = 0) -> str:
    return f'<hp:p paraPrIDRef="{para_id}" styleIDRef="0">{_run(text, char_id)}</hp:p>'


def _col_widths(col_count: int) -> list[int]:
    base = BODY_WIDTH // col_count
    widths = [base] * col_count
    widths[-1] += BODY_WIDTH - base * col_count
    return widths


def _tbl_open(row_cnt: int, col_cnt: int, border_fill: int) -> str:
    return (
        f'<hp:tbl id="0" zOrder="0" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
        f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
        f'rowCnt="{row_cnt}" colCnt="{col_cnt}" cellSpacing="0" borderFillIDRef="{border_fill}" noAdjust="0">'
        f'<hp:sz width="{BODY_WIDTH}" widthRelTo="ABSOLUTE" height="{row_cnt * ROW_HEIGHT}" '
        f'heightRelTo="ABSOLUTE" protect="0"/>'
        '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" '
        'holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="COLUMN" vertAlign="TOP" horzAlign="LEFT" '
        'vertOffset="0" horzOffset="0"/>'
        '<hp:outMargin left="0" right="0" top="141" bottom="141"/>'
        '<hp:inMargin left="510" right="510" top="141" bottom="141"/>'
    )


def _tc(paragraphs: str, col: int, row: int, width: int, fill: int) -> str:
    return (
        f'<hp:tc name="" header="0" hasMargin="0" protect="0" editable="0" dirty="0" '
        f'borderFillIDRef="{fill}">'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
        f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" '
        f'hasNumRef="0">{paragraphs}</hp:subList>'
        f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
        '<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{ROW_HEIGHT}"/>'
        '<hp:cellMargin left="510" right="510" top="141" bottom="141"/>'
        "</hp:tc>"
    )


def _table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    col_count = max(len(row) for row in rows)
    widths = _col_widths(col_count)
    parts = [_tbl_open(len(rows), col_count, 1)]
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
            parts.append(_tc(para, col_index, row_index, widths[col_index], fill_id))
        parts.append("</hp:tr>")
    parts.append("</hp:tbl>")
    # A table object lives inside a paragraph run in OWPML.
    return f'<hp:p paraPrIDRef="{BODY_PARA}" styleIDRef="0"><hp:run charPrIDRef="0">{"".join(parts)}</hp:run></hp:p>'


def _single_cell_table(paragraphs: str, fill_id: int) -> str:
    return (
        f'<hp:p paraPrIDRef="{BODY_PARA}" styleIDRef="0"><hp:run charPrIDRef="0">'
        f"{_tbl_open(1, 1, fill_id)}<hp:tr>"
        f"{_tc(paragraphs, 0, 0, BODY_WIDTH, fill_id)}"
        "</hp:tr></hp:tbl></hp:run></hp:p>"
    )


def _chapter_bar(text: str, level: int) -> str:
    # Chapter heading on an accent-filled full-width bar; the inner paragraph
    # keeps the heading paraPr id so toc matching still sees it as a heading.
    heading = _paragraph(text, HEADING_PARA.get(level, 3), CHAPTER_BAR_CHAR)
    return _single_cell_table(heading, CHAPTER_BAR_FILL_ID)


def _callout_box(title: str, lines: list[str]) -> str:
    paragraphs: list[str] = []
    if title:
        paragraphs.append(_paragraph(title, BODY_PARA, 2))
    for line in lines:
        paragraphs.append(_paragraph(line, BODY_PARA, 0))
    if not paragraphs:
        return ""
    return _single_cell_table("".join(paragraphs), BOX_BORDER_FILL_ID)


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
    result.paragraph_count = len(body)
    return "".join(body)


def _maybe_embed_image(src: str, images_root: Path, result: BuildResult) -> None:
    candidate = (images_root / src).resolve()
    if candidate.exists() and candidate.is_file():
        result.embedded_images.append(src)
    else:
        result.missing_images.append(src)


def _header_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<hh:head xmlns:hh="{HEAD_NS}" version="1.4" secCnt="1">'
        "<hh:refList>"
        '<hh:fontfaces itemCnt="7">'
        + "".join(
            f'<hh:fontface lang="{lang}" fontCnt="1">'
            '<hh:font id="0" face="함초롬바탕" type="TTF" isEmbedded="0"/></hh:fontface>'
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
        f'<hh:charPr id="{index}" height="{height}" textColor="{color}" shadeColor="none">'
        f'<hh:fontRef hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f"{bold_tag}</hh:charPr>"
    )


def _para_property(index: int, align: str = "LEFT") -> str:
    return (
        f'<hh:paraPr id="{index}" tabPrIDRef="0" condense="0" fontLineHeight="0" '
        f'snapToGrid="1" suppressLineNumbers="0" checked="0">'
        f'<hh:align horizontal="{align}" vertical="BASELINE"/>'
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
        "</hp:p>"
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


def _content_hpf() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<hpf:package xmlns:hpf="http://www.hancom.co.kr/schema/2011/hpf" '
        'xmlns:opf="http://www.idpf.org/2007/opf/" version="">'
        "<opf:metadata><opf:title>연구대회 보고서</opf:title></opf:metadata>"
        '<opf:manifest>'
        '<opf:item id="header" href="Contents/header.xml" media-type="application/xml"/>'
        '<opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>'
        "</opf:manifest>"
        '<opf:spine><opf:itemref idref="section0" linear="yes"/></opf:spine>'
        "</hpf:package>"
    )


def _manifest_xml(embedded_images: list[str]) -> str:
    entries = [
        '<odf:file-entry full-path="/" media-type="application/hwp+zip"/>',
        '<odf:file-entry full-path="Contents/header.xml" media-type="application/xml"/>',
        '<odf:file-entry full-path="Contents/section0.xml" media-type="application/xml"/>',
    ]
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


def build_hwpx(markdown_text: str, output_path: Path, images_root: Path) -> BuildResult:
    blocks = parse_markdown(markdown_text)
    result = BuildResult(
        hwpx_path=output_path,
        paragraph_count=0,
        table_count=0,
        heading_count=0,
        image_count=0,
    )
    body = _blocks_to_section(blocks, images_root, result)
    section = _section_xml(body)

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
        archive.writestr("META-INF/manifest.xml", _manifest_xml(result.embedded_images))
        archive.writestr("Contents/content.hpf", _content_hpf())
        archive.writestr("Contents/header.xml", _header_xml())
        archive.writestr("Contents/section0.xml", section)
        archive.writestr("Preview/PrvText.txt", _prv_text(blocks))
        for index, src in enumerate(result.embedded_images):
            data = (images_root / src).read_bytes()
            archive.writestr(f"BinData/image{index}", data)

    return result


def build_hwpx_from_bundle(bundle_paths: list[Path], output_path: Path, images_root: Path) -> BuildResult:
    parts: list[str] = []
    for path in bundle_paths:
        if path.exists():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return build_hwpx("\n\n".join(parts), output_path, images_root)
