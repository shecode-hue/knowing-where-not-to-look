"""Render a markdown document to PDF with fpdf2, no LaTeX needed."""
import argparse
import os
import re
from pathlib import Path

import matplotlib
from fpdf import FPDF

FONTS = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
INK = (26, 26, 28)
GREY = (108, 110, 116)
BLUE = (28, 74, 128)
RED = (178, 48, 58)
WASH = (246, 244, 241)
CODE_BG = (243, 243, 240)
LEFT, RIGHT, TOP = 16, 194, 15
WIDTH = RIGHT - LEFT

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def clean(text):
    text = _LINK.sub(r"\1", text)
    text = _BOLD.sub(r"\1", text)
    return _CODE.sub(r"\1", text)


class Doc(FPDF):
    def __init__(self, title):
        super().__init__(format="A4")
        self.title_text = title
        self.set_margins(LEFT, TOP, 210 - RIGHT)
        self.set_auto_page_break(True, margin=18)
        for style, name in (("", "DejaVuSans.ttf"), ("B", "DejaVuSans-Bold.ttf"),
                            ("I", "DejaVuSans-Oblique.ttf")):
            self.add_font("DJ", style, str(FONTS / name))
        self.add_font("MONO", "", str(FONTS / "DejaVuSansMono.ttf"))
        self.set_text_color(*INK)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-13)
        self.set_font("DJ", "", 7.4)
        self.set_text_color(*GREY)
        self.cell(0, 5, self.title_text, align="L")
        self.cell(0, 5, str(self.page_no()), align="R")
        self.set_text_color(*INK)

    def need(self, mm):
        if self.get_y() + mm > self.h - self.b_margin:
            self.add_page()

    def para(self, text, size=9.3, lead=4.7, style=""):
        if not text:
            return
        self.need(10)
        self.set_x(LEFT)
        self.set_font("DJ", style, size)
        self.multi_cell(WIDTH, lead, clean(text))
        self.set_x(LEFT)
        self.ln(1.6)

    def heading(self, level, text):
        sizes = {1: 16, 2: 12.5, 3: 10.5}
        self.need(22 if level == 1 else 15)
        self.ln(3.5 if level == 1 else 2.2)
        y = self.get_y()
        if level == 1:
            self.set_fill_color(*RED)
            self.rect(LEFT, y, 2.6, 8.4, "F")
        self.set_xy(LEFT + (5.5 if level == 1 else 0), y)
        self.set_font("DJ", "B", sizes.get(level, 10))
        self.set_text_color(*(INK if level < 3 else BLUE))
        self.multi_cell(WIDTH - 6, sizes[level] * 0.46, clean(text))
        self.set_text_color(*INK)
        self.set_x(LEFT)
        self.ln(1.8)

    def bullet(self, text, marker="•", indent=0):
        self.need(9)
        x = LEFT + indent
        self.set_xy(x, self.get_y())
        self.set_font("DJ", "", 9.3)
        self.cell(5.5, 4.7, marker)
        self.set_x(x + 5.5)
        self.multi_cell(WIDTH - 5.5 - indent, 4.7, clean(text))
        self.set_x(LEFT)
        self.ln(0.7)

    def code(self, lines):
        self.set_font("MONO", "", 7.9)
        height = 3.9 * len(lines) + 5
        self.need(height + 3)
        y = self.get_y() + 1
        self.set_fill_color(*CODE_BG)
        self.rect(LEFT, y, WIDTH, height, "F")
        self.set_fill_color(*GREY)
        self.rect(LEFT, y, 0.9, height, "F")
        self.set_xy(LEFT + 4, y + 2.4)
        for line in lines:
            self.set_x(LEFT + 4)
            self.cell(WIDTH - 8, 3.9, line[:108], new_x="LMARGIN",
                      new_y="NEXT")
        self.set_xy(LEFT, y + height + 2.6)

    def table(self, rows):
        head, body = rows[0], rows[1:]
        n = len(head)
        widths = self._widths(rows, n)
        self.need(16)
        self.ln(1)
        self._row(head, widths, bold=True, fill=WASH)
        for i, row in enumerate(body):
            self._row(row, widths, fill=(252, 252, 251) if i % 2 else None)
        self.ln(2.2)

    def _widths(self, rows, n):
        self.set_font("DJ", "", 8.2)
        want = []
        for col in range(n):
            longest = max(self.get_string_width(clean(r[col])) if col < len(r)
                          else 0 for r in rows)
            want.append(max(longest + 6, 16))
        total = sum(want)
        return [w * WIDTH / total for w in want]

    def _row(self, cells, widths, bold=False, fill=None):
        self.set_font("DJ", "B" if bold else "", 8.2)
        heights = []
        for text, w in zip(cells, widths):
            lines = self.multi_cell(w - 3, 4.1, clean(text), dry_run=True,
                                    output="LINES")
            heights.append(4.1 * len(lines))
        height = max(heights) + 2.6
        self.need(height + 2)
        y = self.get_y()
        if fill:
            self.set_fill_color(*fill)
            self.rect(LEFT, y, WIDTH, height, "F")
        x = LEFT
        for text, w in zip(cells, widths):
            self.set_xy(x + 1.5, y + 1.3)
            self.multi_cell(w - 3, 4.1, clean(text))
            x += w
        self.set_draw_color(226, 224, 220)
        self.set_line_width(0.25)
        self.line(LEFT, y + height, RIGHT, y + height)
        self.set_xy(LEFT, y + height)


