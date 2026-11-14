"""Cheap layout audit: every text box must fit its own frame and stay on the slide."""

from pathlib import Path

from PIL import ImageFont
from pptx import Presentation
from pptx.util import Emu

DECK = Path(__file__).resolve().parent / "MetaVision.pptx"
REG = r"C:\Windows\Fonts\segoeui.ttf"
BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
_cache: dict = {}


def font(size, bold):
    key = (round(size, 1), bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(BOLD if bold else REG, max(6, int(round(size))))
    return _cache[key]


def wrap_height(paragraphs, width_pt):
    total = 0.0
    for p in paragraphs:
        runs = []
        for r in p.runs:
            size = r.font.size.pt if r.font.size else 18
            runs.append((r.text, size, bool(r.font.bold)))
        if not runs:
            continue
        lines, cur = 1, 0.0
        for text, size, bold in runs:
            f = font(size, bold)
            for word in text.replace("\n", " \n ").split(" "):
                if word == "":
                    continue
                w = f.getlength(word + " ")
                if cur + w > width_pt and cur > 0:
                    lines += 1
                    cur = 0
                cur += w
        max_size = max(s for _, s, _ in runs)
        total += lines * max_size * (p.line_spacing or 1.05) * 1.02
        total += (p.space_after.pt if p.space_after is not None else 0)
    return total


def main():
    prs = Presentation(str(DECK))
    sw, sh = prs.slide_width, prs.slide_height
    problems = 0
    for i, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.left < -10000 or shape.top < -10000 or shape.left + shape.width > sw + 10000 or shape.top + shape.height > sh + 10000:
                print(f"slide {i}: off-slide {shape.shape_type} {shape.name}")
                problems += 1
            if not shape.has_text_frame:
                continue
            tf = shape.text_frame
            text = tf.text.strip()
            if not text:
                continue
            wpt = Emu(shape.width).pt - Emu(tf.margin_left).pt - Emu(tf.margin_right).pt
            hpt = Emu(shape.height).pt - Emu(tf.margin_top).pt - Emu(tf.margin_bottom).pt
            need = wrap_height(tf.paragraphs, wpt)
            if need > hpt + 2:
                print(f"slide {i}: overflow ~{need - hpt:.0f}pt  {shape.name}  {text[:58]!r}")
                problems += 1
    print(f"Layout audit: {problems} problem(s) across {len(prs.slides._sldIdLst)} slides")


if __name__ == "__main__":
    main()
