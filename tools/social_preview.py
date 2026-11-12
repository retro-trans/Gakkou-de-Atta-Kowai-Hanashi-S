"""GitHub social preview (1280x640) in the retro-trans style: game art panel left, title right.

The art panel is composed from the game's own stills (the six storytellers' portraits and the
title logo, SCE00/*.BS), read from your extracted game files; nothing is downloaded.

python tools/social_preview.py [out.png]      (default work/release/social-preview.png)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import bs  # noqa: E402

FONT = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'NotoSansJP-VF.ttf')
SCE00 = os.path.join(ROOT, 'work', 'source', 'grp', 'SCE00')
W, H = 1280, 640
CREAM, BLUE, GOLD = (246, 238, 222), (122, 166, 232), (232, 184, 48)
TELLERS = ['ARAI', 'SINDOU', 'HOSODA', 'KAZAMA', 'IWASITA', 'FUKUZAWA']


def still(name, w, h):
    d = open(os.path.join(SCE00, name), 'rb').read()
    return Image.fromarray(bs.decode(d, w, h)[0])


def font(size, weight):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def background():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - 760) / 900) ** 2 + ((y - 180) / 620) ** 2)
    t = np.clip(d, 0, 1)[..., None]
    top, bottom = np.array((22, 52, 112), np.float32), np.array((8, 18, 52), np.float32)
    img = top * (1 - t) + bottom * t
    noise = np.random.default_rng(7).normal(0, 2.2, img.shape[:2])[..., None]
    return Image.fromarray(np.clip(img + noise, 0, 255).astype(np.uint8), 'RGB')


def logo_card(pw):
    """The title screen's logo (学校であった怖い話 S + the mirror) on its own white, no copyright."""
    t = still('TITLE.BS', 320, 192).crop((8, 6, 318, 152))
    return t.resize((pw, int(t.height * pw / t.width)), Image.LANCZOS)


def art_panel(pw, ph):
    """The six storytellers, dim, fading up into the white of the title logo below."""
    panel = Image.new('RGBA', (pw, ph), (255, 255, 255, 255))
    card = logo_card(pw)
    top_h = ph - card.height                      # portraits end where the logo card starts
    cols, rows = 2, 3
    cw, ch = pw // cols, top_h // rows
    faces = Image.new('RGB', (pw, top_h), (0, 0, 0))
    for i, n in enumerate(TELLERS):
        f = still(n + '.BS', 128, 128).convert('RGB')
        s = max(cw / 128, ch / 128)
        f = f.resize((int(128 * s + 0.5), int(128 * s + 0.5)), Image.LANCZOS)
        f = f.crop(((f.width - cw) // 2, 0, (f.width - cw) // 2 + cw, ch))
        g = np.asarray(f, np.float32)                # cold, dim, slightly desaturated
        m = g.mean(2, keepdims=True)
        g = (g * 0.55 + m * 0.45) * np.array((0.82, 0.88, 1.0)) * 0.9
        faces.paste(Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)), ((i % cols) * cw, (i // cols) * ch))
    d = ImageDraw.Draw(faces)
    d.line((cw, 0, cw, top_h), fill=(0, 0, 0), width=3)
    for r in range(1, rows):
        d.line((0, ch * r, pw, ch * r), fill=(0, 0, 0), width=3)
    # fade to white over the lower portraits, fully white where the card starts
    y = np.linspace(0, 1, top_h)[:, None]
    k = (np.clip((y - 0.55) / 0.45, 0, 1) ** 1.5)[..., None]
    fa = np.asarray(faces, np.float32) * (1 - k) + 255 * k
    panel.paste(Image.fromarray(fa.astype(np.uint8)), (0, 0))
    panel.paste(card, (0, ph - card.height))
    return panel


def main(out):
    img = background().convert('RGBA')
    px, py, pw, ph = 62, 52, 392, 536
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((px - 2, py + 8, px + pw + 10, py + ph + 14), fill=(0, 0, 0, 150))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(img).rectangle((px - 4, py - 4, px + pw + 3, py + ph + 3), fill=(236, 236, 236, 255))
    img.alpha_composite(art_panel(pw, ph), (px, py))

    dr = ImageDraw.Draw(img)
    x0 = 520
    f = font(30, 700)
    x = x0
    for ch in 'PLAYSTATION':
        dr.text((x, 120), ch, font=f, fill=BLUE, anchor='ls')
        x += dr.textlength(ch, font=f) + 11
    lines = ['GAKKOU DE ATTA', 'KOWAI', 'HANASHI S']
    maxw = W - x0 - 60
    size = 120
    while True:
        f = font(size, 900)
        if max(dr.textlength(l, font=f) for l in lines[1:]) <= maxw:
            break
        size -= 2
    y = 150
    for k, l in enumerate(lines):
        fl = font(int(size * (0.62 if k == 0 else 1.0)), 900)
        asc = fl.getbbox('M')[3] - fl.getbbox('M')[1]
        y += asc
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x0 + 3, y + 5), l, font=fl, fill=(0, 0, 0, 120), anchor='ls')
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
        dr = ImageDraw.Draw(img)
        dr.text((x0, y), l, font=fl, fill=CREAM, anchor='ls')
        y += int(size * 0.22)
    y += 14
    dr.rectangle((x0 + 2, y, x0 + 262, y + 7), fill=GOLD)
    y += 62
    dr.text((x0, y), 'English translation patch', font=font(46, 700), fill=CREAM, anchor='ls')
    dr.text((W - 44, H - 40), 'retro-trans', font=font(32, 600), fill=BLUE, anchor='rs')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.convert('RGB').save(out)
    print(out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'work', 'release', 'social-preview.png'))
