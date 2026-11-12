"""Compare Kowai Pixel (the game font) with another pixel TTF, drawn the way the game draws.

    python tools/fontcompare.py <out_dir> [ttf] [px] [--top N]

Default: Silver by Poppy Works (tools/fonts/silver/Silver.ttf, CC BY 4.0, 19 px grid,
100 units per pixel). The TTF is rasterised at its native pixel size (1 font pixel =
1 screen pixel, no smoothing), put on the game's 16-row cell with the same baseline
(row 12) and 1 px left bearing, and given +1 px spacing so the 1 px outline fits like
in the game. Writes compare_sheet_x4.png, compare_ingame_x4.png, compare_closeup_x8.png.
"""
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixfont  # noqa: E402
import vwf  # noqa: E402

ROOT = pixfont.ROOT
SILVER = os.path.join(ROOT, 'tools', 'fonts', 'silver', 'Silver.ttf')
CELL_H = vwf.CELL_H


def build_ttf_font(ttf, px, top, spacing=1, tight=False):
    """-> (widths, bmp, missing) in vwf's format. tight: advance = bearing + ink + 1
    (Kowai Pixel's rule) instead of the font's own advance + spacing."""
    from fontTools.ttLib import TTFont
    cmap = TTFont(ttf).getBestCmap()
    f = ImageFont.truetype(ttf, px)
    widths = [0] * 128
    bmp = bytearray(128 * CELL_H * 2)
    missing = []
    for code, ch in vwf.glyph_chars().items():
        if ord(ch) not in cmap:
            missing.append(ch)
            continue
        im = Image.new('1', (32, CELL_H + 8), 0)
        d = ImageDraw.Draw(im)
        d.fontmode = '1'                       # no anti-aliasing: exact pixels
        d.text((pixfont.BEARING, top), ch, font=f, fill=1)
        p = im.load()
        widths[code] = int(round(f.getlength(ch))) + spacing
        cols = [x for x in range(32) for y in range(CELL_H) if p[x, y]]
        if tight:
            widths[code] = (max(cols) + 1 + pixfont.GAP) if cols else 4
        for y in range(CELL_H):
            v = 0
            for x in range(16):
                if p[x, y]:
                    v |= 0x8000 >> x
            struct.pack_into('<H', bmp, (code * CELL_H + y) * 2, v)
    widths[vwf.FILLER] = 0
    return widths, bytes(bmp), missing


def ink_bbox_rows(font, ch):
    code = ord(ch)
    rows = [struct.unpack_from('<H', font[1], (code * CELL_H + y) * 2)[0] for y in range(CELL_H)]
    lit = [y for y in range(CELL_H) if rows[y]]
    return lit[0], lit[-1]


def stack(images, gap=12, bg=(24, 24, 28)):
    w = max(i.width for i in images)
    out = Image.new('RGB', (w, sum(i.height for i in images) + gap * (len(images) - 1)), bg)
    y = 0
    for i in images:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out_dir = args[0]
    ttf = args[1] if len(args) > 1 else SILVER
    px = int(args[2]) if len(args) > 2 else 19
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else None
    name = os.path.splitext(os.path.basename(ttf))[0]

    kowai = pixfont.build_font()
    if top is None:                           # line the cap top up with Kowai Pixel's
        probe = build_ttf_font(ttf, px, 0)
        top = ink_bbox_rows(kowai, 'H')[0] - ink_bbox_rows(probe, 'H')[0]
    other = build_ttf_font(ttf, px, top)
    if other[2]:
        print('%s has no glyph for: %s (drawn blank)' % (name, ' '.join(other[2])))
    tight = build_ttf_font(ttf, px, top, tight=True)[:2]
    fonts = [('Kowai Pixel (ours)', kowai),
             ('%s %dpx as designed (+1 px for the outline)' % (name, px), other[:2]),
             ('%s %dpx tightened to our spacing' % (name, px), tight)]
    for label_, f in fonts:
        b, e = ink_bbox_rows(f, 'H'), ink_bbox_rows(f, 'x')
        print('%-40s cap %d px, x-height %d px, story width %d px'
              % (label_, b[1] - b[0] + 1, e[1] - e[0] + 1,
                 sum(f[0][c] for c in pixfont.codes(pixfont.STORY))))
    os.makedirs(out_dir, exist_ok=True)

    # 1. glyph sheet x4
    W, S = 330, 4
    H = 4 + 17 * len(pixfont.SAMPLE)
    blocks = [pixfont.label(pixfont.text_block(f, pixfont.SAMPLE, W, H).resize((W * S, H * S), Image.NEAREST), n, 2)
              for n, f in fonts]
    stack(blocks).save(os.path.join(out_dir, 'compare_sheet_x4.png'))

    # 2. in-game mock x4, side by side, same wrap width as the build (textenc.WIN_W)
    bg = pixfont.clean_bg(os.path.join(ROOT, 'work', 'emulator', 'shots', 'v020', 'q08.png'))
    bp = bg.load()                            # rub out the page cursor left of x 190
    for y in range(12, 36):
        for x in range(104, 190):
            bp[x, y] = bp[190 + (x % 4), y]
    shots = []
    for n, f in fonts:
        lines = pixfont.wrap(f, pixfont.STORY, 198)
        print('%-40s %d lines' % (n, len(lines)))
        shots.append(pixfont.label(pixfont.scene(f, bg, lines).resize((320 * S, 240 * S), Image.NEAREST), n, 2))
    both = Image.new('RGB', ((320 * S + 16) * len(shots) - 16, shots[0].height), (24, 24, 28))
    for i, sh in enumerate(shots):
        both.paste(sh, (i * (320 * S + 16), 0))
    both.save(os.path.join(out_dir, 'compare_ingame_x4.png'))

    # 3. close-up x8 of the first lines
    crop = (100, 12, 310, 12 + 17 * 5 + 6)
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    ups = [pixfont.label(pixfont.scene(f, bg, pixfont.wrap(f, pixfont.STORY, 198)).crop(crop)
                         .resize((cw * 8, ch * 8), Image.NEAREST), n + ' (x8)', 3) for n, f in fonts]
    stack(ups, 16).save(os.path.join(out_dir, 'compare_closeup_x8.png'))
    print('wrote', out_dir)


if __name__ == '__main__':
    main()
