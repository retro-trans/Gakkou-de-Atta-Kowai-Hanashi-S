"""English graphics: replacement files built from the originals (step 4 of docs/ui_plan.md).

    python tools/gfx.py preview <outdir>      write PNG previews of every replacement
    (tools/build.py calls build_all() and writes the files into the image)

Each entry of GFX: disc path inside the GRP tree (work/source/grp/<GRP dir>/<name>) ->
function returning the new file bytes. Art made here is drawn with Noto Sans (OFL,
tools/fonts/noto-sans) so no third-party bitmap is copied.
"""
import json
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tim  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRP = os.path.join(ROOT, 'work', 'source', 'grp')
TTF = os.path.join(ROOT, 'tools', 'fonts', 'noto-sans', 'NotoSans-Regular.ttf')


def text_mask(text, w, h, size, stroke=1, scale=4):
    """Boolean mask (h, w) of text centred in the box, drawn 4x and reduced (bold via stroke)."""
    f = ImageFont.truetype(TTF, size * scale)
    im = Image.new('L', (w * scale, h * scale), 0)
    dr = ImageDraw.Draw(im)
    bb = dr.textbbox((0, 0), text, font=f, stroke_width=stroke * scale)
    x = (w * scale - (bb[2] - bb[0])) // 2 - bb[0]
    y = (h * scale - (bb[3] - bb[1])) // 2 - bb[1]
    dr.text((x, y), text, font=f, fill=255, stroke_width=stroke * scale, stroke_fill=255)
    return np.asarray(im.resize((w, h), Image.BOX)) >= 128


def outline(mask):
    m = np.pad(mask, 1)
    near = np.zeros_like(m)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            near |= np.roll(np.roll(m, dy, 0), dx, 1)
    return (near & ~m)[1:-1, 1:-1]


def tim_4bpp_set(data, t, pix):
    """Write a (h, w) array of 4-bit indices into the TIM bytes."""
    d = bytearray(data)
    h, w = pix.shape
    flat = pix.reshape(-1).astype(np.uint8)
    packed = (flat[0::2] | (flat[1::2] << 4)).astype(np.uint8)
    d[t['data_off']:t['data_off'] + len(packed)] = packed.tobytes()
    return bytes(d)


def tim_4bpp_get(t):
    a = np.frombuffer(t['data'], np.uint8)
    return np.stack([a & 15, a >> 4], 1).reshape(t['h'], t['w'])


def di2():
    """Gender screen captions 男子 / 女子 (64x32 each) -> Boy (blue) / Girl (red)."""
    data = open(os.path.join(GRP, 'SCE00', 'DI2.TIM'), 'rb').read()
    _, t = tim.scan(data)[0]
    pix = np.zeros((64, 64), np.uint8)
    for row, (word, fill, shade) in enumerate((('Boy', 7, 8), ('Girl', 1, 2))):
        m = text_mask(word, 64, 32, 23, stroke=1)
        part = np.zeros((32, 64), np.uint8)
        part[m] = fill
        part[16:][m[16:]] = shade             # lower half one shade darker, like the brush art
        part[outline(m)] = 15
        pix[row * 32:row * 32 + 32] = part
    return tim_4bpp_set(data, t, pix)


# ---- MDEC stills (.BS / .BG): decode, paint, re-encode within the original size -------------

def bs_edit(key, w, h, edit):
    import bs
    d = open(os.path.join(GRP, *key.split('/')), 'rb').read()
    prefix, body = (b'', d) if d[2:4] == b'\x00\x38' else (d[:4], d[4:])
    rgb, _ = bs.decode(body, w, h)
    img = Image.fromarray(rgb)
    edit(img)
    max_hdr = int.from_bytes(body[:2], 'little')
    data, q = bs.encode_fit(np.asarray(img), len(d) - len(prefix), max_hdr)
    return prefix + data


