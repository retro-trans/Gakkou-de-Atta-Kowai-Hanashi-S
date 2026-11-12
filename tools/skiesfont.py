"""Riot Stars text font (Skies of Arcadia's Latin font at 2x density) with alignment fixes.

The glyph pixels are SEGA artwork. They are never stored in this project: they come
from ../Riot Stars (tools/skies_font.py decodes them from the user's own Skies disc
into that project's work/source/). This module only holds *edits* (row operations),
applied on load, so every glyph sits on the same lines:

  texel rows (2x):  2 cap top / ascender   7 x-height   20 baseline (last ink row)
                    21-22 descenders

Skies draws round digits with overshoot (an extra anti-aliased row above and below)
and leaves faint 50 %-transparent texels outside the lines; at this size those read
as letters that are taller or lower than their neighbours.

Ops per glyph, applied in order on the 12x24 mask:
  ('clear', rows)    rows -> blank
  ('shift', dy)      whole glyph down by dy (negative = up)
  ('del_up', r)      delete row r, rows below move up one
  ('del_down', r)    delete row r, rows above move down one

    python tools/skiesfont.py check     extents of every glyph before/after
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RIOT_TOOLS = os.path.join(os.path.dirname(ROOT), 'Riot Stars', 'tools')
sys.path.insert(0, RIOT_TOOLS)
import font_atlas  # noqa: E402

CAP_TOP, X_TOP, BASE = 2, 7, 20
SOLID = 128                       # font_atlas.SKIES_COVER: levels 187 / 255 are solid ink

def _rows(src, dest0, extra):
    """remap table: source rows `src` to destination rows dest0.., plus {dest: src}."""
    m = {dest0 + i: s for i, s in enumerate(src)}
    m.update(extra)
    return m


FIXES = {
    # digits: drop the overshoot rows so all ten span rows 2-20 like the capitals
    '0': [('clear', [1, 21])],
    '1': [('clear', [1, 21])],
    '2': [('clear', [1])],
    '3': [('clear', [1, 21])],
    '4': [('clear', [1, 21])],
    '5': [('clear', [21])],
    '6': [('clear', [1, 21])],
    '7': [('clear', [21])],
    '8': [('clear', [1, 21])],
    '9': [('clear', [1, 21])],
    # capitals
    'A': [('clear', [1])],        # faint apex texel above the cap line
    'J': [('del_up', 10)],        # hook dipped one row under the baseline
    'V': [('clear', [21])],
    'W': [('clear', [21])],
    # lowercase
    'a': [('del_down', 9)],       # started one row above the x-height
    'v': [('clear', [21])],
    'f': [('clear', [1])],        # hook one row above the other ascenders
    # descenders: Skies squeezes them into rows 21-22 by ending the bowls of g p q two rows
    # above the baseline (p q also start one row above the x-height). Bowls stretched by
    # repeating straight middle rows to rows 7-20 like 'o'; the descender goes to rows 21-23.
    'g': [('remap', _rows([7, 8, 9, 10, 11, 12, 12, 13, 13, 14, 15, 16, 17, 18], 7, {21: 20, 22: 21, 23: 22}))],
    'p': [('remap', _rows([6, 7, 8, 9, 10, 11, 12, 12, 13, 14, 15, 16, 17, 18], 7, {21: 19, 22: 20, 23: 21}))],
    'q': [('remap', _rows([6, 7, 8, 9, 10, 11, 12, 12, 13, 14, 15, 16, 17, 18], 7, {21: 19, 22: 20, 23: 21}))],
    # punctuation: dots on the baseline, colon / semicolon dots level with the period
    '!': [('clear', [1]), ('del_up', 17)],
    '?': [('del_up', 17)],
    '.': [('shift', -1)],
    ':': [('shift', 1)],
    ';': [('shift', 1)],
    "'": [('shift', 1)],          # quotes start on the cap line
    '"': [('shift', 1)],
    '%': [('shift', -1)],         # symbols that sat one row under the baseline
    '&': [('shift', -1), ('clear', [21])],
    '#': [('shift', -1)],
    '/': [('shift', -1)],
}

# Characters Riot Stars takes from its outline font (GenEi), built here from Skies' own
# glyphs instead so they match: the ellipsis is three periods on the baseline, the
# curly quotes are Skies' quote marks (mirrored for the opening ones).
QUOTE_TOP = CAP_TOP


def _ink(img):
    box = img.getbbox()
    return img.crop(box) if box else None


def _compose(parts, w=12, h=24):
    out = Image.new('L', (w, h), 0)
    for piece, x, y in parts:
        out.paste(piece, (x, y))
    return out


def synth(ch):
    dot = _ink(fixed_mask('.'))
    dot_top = extents(fixed_mask, '.')[2]
    gap = 2
    if ch == '…':
        return _compose([(dot, 1 + i * (dot.width + gap), dot_top) for i in range(3)])
    # Skies' own apostrophe / double quote are slanted like closing quotes; mirrored
    # they make the opening ones.
    single = _ink(fixed_mask("'"))
    double = _ink(fixed_mask('"'))
    if ch == '’':
        return _compose([(single, 1, QUOTE_TOP)])
    if ch == '‘':
        return _compose([(single.transpose(Image.FLIP_LEFT_RIGHT), 1, QUOTE_TOP)])
    if ch == '”':
        return _compose([(double, 1, QUOTE_TOP)])
    if ch == '“':
        return _compose([(double.transpose(Image.FLIP_LEFT_RIGHT), 1, QUOTE_TOP)])
    return None


SYNTH = '…‘’“”'

_orig_mask = font_atlas.skies_mask
_cache = {}


def apply(img, ops):
    w, h = img.size
    rows = [[img.getpixel((x, y)) for x in range(w)] for y in range(h)]
    blank = [0] * w
    for op, arg in ops:
        if op == 'clear':
            for r in arg:
                rows[r] = list(blank)
        elif op == 'shift':
            rows = ([list(blank)] * arg + rows[:h - arg]) if arg >= 0 else (rows[-arg:] + [list(blank)] * -arg)
        elif op == 'del_up':
            rows = rows[:arg] + rows[arg + 1:] + [list(blank)]
        elif op == 'del_down':
            rows = [list(blank)] + rows[:arg] + rows[arg + 1:]
        elif op == 'remap':            # {destination row: source row}, other rows blank
            rows = [list(rows[arg[y]]) if y in arg else list(blank) for y in range(h)]
        else:
            raise ValueError(op)
    out = Image.new(img.mode, (w, h))
    out.putdata([v for r in rows for v in r])
    return out


def fixed_mask(ch):
    if ch not in _cache:
        m = synth(ch) if ch in SYNTH else _orig_mask(ch)
        if m is not None and ch in FIXES:
            m = apply(m, FIXES[ch])
        _cache[ch] = m
    return _cache[ch]


def enable():
    """Route Riot Stars' layout code (line_coverage, skies_box, build) through the fixes."""
    font_atlas.skies_mask = fixed_mask
    font_atlas._BUILT.clear()


