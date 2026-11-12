"""Kowai Pixel: the hand-drawn dialogue font (tools/fonts/kowai-pixel/glyphs.txt).

Builds the same (widths[128], bitmaps) pair as vwf.build_font, so it can replace the
Noto Sans rasterisation without touching the renderer: 16-row cell, u16 rows with
bit 15 = leftmost pixel, same baseline (row 12), same outline pass.

    python tools/pixfont.py check                  glyph sanity report
    python tools/pixfont.py preview <out_dir>      old vs new comparison PNGs
"""
import os
import struct
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vwf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLYPHS = os.path.join(ROOT, 'tools', 'fonts', 'kowai-pixel', 'glyphs.txt')
CELL_H = vwf.CELL_H
BEARING = 1          # empty columns left of the ink
GAP = 1              # empty columns right of the ink (2 px between letters in total)


def load(path=GLYPHS):
    """-> {char: (top_row, [row strings], advance)}"""
    out = {}
    cur = None
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n').rstrip()
        if cur is not None:
            if line == '':
                out[cur[0]] = cur[1:]
                cur = None
                continue
            assert set(line) <= {'#', '.'}, 'bad row %r in %r' % (line, cur[0])
            cur[2].append(line)
            continue
        if not line or line.startswith('#'):
            continue
        assert line.startswith('@ '), line
        parts = line.split(' ')
        ch = ' ' if parts[1] == 'space' else parts[1]
        adv = None
        for p in parts[3:]:
            if p.startswith('adv='):
                adv = int(p[4:])
        cur = [ch, int(parts[2]), [], adv]
    if cur is not None:
        out[cur[0]] = cur[1:]
    res = {}
    for ch, (top, rows, adv) in out.items():
        w = max((len(r) for r in rows), default=0)
        if adv is None:
            adv = BEARING + w + GAP
        res[ch] = (top, rows, adv)
    return res


def build_font(path=GLYPHS):
    glyphs = load(path)
    widths = [0] * 128
    bmp = bytearray(128 * CELL_H * 2)
    missing = []
    for code, ch in vwf.glyph_chars().items():
        if ch not in glyphs:
            missing.append(ch)
            continue
        top, rows, adv = glyphs[ch]
        assert top + len(rows) <= CELL_H, (ch, 'too tall')
        assert BEARING + max((len(r) for r in rows), default=0) <= 16, (ch, 'too wide')
        widths[code] = adv
        for i, r in enumerate(rows):
            v = 0
            for x, c in enumerate(r):
                if c == '#':
                    v |= 0x8000 >> (BEARING + x)
            struct.pack_into('<H', bmp, (code * CELL_H + top + i) * 2, v)
    assert not missing, 'missing glyphs: %r' % missing
    widths[vwf.FILLER] = 0
    return widths, bytes(bmp)


# ---- rendering helpers ---------------------------------------------------------

def codes(text):
    return [ord(c) if ord(c) < 0x80 else vwf.CODE_OF[c] for c in text]


def ink(font, text, x0, y0):
    """-> set of lit pixels for one line, pen at x0, cell top at y0; and the end pen."""
    widths, bmp = font
    on = set()
    for code in codes(text):
        for y in range(CELL_H):
            row = struct.unpack_from('<H', bmp, (code * CELL_H + y) * 2)[0]
            for x in range(16):
                if row & (0x8000 >> x):
                    on.add((x0 + x, y0 + y))
        x0 += widths[code]
    return on, x0


def stamp(im, on, fg=(248, 248, 248), ol=(8, 0, 0)):
    """Draw like vwf_glyph: outline pass (8 neighbours) then the letter pass."""
    px = im.load()
    W, H = im.size
    for (x, y) in on:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if 0 <= x + dx < W and 0 <= y + dy < H:
                    px[x + dx, y + dy] = ol
    for (x, y) in on:
        if 0 <= x < W and 0 <= y < H:
            px[x, y] = fg


def text_block(font, lines, w, h, bg=(58, 44, 44), x0=4, y0=2, pitch=vwf.LINE_H):
    im = Image.new('RGB', (w, h), bg)
    for i, line in enumerate(lines):
        on, _ = ink(font, line, x0, y0 + i * pitch)
        stamp(im, on)
    return im


def wrap(font, text, width):
    widths = font[0]
    out, cur = [], ''
    for word in text.split(' '):
        cand = word if not cur else cur + ' ' + word
        if sum(widths[c] for c in codes(cand)) <= width:
            cur = cand
        else:
            out.append(cur)
            cur = word
    out.append(cur)
    return out


def check():
    glyphs = load()
    print('%d glyphs' % len(glyphs))
    old_w = vwf.build_font_noto()[0]
    new_w = build_font()[0]
    for code, ch in sorted(vwf.glyph_chars().items()):
        if old_w[code] != new_w[code]:
            print('  %r  old %2d  new %2d' % (ch, old_w[code], new_w[code]))
    sample = ('Well then, shall I tell the first story? My name is Akemi Iwashita. '
              'Pleased to meet you. I\'ll get straight to it: this school has no such '
              'thing as "seven wonders." Because seven wouldn\'t even begin to cover it.')
    for name, f in (('old', (old_w, None)), ('new', (new_w, None))):
        n = sum(f[0][c] for c in codes(sample))
        print('%s: sample %d px' % (name, n))


