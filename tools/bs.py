"""PlayStation MDEC still images (.BS, and the .BG backgrounds = 4-byte prefix + BS).

    python tools/bs.py png <file> <out.png> [w h]     decode (w h default from the BG prefix / 320 240)
    python tools/bs.py sheet <out.png> <files...>     contact sheet

Format (as libavcodec mdec.c reads it): 8-byte header (u16 size/4?, 0x3800, qscale,
version 2/3), then a bitstream of 16-bit little-endian words read MSB first. Macroblocks
16x16, column by column; each = Cr, Cb, Y0, Y1, Y2, Y3 (8x8 blocks). DC: v2 10-bit
signed, v3 MPEG-1 DC size VLC + difference (per component). AC: MPEG-1 table B.14
(EOB '10'), escape '000001' + 6-bit run + 10-bit signed level. Dequant
(level * qscale * Q[zz]) >> 3 with the MPEG-1 intra matrix; 8x8 IDCT; YCbCr -> RGB.
"""
import os
import sys

import numpy as np
from PIL import Image

ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48,
          41, 34, 27, 20, 13, 6, 7, 14, 21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15,
          23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]
QMAT = [8, 16, 19, 22, 26, 27, 29, 34, 16, 16, 22, 24, 27, 29, 34, 37, 19, 22, 26, 27, 29, 34, 34, 38,
        22, 22, 26, 27, 29, 34, 37, 40, 22, 26, 27, 29, 32, 35, 40, 48, 26, 27, 29, 32, 35, 40, 48, 58,
        26, 27, 29, 34, 38, 46, 56, 69, 27, 29, 35, 38, 46, 56, 69, 83]

# MPEG-1 table B.14 without the sign bit: code -> (run, level)
AC = {
    '11': (0, 1), '011': (1, 1), '0100': (0, 2), '0101': (2, 1), '00101': (0, 3), '00111': (3, 1),
    '00110': (4, 1), '000110': (1, 2), '000111': (5, 1), '000101': (6, 1), '000100': (7, 1),
    '0000110': (0, 4), '0000100': (2, 2), '0000111': (8, 1), '0000101': (9, 1),
    '00100110': (0, 5), '00100001': (0, 6), '00100101': (1, 3), '00100100': (3, 2), '00100111': (10, 1),
    '00100011': (11, 1), '00100010': (12, 1), '00100000': (13, 1),
    '0000001010': (0, 7), '0000001100': (1, 4), '0000001011': (2, 3), '0000001111': (4, 2),
    '0000001001': (5, 2), '0000001110': (14, 1), '0000001101': (15, 1), '0000001000': (16, 1),
    '000000011101': (0, 8), '000000011000': (0, 9), '000000010011': (0, 10), '000000010000': (0, 11),
    '000000011011': (1, 5), '000000010100': (2, 4), '000000011100': (3, 3), '000000010010': (4, 3),
    '000000011110': (6, 2), '000000010101': (7, 2), '000000010001': (8, 2), '000000011111': (17, 1),
    '000000011010': (18, 1), '000000011001': (19, 1), '000000010111': (20, 1), '000000010110': (21, 1),
    '0000000011010': (0, 12), '0000000011001': (0, 13), '0000000011000': (0, 14), '0000000010111': (0, 15),
    '0000000010110': (1, 6), '0000000010101': (1, 7), '0000000010100': (2, 5), '0000000010011': (3, 4),
    '0000000010010': (5, 3), '0000000010001': (9, 2), '0000000010000': (10, 2), '0000000011111': (22, 1),
    '0000000011110': (23, 1), '0000000011101': (24, 1), '0000000011100': (25, 1), '0000000011011': (26, 1),
    '00000000011111': (0, 16), '00000000011110': (0, 17), '00000000011101': (0, 18), '00000000011100': (0, 19),
    '00000000011011': (0, 20), '00000000011010': (0, 21), '00000000011001': (0, 22), '00000000011000': (0, 23),
    '00000000010111': (0, 24), '00000000010110': (0, 25), '00000000010101': (0, 26), '00000000010100': (0, 27),
    '00000000010011': (0, 28), '00000000010010': (0, 29), '00000000010001': (0, 30), '00000000010000': (0, 31),
    '000000000011000': (0, 32), '000000000010111': (0, 33), '000000000010110': (0, 34), '000000000010101': (0, 35),
    '000000000010100': (0, 36), '000000000010011': (0, 37), '000000000010010': (0, 38), '000000000010001': (0, 39),
    '000000000010000': (0, 40), '000000000011111': (1, 8), '000000000011110': (1, 9), '000000000011101': (1, 10),
    '000000000011100': (1, 11), '000000000011011': (1, 12), '000000000011010': (1, 13), '000000000011001': (1, 14),
    '0000000000010011': (1, 15), '0000000000010010': (1, 16), '0000000000010001': (1, 17), '0000000000010000': (1, 18),
    '0000000000010100': (6, 3), '0000000000011010': (11, 2), '0000000000011001': (12, 2), '0000000000011000': (13, 2),
    '0000000000010111': (14, 2), '0000000000010110': (15, 2), '0000000000010101': (16, 2), '0000000000011111': (27, 1),
    '0000000000011110': (28, 1), '0000000000011101': (29, 1), '0000000000011100': (30, 1), '0000000000011011': (31, 1),
}
AC_CODE = {v: k for k, v in AC.items()}
DC_LUMA = {'100': 0, '00': 1, '01': 2, '101': 3, '110': 4, '1110': 5, '11110': 6, '111110': 7, '1111110': 8}
DC_CHROMA = {'00': 0, '01': 1, '10': 2, '110': 3, '1110': 4, '11110': 5, '111110': 6, '1111110': 7, '11111110': 8}
DC_LUMA_CODE = {v: k for k, v in DC_LUMA.items()}
DC_CHROMA_CODE = {v: k for k, v in DC_CHROMA.items()}

