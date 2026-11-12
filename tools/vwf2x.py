"""2x-density dialogue text: the Riot Stars font (Skies of Arcadia Latin, tools/skiesfont.py)
drawn as half-size sprites, so upscaling emulators show the full detail.

How it plugs into the game (the 1x canvas path in tools/vwf.py stays for menus):

  vwf_char (payload)   -> text2x_rec: each dialogue letter becomes two POLY_FT4 from the font
                          sheet (outline pass, then letter pass) appended to a prebuilt chain
  0x80017A3C           -> text2x_strips: the window's 10 strips as before, then the chain is
                          linked into the last strip's OT slot (only while the window shows)
  0x80013CE8 (clear)   -> clear2x: for the dialogue window, empty the chain and upload the
                          font sheet + CLUTs (also restores them after movies / other screens)

Font sheet: 4bpp in VRAM (960,32) [page x=960, v 32..], one cell per glyph with a 2-texel
(1 px) border. Texel values: 0 empty, 1 outline, 2 faint ink (50 % see-through), 3 ink.
CLUT_O (960,224) draws 1-3 black (outline pass); CLUT_I (976,224) draws 2 white with STP
(semi-transparent quad: averaged with the outline below) and 3 white.

Code + tables + sheet live in free RAM (HI, the start-up heap the game abandons, see
docs/text_system.md "Main RAM map"); the boot stub copies them there. The sprite buffer
follows (not copied).

    python tools/vwf2x.py info          sizes and addresses
    python tools/vwf2x.py sheet <png>   the font sheet as an image (local only: Skies art)
"""
import os
import struct
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from masm import assemble  # noqa: E402

HI = 0x801CB000
HI_END = 0x801F7000           # stay clear of the stack reserve (0x801F7FF0)
SHEET_X, SHEET_Y = 960, 32    # VRAM (halfwords, rows); page x = 960, y = 0
SHEET_MAX_H = 224 - SHEET_Y   # rows 32..223 are free in every screen checked
CLUT_X, CLUT_Y = 960, 224
MAXG = 900                    # sprites per page (two prims each)
SCREEN_DX, SCREEN_DY = 50, 15  # canvas -> screen (strip k: canvas u 55 + 20k at x 105 + 20k; v 0 at y 15)
OT = 0x800637E0
STRIPS = 0x800628CC
WIN = 0x80060FB0
ADDPRIM = 0x80035850
LOADIMAGE = 0x8003309C
TPAGE = (SHEET_X & 0x3FF) >> 6          # 4bpp, abr 0 (average), y 0
CLUT_O = (CLUT_Y << 6) | (CLUT_X >> 4)
CLUT_I = (CLUT_Y << 6) | ((CLUT_X + 16) >> 4)


def level(v):
    return 3 if v >= 128 else 2 if v else 0