# ---- preview -------------------------------------------------------------------

SAMPLE = [
    'The quick brown fox jumps over the lazy dog.',
    'SAKAGAMI SHUICHI, KURATA EMI, IWASHITA AKEMI',
    '"Who\'s there?" 0123456789 !?,.;:()[]-&%$#@',
    '… — ‘x’ “x” é è ï ü · ♪ ☆ ★ – /\\<>+=*_~^{}|`',
]

STORY = ('Heh heh heh… Do you want to know? An evil spirit lives in this school. '
         'And that evil spirit is always bringing misfortune with it. That\'s why '
         'this school is full of strange happenings. The story I\'m going to tell '
         'is about a prank…')


def clean_bg(path):
    """Screenshot with its own text rubbed out (text-white and outline pixels in the text
    area are replaced from the nearest clean pixel above/below)."""
    im = Image.open(path).convert('RGB')
    px = im.load()
    W, H = im.size

    def is_text(p):
        return p == (248, 248, 248) or p == (8, 0, 0)

    bad = set()
    for y in range(10, 230):
        for x in range(100, 320):
            if is_text(px[x, y]):
                bad.update((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
    for (x, y) in sorted(bad):
        for d in range(1, 12):
            for yy in (y - d, y + d):
                if 0 <= yy < H and (x, yy) not in bad:
                    px[x, y] = px[x, yy]
                    break
            else:
                continue
            break
    return im


def scene(font, bg, lines):
    im = bg.copy()
    pen_x = vwf.STRIP_X              # screen x of pen 0
    for i, line in enumerate(lines):
        on, _ = ink(font, line, pen_x, 16 + i * vwf.LINE_H)
        stamp(im, on)
    return im


def label(im, text, scale):
    """Big caption drawn with the new font itself."""
    font = build_font()
    on, end = ink(font, text, 2, 0)
    cap = Image.new('RGB', (im.width, (CELL_H + 2) * scale), (24, 24, 28))
    small = Image.new('RGB', (end + 4, CELL_H + 2), (24, 24, 28))
    stamp(small, on, fg=(255, 214, 120), ol=(24, 24, 28))
    cap.paste(small.resize((small.width * scale, small.height * scale), Image.NEAREST), (0, 0))
    out = Image.new('RGB', (im.width, im.height + cap.height), (24, 24, 28))
    out.paste(cap, (0, 0))
    out.paste(im, (0, cap.height))
    return out


def preview(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    old, new = vwf.build_font_noto(), build_font()

    # 1. glyph sheet, both fonts, x4
    W, H, S = 330, 4 + 17 * len(SAMPLE), 4
    blocks = []
    for name, f in (('Before: Noto Sans 12px (auto-rasterised)', old), ('After: Kowai Pixel (hand-drawn)', new)):
        b = text_block(f, SAMPLE, W, H)
        blocks.append(label(b.resize((W * S, H * S), Image.NEAREST), name, 2))
    sheet = Image.new('RGB', (W * S, sum(b.height for b in blocks) + 8), (24, 24, 28))
    y = 0
    for b in blocks:
        sheet.paste(b, (0, y))
        y += b.height + 8
    sheet.save(os.path.join(out_dir, 'font_compare_x4.png'))

    # 2. in-game mock, x4, same screenshot and wrap width as the game (textenc.WIN_W)
    bg = clean_bg(os.path.join(ROOT, 'work', 'emulator', 'shots', 'v020', 'q08.png'))
    shots = []
    for name, f in (('Before', old), ('After', new)):
        lines = wrap(f, STORY, 198)
        shots.append(label(scene(f, bg, lines).resize((320 * S, 240 * S), Image.NEAREST), name, 2))
    both = Image.new('RGB', (320 * S * 2 + 16, shots[0].height), (24, 24, 28))
    both.paste(shots[0], (0, 0))
    both.paste(shots[1], (320 * S + 16, 0))
    both.save(os.path.join(out_dir, 'ingame_compare_x4.png'))

    # 3. close-up of the text area, x8
    crop = (100, 12, 310, 12 + 17 * 5 + 6)
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    ups = []
    for name, f in (('Before (x8)', old), ('After (x8)', new)):
        lines = wrap(f, STORY, 198)
        c = scene(f, bg, lines).crop(crop).resize((cw * 8, ch * 8), Image.NEAREST)
        ups.append(label(c, name, 3))
    z = Image.new('RGB', (cw * 8, sum(u.height for u in ups) + 16), (24, 24, 28))
    z.paste(ups[0], (0, 0))
    z.paste(ups[1], (0, ups[0].height + 16))
    z.save(os.path.join(out_dir, 'closeup_x8.png'))

    # native 1x for reference
    scene(new, bg, wrap(new, STORY, 198)).save(os.path.join(out_dir, 'ingame_new_x1.png'))
    print('wrote', out_dir)


if __name__ == '__main__':
    if sys.argv[1] == 'check':
        check()
    elif sys.argv[1] == 'preview':
        preview(sys.argv[2])