_k = np.arange(8)
_T = np.cos((2 * _k[None, :] + 1) * _k[:, None] * np.pi / 16) * np.where(_k[:, None] == 0, np.sqrt(1 / 8), np.sqrt(2 / 8))


class Bits:
    def __init__(self, data):
        w = np.frombuffer(data[:len(data) // 2 * 2], '<u2')
        self.s = ''.join(format(int(x), '016b') for x in w)
        self.p = 0

    def get(self, n):
        v = self.s[self.p:self.p + n]
        if len(v) < n:
            raise EOFError
        self.p += n
        return v

    def vlc(self, table, maxlen=17):
        for n in range(1, maxlen):
            c = self.s[self.p:self.p + n]
            if c in table:
                self.p += n
                return table[c]
        raise ValueError('bad code at %d' % self.p)


def sbits(b):
    v = int(b, 2)
    return v - (1 << len(b)) if b[0] == '1' else v


def dc_diff(size, bits):
    if size == 0:
        return 0
    v = int(bits, 2)
    return v if bits[0] == '1' else v - (1 << size) + 1


def header(data):
    q = int.from_bytes(data[4:6], 'little')
    ver = int.from_bytes(data[6:8], 'little')
    assert data[2:4] == b'\x00\x38', 'not a BS header'
    return q, ver


def decode(data, w, h):
    """data starts at the BS header -> RGB uint8 array (h, w, 3)."""
    q, ver = header(data)
    b = Bits(data[8:])
    mbw, mbh = (w + 15) // 16, (h + 15) // 16
    Y = np.zeros((mbh * 16, mbw * 16))
    Cb = np.zeros((mbh * 8, mbw * 8))
    Cr = np.zeros((mbh * 8, mbw * 8))
    last = [0, 0, 0]
    for mx in range(mbw):
        for my in range(mbh):
            for n in range(6):          # Cr, Cb, Y0..Y3
                comp = 2 if n == 0 else 1 if n == 1 else 0
                coef = np.zeros(64)
                if ver <= 2:
                    coef[0] = 2 * sbits(b.get(10)) + 1024
                else:
                    tab = DC_LUMA if comp == 0 else DC_CHROMA
                    size = b.vlc(tab, 10)
                    last[comp] += dc_diff(size, b.get(size) if size else '')
                    coef[0] = last[comp] * 8 + 1024
                i = 0
                while True:
                    if b.s[b.p:b.p + 2] == '10':
                        b.p += 2
                        break
                    if b.s[b.p:b.p + 6] == '000001':
                        b.p += 6
                        run = int(b.get(6), 2)
                        level = sbits(b.get(10))
                    else:
                        run, level = b.vlc(AC)
                        if b.get(1) == '1':
                            level = -level
                    i += run + 1
                    if i > 63:
                        raise ValueError('coefficient overflow mb %d,%d' % (mx, my))
                    j = ZIGZAG[i]
                    coef[j] = (level * q * QMAT[j]) / 8
                blk = _T.T @ coef.reshape(8, 8) @ _T
                if n >= 2:
                    k = n - 2
                    y0, x0 = my * 16 + (k // 2) * 8, mx * 16 + (k % 2) * 8
                    Y[y0:y0 + 8, x0:x0 + 8] = blk
                else:
                    (Cr if n == 0 else Cb)[my * 8:my * 8 + 8, mx * 8:mx * 8 + 8] = blk - 128
    cb = Cb.repeat(2, 0).repeat(2, 1)
    cr = Cr.repeat(2, 0).repeat(2, 1)
    r = Y + 1.402 * cr
    g = Y - 0.344136 * cb - 0.714136 * cr
    bl = Y + 1.772 * cb
    rgb = np.clip(np.stack([r, g, bl], -1), 0, 255).astype(np.uint8)
    return rgb[:h, :w], b.p


def _vlc_bits(run, level):
    """AC run/level -> bit string (table code + sign, or escape 6+10 bits)."""
    a = abs(level)
    code = AC_CODE.get((run, a))
    if code is not None:
        return code + ('1' if level < 0 else '0')
    return '000001' + format(run, '06b') + format(level & 0x3FF, '010b')


def encode(rgb, q, version=3):
    """RGB uint8 (h, w, 3) -> (BS bytes with header, number of MDEC codes). Version 3 only."""
    assert version == 3
    h, w = rgb.shape[:2]
    H, W = (h + 15) // 16 * 16, (w + 15) // 16 * 16
    img = np.zeros((H, W, 3))
    img[:h, :w] = rgb
    img[h:, :] = img[h - 1:h, :] if h < H else 0
    img[:, w:] = img[:, w - 1:w] if w < W else 0
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    Y = 0.299 * r + 0.587 * g + 0.114 * b
    Cb = -0.168736 * r - 0.331264 * g + 0.5 * b
    Cr = 0.5 * r - 0.418688 * g - 0.081312 * b
    Cb = Cb.reshape(H // 2, 2, W // 2, 2).mean((1, 3)) + 128
    Cr = Cr.reshape(H // 2, 2, W // 2, 2).mean((1, 3)) + 128
    out = []
    last = [0, 0, 0]
    ncodes = 0
    for mx in range(W // 16):
        for my in range(H // 16):
            blocks = [(2, Cr[my * 8:my * 8 + 8, mx * 8:mx * 8 + 8]), (1, Cb[my * 8:my * 8 + 8, mx * 8:mx * 8 + 8])]
            for k in range(4):
                y0, x0 = my * 16 + (k // 2) * 8, mx * 16 + (k % 2) * 8
                blocks.append((0, Y[y0:y0 + 8, x0:x0 + 8]))
            for comp, blk in blocks:
                C = (_T @ blk @ _T.T).reshape(64)
                dc = int(round((C[0] - 1024) / 8))
                dc = max(-128, min(127, dc))
                diff = dc - last[comp]
                last[comp] = dc
                size = abs(diff).bit_length()
                tab = DC_LUMA_CODE if comp == 0 else DC_CHROMA_CODE
                bits = '' if size == 0 else format(diff if diff > 0 else diff + (1 << size) - 1, '0%db' % size)
                out.append(tab[size] + bits)
                ncodes += 2                     # DC + EOB
                run = 0
                for i in range(1, 64):
                    j = ZIGZAG[i]
                    lv = int(round(C[j] * 8 / (q * QMAT[j])))
                    lv = max(-511, min(511, lv))
                    if lv == 0:
                        run += 1
                        continue
                    out.append(_vlc_bits(run, lv))
                    ncodes += 1
                    run = 0
                out.append('10')
    bits = ''.join(out) + '1111111111'     # end of frame (every original stream has it)
    bits += '0' * (-len(bits) % 32)
    words = [int(bits[i:i + 16], 2) for i in range(0, len(bits), 16)]
    body = np.array(words, '<u2').tobytes()
    hdr = (((ncodes + 1) // 2 + 31) // 32 * 32).to_bytes(2, 'little') + b'\x00\x38' + \
        q.to_bytes(2, 'little') + version.to_bytes(2, 'little')
    return hdr + body, ncodes


def encode_fit(rgb, max_bytes, max_hdr):
    """Smallest qscale whose output fits max_bytes and the original MDEC code count."""
    for q in range(1, 64):
        data, n = encode(rgb, q)
        if len(data) <= max_bytes and int.from_bytes(data[:2], 'little') <= max_hdr:
            return data, q
    raise ValueError('does not fit')


# ---- partial re-encoding: keep the original coefficients of untouched macroblocks ----------

def decode_levels(data, w, h):
    """-> (qscale, [(comp, dc, [(run, level), ...]) per block in stream order]) (v3 only)."""
    q, ver = header(data)
    assert ver == 3
    b = Bits(data[8:])
    mbw, mbh = (w + 15) // 16, (h + 15) // 16
    last = [0, 0, 0]
    out = []
    for _ in range(mbw * mbh):
        for n in range(6):
            comp = 2 if n == 0 else 1 if n == 1 else 0
            size = b.vlc(DC_LUMA if comp == 0 else DC_CHROMA, 10)
            last[comp] += dc_diff(size, b.get(size) if size else '')
            ac = []
            while True:
                if b.s[b.p:b.p + 2] == '10':
                    b.p += 2
                    break
                if b.s[b.p:b.p + 6] == '000001':
                    b.p += 6
                    run = int(b.get(6), 2)
                    level = sbits(b.get(10))
                else:
                    run, level = b.vlc(AC)
                    if b.get(1) == '1':
                        level = -level
                ac.append((run, level))
            out.append((comp, last[comp], ac))
    return q, out


def block_levels(pix, q, keep=64):
    """8x8 pixel block (Y 0-255, or chroma + 128) -> (dc, [(run, level)]), AC up to zigzag keep."""
    C = (_T @ pix @ _T.T).reshape(64)
    dc = max(-128, min(127, int(round((C[0] - 1024) / 8))))
    ac, run = [], 0
    for i in range(1, keep):
        j = ZIGZAG[i]
        lv = max(-511, min(511, int(round(C[j] * 8 / (q * QMAT[j])))))
        if lv == 0:
            run += 1
            continue
        ac.append((run, lv))
        run = 0
    return dc, ac


def encode_blocks(blocks, q):
    """[(comp, dc, ac)] in stream order -> (BS v3 bytes, MDEC code count)."""
    out = []
    last = [0, 0, 0]
    ncodes = 0
    for comp, dc, ac in blocks:
        diff = dc - last[comp]
        last[comp] = dc
        size = abs(diff).bit_length()
        tab = DC_LUMA_CODE if comp == 0 else DC_CHROMA_CODE
        out.append(tab[size] + ('' if size == 0 else format(diff if diff > 0 else diff + (1 << size) - 1, '0%db' % size)))
        for run, lv in ac:
            out.append(_vlc_bits(run, lv))
        out.append('10')
        ncodes += 2 + len(ac)
    bits = ''.join(out) + '1111111111'
    bits += '0' * (-len(bits) % 32)
    words = [int(bits[i:i + 16], 2) for i in range(0, len(bits), 16)]
    hdr = (((ncodes + 1) // 2 + 31) // 32 * 32).to_bytes(2, 'little') + bytes([0, 0x38]) + \
        q.to_bytes(2, 'little') + (3).to_bytes(2, 'little')
    return hdr + np.array(words, '<u2').tobytes(), ncodes


def mb_blocks(rgb, mx, my, q, keep=64):
    """The 6 blocks (Cr, Cb, Y0-Y3) of macroblock (mx, my) of an RGB image."""
    px = rgb[my * 16:my * 16 + 16, mx * 16:mx * 16 + 16].astype(float)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    Y = 0.299 * r + 0.587 * g + 0.114 * b
    Cb = (-0.168736 * r - 0.331264 * g + 0.5 * b).reshape(8, 2, 8, 2).mean((1, 3)) + 128
    Cr = (0.5 * r - 0.418688 * g - 0.081312 * b).reshape(8, 2, 8, 2).mean((1, 3)) + 128
    out = [(2,) + block_levels(Cr, q, keep), (1,) + block_levels(Cb, q, keep)]
    for k in range(4):
        out.append((0,) + block_levels(Y[(k // 2) * 8:(k // 2) * 8 + 8, (k % 2) * 8:(k % 2) * 8 + 8], q, keep))
    return out


def reencode_rows(data, w, h, rgb, rows, max_bytes, max_hdr):
    """Frame with only macroblock rows `rows` re-encoded from rgb (others bit-exact in
    coefficients). Fewer AC coefficients in those rows when it does not fit."""
    q, blocks = decode_levels(data, w, h)
    mbh = (h + 15) // 16
    for keep in (64, 36, 21, 10, 6, 3, 1):
        new = list(blocks)
        for mx in range((w + 15) // 16):
            for my in rows:
                i = (mx * mbh + my) * 6
                new[i:i + 6] = mb_blocks(rgb, mx, my, q, keep)
        enc, n = encode_blocks(new, q)
        if len(enc) <= max_bytes and int.from_bytes(enc[:2], 'little') <= max_hdr:
            return enc, keep
    raise ValueError('subtitle frame does not fit')


# ---- overlays on a frame (movie subtitles): only the touched macroblocks are re-encoded,
# at full precision; the bytes they need come from the rest of the frame --------------------

def _levels_r(pix, q, r):
    """block_levels with rounding offset r (0.5 = round; smaller = dead zone)."""
    C = (_T @ pix @ _T.T).reshape(64)
    dc = max(-128, min(127, int(round((C[0] - 1024) / 8))))
    ac, run = [], 0
    for i in range(1, 64):
        j = ZIGZAG[i]
        v = C[j] * 8 / (q * QMAT[j])
        lv = max(-511, min(511, int(np.sign(v) * np.floor(abs(v) + r))))
        if lv == 0:
            run += 1
            continue
        ac.append((run, lv))
        run = 0
    return dc, ac


def _mb_blocks_r(rgb, mx, my, q, r):
    px = rgb[my * 16:my * 16 + 16, mx * 16:mx * 16 + 16].astype(float)
    R, G, B = px[..., 0], px[..., 1], px[..., 2]
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    Cb = (-0.168736 * R - 0.331264 * G + 0.5 * B).reshape(8, 2, 8, 2).mean((1, 3)) + 128
    Cr = (0.5 * R - 0.418688 * G - 0.081312 * B).reshape(8, 2, 8, 2).mean((1, 3)) + 128
    out = [(2,) + _levels_r(Cr, q, r), (1,) + _levels_r(Cb, q, r)]
    for k in range(4):
        out.append((0,) + _levels_r(Y[(k // 2) * 8:(k // 2) * 8 + 8, (k % 2) * 8:(k % 2) * 8 + 8], q, r))
    return out


def trim_ac(ac, kmin, lmax):
    """Drop AC levels with |level| <= lmax at zigzag index >= kmin (faint fine detail)."""
    out, pos, carry = [], 0, 0
    for run, lv in ac:
        pos += run + 1
        if pos >= kmin and abs(lv) <= lmax:
            carry += run + 1
            continue
        out.append((run + carry, lv))
        carry = 0
    return out


def requant(blocks, q, q2):
    """AC levels from qscale q to q2 (DC does not depend on qscale)."""
    out = []
    for comp, dc, ac in blocks:
        new, carry = [], 0
        for run, lv in ac:
            l2 = int(np.sign(lv) * np.floor(abs(lv) * q / q2 + 0.5))
            if l2 == 0:
                carry += run + 1
                continue
            new.append((run + carry, l2))
            carry = 0
        out.append((comp, dc, new))
    return out


# trims of the untouched macroblocks, mildest first
OVERLAY_TRIMS = [None] + [(k, 1) for k in (48, 40, 32, 26, 20, 15, 11)] + [(k, 2) for k in (32, 24, 18, 13)]


def overlay_mbs(mask):
    """Macroblocks (mx, my) any pixel of the bool mask falls in."""
    h, w = mask.shape
    return [(mx, my) for my in range((h + 15) // 16) for mx in range((w + 15) // 16)
            if mask[my * 16:my * 16 + 16, mx * 16:mx * 16 + 16].any()]


def reencode_overlay(data, w, h, rgb, mbs, max_bytes, max_hdr, max_bump=3):
    """Frame with macroblocks `mbs` re-encoded from rgb; the others keep their coefficients.
    To fit max_bytes, in this order: faint fine detail of the other macroblocks is dropped
    (OVERLAY_TRIMS), then the frame's qscale goes up one step (the whole frame requantised),
    then (last resort) the overlay macroblocks get a dead zone. -> (bytes, (bump, trim, r))"""
    q0, blocks0 = decode_levels(data, w, h)
    mbh = (h + 15) // 16

    def attempt(q, blocks, trim, r):
        tb = {}
        for mx, my in mbs:
            i = (mx * mbh + my) * 6
            for k, b in enumerate(_mb_blocks_r(rgb, mx, my, q, r)):
                tb[i + k] = b
        new = [tb[i] if i in tb else (b if trim is None else (b[0], b[1], trim_ac(b[2], *trim)))
               for i, b in enumerate(blocks)]
        enc, _ = encode_blocks(new, q)
        ok = len(enc) <= max_bytes and int.from_bytes(enc[:2], 'little') <= max_hdr
        return enc if ok else None

    for bump in range(max_bump + 1):
        q = q0 + bump
        blocks = blocks0 if bump == 0 else requant(blocks0, q0, q)
        for trim in OVERLAY_TRIMS:
            enc = attempt(q, blocks, trim, 0.5)
            if enc:
                return enc, (bump, trim, 0.5)
    for r in (0.3, 0.1, 0.0):
        enc = attempt(q, blocks, OVERLAY_TRIMS[-1], r)
        if enc:
            return enc, (max_bump, OVERLAY_TRIMS[-1], r)
    raise ValueError('overlay frame does not fit')


def load(path):
    """-> (bs bytes, w, h) for .BG (prefix) and .BS files."""
    d = open(path, 'rb').read()
    if d[2:4] == b'\x00\x38':
        return d, None, None
    w = int.from_bytes(d[2:4], 'little')
    h = d[1]
    return d[4:], w, h


def main():
    cmd = sys.argv[1]
    if cmd == 'png':
        data, w, h = load(sys.argv[2])
        if len(sys.argv) > 4:
            w, h = int(sys.argv[4]), int(sys.argv[5])
        rgb, used = decode(data, w or 320, h or 240)
        Image.fromarray(rgb).save(sys.argv[3])
        print('%dx%d, %d of %d bits' % (rgb.shape[1], rgb.shape[0], used, (len(data) - 8) * 8))
    elif cmd == 'sheet':
        out, files = sys.argv[2], sys.argv[3:]
        tw, th, cols = 160, 120, 8
        rows = (len(files) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * tw, rows * (th + 12)), (40, 40, 40))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(sheet)
        for i, f in enumerate(files):
            x, y = (i % cols) * tw, (i // cols) * (th + 12)
            try:
                data, w, h = load(f)
                rgb, _ = decode(data, w or 320, h or 240)
                sheet.paste(Image.fromarray(rgb).resize((tw, th)), (x, y))
            except Exception as e:      # noqa: BLE001
                dr.text((x + 2, y + 40), str(e)[:24], fill=(255, 80, 80))
            dr.text((x + 2, y + th), os.path.basename(f), fill=(255, 255, 0))
        sheet.save(out)


if __name__ == '__main__':
    main()