# ---- glyphs Skies does not have (our own art: tools/fonts/skies-extra/glyphs2x.txt) ---

EXTRA_ART = os.path.join(ROOT, 'tools', 'fonts', 'skies-extra', 'glyphs2x.txt')
LEVEL = {'#': 255, '+': 187, ':': 85, '.': 0}
_pieces = {}


def piece(name):
    """-> (image cropped to its rows, top row)"""
    if not _pieces:
        cur = None
        for raw in open(EXTRA_ART, encoding='utf-8'):
            line = raw.rstrip()
            if line.startswith('@ '):
                _, n, top = line.split()
                cur = _pieces[n] = [int(top), []]
            elif cur is not None and line:      # '#' rows are ink inside a block
                cur[1].append(line)
            elif not line:
                cur = None
        for n, (top, rows) in list(_pieces.items()):
            w = max(len(r) for r in rows)
            im = Image.new('L', (w, len(rows)), 0)
            im.putdata([LEVEL[c] for r in rows for c in r.ljust(w, '.')])
            _pieces[n] = (im, top)
    return _pieces[name]


def _quantise(cover):
    """Supersampled coverage -> Skies' four levels."""
    return cover.point(lambda v: 0 if v < 40 else 85 if v < 115 else 187 if v < 200 else 255)


