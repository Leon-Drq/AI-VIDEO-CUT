"""Render a tightly cropped, unoutlined gradient number and optional baseline unit."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STOPS = [(0, (255, 222, 149)), (0.43, (255, 195, 86)), (1, (255, 158, 1))]


def glyph_mask(text, face, height, weight, width):
    font = ImageFont.truetype(str(face), height * 2)
    try:
        axes = font.get_variation_axes()
    except (OSError, ValueError):
        axes = []
    if axes:
        values = []
        for axis in axes:
            name = axis['name'].decode(errors='ignore').lower()
            value = {'width': width, 'weight': weight}.get(name, axis['default'])
            values.append(min(axis['maximum'], max(axis['minimum'], value)))
        font.set_variation_by_axes(values)
    left, top, right, bottom = font.getbbox(text)
    mask = Image.new('L', (max(1, right-left), max(1, bottom-top)))
    ImageDraw.Draw(mask).text((-left, -top), text, font=font, fill=255)
    box = mask.getbbox()
    if not box:
        raise ValueError('Text must contain visible glyphs')
    mask = mask.crop(box)
    return mask.resize((max(1, round(mask.width*height/mask.height)), height),
                       Image.Resampling.LANCZOS)


def gold(mask):
    stripe = Image.new('RGB', (1, mask.height))
    for row in range(mask.height):
        pos = row / max(1, mask.height - 1)
        a, b = STOPS[:2] if pos <= STOPS[1][0] else STOPS[1:]
        f = (pos-a[0]) / (b[0]-a[0])
        stripe.putpixel((0, row), tuple(round(x+(y-x)*f) for x, y in zip(a[1], b[1])))
    out = stripe.resize(mask.size)
    out.putalpha(mask)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('text')
    p.add_argument('output', type=Path)
    p.add_argument('--font', type=Path, required=True)
    p.add_argument('--height', type=int, default=220)
    p.add_argument('--unit', default='')
    p.add_argument('--unit-font', type=Path)
    p.add_argument('--unit-ratio', type=float, default=.32)
    a = p.parse_args()
    if not 4 <= a.height <= 2000 or not 0 < a.unit_ratio <= 1:
        p.error('Use height 4..2000 and a unit ratio between 0 and 1')
    if a.output.suffix.lower() != '.png':
        p.error('Use .png for the transparent output')
    number = gold(glyph_mask(a.text, a.font, a.height, 700, 86))
    if a.unit:
        unit = gold(glyph_mask(a.unit, a.unit_font or a.font,
                               max(1, round(a.height*a.unit_ratio)), 790, 100))
        gap = round(a.height*.08)
        result = Image.new('RGBA', (number.width+gap+unit.width, number.height))
        result.alpha_composite(number)
        result.alpha_composite(unit, (number.width+gap, number.height-unit.height))
    else:
        result = number
    with a.output.open('xb') as out:
        result.save(out, format='PNG')


if __name__ == '__main__':
    main()