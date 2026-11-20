"""Rasterize each slide of a pptx to PNG so the design can actually be seen."""
import io
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.util import Emu

DPI = 150
W, H = int(10 * DPI), int(5.625 * DPI)
DF = Path("/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts")
FONTS = {
    ("Cambria", False): DF / "Cambria.ttc",
    ("Cambria", True): DF / "Cambriab.ttf",
    ("Calibri", False): DF / "Calibri.ttf",
    ("Calibri", True): DF / "Calibrib.ttf",
}
_cache = {}


def font(name, size_pt, bold):
    key = (name, bold, size_pt)
    if key not in _cache:
        path = FONTS.get((name, bold)) or FONTS[("Calibri", bold)]
        _cache[key] = ImageFont.truetype(str(path), int(size_pt * DPI / 72))
    return _cache[key]


def rgb(color, default):
    try:
        v = color.rgb
        return (v[0], v[1], v[2])
    except Exception:
        return default


def para_font_name(run, theme_head="Cambria", theme_body="Calibri"):
    name = run.font.name
    if name in ("Cambria", "Calibri"):
        return name
    return theme_body


def draw_text_frame(img, draw, shape, default_color):
    x = Emu(shape.left).inches * DPI
    y = Emu(shape.top).inches * DPI
    w = Emu(shape.width).inches * DPI
    tf = shape.text_frame
    cy = y + 2
    for p in tf.paragraphs:
        runs = p.runs
        if not runs:
            cy += 14
            continue
        size = next((r.font.size.pt for r in runs if r.font.size), 12.0)
        spacing = p.line_spacing if isinstance(p.line_spacing, float) else 1.22
        line_h = size * DPI / 72 * spacing
        bullet = p._pPr is not None and p._pPr.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}buChar"
        ) is not None
        segs = []
        for r in runs:
            fname = para_font_name(r)
            fsize = r.font.size.pt if r.font.size else size
            col = rgb(r.font.color, default_color)
            for word in r.text.split(" "):
                segs.append((word, font(fname, fsize, bool(r.font.bold)), col))
        lines, line, used = [], [], 0.0
        indent = 26 if bullet else 0
        for word, f, col in segs:
            wlen = draw.textlength(word + " ", font=f)
            if line and used + wlen > w - 8 - indent:
                lines.append(line)
                line, used = [], 0.0
            line.append((word, f, col))
            used += wlen
        if line:
            lines.append(line)
        align = p.alignment
        for li, ln in enumerate(lines):
            total = sum(draw.textlength(t + " ", font=f) for t, f, _ in ln)
            cx = x + 4 + indent
            if str(align) == "RIGHT (3)":
                cx = x + w - total - 4
            if bullet and li == 0:
                draw.text((x + 6, cy), "•", font=ln[0][1],
                          fill=ln[0][2])
            for t, f, col in ln:
                draw.text((cx, cy), t, font=f, fill=col)
                cx += draw.textlength(t + " ", font=f)
            cy += line_h
        try:
            if p.space_after is not None:
                cy += p.space_after.pt * DPI / 72
        except Exception:
            pass


def draw_table(img, draw, shape, line_rgb):
    x0 = Emu(shape.left).inches * DPI
    y0 = Emu(shape.top).inches * DPI
    tbl = shape.table
    col_w = [Emu(c.width).inches * DPI for c in tbl.columns]
    row_h = [Emu(r.height).inches * DPI for r in tbl.rows]
    cy = y0
    for ri, row in enumerate(tbl.rows):
        cx = x0
        for ci, cell in enumerate(row.cells):
            fill = cell.fill
            try:
                if fill.type is not None and str(fill.type) != "BACKGROUND (5)":
                    col = rgb(fill.fore_color, None)
                    if col:
                        draw.rectangle([cx, cy, cx + col_w[ci],
                                        cy + row_h[ri]], fill=col)
            except Exception:
                pass
            para = cell.text_frame.paragraphs[0]
            runs = para.runs or []
            text = "".join(r.text for r in runs)
            if text:
                r0 = runs[0]
                size = r0.font.size.pt if r0.font.size else 12
                f = font(para_font_name(r0), size, bool(r0.font.bold))
                col = rgb(r0.font.color, (20, 20, 20))
                ty = cy + (row_h[ri] - size * DPI / 72) / 2
                draw.text((cx + 9, ty), text, font=f, fill=col)
            cx += col_w[ci]
        cy += row_h[ri]
        tone = line_rgb if ri > 0 else (26, 26, 28)
        width = 1 if ri > 0 else 2
        draw.line([x0, cy, x0 + sum(col_w), cy], fill=tone, width=width)
    draw.line([x0, y0 + row_h[0], x0 + sum(col_w), y0 + row_h[0]],
              fill=(26, 26, 28), width=2)


def main(path):
    deck = Presentation(path)
    out = Path("preview")
    out.mkdir(exist_ok=True)
    for i, slide in enumerate(deck.slides, 1):
        bg = (255, 255, 255)
        try:
            lay = slide.slide_layout
            col = rgb(lay.background.fill.fore_color, None)
            if col:
                bg = col
        except Exception:
            pass
        try:
            col = rgb(slide.background.fill.fore_color, None)
            if col:
                bg = col
        except Exception:
            pass
        img = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(img)
        default = (26, 26, 28) if sum(bg) > 380 else (235, 238, 244)
        for shape in slide.shapes:
            if shape.shape_type == 13:
                blob = shape.image.blob
                pic = Image.open(io.BytesIO(blob)).convert("RGB")
                pw = int(Emu(shape.width).inches * DPI)
                ph = int(Emu(shape.height).inches * DPI)
                scale = max(pw / pic.size[0], ph / pic.size[1])
                rw, rh = int(pic.size[0] * scale), int(pic.size[1] * scale)
                pic = pic.resize((rw, rh))
                cx, cy = (rw - pw) // 2, (rh - ph) // 2
                pic = pic.crop((cx, cy, cx + pw, cy + ph))
                img.paste(pic, (int(Emu(shape.left).inches * DPI),
                                int(Emu(shape.top).inches * DPI)))
            elif shape.has_table:
                draw_table(img, draw, shape, (120, 126, 136))
            elif shape.shape_type == 1:
                try:
                    col = rgb(shape.fill.fore_color, None)
                    if col:
                        x = int(Emu(shape.left).inches * DPI)
                        y = int(Emu(shape.top).inches * DPI)
                        w2 = int(Emu(shape.width).inches * DPI)
                        h2 = int(Emu(shape.height).inches * DPI)
                        m = re.search(r'alpha val="(\d+)"',
                                      shape.fill._xPr.xml
                                      if hasattr(shape.fill, "_xPr") else
                                      shape._element.xml)
                        if m:
                            a = int(int(m.group(1)) / 100000 * 255)
                            layer = Image.new("RGBA", (w2, h2),
                                              col + (a,))
                            img.paste(Image.alpha_composite(
                                img.crop((x, y, x + w2, y + h2))
                                   .convert("RGBA"), layer).convert("RGB"),
                                (x, y))
                        else:
                            draw.rectangle([x, y, x + w2, y + h2], fill=col)
                except Exception:
                    pass
                if shape.has_text_frame:
                    draw_text_frame(img, draw, shape, default)
            elif shape.has_text_frame:
                draw_text_frame(img, draw, shape, default)
        img.save(out / f"slide-{i:02d}.png")
    print(f"{len(deck.slides._sldIdLst)} previews -> {out}/")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "knowing_where_not_to_look.pptx")