def _star(filled, w=18, top=3, r=9.3):
    import math
    from PIL import ImageDraw
    S = 8
    cx, cy = w / 2, top + r
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.40
        pts.append(((cx + rr * math.cos(a)) * S, (cy + rr * math.sin(a)) * S))
    big = Image.new('L', (w * S, 24 * S), 0)
    d = ImageDraw.Draw(big)
    d.polygon(pts, fill=255)
    if not filled:                       # hollow: cut a smaller star out of it
        inner = [((x / S - cx) * 0.58 + cx) * S for x, _ in pts]
        innery = [((y / S - cy) * 0.58 + cy) * S for _, y in pts]
        d.polygon(list(zip(inner, innery)), fill=0)
    return _quantise(big.resize((w, 24), Image.BOX))


def _note():
    from PIL import ImageDraw
    S, w = 8, 12
    big = Image.new('L', (w * S, 24 * S), 0)
    d = ImageDraw.Draw(big)
    d.ellipse([0.5 * S, 15 * S, 7.5 * S, 21 * S], fill=255)             # head
    d.rectangle([5.5 * S, 3 * S, 7.5 * S, 18.5 * S], fill=255)          # stem
    d.polygon([(7.5 * S, 3 * S), (11 * S, 7.5 * S), (11 * S, 11 * S),   # flag
               (9.5 * S, 8.5 * S), (7.5 * S, 7 * S)], fill=255)
    return _quantise(big.resize((w, 24), Image.BOX))


def _onto(base_ch, parts, w=12):
    base = fixed_mask(base_ch)
    out = Image.new('L', (max(w, base.width), 24), 0)
    out.paste(base, (0, 0))
    for name, x in parts:
        im, top = piece(name)
        out.paste(im, (x, top))
    return out


def _clear_rows(img, rows):
    return apply(img, [('clear', rows)])


CUSTOM = {
    '★': lambda: _star(True),
    '☆': lambda: _star(False),
    '♪': _note,
    '·': lambda: _compose([(piece('middot')[0], 1, piece('middot')[1])]),
    '–': lambda: _compose([(piece('endash')[0], 1, piece('endash')[1])], w=14),
    'é': lambda: _onto('e', [('acute', 2)]),
    'è': lambda: _onto('e', [('grave', 1)]),
    'ï': lambda: (lambda b: _compose([(b, 0, 0), (piece('diaeresis_i')[0], 2, piece('diaeresis_i')[1])]))(
        _clear_rows(fixed_mask('i'), [2, 3, 4])),
    'ü': lambda: _onto('u', [('diaeresis_u', 2)]),
}
_custom_cache = {}


def glyph(ch):
    """Mask (L, w x 24) of ch in the fixed font, or None (outline-font fallback)."""
    if ch in CUSTOM:
        if ch not in _custom_cache:
            _custom_cache[ch] = CUSTOM[ch]()
        return _custom_cache[ch]
    return fixed_mask(ch)


# ---- line layout (Riot Stars' rules, any glyph width) ------------------------------

BASELINE = font_atlas.BASELINE        # line row of the baseline edge (2x texels)


def _box(m):
    """Same rules as font_atlas.skies_box, for any mask width."""
    px = m.load()
    w = m.width
    solid = [(x, y) for y in range(24) for x in range(w) if px[x, y] >= SOLID]
    ink = [(x, y) for y in range(24) for x in range(w) if px[x, y]]
    if not solid:
        return None
    left = min(x for x, _ in solid)
    ink_w = max(x for x, _ in solid) + 1 - left
    x0, x1 = min(x for x, _ in ink), max(x for x, _ in ink) + 1
    x0 -= (left - x0) & 1
    y0, y1 = min(y for _, y in ink), max(y for _, y in ink) + 1
    top = y0 + BASELINE - (BASE + 1)
    if top & 1:
        y0, top = y0 - 1, top - 1
    x1 += (x1 - x0) & 1                 # even box: whole screen pixels
    y1 += (y1 - y0) & 1
    return (x0, y0, x1, y1), top, x0 - left, ink_w


def advance(ch):
    """Pen advance in screen px."""
    m = glyph(ch)
    b = _box(m) if m is not None else None
    if b:
        return (b[3] + font_atlas.SKIES_GAP + 1) // 2
    items = _items()
    g = ord(ch) if ord(ch) < 0x80 else {c: k for k, c in font_atlas.glyph_chars().items()}.get(ch, font_atlas.PLACEHOLDER)
    return items.get(g, items[font_atlas.PLACEHOLDER])[3]