def build_glyphs(glyph_chars):
    """-> (table bytes 128 x 8, advances bytes 128, sheet bytes, sheet height, report)"""
    import skiesfont
    skiesfont.enable()
    cells = {}
    adv = [0] * 128
    for code, ch in glyph_chars.items():
        img, xoff, top, a = skiesfont.cell(ch)
        adv[code] = a
        if img is None:
            continue
        w, h = img.size
        assert w % 2 == 0 and h % 2 == 0 and xoff % 2 == 0 and top % 2 == 0, (ch, w, h, xoff, top)
        cw, chh = w + 4, h + 4
        grid = [[0] * cw for _ in range(chh)]
        px = img.load()
        ink = [(x + 2, y + 2, level(px[x, y])) for y in range(h) for x in range(w) if px[x, y]]
        for x, y, _ in ink:                       # outline: 2 texels around any ink
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    grid[y + dy][x + dx] = max(grid[y + dy][x + dx], 1)
        for x, y, v in ink:
            grid[y][x] = v
        cells[code] = (grid, cw, chh, xoff // 2, top // 2)
    # shelf packing, tallest first; u + w <= 255 and v + h <= 255 (byte coordinates)
    order = sorted(cells, key=lambda c: (-cells[c][2], c))
    place, x, y, shelf = {}, 0, 0, 0
    for c in order:
        grid, cw, chh, _, _ = cells[c]
        if x + cw > 255:
            x, y, shelf = 0, y + shelf, 0
        place[c] = (x, y)
        x += cw
        shelf = max(shelf, chh)
    height = y + shelf
    height += height & 1
    assert height <= SHEET_MAX_H, 'font sheet too tall: %d' % height
    sheet = bytearray(128 * height)               # 256 texels / row, 2 per byte, low nibble left
    for c, (x0, y0) in place.items():
        grid, cw, chh, _, _ = cells[c]
        for yy in range(chh):
            for xx in range(cw):
                v = grid[yy][xx]
                if v:
                    o = (y0 + yy) * 128 + (x0 + xx) // 2
                    sheet[o] |= v << (4 * ((x0 + xx) & 1))
    table = bytearray(128 * 8)
    for c, (x0, y0) in place.items():
        _, cw, chh, dx, dy = cells[c]
        struct.pack_into('<BBBBbbBB', table, c * 8, x0, SHEET_Y + y0, cw, chh, dx, dy, adv[c], 1)
    for c in range(128):
        table[c * 8 + 6] = adv[c]
    return bytes(table), bytes(adv), bytes(sheet), height, {'glyphs': len(cells), 'sheet_rows': height}


def clut_bytes():
    black = 0x8000                                   # STP set: opaque black (0 = transparent)
    o = [0, black, black, black] + [0] * 12
    i = [0, 0, 0xFFFF, 0x7FFF] + [0] * 12            # 2: white + STP (semi), 3: white
    return struct.pack('<32H', *(o + i))


ASM = r'''
; ---- text2x_rec(a0 = code, a1 = canvas x0, a2 = canvas y0): two sprites for one letter ---
text2x_rec:
    sll   t1, a0, 3
    la    t0, g2_tab
    addu  t0, t0, t1
    lbu   t2, 2(t0)               ; cell w (texels)
    lbu   t3, 3(t0)               ; cell h
    beqz  t2, @ret
    nop
    la    t9, g2_state            ; +0 n, +4 head, +8 last outline, +12 last letter
    lw    t4, 0(t9)
    li    t5, MAXG
    sltu  t5, t4, t5
    beqz  t5, @ret
    nop
    sll   t5, t4, 6
    sll   t6, t4, 4
    addu  t5, t5, t6              ; n * 80
    li    t6, PRIMS
    addu  t5, t5, t6              ; outline prim; letter prim = +40
    lb    t7, 4(t0)               ; dx
    lb    t8, 5(t0)               ; dy
    addiu a1, a1, SCREEN_DX
    addu  a1, a1, t7              ; left
    addiu a2, a2, SCREEN_DY
    addu  a2, a2, t8              ; top
    srl   t7, t2, 1
    addu  t7, a1, t7              ; right
    srl   t8, t3, 1
    addu  t8, a2, t8              ; bottom
    lbu   v0, 0(t0)               ; u
    lbu   v1, 1(t0)               ; v
    addu  t2, v0, t2              ; u right
    addu  t3, v1, t3              ; v bottom
    move  t6, t5
    ori   a3, zero, 2             ; two prims
@fill:
    sh    a1, 8(t6)
    sh    a2, 10(t6)
    sb    v0, 12(t6)
    sb    v1, 13(t6)
    sh    t7, 16(t6)
    sh    a2, 18(t6)
    sb    t2, 20(t6)
    sb    v1, 21(t6)
    sh    a1, 24(t6)
    sh    t8, 26(t6)
    sb    v0, 28(t6)
    sb    t3, 29(t6)
    sh    t7, 32(t6)
    sh    t8, 34(t6)
    sb    t2, 36(t6)
    sb    t3, 37(t6)
    ori   t1, zero, TPAGE
    sh    t1, 22(t6)
    addiu a3, a3, -1
    bnez  a3, @fill
    addiu t6, t6, 40
    li    t1, 0x2D808080          ; outline: textured quad, raw texture, opaque
    sw    t1, 4(t5)
    ori   t1, zero, CLUT_O
    sh    t1, 14(t5)
    li    t1, 0x2F808080          ; letter: raw texture, semi-transparent
    sw    t1, 44(t5)
    ori   t1, zero, CLUT_I
    sh    t1, 54(t5)
    ; link: outlines first, then letters
    lui   a0, 0x0900
    lui   a3, 0x00FF
    ori   a3, a3, 0xFFFF
    addiu t6, t5, 40              ; letter prim
    bnez  t4, @more
    nop
    and   t1, t6, a3
    or    t1, t1, a0
    sw    t1, 0(t5)               ; outline -> its letter (first letter)
    li    t1, 0x09FFFFFF
    sw    t1, 0(t6)               ; end (set per frame)
    sw    t5, 4(t9)               ; head
    b     @linked
    nop
@more:
    lw    t1, 8(t9)               ; last outline
    nop
    lw    t2, 0(t1)
    nop
    sw    t2, 0(t5)               ; new outline -> first letter
    and   t2, t5, a3
    or    t2, t2, a0
    sw    t2, 0(t1)               ; last outline -> new outline
    lw    t1, 12(t9)              ; last letter
    nop
    lw    t2, 0(t1)
    nop
    sw    t2, 0(t6)               ; new letter -> what the last letter pointed to
    and   t2, t6, a3
    or    t2, t2, a0
    sw    t2, 0(t1)               ; last letter -> new letter
@linked:
    sw    t5, 8(t9)
    sw    t6, 12(t9)
    addiu t4, t4, 1
    sw    t4, 0(t9)
@ret:
    jr    ra
    nop

; ---- text2x_strips(a0 = first OT slot index) -> v0 = next slot (replaces the strip loop) --
text2x_strips:
    addiu sp, sp, -0x20
    sw    ra, 0x1C(sp)
    sw    s0, 0x10(sp)
    sw    s1, 0x14(sp)
    move  s0, a0
    move  s1, zero
@lp:
    li    a0, OT
    sll   t0, s0, 2
    addu  a0, a0, t0
    sll   t1, s1, 2
    addu  t1, t1, s1
    sll   t1, t1, 3
    li    a1, STRIPS
    jal   ADDPRIM
    addu  a1, a1, t1
    addiu s1, s1, 1
    slti  t0, s1, 10
    bnez  t0, @lp
    addiu s0, s0, 1
    la    t9, g2_state
    lw    t1, 0(t9)
    nop
    beqz  t1, @done
    nop
    li    t2, OT
    addiu t3, s0, -1
    sll   t3, t3, 2
    addu  t2, t2, t3              ; the last strip's slot
    lui   t6, 0x00FF
    ori   t6, t6, 0xFFFF
    lw    t4, 0(t2)
    lw    t5, 12(t9)              ; last letter
    and   t7, t4, t6
    lui   t8, 0x0900
    or    t7, t7, t8
    sw    t7, 0(t5)               ; last letter -> rest of the slot
    lw    t7, 4(t9)               ; head
    lui   t8, 0xFF00
    and   t4, t4, t8
    and   t7, t7, t6
    or    t4, t4, t7
    sw    t4, 0(t2)               ; slot -> head
@done:
    move  v0, s0
    lw    ra, 0x1C(sp)
    lw    s0, 0x10(sp)
    lw    s1, 0x14(sp)
    jr    ra
    addiu sp, sp, 0x20

; ---- clear2x (from 0x80013CE8, a0 = window): dialogue window -> empty chain, upload sheet --
clear2x:
    li    t0, WIN
    bne   a0, t0, @orig
    nop
    la    t1, g2_state
    sw    zero, 0(t1)
    addiu sp, sp, -0x18
    sw    ra, 0x14(sp)
    sw    a0, 0x10(sp)
    la    a0, sheet_rect
    la    a1, sheet_data
    jal   LOADIMAGE
    nop
    la    a0, clut_rect
    la    a1, clut_data
    jal   LOADIMAGE
    nop
    lw    ra, 0x14(sp)
    lw    a0, 0x10(sp)
    addiu sp, sp, 0x18
@orig:
    lw    t0, 0(a0)               ; the two replaced instructions
    addi  t1, zero, 0x2000
    j     0x80013CF0
    nop

    .align 4
g2_state:
    .word 0
    .word 0
    .word 0
    .word 0
sheet_rect:
    .half SHEET_X
    .half SHEET_Y
    .half 64
    .half SHEET_H
clut_rect:
    .half CLUT_X
    .half CLUT_Y
    .half 32
    .half 1
clut_data:
    .incbin clut
font2_w:
    .incbin adv
g2_tab:
    .incbin table
    .align 4
sheet_data:
    .incbin sheet
hi_end:
'''


def build(glyph_chars):
    """-> (blob to copy to HI, symbols, report)"""
    table, adv, sheet, height, rep = build_glyphs(glyph_chars)
    syms = {'MAXG': MAXG, 'SCREEN_DX': SCREEN_DX, 'SCREEN_DY': SCREEN_DY, 'TPAGE': TPAGE,
            'CLUT_O': CLUT_O, 'CLUT_I': CLUT_I, 'OT': OT, 'STRIPS': STRIPS, 'WIN': WIN,
            'ADDPRIM': ADDPRIM, 'LOADIMAGE': LOADIMAGE, 'SHEET_X': SHEET_X, 'SHEET_Y': SHEET_Y,
            'SHEET_H': height, 'CLUT_X': CLUT_X, 'CLUT_Y': CLUT_Y, 'PRIMS': 0}
    blobs = {'clut': clut_bytes(), 'adv': adv, 'table': table, 'sheet': sheet}
    code, s = assemble(ASM, HI, symbols=syms, blobs=blobs)
    prims = (HI + len(code) + 15) & ~15
    syms['PRIMS'] = prims
    code, s = assemble(ASM, HI, symbols=syms, blobs=blobs)
    end = prims + MAXG * 80
    assert end <= HI_END, 'HI area overflow: %08X' % end
    code += bytes(-len(code) % 4)
    rep.update({'blob': len(code), 'prims': prims, 'end': end})
    return code, s, rep, adv


def widths(glyph_chars):
    """Dialogue advances (px) per code, as the payload uses them."""
    import skiesfont
    skiesfont.enable()
    w = [0] * 128
    for code, ch in glyph_chars.items():
        w[code] = skiesfont.cell(ch)[3]
    return w


def sheet_png(path, glyph_chars):
    _, _, sheet, height, _ = build_glyphs(glyph_chars)
    im = Image.new('RGB', (256, height))
    pal = [(40, 30, 30), (0, 0, 0), (150, 150, 150), (255, 255, 255)]
    im.putdata([pal[(sheet[y * 128 + x // 2] >> (4 * (x & 1))) & 15] for y in range(height) for x in range(256)])
    im.resize((1024, height * 4), Image.NEAREST).save(path)


if __name__ == '__main__':
    import vwf
    if sys.argv[1] == 'info':
        code, s, rep, _ = build(vwf.glyph_chars())
        print('HI %08X: blob %d bytes, sprites at %08X..%08X (%d KB used of %d KB)' % (
            HI, rep['blob'], rep['prims'], rep['end'], (rep['end'] - HI) // 1024, (HI_END - HI) // 1024))
        print('glyphs %d, font sheet 256 x %d texels at VRAM (%d,%d)' % (rep['glyphs'], rep['sheet_rows'], SHEET_X, SHEET_Y))
        for k in ('text2x_rec', 'text2x_strips', 'clear2x', 'font2_w', 'g2_tab', 'sheet_data'):
            print('  %-14s %08X' % (k, s[k]))
    elif sys.argv[1] == 'sheet':
        sheet_png(sys.argv[2], vwf.glyph_chars())
