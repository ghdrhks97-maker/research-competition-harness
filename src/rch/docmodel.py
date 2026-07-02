"""Shared markdown document model.

Parses the assembled markdown bundle into structured blocks so the HWPX
builder and render checker can reason about headings, paragraphs, tables,
lists, and images without re-implementing a parser each time.

This is intentionally a small, forgiving subset of markdown that matches
what the draft and assemble steps emit: ATX headings, GFM pipe tables,
ordered/unordered lists, images, and plain paragraphs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

BlockKind = Literal["heading", "paragraph", "table", "list", "image", "hr", "box"]

IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*\S)\s*$")
ORDERED_RE = re.compile(r"^\s*\d+[.)]\s+(?P<text>.*)$")
UNORDERED_RE = re.compile(r"^\s*[-*+]\s+(?P<text>.*)$")
# Design directive: a callout box the HWPX builder renders as a shaded
# single-cell table. `:::box 제목` ... `:::`
BOX_OPEN_RE = re.compile(r"^:::box(?:\s+(?P<title>.*\S))?\s*$")
BOX_CLOSE = ":::"


@dataclass
class Block:
    kind: BlockKind
    # heading: text; paragraph: text; image: alt
    text: str = ""
    level: int = 0
    # table rows (list of list of cell strings), first row treated as header
    rows: list[list[str]] = field(default_factory=list)
    # list items
    items: list[str] = field(default_factory=list)
    ordered: bool = False
    # image source
    src: str = ""


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _is_table_divider(line: str) -> bool:
    stripped = line.strip().strip("|")
    if not stripped:
        return False
    cells = [cell.strip() for cell in stripped.split("|")]
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def parse_markdown(text: str) -> list[Block]:
    """Parse markdown into an ordered list of blocks."""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks: list[Block] = []
    index = 0
    total = len(lines)
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            joined = " ".join(part.strip() for part in paragraph).strip()
            if joined:
                blocks.append(Block(kind="paragraph", text=joined))
            paragraph.clear()

    while index < total:
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        box_open = BOX_OPEN_RE.match(stripped)
        if box_open:
            flush_paragraph()
            index += 1
            box_lines: list[str] = []
            while index < total and lines[index].strip() != BOX_CLOSE:
                if lines[index].strip():
                    box_lines.append(lines[index].strip())
                index += 1
            if index < total:
                index += 1  # consume the closing :::
            blocks.append(
                Block(kind="box", text=(box_open["title"] or "").strip(), items=box_lines)
            )
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            blocks.append(
                Block(kind="heading", text=heading["text"].strip(), level=len(heading["hashes"]))
            )
            index += 1
            continue

        if stripped in {"---", "***", "___"}:
            flush_paragraph()
            blocks.append(Block(kind="hr"))
            index += 1
            continue

        # Standalone image line.
        image = IMAGE_RE.fullmatch(stripped)
        if image:
            flush_paragraph()
            blocks.append(Block(kind="image", text=image["alt"].strip(), src=image["src"].strip()))
            index += 1
            continue

        if _is_table_row(line):
            flush_paragraph()
            rows: list[list[str]] = []
            while index < total and _is_table_row(lines[index]):
                if _is_table_divider(lines[index]):
                    index += 1
                    continue
                rows.append(_split_table_row(lines[index]))
                index += 1
            if rows:
                blocks.append(Block(kind="table", rows=rows))
            continue

        list_match = ORDERED_RE.match(line) or UNORDERED_RE.match(line)
        if list_match:
            flush_paragraph()
            ordered = bool(ORDERED_RE.match(line))
            items: list[str] = []
            while index < total:
                current = lines[index]
                match = (ORDERED_RE if ordered else UNORDERED_RE).match(current)
                if not match:
                    break
                items.append(match["text"].strip())
                index += 1
            blocks.append(Block(kind="list", items=items, ordered=ordered))
            continue

        paragraph.append(line)
        index += 1

    flush_paragraph()
    return blocks


def iter_images(blocks: Iterable[Block]) -> list[str]:
    """Return every image source referenced in the blocks."""
    sources: list[str] = []
    for block in blocks:
        if block.kind == "image" and block.src:
            sources.append(block.src)
    return sources


def strip_inline_markup(text: str) -> str:
    """Reduce common inline markdown to plain text for renderers."""
    text = IMAGE_RE.sub(lambda match: match["alt"], text)
    text = re.sub(r"\[(?P<label>[^\]]+)\]\([^)]+\)", lambda match: match["label"], text)
    text = re.sub(r"\*\*(?P<inner>[^*]+)\*\*", lambda match: match["inner"], text)
    text = re.sub(r"(?<!\*)\*(?P<inner>[^*]+)\*(?!\*)", lambda match: match["inner"], text)
    text = re.sub(r"`(?P<inner>[^`]+)`", lambda match: match["inner"], text)
    return text
