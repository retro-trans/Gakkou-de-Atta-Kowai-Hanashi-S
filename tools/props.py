"""Photo props: remove Japanese lettering from a background picture and letter English in.

Used by tools/gfx.py (PROPS). No OpenCV: the text is masked by colour against its local
background, filled from the blurred surroundings (normalised masked blur) with a little
grain, and the English is drawn with Noto Sans (OFL) straight, rotated or mapped onto a
quadrilateral (perspective), optionally in a rough "marker" style.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, 'tools', 'fonts', 'noto-sans', 'NotoSans-Regular.ttf')


def _blur(a, r):
    """Separable Gaussian blur (sigma r) with edge padding, numpy only."""
    if a.ndim == 3:
        return np.stack([_blur(a[..., c], r) for c in range(a.shape[2])], -1)
    k = int(3 * r + 1)
    x = np.arange(-k, k + 1)
    g = np.exp(-x * x / (2 * r * r))
    g /= g.sum()
    p = np.pad(a.astype(float), k, mode='edge')
    p = sum(g[i] * p[:, i:i + a.shape[1]] for i in range(2 * k + 1))
    return sum(g[i] * p[i:i + a.shape[0], :] for i in range(2 * k + 1))


def ink_mask(a, box, mode='dark', t=30, grow=1):
    """Pixels of lettering inside box (x0, y0, x1, y1) or polygon [(x, y)...]."""
    h, w = a.shape[:2]
    region = Image.new('L', (w, h), 0)
    if len(box) == 4 and not isinstance(box[0], (tuple, list)):
        ImageDraw.Draw(region).rectangle(box, fill=255)
    else:
        ImageDraw.Draw(region).polygon([tuple(p) for p in box], fill=255)
    region = np.asarray(region) > 0
    f = a.astype(float)
    lum = f.mean(2)
    bg = _blur(lum, 6)
    if mode == 'dark':
        m = lum < bg - t
    elif mode == 'light':
        m = lum > bg + t
    elif mode == 'red':
        m = (f[..., 0] - (f[..., 1] + f[..., 2]) / 2) > t
    elif mode == 'redark':      # dark-red strokes: reddish or clearly darker than the wall
        m = ((f[..., 0] - (f[..., 1] + f[..., 2]) / 2) > t / 2) | (lum < bg - t)
    elif mode == 'all':
        m = np.ones_like(region)
    else:
        raise ValueError(mode)
    m &= region
    if grow:
        m = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * grow + 1))) > 0
        m &= region if mode != 'all' else True
    return m


def fill(a, mask, grain=True, seed=1, support=None):
    """Fill masked pixels from the unmasked surroundings (coarse to fine); support limits
    which pixels may be sampled (e.g. only the paper, not the black background)."""
    f = a.astype(float)
    keep = (~mask if support is None else (~mask & support)).astype(float)
    out = f.copy()
    for r in (12, 6, 3, 1.5):
        num = _blur(f * keep[..., None], r)
        den = _blur(keep, r)[..., None]
        est = num / np.maximum(den, 1e-3)
        sel = mask & (den[..., 0] > 0.05)
        out[sel] = est[sel]
    if grain:
        rng = np.random.default_rng(seed)
        resid = f - _blur(f, 1.5)
        sd = np.sqrt(_blur((resid ** 2).mean(2) * keep, 4) / np.maximum(_blur(keep, 4), 1e-3))
        noise = rng.normal(0, 1, mask.shape) * sd
        out[mask] += noise[mask][:, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def text_alpha(text, size, bold=0, marker=False, line_gap=1.15, align='left', seed=3):
    """Text (multi-line with \\n) as a float alpha array at 4x scale, tightly cropped."""
    S = 4
    f = ImageFont.truetype(TTF, size * S)
    lines = text.split('\n')
    dr0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    widths = [dr0.textbbox((0, 0), ln, font=f, stroke_width=bold * S)[2] for ln in lines]
    lh = int(size * S * line_gap)
    W, H = max(widths) + 8 * S, lh * len(lines) + 8 * S
    im = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(im)
    rng = np.random.default_rng(seed)
    for i, ln in enumerate(lines):
        x = 4 * S + {'left': 0, 'center': (max(widths) - widths[i]) // 2, 'right': max(widths) - widths[i]}[align]
        y = 4 * S + i * lh
        if marker:              # letter by letter with a small wobble
            for ch in ln:
                cw = dr.textlength(ch, font=f)
                dx, dy = rng.normal(0, size * S * 0.03, 2)
                dr.text((x + dx, y + dy), ch, font=f, fill=255, stroke_width=bold * S, stroke_fill=255)
                x += cw
        else:
            dr.text((x, y), ln, font=f, fill=255, stroke_width=bold * S, stroke_fill=255)
    a = np.asarray(im).astype(float) / 255
    if marker:
        a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(S * 0.4))).astype(float) / 255
    ys, xs = np.nonzero(a > 0.02)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _coeffs(dst, src):
    """PIL PERSPECTIVE coefficients mapping output dst quad -> input src quad."""
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def place(img, alpha, quad, color, opacity=1.0, fit='contain'):
    """Map the alpha text block onto quad [TL, TR, BR, BL] in img (PIL RGB), keeping its aspect
    (centred in the quad) unless fit == 'stretch'."""
    ah, aw = alpha.shape
    q = np.array(quad, float)
    if fit == 'contain':
        qw = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
        qh = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
        sc = min(qw / aw, qh / ah)
        pw, ph = (qw / sc - aw) / 2, (qh / sc - ah) / 2       # padding in alpha units
        src = [(-pw, -ph), (aw + pw, -ph), (aw + pw, ah + ph), (-pw, ah + ph)]
    else:
        src = [(0, 0), (aw, 0), (aw, ah), (0, ah)]
    W, H = img.size
    m = Image.fromarray((alpha * 255).astype(np.uint8)).transform(
        (W, H), Image.PERSPECTIVE, _coeffs(q.tolist(), src), Image.BICUBIC)
    m = np.asarray(m).astype(float) / 255 * opacity
    a = np.asarray(img).astype(float)
    col = np.array(color, float)
    out = a * (1 - m[..., None]) + col * m[..., None]
    img.paste(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)))


def rect_quad(x, y, w, h, angle=0.0):
    """Quad of a w x h box with its top-left at (x, y), rotated by angle degrees (about TL)."""
    t = np.radians(angle)
    c, s = np.cos(t), np.sin(t)
    pts = [(0, 0), (w, 0), (w, h), (0, h)]
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in pts]


def text_quad(alpha, x, y, height, angle=0.0):
    """Quad for an alpha block drawn with its top-left at (x, y), given pixel height."""
    ah, aw = alpha.shape
    return rect_quad(x, y, aw * height / ah, height, angle)