def paint_text(img, xy, text, size, fill, shear=0.0, outline_fill=None):
    """Antialiased text onto an RGB image (4x supersampled), optional italic shear."""
    f = ImageFont.truetype(TTF, size * 4)
    dr0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    bb = dr0.textbbox((0, 0), text, font=f)
    W, H = bb[2] + 8 * 4, bb[3] + 8 * 4
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).text((4 * 4 - bb[0], 4 * 4 - bb[1]), text, font=f, fill=255)
    if shear:
        m = m.transform((W + int(H * shear), H), Image.AFFINE, (1, shear, -H * shear, 0, 1, 0), Image.BICUBIC)
    m = m.resize((m.width // 4, m.height // 4), Image.LANCZOS)
    x, y = xy[0] - 4, xy[1] - 4
    if outline_fill is not None:
        from PIL import ImageFilter
        o = m.filter(ImageFilter.MaxFilter(3))
        img.paste(Image.new('RGB', o.size, outline_fill), (x, y), o)
    img.paste(Image.new('RGB', m.size, fill), (x, y), m)


def _copyright(img):
    ImageDraw.Draw(img).rectangle((104, 166, 200, 178), fill=(255, 255, 255))
    paint_text(img, (106, 168), '© PANDORA BOX', 9, (50, 50, 50))


def _afterwards(img):
    _copyright(img)
    ImageDraw.Draw(img).rectangle((2, 60, 70, 86), fill=(255, 255, 255))
    paint_text(img, (8, 66), 'Afterwards', 13, (150, 20, 30), shear=0.25, outline_fill=(40, 10, 10))


def title_bs():
    """Title still: copyright line in English (the brush logo stays)."""
    return bs_edit('SCE00/TITLE.BS', 320, 192, _copyright)


def title_bg():
    return bs_edit('SCE00/TITLE.BG', 320, 192, _copyright)


def title47():
    """The 'Afterwards' title (その後の学校であった怖い話): red subtitle in English."""
    return bs_edit('SCE47/47A44.BG', 320, 192, _afterwards)


# ---- movie text (STR/MV video sectors): re-encode the frames that show text --------------

def movie_sectors(path):
    """-> {frame: [(chunk, sector index, 32-byte header)]}, {frame: (w, h, bs data)}"""
    d = open(path, 'rb').read()
    secs, chunks = {}, {}
    for i in range(len(d) // 2048):
        s = d[i * 2048:(i + 1) * 2048]
        if s[0:4] != b'\x60\x01\x01\x80':
            continue
        chunk, n, frame, size, w, h = struct.unpack_from('<HHIIHH', s, 4)
        secs.setdefault(frame, []).append((chunk, i, s[:32]))
        chunks.setdefault(frame, {})[chunk] = s[32:]
    frames = {}
    for f, lst in secs.items():
        lst.sort()
        n = struct.unpack_from('<H', lst[0][2], 6)[0]
        if len(lst) != n:
            continue
        _, _, _, size, w, h = struct.unpack_from('<HHIIHH', lst[0][2], 4)
        frames[f] = (w, h, b''.join(chunks[f][c] for c, _, _ in lst))
    return secs, frames


def _layer(text, size, w, h, x, y):
    """Float mask (h, w) of white text with its left edge at x, top of caps near y."""
    f = ImageFont.truetype(TTF, size * 4)
    im = Image.new('L', (w * 4, h * 4), 0)
    dr = ImageDraw.Draw(im)
    bb = dr.textbbox((0, 0), 'H', font=f)
    dr.text((x * 4, y * 4 - bb[1]), text, font=f, fill=255)
    m = np.asarray(im.resize((w, h), Image.LANCZOS)).astype(float) / 255
    xs = np.nonzero(m.max(0) > 0.05)[0]
    return m, (int(xs.min()), int(xs.max())) if len(xs) else (x, x)


def movie_text(key, elements):
    """elements: [(y0, y1, x0, x1 of the Japanese text, English, size, y of the English)].
    For every frame with lit pixels in an element's band: English at the same brightness,
    revealed left to right as far as the Japanese was (soft 12 px edge)."""
    import bs
    path = os.path.join(GRP, *key.split('/'))
    secs, frames = movie_sectors(path)
    max_hdr = max(int.from_bytes(fr[2][:2], 'little') for fr in frames.values())
    out = {}
    for f, (w, h, data) in sorted(frames.items()):
        rgb, _ = bs.decode(data, w, h)
        lum = rgb.max(2).astype(float)
        frame = np.zeros((h, w))
        lit = False
        for y0, y1, jx0, jx1, text, size, ey in elements:
            band = lum[y0:y1, :]
            if band.max() < 5:                  # even a faint fade-in frame is replaced
                continue
            lit = True
            b = band.max() / 255
            xs = np.nonzero(band.max(0) >= max(5, band.max() * 0.3))[0]
            reveal = (xs.max() - jx0) / max(1, jx1 - jx0)
            m, (ex0, ex1) = _layer(text, size, w, h, jx0, ey)
            edge = ex0 + reveal * (ex1 - ex0 + 12)
            ramp = np.clip((edge - np.arange(w)) / 12, 0, 1)
            frame = np.maximum(frame, m * ramp[None, :] * b * 255)
        if not lit:
            continue
        img = np.repeat(frame[..., None], 3, 2).clip(0, 255).astype(np.uint8)
        lst = secs[f]
        cap = len(lst) * 2016
        new, q = bs.encode_fit(img, cap, max_hdr)
        used = (len(new) + 3) // 4 * 4          # header +12: frame bytes, rounded to 4
        new = new.ljust(cap, b'\0')
        for k, (chunk, idx, hdr) in enumerate(lst):
            hd = bytearray(hdr)
            struct.pack_into('<I', hd, 12, used)
            hd[20:28] = new[0:8]
            out[idx] = bytes(hd) + new[k * 2016:(k + 1) * 2016]
    return out


END_LINE = 'And so the terror begins again...'
END_WORD = 'The End'


def theend():
    return movie_text('SCE00/THEEND.STR', [(80, 120, 27, 293, END_LINE, 17, 91),
                                           (125, 178, 27, 62, END_WORD, 24, 142)])


def theend47():
    return movie_text('SCE47/47D01.MV', [(80, 120, 27, 293, END_LINE, 17, 91),
                                         (125, 178, 27, 62, END_WORD, 24, 142)])


def badend():
    return movie_text('SCE00/BADEND.STR', [(80, 120, 18, 305, 'And then, it was all over...', 17, 91)])


# ---- story props in photographed backgrounds (tools/props.py) ------------------------------
# each: background id -> edit(img); every BG file with the same bytes gets the result

def _write(img, text, quad, color, size=24, bold=0, marker=False, align='center', opacity=1.0):
    import props
    a = props.text_alpha(text, size, bold=bold, marker=marker, align=align)
    props.place(img, a, quad, color, opacity=opacity)


def _erase(img, boxes, mode='dark', t=30, grow=1, bright=None):
    """Remove lettering; bright = minimum brightness of pixels the fill may sample (paper)."""
    import props
    a = np.asarray(img)
    m = np.zeros(a.shape[:2], bool)
    for b in boxes:
        m |= props.ink_mask(a, b, mode, t, grow)
    support = None if bright is None else (a.mean(2) > bright)
    img.paste(Image.fromarray(props.fill(a, m, support=support)))


def _rq(x, y, w, h, angle=0.0):
    import props
    return props.rect_quad(x, y, w, h, angle)


def p04a26(img):            # photo name card 赤坂 陽介
    _erase(img, [[(104, 0), (216, 0), (216, 18), (104, 42)]], 'dark', 28)
    _write(img, 'Yosuke Akasaka', _rq(110, 17, 104, 15, -9), (45, 45, 45), align='left')


def p04a27(img):            # 畑中 亨
    _erase(img, [[(48, 4), (140, 4), (140, 27), (48, 45)]], 'dark', 28)
    _write(img, 'Toru Hatanaka', _rq(52, 25, 98, 15, -9), (45, 45, 45), align='left')


def p07a06(img):            # door plate 新聞部 (newspaper club room)
    plate = [(92, 112), (218, 36), (224, 82), (93, 154)]
    _erase(img, [plate], 'dark', 22, 2)
    _write(img, 'Newspaper Club', [(100, 106), (214, 44), (218, 78), (101, 146)], (30, 30, 30), bold=1)


def p30a13(img):            # class plate 1年E組
    _erase(img, [(133, 74, 208, 101)], 'dark', 30)
    _write(img, 'Class 1-E', _rq(138, 78, 66, 20), (25, 25, 25), bold=1)


def p39a02(img):            # tear-off calendar 五月 13 金
    _erase(img, [(147, 26, 179, 44), (149, 114, 183, 143)], 'dark', 30)
    _write(img, 'MAY', _rq(149, 29, 28, 13), (30, 30, 30))
    _write(img, 'FRI', _rq(148, 118, 36, 22), (30, 30, 30))


def p51a17(img):            # note on the movie ticket
    _erase(img, [[(40, 40), (234, 66), (252, 152), (24, 102)]], 'dark', 20, 2, bright=70)
    _write(img, 'Please come.', _rq(66, 55, 84, 14, 14), (70, 70, 80), marker=True, align='left')
    _write(img, 'I might be no good anymore...', _rq(48, 80, 190, 14, 15), (70, 70, 80), marker=True, align='left')


def p60a05(img):            # red note: "It's not fair"
    _erase(img, [(128, 14, 208, 166)], 'red', 20, 2, bright=90)
    _write(img, "It's\nnot\nfair", _rq(136, 30, 62, 118), (175, 35, 35), marker=True)


def p60a06(img):            # red note: "You're coming with me too"
    _erase(img, [[(124, 50), (226, 50), (214, 168), (100, 162)]], 'red', 18, 2, bright=90)
    _write(img, "You're\ncoming\nwith me\ntoo", _rq(132, 52, 78, 104, 6), (175, 35, 35), marker=True)


def p60a10(img):            # red note: "...no such thing as curses"
    _erase(img, [(104, 18, 216, 166)], 'red', 20, 2, bright=90)
    _write(img, 'And you\nsaid there\nwas no such\nthing as\ncurses...', _rq(118, 36, 84, 112), (175, 35, 35), marker=True)


def _kokkuri(img, yes_box, no_box, h):
    _erase(img, [yes_box, no_box], 'dark', 25, 1)
    for word, (x0, y0, x1, y1) in (('YES', yes_box), ('NO', no_box)):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w = h * (2.2 if word == 'YES' else 1.6)
        _write(img, word, _rq(cx - w / 2, cy - h / 2, w, h), (40, 40, 40), marker=True)


def p17a02(img):            # Kokkuri-san board: はい / いいえ (the kana stay, as in the script)
    _kokkuri(img, (80, 13, 116, 34), (190, 13, 243, 34), 15)


def p26a23(img):
    _kokkuri(img, (80, 13, 116, 34), (190, 13, 243, 34), 15)


def p20a05(img):
    _kokkuri(img, (82, 11, 118, 28), (193, 11, 235, 30), 13)


def p22a23(img):            # scratched words on the restroom wall (22:a9a4)
    _erase(img, [(0, 0, 320, 192)], 'redark', 26, 2)
    red = (115, 15, 20)
    _write(img, 'Running away alone', _rq(150, 16, 210, 24, 3), red, marker=True, align='left', opacity=0.9)
    _write(img, 'I called for help so many times', _rq(88, 58, 330, 24, 2), red, marker=True, align='left', opacity=0.9)
    _write(img, 'I was killed', _rq(58, 100, 150, 26, -2), red, marker=True, align='left', opacity=0.9)
    _write(img, 'Dragged in here', _rq(6, 140, 190, 26, 1), red, marker=True, align='left', opacity=0.9)


def p66a07(img):            # school paper: the missing girl (last story)
    _erase(img, [(78, 32, 130, 47), (161, 36, 200, 46), (170, 40, 189, 152), (148, 58, 169, 152),
                 (87, 44, 109, 152)], 'dark', 25)
    _erase(img, [(188, 40, 212, 152)], 'light', 30)
    ink = (25, 25, 25)
    _write(img, 'SCHOOL NEWS', _rq(80, 34, 48, 11), ink, bold=1)
    _write(img, '7 WONDERS', _rq(162, 37, 37, 9), ink, bold=1)
    _write(img, 'GIRL STUDENT MISSING', _rq(210, 44, 104, 18, 90), (235, 235, 235), bold=1)
    _write(img, 'CLUB MEMBER WHO COVERED THE 7 WONDERS', _rq(188, 44, 104, 15, 90), ink)
    _write(img, 'SEARCH ON - INFO WANTED', _rq(168, 62, 86, 15, 90), ink, bold=1)
    _write(img, 'THE 7TH STORY: A BIZARRE CASE', _rq(108, 47, 102, 18, 90), ink, bold=1)


def p18a08(img):            # wall newspaper featuring Kazama
    _erase(img, [(253, 6, 279, 80)], 'dark', 30)
    ink = (20, 20, 20)
    ImageDraw.Draw(img).rectangle((109, 24, 127, 70), fill=(205, 205, 205), outline=(25, 25, 25))
    _write(img, 'KAZAMA', _rq(126, 27, 41, 15, 90), ink, bold=1)
    _write(img, 'SCHOOL NEWS', _rq(278, 10, 66, 20, 90), ink, bold=1)


PROPS = {
    '04A26': p04a26, '04A27': p04a27, '07A06': p07a06, '30A13': p30a13, '39A02': p39a02,
    '51A17': p51a17, '60A05': p60a05, '60A06': p60a06, '60A10': p60a10, '17A02': p17a02,
    '26A23': p26a23, '20A05': p20a05, '22A23': p22a23, '66A07': p66a07, '18A08': p18a08,
}


def props_all():
    """-> {'SCExx/NNANN.BG': bytes} for every copy of every edited background."""
    import glob
    paths = sorted(glob.glob(os.path.join(GRP, 'SCE*', '*.BG')))
    by_name = {os.path.basename(p)[:-3]: p for p in paths}
    out = {}
    for pid, edit in PROPS.items():
        src = by_name[pid]
        key = os.path.relpath(src, GRP).replace(os.sep, '/')
        data = bs_edit(key, 320, 192, edit)
        orig = open(src, 'rb').read()
        for p in paths:
            if open(p, 'rb').read() == orig:
                out[os.path.relpath(p, GRP).replace(os.sep, '/')] = data
    return out


# ---- movie subtitles (work/translation/en/movie_subs.json): burnt into the frames ---------
# Noto Sans 13 px, antialiased (drawn at 4x and box-filtered), white with a 1.5 px dark
# outline and a soft drop shadow, no band. Smooth edges cost far fewer DCT coefficients than
# 1-bit pixel letters. Only the macroblocks the text touches are re-encoded, at full precision;
# bs.reencode_overlay frees the bytes from the rest of the frame (see there).

SUB_SIZE = 13          # px
SUB_LINE_H = 16
SUB_BOTTOM = 5         # baseline of the last line, px above the frame bottom
SUB_STROKE = 1.5
SUB_SS = 4             # supersampling


def _sub_layer(text, w, h):
    """-> (fill alpha, dark alpha) float arrays (h, w), lines centred at the bottom."""
    f = ImageFont.truetype(TTF, SUB_SIZE * SUB_SS)
    W, H = w * SUB_SS, h * SUB_SS
    fill, dark = Image.new('L', (W, H)), Image.new('L', (W, H))
    df, dd = ImageDraw.Draw(fill), ImageDraw.Draw(dark)
    lines = text.split('\n')
    asc, _ = f.getmetrics()
    st = int(round(SUB_STROKE * SUB_SS))
    for i, ln in enumerate(lines):
        y = (h - SUB_BOTTOM - (len(lines) - 1 - i) * SUB_LINE_H) * SUB_SS - asc
        tw = df.textlength(ln, font=f)
        if tw / SUB_SS > w - 8:
            raise ValueError('subtitle line too wide (%d px): %r' % (tw / SUB_SS, ln))
        x = (W - tw) / 2
        dd.text((x + SUB_SS, y + SUB_SS), ln, font=f, fill=150, stroke_width=st, stroke_fill=150)
        dd.text((x, y), ln, font=f, fill=255, stroke_width=st, stroke_fill=255)
        df.text((x, y), ln, font=f, fill=255)
    a_f = np.asarray(fill.resize((w, h), Image.BOX), float) / 255
    a_d = np.asarray(dark.resize((w, h), Image.BOX), float) / 255
    return a_f, a_d


def _sub_compose(rgb, a_f, a_d):
    out = rgb.astype(float) * (1 - a_d[..., None])
    out = out * (1 - a_f[..., None]) + 235 * a_f[..., None]
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def movie_subs(key, cue_file):
    import bs
    import hashlib
    import inspect
    import pickle
    path = os.path.join(GRP, *key.split('/'))
    cues = json.load(open(cue_file, encoding='utf-8'))['cues']
    # the encode takes minutes: cached on the movie, the cues, the font and the encoder code
    hsh = hashlib.sha1()
    for p in (path, cue_file, TTF, bs.__file__):
        hsh.update(open(p, 'rb').read())
    for fn in (_sub_layer, _sub_compose, movie_subs):
        hsh.update(inspect.getsource(fn).encode())
    hsh.update(repr((SUB_SIZE, SUB_LINE_H, SUB_BOTTOM, SUB_STROKE, SUB_SS)).encode())
    cache = os.path.join(ROOT, 'work', 'cache', 'movie_subs_%s.pkl' % hsh.hexdigest()[:16])
    if os.path.exists(cache):
        movie_subs.report, out = pickle.load(open(cache, 'rb'))
        return out
    secs, frames = movie_sectors(path)
    max_hdr = max(int.from_bytes(fr[2][:2], 'little') for fr in frames.values())
    layers = {}
    out = {}
    report = {}
    for f, (w, h, data) in sorted(frames.items()):
        t = secs[f][0][1] / 150.0
        cue = next((c for c in cues if c['start'] <= t < c['end']), None)
        if cue is None:
            continue
        if cue['en'] not in layers:
            a_f, a_d = _sub_layer(cue['en'], w, h)
            layers[cue['en']] = (a_f, a_d, bs.overlay_mbs(a_d > 0.01))
        a_f, a_d, mbs = layers[cue['en']]
        rgb, _ = bs.decode(data, w, h)
        lst = secs[f]
        cap = len(lst) * 2016
        new, how = bs.reencode_overlay(data, w, h, _sub_compose(rgb, a_f, a_d), mbs, cap, max_hdr)
        report[how] = report.get(how, 0) + 1
        used = (len(new) + 3) // 4 * 4
        new = new.ljust(cap, bytes(1))
        for k, (chunk, idx, hdr) in enumerate(lst):
            hd = bytearray(hdr)
            struct.pack_into('<I', hd, 12, used)
            hd[20:28] = new[0:8]
            out[idx] = bytes(hd) + new[k * 2016:(k + 1) * 2016]
    movie_subs.report = report
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    for old in os.listdir(os.path.dirname(cache)):
        if old.startswith('movie_subs_'):
            os.remove(os.path.join(os.path.dirname(cache), old))
    pickle.dump((report, out), open(cache, 'wb'))
    return out


def opening_subs():
    return movie_subs('MOVIES/SEXMOVIE.STR', os.path.join(ROOT, 'work', 'translation', 'en', 'movie_subs.json'))


# ---- title menu credit: version + group, bottom right of the notebook picture -------------
VERSION = 'dev'                  # set by tools/build.py (gfx.VERSION = <build version>)
CREDIT = 'github.com/retro-trans'


def _font_line(img, text, right, top, fill=(235, 235, 235)):
    """One line in the menu font (Kowai Pixel 1x) with a 1 px black outline, right-aligned."""
    import vwf
    widths, bmp = vwf.build_font()
    a = np.asarray(img).copy()
    h, w = a.shape[:2]
    codes = [vwf.CODE_OF.get(ch, ord(ch)) for ch in text]
    x = right - sum(widths[c] for c in codes)
    ink = np.zeros((h, w), bool)
    for c in codes:
        for r in range(16):
            row = struct.unpack_from('<H', bmp, (c * 16 + r) * 2)[0]
            for k in range(16):
                if row & (0x8000 >> k) and 0 <= top + r < h and 0 <= x + k < w:
                    ink[top + r, x + k] = True
        x += widths[c]
    p = np.pad(ink, 1)
    near = np.zeros_like(ink)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            near |= p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
    a[near & ~ink] = 0
    a[ink] = fill
    img.paste(Image.fromarray(a))


def _menu_ink(text, top, h, w):
    """Ink mask (h, w) of one line in the menu font (Kowai Pixel 1x), left edge at x = 1."""
    import vwf
    widths, bmp = vwf.build_font()
    ink = np.zeros((h, w), bool)
    x = 1
    for ch in text:
        c = vwf.CODE_OF.get(ch, ord(ch))
        for r in range(16):
            row = struct.unpack_from('<H', bmp, (c * 16 + r) * 2)[0]
            for k in range(16):
                if row & (0x8000 >> k) and 0 <= top + r < h and 0 <= x + k < w:
                    ink[top + r, x + k] = True
        x += widths[c]
    assert x <= w, (text, x)
    return ink


# In-story Start menu (取材メモを呼び出す / 話の続きを聞く): a 128x48 4bpp image inside the EXE
# (TIM pixel block, CLUT at 0x8004AB00: 0 clear, 1 white, 2 dark outline), uploaded to VRAM
# (832,128) at start-up by 0x80016988 and drawn by the POLY_FT4 at 0x80063584.
STORY_MENU = ('Open the notes', 'Continue the story')
STORY_MENU_PIX = 0x8004AB2C
# the sprite's screen x (0x72-0xF2) moved 2 px left so the long line sits centred in the
# highlight bar (0x6B-0xE6); plain immediates in the start-up code, safe on hardware
STORY_MENU_X = {0x80016904: (0x34040072, 0x34040070),     # ori a0, zero, 0x72 -> 0x70
                0x80016914: (0x340300F2, 0x340300F0)}     # ori v1, zero, 0xf2 -> 0xf0


def story_menu_pix():
    """(48, 128) array of CLUT indices: each line's caps centred on its highlight bar row."""
    h, w = 48, 128
    pix = np.zeros((h, w), np.uint8)
    for text, top in zip(STORY_MENU, (-1, 17)):
        ink = _menu_ink(text, top, h, w)
        pix[outline(ink)] = 2
        pix[ink] = 1
    return pix


def story_menu_exe(exe):
    """Patch the menu image and the sprite position into the EXE bytes (file offsets)."""
    exe = bytearray(exe)
    off = STORY_MENU_PIX - 0x80010000 + 0x800
    assert exe[off - 12:off] == bytes.fromhex('0c0c000000030000') + struct.pack('<HH', 0x20, 0x30)
    flat = story_menu_pix().reshape(-1)
    exe[off:off + 3072] = (flat[0::2] | (flat[1::2] << 4)).astype(np.uint8).tobytes()
    for addr, (old, new) in STORY_MENU_X.items():
        o = addr - 0x80010000 + 0x800
        assert struct.unpack_from('<I', exe, o)[0] == old, hex(addr)
        struct.pack_into('<I', exe, o, new)
    return bytes(exe)


def _credit(img):
    _font_line(img, 'v' + VERSION, 314, 155)
    _font_line(img, CREDIT, 314, 169)


def title_credit():
    """HAIKEI1.BS (title menu; also behind name entry and the save/load screens)."""
    return bs_edit('SCE00/HAIKEI1.BS', 320, 192, _credit)


GFX = {
    'SCE00/HAIKEI1.BS': title_credit,     # version + retro-trans credit
    'SCE00/DI2.TIM': di2,
    'SCE00/TITLE.BS': title_bs,
    'SCE00/TITLE.BG': title_bg,
    'SCE47/47A44.BG': title47,
}


# movies: sector patches {sector index in the file: 2048 bytes} (video sectors only)
GFX_SECTORS = {
    'SCE00/THEEND.STR': theend,
    'SCE47/47D01.MV': theend47,
    'SCE00/BADEND.STR': badend,
    'MOVIES/SEXMOVIE.STR': opening_subs,   # opening narration subtitles
}


def build_all():
    todo = dict(GFX)
    for k, v in props_all().items():
        todo[k] = (lambda v=v: v)
    if os.environ.get('GFX_TEST'):        # test only: still paths re-encoded unchanged
        todo['SCE00/DANJO.BS'] = lambda: bs_edit('SCE00/DANJO.BS', 128, 256, lambda img: None)
        todo['SCE00/00A01.BG'] = lambda: bs_edit('SCE00/00A01.BG', 320, 192, lambda img: None)
    return {k: f() for k, f in todo.items()}


def movie_roundtrip(key):
    """Test only (GFX_TEST=1): every frame decoded and re-encoded, to check the movie path."""
    import bs
    secs, frames = movie_sectors(os.path.join(GRP, *key.split('/')))
    max_hdr = max(int.from_bytes(fr[2][:2], 'little') for fr in frames.values())
    out = {}
    for f, (w, h, data) in sorted(frames.items()):
        rgb, _ = bs.decode(data, w, h)
        cap = len(secs[f]) * 2016
        new, q = bs.encode_fit(rgb, cap, max_hdr)
        used = (len(new) + 3) // 4 * 4
        new = new.ljust(cap, bytes(1))
        for k, (chunk, idx, hdr) in enumerate(secs[f]):
            hd = bytearray(hdr)
            struct.pack_into('<I', hd, 12, used)
            hd[20:28] = new[0:8]
            out[idx] = bytes(hd) + new[k * 2016:(k + 1) * 2016]
    return out


def build_sectors():
    todo = dict(GFX_SECTORS)
    if os.environ.get('GFX_TEST'):
        todo['SCE00/PBROGO.MV'] = lambda: movie_roundtrip('SCE00/PBROGO.MV')
    return {k: f() for k, f in todo.items()}


def preview(outdir):
    os.makedirs(outdir, exist_ok=True)
    for k, f in GFX.items():
        data = f()
        if k.endswith(('.BS', '.BG')):
            import bs
            body = data if data[2:4] == b'\x00\x38' else data[4:]
            rgb, _ = bs.decode(body, 320, 192)
            Image.fromarray(rgb).resize((640, 384), Image.NEAREST).save(os.path.join(outdir, k.replace('/', '_') + '.png'))
        if k.endswith('.TIM'):
            for off, t in tim.scan(data):
                tim.to_image(t).convert('RGB').resize((t['w'] * 4, t['h'] * 4), Image.NEAREST).save(
                    os.path.join(outdir, k.replace('/', '_') + '.png'))
        print(k, len(data), 'bytes')
    import bs
    for k, f in GFX_SECTORS.items():
        secs = f()
        path = os.path.join(GRP, *k.split('/'))
        d = bytearray(open(path, 'rb').read())
        for i, s in secs.items():
            d[i * 2048:(i + 1) * 2048] = s
        tmp = os.path.join(outdir, '_tmp.str')
        open(tmp, 'wb').write(d)
        import strframes
        fr = strframes.frames(tmp)
        os.remove(tmp)
        tiles = [Image.fromarray(bs.decode(data, w, h)[0]) for n, w, h, data in fr[::8]]
        sheet = Image.new('RGB', (4 * 320, ((len(tiles) + 3) // 4) * 192))
        for j, t in enumerate(tiles):
            sheet.paste(t, ((j % 4) * 320, (j // 4) * 192))
        sheet.save(os.path.join(outdir, k.replace('/', '_') + '.png'))
        print(k, len(secs), 'sectors')


if __name__ == '__main__':
    if sys.argv[1] == 'preview':
        preview(sys.argv[2])