def is_table(line):
    return line.strip().startswith("|") and line.count("|") >= 2


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md_path, pdf_path, title=None):
    text = Path(md_path).read_text()
    lines = text.split("\n")
    title = title or Path(md_path).stem.replace("_", " ").title()
    doc = Doc(title)
    doc.add_page()

    i, first = 0, True
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i].rstrip())
                i += 1
            doc.code(block or [""])
        elif is_table(line) and i + 1 < len(lines) and set(
                lines[i + 1].replace("|", "").replace(" ", "")) <= set("-:"):
            rows = [split_row(line)]
            i += 2
            while i < len(lines) and is_table(lines[i]):
                rows.append(split_row(lines[i]))
                i += 1
            doc.table(rows)
            continue
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            heading = line.lstrip("# ").strip()
            if first and level == 1:
                doc.set_font("DJ", "B", 21)
                doc.multi_cell(WIDTH, 10, clean(heading))
                doc.ln(2)
                first = False
            else:
                doc.heading(min(level, 3), heading)
        elif re.match(r"^\s*[-*] ", line):
            indent = (len(line) - len(line.lstrip())) * 1.6
            doc.bullet(re.sub(r"^\s*[-*] ", "", line), indent=indent)
        elif re.match(r"^\s*\d+\. ", line):
            num = re.match(r"^\s*(\d+)\. ", line).group(1)
            doc.bullet(re.sub(r"^\s*\d+\. ", "", line), marker=f"{num}.")
        elif line.strip() in ("---", "***", "___"):
            doc.need(6)
            doc.ln(2)
            doc.set_draw_color(215, 212, 208)
            doc.set_line_width(0.4)
            doc.line(LEFT, doc.get_y(), RIGHT, doc.get_y())
            doc.ln(3)
        elif line.startswith(">"):
            doc.para(line.lstrip("> "), style="I")
        elif line.strip():
            buf = [line]
            while (i + 1 < len(lines) and lines[i + 1].strip()
                   and not re.match(r"^\s*([-*#>|]|\d+\.|```)", lines[i + 1])):
                i += 1
                buf.append(lines[i].strip())
            doc.para(" ".join(buf))
        i += 1

    doc.output(str(pdf_path))
    return doc.page_no()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()
    for src in args.inputs:
        out = Path(src).with_suffix(".pdf")
        pages = render(src, out, args.title)
        print(f"{out}  ({pages} pages)")
