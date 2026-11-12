"""Compare Kowai Pixel with the Riot Stars text font (Skies of Arcadia's Latin font,
../Riot Stars/tools/font_atlas.py), in this game's dialogue scene.

    python tools/fontcompare_riot.py <out_dir> [--raw]

Uses the aligned glyphs (tools/skiesfont.py fixes); --raw shows Riot Stars' glyphs as is.
riot_align_x6.png: before/after sheet with the cap, x-height and baseline guides.

Riot Stars' own code lays the lines out (line_coverage: its glyphs, advances and
outline-font fallbacks) - nothing in that project is written. Its glyphs are 2x
density (12x24 texels per 6x12 px cell, drawn as half-size quads), so three versions:

  1. Kowai Pixel, as in v0.7.0.
  2. Skies 2x density as in Riot Stars: faint level 50 % see-through, two strong
     levels solid, plus a 1 screen px (2 texel) black outline like this game's.
     Needs a 2x canvas in our renderer to look like this.
  3. Skies reduced to 1x 1bpp (2x2 texel blocks, ink if >= 2 solid texels), with
     this game's outline: what the current renderer could show without changes.

The Skies pixels are SEGA artwork decoded from the user's own disc in Riot Stars;
these images are for local comparison only.
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixfont  # noqa: E402
import vwf  # noqa: E402
from fontcompare import stack  # noqa: E402

RIOT_TOOLS = os.path.join(os.path.dirname(pixfont.ROOT), 'Riot Stars', 'tools')
sys.path.insert(0, RIOT_TOOLS)
import font_atlas  # noqa: E402
import skiesfont  # noqa: E402

WRAP_W = 198
TEXT_WHITE = (248, 248, 248)
OUTLINE = (8, 0, 0)
FAINT, STRONG = 28, 137      # line_coverage values of the two weaker Skies levels


FIXED = [False]


def riot_line(s):
    """-> (coverage image 2x, cap top row in texels)."""
    return skiesfont.line_coverage(s) if FIXED[0] else font_atlas.line_coverage(s)


def riot_width(s):
    return riot_line(s)[0].width / 2 if s else 0


def riot_wrap(text, width=WRAP_W):
    out, cur = [], ''
    for word in text.split(' '):
        cand = word if not cur else cur + ' ' + word
        if riot_width(cand) <= width:
            cur = cand
        else:
            out.append(cur)
            cur = word
    out.append(cur)
    return out


def scene_riot2x(bg, lines, pitch=vwf.LINE_H):
    """Scene at 2x (640x480): background doubled, Skies text at texel resolution."""
    big = bg.resize((bg.width * 2, bg.height * 2), Image.NEAREST)
    px = big.load()
    W, H = big.size
    cap_row = 4                       # Kowai Pixel's cap top inside the 16-row cell
    for i, line in enumerate(lines):
        cov, cap = riot_line(line)
        ox = 2 * vwf.STRIP_X + 2      # pen 0 + Kowai's 1 px left bearing, in texels
        oy = 2 * (16 + i * pitch + cap_row) - cap
        c = cov.load()
        ink = {(ox + x, oy + y): c[x, y] for y in range(cov.height) for x in range(cov.width) if c[x, y]}
        for (x, y) in ink:            # 2-texel (1 screen px) outline, 8 neighbours
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if 0 <= x + dx < W and 0 <= y + dy < H and (x + dx, y + dy) not in ink:
                        px[x + dx, y + dy] = OUTLINE
        for (x, y), v in ink.items():
            if 0 <= x < W and 0 <= y < H:
                if v <= FAINT:        # semi-transparent (PS1 mode 0: average)
                    b = px[x, y]
                    px[x, y] = tuple((a + t) // 2 for a, t in zip(b, TEXT_WHITE))
                else:
                    px[x, y] = TEXT_WHITE
    return big


def riot_1x_font_lines(lines):
    """Skies reduced to 1x: set of lit screen pixels per line (pen 0 at x=0, cell top 0)."""
    out = []
    for line in lines:
        cov, cap = riot_line(line)
        c = cov.load()
        on = set()
        oy = 2 * 4 - cap              # texel row of cell row 0
        for Y in range(16):
            for X in range((cov.width + 1) // 2):
                n = 0
                for dx in (0, 1):
                    for dy in (0, 1):
                        x, y = 2 * X + dx, 2 * Y + dy - oy
                        if 0 <= x < cov.width and 0 <= y < cov.height and c[x, y] >= STRONG:
                            n += 1
                if n >= 2:
                    on.add((X + 1, Y))
        out.append(on)
    return out


def scene_riot1x(bg, lines, pitch=vwf.LINE_H):
    im = bg.copy()
    for i, on in enumerate(riot_1x_font_lines(lines)):
        pixfont.stamp(im, {(vwf.STRIP_X + x, 16 + i * pitch + y) for x, y in on})
    return im


ALIGN = ['0123456789 $%&#/', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz',
         ".,:;!?'\"()-—…‘’“”",
         "☆★♪ · – éèïü  Wh-what is this★  tell me☆"]


def align_sheet(title, scale=6):
    """Texel-level lines with guides: cap top (row 2), x-height (7), baseline (20)."""
    blocks = []
    for line in ALIGN:
        cov, cap = riot_line(line)
        base = font_atlas.BASELINE - font_atlas.skies_baseline()   # line row of cell row 0
        w, h = cov.width + 8, 30
        im = Image.new('RGB', (w * scale, h * scale), (40, 32, 34))
        px = cov.load()
        from PIL import ImageDraw
        d = ImageDraw.Draw(im)
        for row, col in ((skiesfont.CAP_TOP, (90, 160, 255)), (skiesfont.X_TOP, (120, 200, 120)),
                         (skiesfont.BASE + 1, (255, 110, 90))):
            y = (row + base - 1) * scale + 3     # line drawn on the edge above the row
            d.line([(0, y), (w * scale, y)], fill=col, width=2)
        for y in range(min(h, cov.height - 1)):
            for x in range(cov.width):
                v = px[x, y + 1]
                if v:
                    c = (150, 150, 150) if v <= FAINT else (248, 248, 248)
                    d.rectangle([(x + 4) * scale, y * scale, (x + 5) * scale - 2, (y + 1) * scale - 2], fill=c)
        blocks.append(im)
    return pixfont.label(stack(blocks, 4), title, 3)


def main():
    out_dir = [a for a in sys.argv[1:] if not a.startswith('--')][0]
    os.makedirs(out_dir, exist_ok=True)
    before = align_sheet('Riot Stars glyphs as they are (grey = faint 50% texels)')
    if '--raw' not in sys.argv:
        skiesfont.enable()
        FIXED[0] = True
    after = align_sheet('Aligned (blue: cap top, green: x-height, red: baseline)')
    stack([before, after], 16).save(os.path.join(out_dir, 'riot_align_x6.png'))
    kowai = pixfont.build_font()
    bg = pixfont.clean_bg(os.path.join(pixfont.ROOT, 'work', 'emulator', 'shots', 'v020', 'q08.png'))
    bp = bg.load()                            # rub out the page cursor
    for y in range(12, 36):
        for x in range(104, 190):
            bp[x, y] = bp[190 + (x % 4), y]

    k_lines = pixfont.wrap(kowai, pixfont.STORY, WRAP_W)
    r_lines = riot_wrap(pixfont.STORY)
    print('Kowai Pixel: %d lines, %d px' % (len(k_lines), sum(kowai[0][c] for c in pixfont.codes(pixfont.STORY))))
    print('Riot Stars (Skies): %d lines, %d px' % (len(r_lines), riot_width(pixfont.STORY)))

    names = ['Kowai Pixel (ours)',
             'Riot Stars font (Skies) at 2x density - needs a 2x canvas',
             'Riot Stars font (Skies) reduced to 1x - current renderer']
    # every scene at 2x so the three line up; x2 -> final x4 / x8
    scenes = [pixfont.scene(kowai, bg, k_lines).resize((640, 480), Image.NEAREST),
              scene_riot2x(bg, r_lines),
              scene_riot1x(bg, r_lines).resize((640, 480), Image.NEAREST)]

    shots = [pixfont.label(s.resize((1280, 960), Image.NEAREST), n, 2) for s, n in zip(scenes, names)]
    row = Image.new('RGB', (1296 * 3 - 16, shots[0].height), (24, 24, 28))
    for i, sh in enumerate(shots):
        row.paste(sh, (i * 1296, 0))
    row.save(os.path.join(out_dir, 'riot_ingame_x4.png'))

    crop = (100, 12, 310, 12 + 17 * 5 + 6)
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    ups = [pixfont.label(s.crop(tuple(v * 2 for v in crop)).resize((cw * 8, ch * 8), Image.NEAREST), n + ' (x8)', 3)
           for s, n in zip(scenes, names)]
    stack(ups, 16).save(os.path.join(out_dir, 'riot_closeup_x8.png'))

    # what a real PS1 / 1x emulator shows: every other texel of the half-size quads
    kow = pixfont.scene(kowai, bg, k_lines)
    big = scene_riot2x(bg, r_lines)
    hw = big.resize((320, 240), Image.NEAREST)
    rows = [pixfont.label(kow.crop(crop).resize((cw * 6, ch * 6), Image.NEAREST),
                          'Kowai Pixel - same on hardware and upscaled (x6)', 3),
            pixfont.label(big.crop(tuple(v * 2 for v in crop)).resize((cw * 6, ch * 6), Image.NEAREST),
                          'Riot Stars font - upscaled emulator (x6)', 3),
            pixfont.label(hw.crop(crop).resize((cw * 6, ch * 6), Image.NEAREST),
                          'Riot Stars font - real PS1 / 1x emulator (x6)', 3)]
    stack(rows, 16).save(os.path.join(out_dir, 'riot_hardware_x6.png'))
    nat = Image.new('RGB', (648, 240), (24, 24, 28))
    nat.paste(kow, (0, 0))
    nat.paste(hw, (328, 0))
    nat.save(os.path.join(out_dir, 'riot_hardware_native_1x.png'))

    # glyph sheet x4: sample lines on a plain background
    sheet_bg = Image.new('RGB', (330, 4 + 17 * len(pixfont.SAMPLE) + 4), (58, 44, 44))
    def sheet(fn, lines):
        return fn(sheet_bg, lines)
    k = Image.new('RGB', sheet_bg.size, (58, 44, 44))
    for i, line in enumerate(pixfont.SAMPLE):
        on, _ = pixfont.ink(kowai, line, 4, 2 + i * 17)
        pixfont.stamp(k, on)
    old_x, old_y = vwf.STRIP_X, None
    vwf.STRIP_X = 3                           # scene_* place pen 0 at STRIP_X, top line at 16
    try:
        shift = Image.new('RGB', (sheet_bg.width, sheet_bg.height + 14), (58, 44, 44))
        r2 = scene_riot2x(shift, pixfont.SAMPLE).crop((0, 28, sheet_bg.width * 2, 28 + sheet_bg.height * 2))
        r1 = scene_riot1x(shift, pixfont.SAMPLE).crop((0, 14, sheet_bg.width, 14 + sheet_bg.height))
    finally:
        vwf.STRIP_X = old_x
    S = 4
    blocks = [pixfont.label(k.resize((k.width * S, k.height * S), Image.NEAREST), names[0], 2),
              pixfont.label(r2.resize((r2.width * S // 2, r2.height * S // 2), Image.NEAREST), names[1], 2),
              pixfont.label(r1.resize((r1.width * S, r1.height * S), Image.NEAREST), names[2], 2)]
    stack(blocks).save(os.path.join(out_dir, 'riot_sheet_x4.png'))
    print('wrote', out_dir)


if __name__ == '__main__':
    main()