_built = []


def _items():
    if not _built:
        enable()
        _built.append(font_atlas.build()['items'])
    return _built[0]


def cell(ch):
    """-> (L image of the glyph box, xoff texels from the pen, top texels from the line top,
    advance px) or (None, 0, 0, advance) for a blank (space). Same boxes as line_coverage."""
    m = glyph(ch)
    b = _box(m) if m is not None else None
    if b:
        (x0, y0, x1, y1), top, xoff, ink_w = b
        return m.crop((x0, y0, x1, y1)), xoff, top, (ink_w + font_atlas.SKIES_GAP + 1) // 2
    items = _items()
    gid = {c: k for k, c in font_atlas.glyph_chars().items()}
    rows, xoff, yoff, adv = items.get(gid.get(ch, font_atlas.PLACEHOLDER), items[font_atlas.PLACEHOLDER])
    if not rows:
        return None, 0, 0, adv
    img = Image.new('L', (len(rows[0]), len(rows)))
    img.putdata([255 if v else 0 for r in rows for v in r])
    return img, xoff, yoff, adv


def line_coverage(s):
    """-> (L image at 2x: 32 rows, baseline edge at BASELINE; cap top row)."""
    items = _items()
    gid = {c: k for k, c in font_atlas.glyph_chars().items()}
    parts, pen = [], 0
    for ch in s:
        m = glyph(ch)
        b = _box(m) if m is not None else None
        if b:
            (x0, y0, x1, y1), top, xoff, ink_w = b
            parts.append((m.crop((x0, y0, x1, y1)), pen + xoff, top))
            pen += 2 * ((ink_w + font_atlas.SKIES_GAP + 1) // 2)
            continue
        rows, xoff, yoff, adv = items.get(gid.get(ch, font_atlas.PLACEHOLDER), items[font_atlas.PLACEHOLDER])
        if rows:
            img = Image.new('L', (len(rows[0]), len(rows)))
            img.putdata([255 if v else 0 for r in rows for v in r])
            parts.append((img, pen + xoff, yoff))
        pen += adv * 2
    out = Image.new('L', (max(1, pen), 32), 0)
    for img, x, y in parts:
        out.paste(img, (x, y), img)
    return out, BASELINE - (BASE + 1) + CAP_TOP


def extents(mask_fn, ch):
    m = mask_fn(ch)
    if m is None:
        return None
    p = m.load()
    s = [y for y in range(24) for x in range(12) if p[x, y] >= SOLID]
    f = [y for y in range(24) for x in range(12) if p[x, y]]
    return (min(s), max(s), min(f), max(f)) if s else None


GROUPS = [('caps', 'ABCDEFGHIJKLMNOPRSTUVWXYZ', CAP_TOP, BASE),
          ('digits', '0123456789', CAP_TOP, BASE),
          ('x-height', 'acemnorsuvwxz', X_TOP, BASE),
          ('ascenders', 'bdfhkl', CAP_TOP, BASE),
          ('baseline punct', '.!?:%&#/…', None, BASE)]


def check(verbose=True):
    """-> list of glyphs still off their lines (after fixes)."""
    bad = []
    for name, chars, top, bot in GROUPS:
        for ch in chars:
            e = extents(fixed_mask, ch)
            if e is None:
                continue
            st, sb, ft, fb = e
            if (top is not None and (st != top or ft < top)) or sb != bot or fb > bot:
                bad.append((ch, e))
    if verbose:
        for name, chars, top, bot in GROUPS:
            print('%-15s' % name + '  '.join('%s %s>%s' % (c, '%d-%d' % extents(_orig_mask, c)[2:]
                                                           if extents(_orig_mask, c) else 'new',
                                                           '%d-%d' % extents(fixed_mask, c)[2:])
                                            for c in chars if extents(fixed_mask, c)))
        print('quotes top row:', {c: extents(fixed_mask, c)[2] for c in "'\"‘’“”"})
        print('off the lines after fixes:', bad or 'none')
    return bad


if __name__ == '__main__':
    if sys.argv[1:] == ['check']:
        check()
