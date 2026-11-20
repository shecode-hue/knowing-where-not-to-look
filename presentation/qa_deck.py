"""Geometry QA: flag text overflow and shape overlaps in the built deck."""
import sys
from pathlib import Path

import matplotlib
from PIL import ImageFont
from pptx import Presentation
from pptx.util import Emu

FONTS = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf"
BODY = ImageFont.truetype(str(FONTS / "DejaVuSans.ttf"), 100)
EMU_IN = 914400


def text_lines(shape):
    out = []
    for p in shape.text_frame.paragraphs:
        text = "".join(r.text for r in p.runs)
        size = next((r.font.size.pt for r in p.runs
                     if r.font.size is not None), None)
        out.append((text, size or 12.0, bool(p._pPr is not None and
                                             p._pPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}buChar') is not None)))
    return out


def wrapped_height(shape):
    w_in = Emu(shape.width).inches - 0.12
    total = 0.0
    for text, size, bullet in text_lines(shape):
        if not text:
            total += size * 1.25
            continue
        usable = max(w_in - (0.17 if bullet else 0.0), 0.5)
        px_per_in = 100.0 / size * 72.0
        budget = usable * px_per_in
        words, line, lines = text.split(" "), "", 1
        for word in words:
            trial = (line + " " + word).strip()
            if BODY.getlength(trial) <= budget:
                line = trial
            else:
                lines += 1
                line = word
        total += lines * size * 1.3 + 7
    return total / 72.0


def boxes(slide):
    out = []
    for shape in slide.shapes:
        if shape.left is None:
            continue
        out.append((shape, Emu(shape.left).inches, Emu(shape.top).inches,
                    Emu(shape.width).inches, Emu(shape.height).inches))
    return out


def overlap(a, b):
    ax, ay, aw, ah = a[1:]
    bx, by, bw, bh = b[1:]
    x = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    y = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return x * y


def main(path):
    deck = Presentation(path)
    problems = 0
    for i, slide in enumerate(deck.slides, 1):
        shapes = boxes(slide)
        for shape, x, y, w, h in shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                need = wrapped_height(shape)
                if need > h * 1.10:
                    problems += 1
                    print(f"slide {i}: text may overflow "
                          f"'{shape.text_frame.text[:38]}' "
                          f"needs ~{need:.2f}in in {h:.2f}in")
            if y + h > 5.63 or x + w > 10.01:
                problems += 1
                print(f"slide {i}: shape leaves the canvas at "
                      f"({x:.2f},{y:.2f},{w:.2f},{h:.2f})")
        for j in range(len(shapes)):
            for k in range(j + 1, len(shapes)):
                a, b = shapes[j], shapes[k]
                inter = overlap(a, b)
                if inter < 0.03:
                    continue
                a_text = a[0].has_text_frame and a[0].text_frame.text.strip()
                b_text = b[0].has_text_frame and b[0].text_frame.text.strip()
                contained = inter > 0.9 * min(a[3] * a[4], b[3] * b[4])
                if a_text and b_text and not contained:
                    problems += 1
                    print(f"slide {i}: text boxes overlap "
                          f"({a[0].text_frame.text[:22]!r} / "
                          f"{b[0].text_frame.text[:22]!r}, {inter:.2f} sq in)")
    print(f"{len(deck.slides.__iter__.__self__._sldIdLst)} slides, "
          f"{problems} flagged")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wk_subgroup.pptx")
