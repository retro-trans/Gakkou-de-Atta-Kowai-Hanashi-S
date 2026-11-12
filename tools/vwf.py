"""Variable-width Latin font and horizontal (left-to-right) renderer for SLPS-00404.

The original dialogue renderer draws 13x13 Shift-JIS glyphs top-to-bottom in columns
that run right-to-left (EXE 0x80013D0C, window struct 0x80060FB0). The English build
stores text as ASCII byte pairs in the 16-bit units the preprocessor already handles
(see docs/text_system.md); any unit below 0x8000 is a pair and goes to vwf_pair, which
draws both letters horizontally into the same 4bpp canvas with the game's outline style.

Coordinates in English mode (struct fields keep their storage, change meaning):
    +0x0C  cx  line offset in px (newline adds the column pitch +0x10 = 20) -> y
    +0x0E  cy  pen position in px from the left edge of the text area       -> x
    canvas x = CANVAS_LEFT + pen, canvas y = winy + cx

On screen the window is 10 textured strips (POLY_FT4 at 0x800628CC, built by the loop
at 0x80018FF8): strip k samples canvas u 55+20k..75+20k. The original spreads them
30 px apart (vertical columns with gaps); the hooks below place them 20 px apart, so
canvas u 55..255 shows as one 200 px area at screen x STRIP_X..STRIP_X+200.

Payload (code + font) lives in kernel RAM at PAYLOAD (free on real hardware: the BIOS
kernel ends below 0x8000B800 here; see docs/vwf.md). A boot stub appended to the EXE
copies it there, flushes the I-cache and jumps to the original entry point.

    python tools/vwf.py preview work/ui/font/vwf_font.png
    python tools/vwf.py info
"""
import json
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from masm import assemble  # noqa: E402
import uitext  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, 'tools', 'fonts', 'noto-sans', 'NotoSans-Regular.ttf')   # build_font_noto only
SIZE = 12            # px em
THRESH = 100         # coverage threshold for the 1bpp glyph
CELL_H = 16          # glyph rows
TOP = 0              # y offset of the TrueType origin inside the cell
SPACING = 1          # px added to every advance (the outline needs room)

CANVAS_LEFT = 56     # canvas x of the first pixel of a line (strip 0 starts at u 55)
TEXT_W = 255 - CANVAS_LEFT   # 199 px: canvas u up to 254 (outline needs 255)
STRIP_X = 105        # screen x of the text area (right edge 305, as in the original)
LINE_H = 17          # line pitch (the window's column pitch, +0x10; was 20)
PAGE_LINES = 12      # lines per page (the preprocessor's column limit; was 10)
UI_DY = -3           # menus: letter cell row 0 sits 3 px above the Shift-JIS glyph top
# name entry layout (screen px): labels / fields in the left half (the kanji panel's place)
NF_TX = 0x70         # title "Enter your name." during the intro
NF_LX = 28
NF_LY1, NF_Y1 = 44, 60
NF_LY2, NF_Y2 = 100, 116
NF_X = 36

PAYLOAD = 0x8000C000
PAYLOAD_MAX = 0x8000E000 - PAYLOAD
ORIG_ENTRY = 0x800316FC
EXE_BASE = 0x80010000

# single-byte codes for letters outside ASCII (bytes 0x01-0x1F, never 0x0A / 0x0D)
EXTRA = {
    0x01: '…',   # ellipsis
    0x02: '—',   # em dash
    0x03: '‘', 0x04: '’', 0x05: '“', 0x06: '”',
    0x07: 'é', 0x08: '♪', 0x09: '–',
    0x0B: 'è', 0x0C: 'ï', 0x0E: 'ü', 0x0F: '·',
    0x10: '☆', 0x11: '★',   # white / black star (hand drawn)
}
CODE_OF = {v: k for k, v in EXTRA.items()}
FILLER = 0x7F         # pad byte: draws nothing, keeps units 2-byte aligned


def glyph_chars():
    out = {c: chr(c) for c in range(0x20, 0x7F)}
    out.update(EXTRA)
    return out


def build_font():
    """-> (widths[128], bitmaps bytes (128 x CELL_H x u16, bit15 = leftmost)).

    The game font is Kowai Pixel, hand drawn in tools/fonts/kowai-pixel/glyphs.txt
    (loader: tools/pixfont.py). build_font_noto is the old Noto Sans rasterisation,
    kept for comparison previews."""
    import pixfont
    return pixfont.build_font()


def build_font_noto():
    """Noto Sans 12 px thresholded to 1bpp (the font up to 0.6.0)."""
    f = ImageFont.truetype(TTF, SIZE)
    widths = [0] * 128
    bmp = bytearray(128 * CELL_H * 2)
    for code, ch in glyph_chars().items():
        adv = int(round(f.getlength(ch)))
        im = Image.new('L', (32, CELL_H + 8), 0)
        ImageDraw.Draw(im).text((0, TOP), ch, font=f, fill=255)
        px = im.load()
        cols = [x for x in range(32) for y in range(CELL_H) if px[x, y] >= THRESH]
        right = max(cols) + 1 if cols else 0
        if ch == ' ':
            adv = 3
        widths[code] = max(adv, right) + SPACING
        for y in range(CELL_H):
            row = 0
            for x in range(16):
                if px[x, y] >= THRESH:
                    row |= 0x8000 >> x
            struct.pack_into('<H', bmp, (code * CELL_H + y) * 2, row)
        assert widths[code] <= 16, (ch, widths[code])
    _overrides(widths, bmp)
    widths[FILLER] = 0
    return widths, bytes(bmp)


STAR = ['....#....', '....#....', '...###...', '#########', '.#######.', '..#####..',
        '..##.##..', '.##...##.', '##.....##']
STAR_W = ['....#....', '....#....', '...#.#...', '####.####', '.#.....#.', '..#...#..',
          '..#.#.#..', '.#.#.#.#.', '##.....##']
NOTE = ['.....##', '.....#.#', '.....#..#', '.....#..#', '.....#...', '.....#...',
        '.....#...', '..###....', '.####....', '..##.....']


def _overrides(widths, bmp):
    """Hand fixes: sans-serif 'I' (this Noto build has slab serifs at 12 px), music note."""
    rows = [struct.unpack_from('<H', bmp, (ord('I') * CELL_H + y) * 2)[0] for y in range(CELL_H)]
    lit = [y for y in range(CELL_H) if rows[y]]
    for y in range(CELL_H):
        struct.pack_into('<H', bmp, (ord('I') * CELL_H + y) * 2, 0x4000 if y in lit else 0)
    widths[ord('I')] = 3
    code = CODE_OF['♪']
    top = lit[0]
    for y in range(CELL_H):
        row = 0
        if 0 <= y - top < len(NOTE):
            for x, c in enumerate(NOTE[y - top]):
                if c == '#':
                    row |= 0x8000 >> x
        struct.pack_into('<H', bmp, (code * CELL_H + y) * 2, row)
    widths[code] = 10
    for ch, pic in (('☆', STAR_W), ('★', STAR)):
        code = CODE_OF[ch]
        for y in range(CELL_H):
            row = 0
            if 0 <= y - top < len(pic):
                for x, c in enumerate(pic[y - top]):
                    if c == '#':
                        row |= 0x8000 >> x
            struct.pack_into('<H', bmp, (code * CELL_H + y) * 2, row)
        widths[code] = 11


def width_of(text_bytes, widths=None):
    widths = widths or build_font()[0]
    return sum(widths[b] for b in text_bytes if b < 0x80)


ASM = r'''
; ---- entered from 0x80015158 (renderer, a0 = 16-bit char code) -------------------
vwf_hook:
    li    t0, 0x8000
    sltu  t1, a0, t0
    beqz  t1, @sjis
    nop
    jal   vwf_pair
    nop
    j     0x8001520C          ; advance the buffer index, continue the page loop
    nop
@sjis:
    lui   t0, %hi(en_mode)
    sb    zero, %lo(en_mode)(t0)
    lui   a1, 0x801A
    jal   0x80013C8C          ; original glyph lookup
    addiu a1, a1, -0x52B0
    j     0x80015168
    nop

; ---- 0x80015EC4 is_in_list(code, list): pairs count as narrow (one unit per column) --
narrow_hook:
    lui   t0, 0x8006
    addiu t0, t0, 0x0A5C
    bne   a1, t0, @orig
    nop
    li    t2, 0x8000
    sltu  t1, a0, t2
    beqz  t1, @orig
    nop
    jr    ra
    ori   v0, zero, 1
@orig:
    addiu sp, sp, -0x20
    j     0x80015ECC
    sw    ra, 0x18(sp)

; ---- draw the two letters of a pair code ------------------------------------------
vwf_pair:
    addiu sp, sp, -0x18
    sw    ra, 0x14(sp)
    sw    s0, 0x10(sp)
    lui   t0, %hi(en_mode)
    ori   t1, zero, 1
    sb    t1, %lo(en_mode)(t0)
    move  s0, a0
    jal   vwf_char
    srl   a0, s0, 8
    jal   vwf_char
    andi  a0, s0, 0xFF
    lw    ra, 0x14(sp)
    lw    s0, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x18

; ---- vwf_char(a0 = byte): dialogue letter at the window pen, pen += advance ------
vwf_char:
    sltiu t0, a0, 0x7F            ; 0x7F (filler), >= 0x80 and 0: nothing
    beqz  t0, @none
    nop
    beqz  a0, @none
    nop
    la    a3, WIN
    la    t1, CHAR_W              ; font_w (1x canvas) or font2_w (2x sprites)
    addu  t1, t1, a0
    lbu   t3, 0(t1)               ; advance
    lhu   t2, 0x0E(a3)            ; pen
    lhu   t6, 0x06(a3)            ; winy
    lhu   t7, 0x0C(a3)            ; cx = line offset
    addiu a1, t2, CANVAS_LEFT     ; x0
    addu  a2, t6, t7              ; y0
    addu  t2, t2, t3
    j     CHAR_DRAW               ; vwf_glyph or text2x_rec
    sh    t2, 0x0E(a3)            ; pen += advance
@none:
    jr    ra
    move  v0, zero

; ---- vwf_glyph(a0 = byte 1..0x7E, a1 = canvas x, a2 = canvas y, a3 = struct) -> v0 = advance
; draws with the struct's canvas (+0) and colours (+0x12 letter, +0x13 outline)
vwf_glyph:
    addiu sp, sp, -0x30
    sw    ra, 0x2C(sp)
    sw    s0, 0x0C(sp)
    sw    s1, 0x10(sp)
    sw    s2, 0x14(sp)
    sw    s3, 0x18(sp)
    sw    s4, 0x1C(sp)
    sw    s5, 0x20(sp)
    sw    s6, 0x24(sp)
    sw    s7, 0x28(sp)
    move  s7, a3
    move  s4, a1                  ; x0
    move  s5, a2                  ; y0
    la    t1, font_w
    addu  t1, t1, a0
    lbu   s6, 0(t1)               ; advance
    addu  t0, s4, s6
    sltiu t0, t0, 256
    beqz  t0, @done               ; past the right edge: advance only
    nop
    la    s0, font_bmp
    sll   t0, a0, 5               ; CELL_H(16) * 2 bytes
    addu  s0, s0, t0
    ori   s3, zero, 1             ; pass 1: outline, pass 0: letter
@pass:
    move  s1, zero                ; row
@row:
    sll   t0, s1, 1
    addu  t0, t0, s0
    lhu   s2, 0(t0)
    move  v1, zero                ; column
    beqz  s2, @nextrow
    nop
@col:
    andi  t0, s2, 0x8000
    beqz  t0, @nextcol
    nop
    addu  a1, s4, v1
    addu  a2, s5, s1
    bnez  s3, @outline
    nop
    lbu   a3, 0x12(s7)
    jal   plot
    move  t8, zero
    b     @nextcol
    nop
@outline:
    lbu   a3, 0x13(s7)
    ori   t8, zero, 1
    addiu a1, a1, -1
    jal   plot                    ; (x-1, y)
    addiu a2, a2, -1
    jal   plot                    ; (x-1, y-1)
    nop
    jal   plot                    ; (x, y-1)
    addiu a1, a1, 1
    jal   plot                    ; (x+1, y-1)
    addiu a1, a1, 1
    jal   plot                    ; (x+1, y)
    addiu a2, a2, 1
    jal   plot                    ; (x+1, y+1)
    addiu a2, a2, 1
    jal   plot                    ; (x, y+1)
    addiu a1, a1, -1
    jal   plot                    ; (x-1, y+1)
    addiu a1, a1, -1
    addiu a2, a2, -1
    jal   plot                    ; (x-1, y)
    nop
@nextcol:
    sll   s2, s2, 1
    andi  s2, s2, 0xFFFF
    bnez  s2, @col
    addiu v1, v1, 1
@nextrow:
    addiu s1, s1, 1
    sltiu t0, s1, 16
    bnez  t0, @row
    nop
    bnez  s3, @pass
    move  s3, zero
@done:
    move  v0, s6
    lw    ra, 0x2C(sp)
    lw    s0, 0x0C(sp)
    lw    s1, 0x10(sp)
    lw    s2, 0x14(sp)
    lw    s3, 0x18(sp)
    lw    s4, 0x1C(sp)
    lw    s5, 0x20(sp)
    lw    s6, 0x24(sp)
    lw    s7, 0x28(sp)
    jr    ra
    addiu sp, sp, 0x30

; ---- ui_text(a0 = string, a1 = canvas x, a2 = cy (row inside the struct), a3 = struct,
; t9 = Shift-JIS advance) -> v0 = width in px. Menu strings: bytes < 0x80 are letters
; (VWF, proportional), anything else is a Shift-JIS character drawn by the game's blit.
ui_text:
    addiu sp, sp, -0x28
    sw    ra, 0x24(sp)
    sw    s0, 0x10(sp)
    sw    s1, 0x14(sp)
    sw    s2, 0x18(sp)
    sw    s3, 0x1C(sp)
    sw    s4, 0x20(sp)
    sw    s5, 0x0C(sp)
    move  s0, a0
    move  s1, a1                  ; pen
    move  s2, a1                  ; start
    move  s3, a2
    move  s4, a3
    move  s5, t9
@loop:
    lbu   a0, 0(s0)
    nop
    beqz  a0, @end
    sltiu t0, a0, 0x80
    beqz  t0, @sjis
    nop
    sltiu t0, a0, 0x7F
    beqz  t0, @next1              ; 0x7F filler
    move  a1, s1
    lhu   a2, 0x06(s4)
    nop
    addu  a2, a2, s3
    addiu a2, a2, UI_DY
    jal   vwf_glyph
    move  a3, s4
    addu  s1, s1, v0
@next1:
    b     @loop
    addiu s0, s0, 1
@sjis:
    lbu   t1, 1(s0)
    sll   a0, a0, 8
    or    a0, a0, t1
    lui   a1, 0x801A
    jal   0x80013C8C              ; glyph lookup
    addiu a1, a1, -0x52B0
    beqz  v0, @skip
    nop
    lbu   t0, 0(v0)               ; glyph width
    lhu   t2, 0x04(s4)            ; window x
    ori   t1, zero, 0xFF          ; blit: left = 0xFF - (wx + cx + w)
    subu  t1, t1, s1
    subu  t1, t1, t0
    subu  t1, t1, t2
    sh    t1, 0x0C(s4)
    sh    s3, 0x0E(s4)
    move  a0, v0
    jal   0x80013D0C
    move  a1, s4
@skip:
    addu  s1, s1, s5
    b     @loop
    addiu s0, s0, 2
@end:
    subu  v0, s1, s2
    lw    ra, 0x24(sp)
    lw    s0, 0x10(sp)
    lw    s1, 0x14(sp)
    lw    s2, 0x18(sp)
    lw    s3, 0x1C(sp)
    lw    s4, 0x20(sp)
    lw    s5, 0x0C(sp)
    jr    ra
    addiu sp, sp, 0x28

; ---- message box / menu (0x8002F048: title menu, memory card and save screens) --------
; one line or item per string at canvas x 0, row s7; s3 = width in px (was the count)
msg_line:                         ; from 0x8002F1A8 (a0 = line * 4), back to 0x8002F238
    lw    t0, 0x18(sp)
    nop
    addu  t0, t0, a0
    lw    a0, 0(t0)
    ori   a1, zero, 1
    addiu a2, s7, 1
    move  a3, fp
    jal   ui_text
    ori   t9, zero, 16
    j     0x8002F238
    addiu s3, v0, 2
msg_item:                         ; from 0x8002F3D4, back to 0x8002F464
    lw    t0, 0x18(sp)
    nop
    addu  t0, t0, a0
    lw    a0, 0(t0)
    ori   a1, zero, 1
    addiu a2, s7, 1
    move  a3, fp
    jal   ui_text
    ori   t9, zero, 16
    j     0x8002F464
    addiu s3, v0, 2

; ---- plot(a1 = x, a2 = y, a3 = colour, t8 = 1: skip pixels that hold the letter colour,
; s7 = struct: canvas +0, letter colour +0x12); uses t0-t5 only
plot:
    sltiu t0, a1, 256
    beqz  t0, @ret
    sltiu t0, a2, 256
    beqz  t0, @ret
    nop
    lw    t1, 0(s7)               ; canvas
    sll   t2, a2, 7
    addu  t1, t1, t2
    srl   t2, a1, 1
    addu  t1, t1, t2
    lbu   t3, 0(t1)
    lbu   t0, 0x12(s7)            ; letter colour
    andi  t4, a1, 1
    beqz  t4, @lo
    nop
    srl   t5, t3, 4
    beqz  t8, @wh
    nop
    beq   t5, t0, @ret
    nop
@wh:
    andi  t3, t3, 0x0F
    sll   t5, a3, 4
    or    t3, t3, t5
    jr    ra
    sb    t3, 0(t1)
@lo:
    andi  t5, t3, 0x0F
    beqz  t8, @wl
    nop
    beq   t5, t0, @ret
    nop
@wl:
    andi  t3, t3, 0xF0
    or    t3, t3, a3
    jr    ra
    sb    t3, 0(t1)
@ret:
    jr    ra
    nop

; ---- 0x800160DC wait-icon rect (a0 = RECT out, VRAM units): after the pen ----------
icon_hook:
    lui   t0, %hi(en_mode)
    lbu   t0, %lo(en_mode)(t0)
    nop
    bnez  t0, @en
    nop
    move  a2, a0
    j     0x800160E4
    lui   a0, 0x8006
@en:
    la    t0, WIN
    lhu   t1, 0x0E(t0)            ; pen
    lhu   t2, 0x0C(t0)            ; line offset
    lhu   t3, 0x06(t0)            ; winy
    addu  t2, t2, t3
    sltiu t4, t1, TEXT_W - 16
    bnez  t4, @fits
    nop
    move  t1, zero                ; no room left on the line: start of the next one
    addiu t2, t2, LINE_H
@fits:
    addiu t1, t1, CANVAS_LEFT + 3
    srl   t1, t1, 2               ; 4bpp pixels -> 16-bit VRAM units
    addiu t2, t2, 0x100
    sh    t1, 0(a0)
    sh    t2, 2(a0)
    ori   t3, zero, 4
    sh    t3, 4(a0)
    ori   t3, zero, 0x10
    sh    t3, 6(a0)
    jr    ra
    move  v0, a0

; ---- 0x8001A56C choice highlight bar (POLY_F4 vertices at 0x800633C4): a line, not a column
bar_hook:
    lui   a2, 0x8006
    addiu a2, a2, 0x33C4
    lui   t2, %hi(en_mode)
    lbu   t2, %lo(en_mode)(t2)
    nop
    beqz  t2, @orig
    nop
    lui   a1, 0x8006
    lbu   v0, 0x3B0D(a1)          ; first line of the selected choice
    lbu   v1, 0x3B0C(a1)          ; its number of lines
    move  t3, v0                  ; (was first + lines - 1: one line low on wrapped choices)
    nop
    ori   t4, zero, LINE_H
    mult  t3, t4
    mflo  t3
    nop
    nop
    mult  v1, t4
    addiu t3, t3, BAR_TOP         ; strips start at y 15, text at canvas row 2
    mflo  t5
    nop
    nop
    addu  t5, t5, t3
    ori   t6, zero, STRIP_X
    ori   t7, zero, STRIP_X + 200
    sh    t6, 0(a2)
    sh    t3, 2(a2)
    sh    t7, 4(a2)
    sh    t3, 6(a2)
    sh    t6, 8(a2)
    sh    t5, 0x0A(a2)
    sh    t7, 0x0C(a2)
    j     0x8001A674
    sh    t5, 0x0E(a2)
@orig:
    j     0x8001A574
    nop

; ---- 0x80014C14 choice copy loop: unit 7F 0A = line break (game's own break path:
; FF03 + two full-width spaces, +1 line for the highlight bar); replaces 'every 13 units'
choice_brk:
    lui   t0, 0x8006
    lw    t0, 0x0F9C(t0)          ; choice text read pointer
    nop
    lbu   t1, 0(t0)
    lbu   t2, 1(t0)
    ori   t3, zero, 0x7F
    bne   t1, t3, @no
    ori   t3, zero, 0x0A
    bne   t2, t3, @no
    nop
    j     0x80014C4C
    ori   v1, zero, 0xFF03
@no:
    j     0x80014CA4
    nop

; ---- story-teller select (0x80029164): "first story".."sixth story" (fixed 48 px slots),
; the six names and the prompt; text from canvas x 3 (sprites start at u 2)
teller_num:                       ; from 0x8002923C (s6 -> string pointer), back to 0x80029298
    lw    a0, 0(s6)
    ori   a1, zero, 3
    move  a2, fp
    move  a3, s4
    jal   ui_text
    ori   t9, zero, 16
    j     0x80029298
    addiu s5, s5, 1
teller_name:                      ; from 0x800292F8 (a0 = index * 4, a1 = table), to 0x80029380
    addu  t0, a0, a1
    lw    a0, 0(t0)
    ori   a1, zero, 3
    move  a2, fp
    move  a3, s4
    jal   ui_text
    ori   t9, zero, 16
    addiu s5, s5, 1
    j     0x80029380
    addiu s0, v0, 2               ; sprite width in px (was the character count)
teller_title:                     ; from 0x800293F4 (a1 = index * 4, a0 = sp + 0x10), to 0x80029470
    addu  t0, a0, a1
    lw    a0, 0x18(t0)
    ori   a1, zero, 3
    move  a2, fp
    move  a3, s4
    jal   ui_text
    ori   t9, zero, 16
    addiu s5, s5, 1
    j     0x80029470
    addiu s0, v0, 2

prompt_x:                         ; from 0x80029800 (teller screen sprites): prompt screen x
    lw    t0, 0x9C(sp)            ; = min(148, 312 - width), so a long prompt stays on screen
    nop
    addu  t0, t0, a3
    lhu   t1, 4(t0)
    ori   a0, zero, 312
    subu  a0, a0, t1
    slti  t2, a0, 0x94
    bnez  t2, @ok
    nop
    ori   a0, zero, 0x94
@ok:
    jr    ra
    nop

; ---- save panel (0x8002759C): gender word after the "Gender: " template (was 男/女 at +6)
gender_fill:                      ; from 0x80027904, back to 0x8002796C
    lw    v1, 0x64(s4)            ; slot
    nop
    sll   v0, v1, 5
    subu  v0, v0, v1
    addu  v0, v0, s7              ; save record (31 bytes)
    lbu   v0, 2(v0)               ; 0 male, 1 female
    la    t0, str_male
    beqz  v0, @m
    nop
    la    t0, str_female
@m:
    addiu t1, sp, 0x30            ; panel line buffer sp+0x28 + len("Gender: ")
@cp:
    lbu   t2, 0(t0)
    addiu t0, t0, 1
    sb    t2, 0(t1)
    bnez  t2, @cp
    addiu t1, t1, 1
    j     0x8002796C
    nop
str_male:
    .ascii "Male"
    .byte 0
str_female:
    .ascii "Female"
    .byte 0
    .align 4

; ==== name entry (0x8002BBAC): Latin letters, up to 8 per name, 1 byte each ==============
; position s6: 0-7 surname, 8-15 given name (was 0-3 / 4-7 with 2-byte characters)

; ---- put_char (replaces 0x8002BA74): a0 = edit buffer table, a1 = pos, a2 = cell, a3 = flags
nm_put:
    sltiu t0, a1, 8
    move  t1, a1                  ; index in the field
    lw    t2, 0(a0)               ; surname buffer
    bnez  t0, @f
    move  t3, a3                  ; its "touched" flag
    addiu t1, a1, -8
    lw    t2, 4(a0)
    addiu t3, a3, 4
@f:
    lw    t4, 0(t3)
    nop
    bnez  t4, @touched
    ori   t4, zero, 1
    sw    t4, 0(t3)               ; first edit: the default name goes
    move  t5, zero
@clr:
    addu  t6, t2, t5
    sb    zero, 0(t6)
    addiu t5, t5, 1
    sltiu t6, t5, 10
    bnez  t6, @clr
    nop
@touched:
    lbu   t5, 0(a2)               ; letter of the cell
    sltiu t6, t5, 0x41            ; A-Z: capital after nothing / - ' . , small after a letter
    bnez  t6, @put
    sltiu t6, t5, 0x5B
    beqz  t6, @put
    nop
    beqz  t1, @put
    addu  t6, t2, t1
    lbu   t7, -1(t6)
    nop
    sltiu t7, t7, 0x41
    bnez  t7, @put
    nop
    ori   t5, t5, 0x20
@put:
    addu  t6, t2, t1
    sb    t5, 0(t6)
    sb    zero, 1(t6)
    sltiu t0, a1, 15
    beqz  t0, @ret
    nop
    addiu a1, a1, 1
@ret:
    jr    ra
    move  v0, a1

; ---- a grid cell was chosen (from 0x8002C524 / C484 / C498): the letter under the cursor
; goes straight into the name (no kanji panel); a blank cell buzzes
nm_add:
    lw    t0, 0x1188(sp)          ; cursor x (0 = right column)
    lw    t1, 0x1190(sp)          ; cursor y (0-9)
    sltiu t2, t1, 5
    xori  t2, t2, 1               ; lower block
    sll   t3, t0, 1
    addu  t3, t3, t2              ; strip = 2x + lower
    sll   t3, t3, 2
    addu  t3, t3, sp
    lw    t3, 0x28(t3)            ; strip string (5 cells x 2 bytes)
    beqz  t2, @a
    move  t4, t1
    addiu t4, t1, -5
@a:
    sll   t4, t4, 1
    addu  s0, t3, t4
    lbu   t5, 0(s0)
    ori   t6, zero, 0x20
    bne   t5, t6, @ok
    nop
    jal   0x80024AE4              ; buzzer
    ori   a0, zero, 3
    j     0x8002C694
    nop
@ok:
    jal   0x80024AE4              ; select sound
    move  a0, zero
    move  a2, s0
    addiu a0, sp, 0x1140
    j     0x8002C4B0              ; jal put_char (a3 in its delay slot), full check, redraw
    move  a1, s6

; ---- Start (from 0x8002C6A0): surname -> given name, given name -> finish
nm_start:
    sltiu t0, s6, 8
    bnez  t0, @sur
    nop
    lw    t1, 0x1144(sp)
    nop
    lbu   t1, 0(t1)
    nop
    beqz  t1, @empty
    nop
    j     0x8002D688              ; finish
    nop
@empty:
    jal   0x80024AE4
    ori   a0, zero, 3
    ori   fp, zero, 0x14
    j     0x8002C7A4
    nop
@sur:
    lw    t1, 0x1140(sp)
    nop
    lbu   t1, 0(t1)
    nop
    beqz  t1, @sempty
    nop
    jal   0x80024AE4
    ori   a0, zero, 4
    lw    v0, 0x114C(sp)          ; given name touched?
    ori   s6, zero, 8
    beqz  v0, @go
    nop
    lw    t1, 0x1144(sp)
    move  t2, zero
@cnt:
    addu  t3, t1, t2
    lbu   t3, 0(t3)
    nop
    beqz  t3, @done
    nop
    addiu t2, t2, 1
    sltiu t3, t2, 7
    bnez  t3, @cnt
    nop
@done:
    addiu s6, t2, 8
@go:
    j     0x8002C784
    nop
@sempty:
    jal   0x80024AE4
    ori   a0, zero, 3
    j     0x8002C784
    nop

; ---- delete (from 0x8002C7D8, grid mode): backspace; an untouched default name is cleared
nm_del:
    sltiu t0, s6, 8
    move  t1, s6
    lw    t2, 0x1140(sp)
    addiu t3, sp, 0x1148
    bnez  t0, @f
    nop
    addiu t1, s6, -8
    lw    t2, 0x1144(sp)
    addiu t3, sp, 0x114C
@f:
    lw    t4, 0(t3)
    nop
    bnez  t4, @touched
    ori   t4, zero, 1
    sw    t4, 0(t3)
    sb    zero, 0(t2)
    sltiu t0, s6, 8
    bnez  t0, @ok
    move  s6, zero
    b     @ok
    ori   s6, zero, 8
@touched:
    addu  t5, t2, t1
    lbu   t6, 0(t5)
    nop
    beqz  t6, @back
    nop
    b     @ok                     ; on a letter (full field): delete it in place
    sb    zero, 0(t5)
@back:
    beqz  t1, @first
    nop
    sb    zero, -1(t5)
    b     @ok
    addiu s6, s6, -1
@first:
    sltiu t0, s6, 8
    bnez  t0, @buzz               ; start of the surname: nothing to delete
    nop
    lw    t2, 0x1140(sp)          ; start of the given name: into the surname
    lw    t4, 0x1148(sp)
    nop
    bnez  t4, @len
    ori   t4, zero, 1
    sw    t4, 0x1148(sp)
    sb    zero, 0(t2)
    b     @ok
    move  s6, zero
@len:
    move  t1, zero
@l2:
    addu  t5, t2, t1
    lbu   t6, 0(t5)
    nop
    beqz  t6, @l3
    nop
    b     @l2
    addiu t1, t1, 1
@l3:
    beqz  t1, @buzz
    nop
    addiu s6, t1, -1
    addu  t5, t2, s6
    b     @ok
    sb    zero, 0(t5)
@buzz:
    jal   0x80024AE4
    ori   a0, zero, 3
    j     0x8002C984
    nop
@ok:
    jal   0x80024AE4
    ori   a0, zero, 1
    j     0x8002C984              ; fp = 0x14, s4 = 1, redraw + upload the fields
    nop

; ---- name fields (replaces 0x8002B044): a0 = canvas, a1 = 2 rects, a2 = edit buffer table
; both names drawn across, at canvas (2, 4) and (2, 24); rect = (0, 20f, width + 4, 18)
nm_fields:
    addiu sp, sp, -0x20
    sw    ra, 0x1C(sp)
    sw    s0, 0x10(sp)
    sw    s1, 0x14(sp)
    sw    s2, 0x18(sp)
    move  s0, a0
    move  s1, a1
    move  s2, a2
    sh    zero, 4(a0)
    jal   0x80013CE8              ; clear the canvas
    sh    zero, 6(a0)
    lw    a0, 0(s2)
    ori   a1, zero, 2
    ori   a2, zero, 4
    move  a3, s0
    jal   ui_text
    ori   t9, zero, 16
    addiu v0, v0, 4
    sh    zero, 0(s1)
    sh    zero, 2(s1)
    sh    v0, 4(s1)
    ori   v0, zero, 18
    sh    v0, 6(s1)
    lw    a0, 4(s2)
    ori   a1, zero, 2
    ori   a2, zero, 24
    move  a3, s0
    jal   ui_text
    ori   t9, zero, 16
    addiu v0, v0, 4
    sh    zero, 8(s1)
    ori   t0, zero, 20
    sh    t0, 10(s1)
    sh    v0, 12(s1)
    ori   v0, zero, 18
    sh    v0, 14(s1)
    ori   v0, zero, 1
    lw    ra, 0x1C(sp)
    lw    s0, 0x10(sp)
    lw    s1, 0x14(sp)
    lw    s2, 0x18(sp)
    jr    ra
    addiu sp, sp, 0x20

; ---- field cursor (from 0x8002B670 in the layout routine): s1 = x, a1 = y, t9 = 16
nm_cursor:
    lw    t0, 0x20(sp)            ; position
    lw    t1, 0x74(sp)            ; slide offset
    sltiu t2, t0, 8
    ori   a1, zero, NF_Y1 + 1
    lw    t3, 0x248(gp)           ; surname edit buffer
    bnez  t2, @f
    nop
    addiu t0, t0, -8
    ori   a1, zero, NF_Y2 + 1
    lw    t3, 0x24C(gp)
@f:
    addiu s1, t1, NF_X + 1
    la    t4, font_w
@l:
    beqz  t0, @done
    nop
    lbu   t5, 0(t3)
    nop
    beqz  t5, @done
    sltiu t6, t5, 0x80
    beqz  t6, @skip
    addu  t6, t4, t5
    lbu   t6, 0(t6)
    nop
    addu  s1, s1, t6
@skip:
    addiu t3, t3, 1
    b     @l
    addiu t0, t0, -1
@done:
    jr    ra
    ori   t9, zero, 16

; ---- grid cells (lookup call at 0x8002AEA4): ASCII cells drawn with the story font
; cell = 2 bytes: letter + 7F, or two letters ("OK", "<-"), centred in the 14 px cell
grid_glyph:
    li    t0, 0x8000
    sltu  t0, a0, t0
    bnez  t0, @asc
    nop
    j     0x80013C8C
    nop
@asc:
    addiu sp, sp, -0x20
    sw    ra, 0x1C(sp)
    sw    s0, 0x18(sp)
    sw    s1, 0x14(sp)
    sw    s2, 0x10(sp)
    andi  s0, a0, 0xFF            ; second byte (7F = none)
    srl   s2, a0, 8               ; first byte
    ori   t1, zero, 0x20
    beq   s2, t1, @blank
    nop
    la    t1, font_w
    addu  t2, t1, s2
    lbu   t2, 0(t2)
    ori   t3, zero, 0x7F
    beq   s0, t3, @one
    move  t7, zero
    addu  t7, t1, s0
    lbu   t7, 0(t7)
@one:
    addu  t2, t2, t7              ; total width
    lhu   t3, 0x0C(s3)            ; cx
    lhu   t4, 0x04(s3)            ; window x
    ori   t5, zero, 0xF2          ; left of a 13 px glyph: 0xFF - 13 - wx - cx
    subu  t5, t5, t3
    subu  t5, t5, t4
    ori   t6, zero, 14
    subu  t6, t6, t2
    sra   t6, t6, 1
    addu  s1, t5, t6
    move  a0, s2
    jal   gg_y
    move  a1, s1
    jal   vwf_glyph
    move  a3, s3
    addu  s1, s1, v0
    ori   t3, zero, 0x7F
    beq   s0, t3, @blank
    move  a0, s0
    jal   gg_y
    move  a1, s1
    jal   vwf_glyph
    move  a3, s3
@blank:
    la    v0, blank_glyph         ; the blit draws nothing, the cell still counts
    lw    ra, 0x1C(sp)
    lw    s0, 0x18(sp)
    lw    s1, 0x14(sp)
    lw    s2, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
gg_y:                             ; a2 = letter y of the cell (struct s3)
    lhu   t3, 0x0E(s3)
    lhu   t4, 0x06(s3)
    addu  a2, t3, t4
    jr    ra
    addiu a2, a2, UI_DY

; ---- labels (from 0x8002AF28 in 0x8002ADC4): title / Surname / Given name, across
label_h:
    sll   t0, s2, 2
    addu  t0, t0, sp
    lw    a0, 0x10(t0)
    sll   t1, s2, 4
    sll   t2, s2, 2
    addu  t1, t1, t2              ; 20 * label
    addiu a2, t1, 0x64
    ori   a1, zero, 2
    move  a3, s3
    jal   ui_text
    ori   t9, zero, 16
    sll   t1, s2, 4
    sll   t2, s2, 2
    addu  t1, t1, t2
    addiu t1, t1, 0x60
    sh    zero, 0(fp)
    sh    t1, 2(fp)
    addiu v0, v0, 4
    sh    v0, 4(fp)
    ori   v0, zero, 18
    sh    v0, 6(fp)
    j     0x8002AFFC
    addiu s7, s7, 1

; ---- name copies: into the edit buffers without 7F fillers (0x8002BC58 / BC6C, a0 = dest,
; a1 = src); back to the game's names padded to an even length (0x8002D764 / D770, a0 = src)
copy_no7f:
    lbu   t0, 0(a1)
    addiu a1, a1, 1
    ori   t1, zero, 0x7F
    beq   t0, t1, copy_no7f
    nop
    sb    t0, 0(a0)
    bnez  t0, copy_no7f
    addiu a0, a0, 1
    jr    ra
    nop
nm_store_s:
    lui   a1, 0x8016
    b     pad_copy
    addiu a1, a1, -0x4AA8         ; 0x8015B558
nm_store_g:
    lui   a1, 0x8016
    addiu a1, a1, -0x4A9C         ; 0x8015B564
pad_copy:                         ; a0 = src, a1 = dest
    move  t1, zero
@l:
    lbu   t0, 0(a0)
    addiu a0, a0, 1
    beqz  t0, @end
    nop
    sb    t0, 0(a1)
    addiu a1, a1, 1
    b     @l
    xori  t1, t1, 1
@end:
    beqz  t1, @z
    ori   t0, zero, 0x7F
    sb    t0, 0(a1)
    addiu a1, a1, 1
@z:
    jr    ra
    sb    zero, 0(a1)

blank_glyph:
    .byte 1, 1, 0, 0, 0, 0, 0, 0

; ---- gender question (0x8002D7AC): prompt + Select / OK hints drawn across (were columns)
gender_text:                      ; from 0x8002D808 (s4 = canvas, s3 = 3 rects, sp+0x10 = strings)
    move  s1, zero
@l:
    sll   t0, s1, 2
    addu  t0, t0, sp
    lw    a0, 0x10(t0)
    sll   t1, s1, 4
    sll   t2, s1, 2
    addu  s6, t1, t2              ; 20 * i
    ori   a1, zero, 2
    addiu a2, s6, 4
    move  a3, s4
    jal   ui_text
    ori   t9, zero, 16
    sh    zero, 0(s3)
    sh    s6, 2(s3)
    addiu v0, v0, 4
    sh    v0, 4(s3)
    ori   v0, zero, 18
    sh    v0, 6(s3)
    addiu s3, s3, 8
    addiu s5, s5, 1
    addiu s1, s1, 1
    slti  t0, s1, 3
    bnez  t0, @l
    nop
    j     0x8002D8F4              ; return the count
    nop

en_mode:
    .word 0

    .align 4
font_w:
    .incbin widths
    .align 4
font_bmp:
    .incbin bitmaps
payload_end:
'''

BOOT = r'''
boot:
    la    t0, payload_src
    la    t1, {payload:#x}
    li    t2, {words}
@cp:
    lw    t3, 0(t0)
    addiu t0, t0, 4
    sw    t3, 0(t1)
    addiu t2, t2, -1
    bnez  t2, @cp
    addiu t1, t1, 4
    la    t0, hi_src              ; 2x text code + font sheet (tools/vwf2x.py) -> free RAM
    la    t1, {hi:#x}
    li    t2, {hi_words}
    beqz  t2, @nohi
    nop
@cp2:
    lw    t3, 0(t0)
    addiu t0, t0, 4
    sw    t3, 0(t1)
    addiu t2, t2, -1
    bnez  t2, @cp2
    addiu t1, t1, 4
@nohi:
    ori   t1, zero, 0x44          ; FlushCache (BIOS A(44h))
    ori   t0, zero, 0xA0
    jalr  t0
    nop
    j     {entry:#x}
    nop
    .align 16
payload_src:
    .incbin payload
    .align 4
hi_src:
    .incbin hi
'''

# EXE patch sites: address -> instruction words (assembled with the payload symbols)
HOOKS = {
    0x80015158: 'j vwf_hook\nnop',
    0x80015EC4: 'j narrow_hook\nnop',
    # window strips: x = 20k + STRIP_X (was 30k + 15), right edge + 20 (was + 0x23)
    0x8001905C: 'sll v0, s3, 2\naddu v0, v0, s3\nsll v0, v0, 2\naddiu v1, v0, %d' % STRIP_X,
    0x80019074: 'addiu v0, v0, %d' % (STRIP_X + 20),
    0x800160DC: 'j icon_hook\nnop',
    # line pitch: the window's column pitch (+0x10), set when the window is created
    0x800145E4: 'ori t0, zero, %d' % LINE_H,
    # choices: highlight bar over a line; no forced column break every 13 units
    0x8001A56C: 'j bar_hook\nnop',
    0x80014C14: 'j choice_brk\nnop',     # line break only at a 7F 0A unit (not every 13)
    0x80014CF0: 'bnez v0, 0x80014C14',  # loop back through the hook (was 0x80014C18, past it)
    # message box / menu (title, memory card, save): proportional lines, width in px
    0x8002F1A8: 'j msg_line\nnop',
    0x8002F238: 'move v1, s3',       # was sll v1, s3, 4 (count * 16)
    0x8002F260: 'move v0, s3',
    0x8002F3D4: 'j msg_item\nnop',
    0x8002F464: 'move v1, s3',
    0x8002F48C: 'move v0, s3',
    # story-teller select: proportional names, sprite width in px
    0x8002923C: 'j teller_num\nnop',
    0x800292F8: 'j teller_name\nnop',
    0x80029380: 'move v0, s0',       # was sll v0, s0, 4
    0x800293F4: 'j teller_title\nnop',
    0x80029470: 'move v0, s0',
    0x80029800: 'jal prompt_x',      # was ori a0, zero, 0x94 (delay slot: ori a1, zero, 0x90)
    # teller bar: storyteller name at screen x 180 (was 216), after '1st'..'6th'
    0x800296C0: 'ori a0, zero, 0xb4',
    0x80029734: 'ori a0, zero, 0xb4',
    # save panel: Western name order (given name first), "Story N: " is 9 bytes, gender word
    0x800278E4: 'addiu a1, a2, 0xc',  # was 3 (surname first)
    0x800278EC: 'addiu a2, a2, 3',    # was 0xc
    0x800279E4: 'addiu a0, a0, 9',    # strcpy(template + 8 -> + 9, teller name)
    0x80027904: 'j gender_fill\nnop',
    # name entry (0x8002BBAC): Latin grid, 8 letters per name, no kanji panel, fields across
    0x8002BA74: 'j nm_put\nnop',
    0x8002C524: 'j nm_add\nnop',
    0x8002C484: 'j nm_add\nnop',
    0x8002C498: 'j nm_add\nnop',
    0x8002C4BC: 'ori v0, zero, 15',  # full check: last position (was 7)
    0x8002C4D0: 'lbu v0, 7(v0)',     # ... and last letter of the given name (was 6)
    0x8002C654: 'ori v0, zero, 15',
    0x8002C668: 'lbu v0, 7(v0)',
    0x8002C6A0: 'j nm_start',
    0x8002C7D8: 'j nm_del\nnop',
    0x8002B044: 'j nm_fields\nnop',
    0x8002AEA4: 'jal grid_glyph',
    0x8002AF28: 'j label_h',
    0x8002BC58: 'jal copy_no7f',
    0x8002BC6C: 'jal copy_no7f',
    0x8002D764: 'jal nm_store_s',
    0x8002D770: 'jal nm_store_g',
    # layout (0x8002B460): labels and fields in the left half, cursor after the last letter
    0x8002B584: 'addiu s1, t0, %d' % NF_LX,
    0x8002B59C: 'ori a1, zero, %d' % NF_LY1,
    0x8002B5D4: 'ori a1, zero, %d' % NF_LY2,
    0x8002B60C: 'addiu s1, t0, %d' % NF_X,
    0x8002B620: 'ori a1, zero, %d' % NF_Y1,
    0x8002B650: 'ori a1, zero, %d' % NF_Y2,
    0x8002B670: 'jal nm_cursor\nnop\nj 0x8002B694\nnop',
    0x8002B6D4: 'ori v0, zero, 8',   # cursor 8 x 16 (was 16 x 16)
    0x8002B6DC: 'sh t9, 0x68e(s3)',
    0x8002B6EC: 'addiu a0, s1, 8',
    0x8002B83C: 'addiu a0, s1, %d' % NF_TX,   # title during the intro (was x 0x100)
    # gender question (0x8002D924 layout): prompt across the top right, icons stacked with
    # their hints beside them (d-pad "Select" over circle "OK")
    0x8002D808: 'j gender_text\nnop',
    0x8002DA20: 'ori a0, zero, 236',  # prompt x (was 0x118, a column)
    0x8002DA48: 'ori a0, zero, 258',  # "Select" (was 0x108, 0x6F)
    0x8002DA4C: 'ori a1, zero, 93',
    0x8002DA68: 'ori a0, zero, 258',  # "OK" (was 0xF8, 0x6F)
    0x8002DA6C: 'ori a1, zero, 113',
    0x8002DAF4: 'ori v0, zero, 240',  # d-pad icon x (was 0x108), y stays 0x5F
    0x8002DB04: 'sh v0, 0x804(fp)',   # circle icon x = 240 (was 0xF8) ...
    0x8002DB08: 'ori v1, zero, 0x73', # ... under the d-pad
    0x8002DB0C: 'sh v1, 0x806(fp)',
    # choice selection: Up or Right = previous (was Right), Down or Left = next (was Left)
    0x8001A394: 'andi v0, v0, 0x3000',
    0x8001A3DC: 'andi v0, v0, 0xC000',
}
# 2x dialogue text (tools/vwf2x.py)
HOOKS_2X = {
    # window strips loop (10 x AddPrim) -> the same strips, then the letter sprites
    0x80017A3C: 'move a0, s3\njal text2x_strips\nnop\nj 0x80017A7C\nmove s3, v0',
    # window clear: the dialogue window also empties the sprite chain and uploads the font sheet
    0x80013CE8: 'j clear2x\nnop',
}
# choice number prefixes "１・" (5-byte entries at 0x80049D7C) -> "1. " as pair units
DATA = {0x80049D7C + 5 * i: bytes([0x31 + i, 0x2E, 0x20, FILLER, 0]) for i in range(9)}
# the preprocessor's 'column count < 9' checks (EXE 0x80015294): PAGE_LINES per page
for _a in (0x80015514, 0x8001554C, 0x800155F0, 0x800156C0, 0x800157B0, 0x80015898,
           0x800159CC, 0x80015B28, 0x80015DB0):
    HOOKS[_a] = 'sltiu v0, v0, %d' % (PAGE_LINES - 1)


# name entry grid: 10 strips of 5 cells (strip 2x + lower block, x = 0 is the right column);
# a cell is a letter + 7F filler or two letters, ' ' = blank
def _grid():
    rows = ['ABCDE', 'FGHIJ', 'KLMNO', 'PQRST', 'UVWXY', "Z-'. ", '     ', '     ', '     ', '     ']
    ICONS = {3: b'<-', 4: b'OK'}       # y = 9: delete (x 3), finish (x 4), were icon glyphs
    out = {}
    for x in range(5):
        for lower in (0, 1):
            k = 2 * x + lower
            b = b''
            for y in range(5 * lower, 5 * lower + 5):
                c = rows[y][4 - x]           # screen column 4 - x
                if y == 9 and x in (3, 4):
                    b += ICONS[x]
                else:
                    b += bytes([ord(c), FILLER])
            out[0x80012E74 + 12 * k] = b + b'\0'
    return out


DATA.update(_grid())


# 2x dialogue text (tools/vwf2x.py): Riot Stars / Skies font as half-size sprites.
# VWF_2X=0 builds the dialogue with the 1x canvas font (Kowai Pixel) as in 0.7.0-0.8.2.
TEXT_2X = os.environ.get('VWF_2X', '1') != '0'
_HI = []


def build_hi():
    """-> (blob for free RAM or b'', symbols)"""
    if not TEXT_2X:
        return b'', {}
    if not _HI:
        import vwf2x
        blob, syms, rep, _ = vwf2x.build(glyph_chars())
        _HI.append((blob, syms, rep))
    return _HI[0][0], _HI[0][1]


def dialogue_widths():
    """Pen advances of the dialogue font (what tools/textenc.py wraps with)."""
    if not TEXT_2X:
        return build_font()[0]
    import vwf2x
    w = vwf2x.widths(glyph_chars())
    w[FILLER] = 0
    return w


def build_payload():
    widths, bmp = build_font()
    hi, hsyms = build_hi()
    symbols = {'WIN': 0x80060FB0, 'CANVAS_LEFT': CANVAS_LEFT, 'TEXT_W': TEXT_W,
               'LINE_H': LINE_H, 'STRIP_X': STRIP_X,
               'BAR_TOP': 15 + 2 - 1, 'UI_DY': UI_DY,
               'NF_X': NF_X, 'NF_Y1': NF_Y1, 'NF_Y2': NF_Y2,
               'CHAR_W': hsyms.get('font2_w', 0), 'CHAR_DRAW': hsyms.get('text2x_rec', 0)}
    blobs = {'widths': bytes(widths), 'bitmaps': bmp}
    code, syms = assemble(ASM, PAYLOAD, symbols=symbols, blobs=blobs)
    if not TEXT_2X:                      # 1x: the payload's own table and plotter
        symbols.update(CHAR_W=syms['font_w'], CHAR_DRAW=syms['vwf_glyph'])
        code, syms = assemble(ASM, PAYLOAD, symbols=symbols, blobs=blobs)
    if len(code) > PAYLOAD_MAX:
        raise SystemExit('payload too big: %d > %d' % (len(code), PAYLOAD_MAX))
    syms = dict(syms)
    for k in ('text2x_strips', 'clear2x', 'text2x_rec', 'font2_w'):
        if k in hsyms:
            syms[k] = hsyms[k]
    return code, syms, widths


def patch_exe(exe):
    """Return the patched EXE bytes and a report dict."""
    exe = bytearray(exe)
    t_addr, t_size = struct.unpack_from('<II', exe, 0x18)
    assert t_addr == EXE_BASE and struct.unpack_from('<I', exe, 0x10)[0] == ORIG_ENTRY
    payload, syms, widths = build_payload()
    payload = payload + bytes(-len(payload) % 4)
    # UI strings (tools/uitext.py): in place / moved inside the EXE; the rest after the payload
    ui_extra, ui_rep, ui_placed = uitext.build(exe, PAYLOAD + len(payload), PAYLOAD_MAX - len(payload))
    payload = payload + ui_extra
    payload = payload + bytes(-len(payload) % 4)
    boot_base = t_addr + t_size
    hi, _ = build_hi()
    import vwf2x
    src = BOOT.format(payload=PAYLOAD, words=len(payload) // 4, entry=ORIG_ENTRY,
                      hi=vwf2x.HI, hi_words=len(hi) // 4)
    boot, bsyms = assemble(src, boot_base, blobs={'payload': payload, 'hi': hi})
    hooks = dict(HOOKS)
    if TEXT_2X:
        hooks.update(HOOKS_2X)
    boot += bytes(-len(boot) % 0x800)
    exe = exe[:0x800 + t_size] + boot
    struct.pack_into('<I', exe, 0x1C, t_size + len(boot))
    struct.pack_into('<I', exe, 0x10, bsyms['boot'])
    for addr, src in hooks.items():
        words, _ = assemble(src, addr, symbols=dict(syms))
        o = addr - t_addr + 0x800
        exe[o:o + len(words)] = words
    for addr, blob in DATA.items():
        o = addr - t_addr + 0x800
        exe[o:o + len(blob)] = blob
    ui = ui_placed
    return bytes(exe), {'payload_size': len(payload), 'payload': payload, 'boot': bsyms['boot'], 'ui': ui, 'ui_report': ui_rep,
                        'hi': hi, 'hi_addr': vwf2x.HI,
                        'symbols': {k: v for k, v in syms.items() if not k.startswith('_') and '__' not in k}}


def preview(out):
    widths, bmp = build_font()
    chars = glyph_chars()
    sample = ['The quick brown fox jumps over the lazy dog.',
              'SAKAGAMI SHUICHI, KURATA EMI, IWASHITA AKEMI',
              '"Who\'s there?" 0123456789 !?,.;:()[]-&%$#@',
              '… — ‘x’ “x” é ♪']
    W, H = 400, 20 * len(sample) + 8
    im = Image.new('RGB', (W, H), (70, 50, 50))
    px = im.load()
    for li, line in enumerate(sample):
        x0, y0 = 4, 4 + li * 20
        on = set()
        for ch in line:
            code = ord(ch) if ord(ch) < 0x80 else CODE_OF[ch]
            for y in range(CELL_H):
                row = struct.unpack_from('<H', bmp, (code * CELL_H + y) * 2)[0]
                for x in range(16):
                    if row & (0x8000 >> x):
                        on.add((x0 + x, y0 + y))
            x0 += widths[code]
        for (x, y) in on:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if (x + dx, y + dy) not in on and 0 <= x + dx < W and 0 <= y + dy < H:
                        px[x + dx, y + dy] = (0, 0, 0)
        for (x, y) in on:
            if x < W and y < H:
                px[x, y] = (255, 255, 255)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.resize((W * 3, H * 3), Image.NEAREST).save(out)
    json.dump({'widths': widths, 'extra': {hex(k): v for k, v in EXTRA.items()}},
              open(os.path.splitext(out)[0] + '.json', 'w'), indent=1)


if __name__ == '__main__':
    if sys.argv[1] == 'preview':
        preview(sys.argv[2])
    elif sys.argv[1] == 'info':
        code, syms, widths = build_payload()
        print('payload %d bytes at %08X' % (len(code), PAYLOAD))
        for k in ('vwf_hook', 'narrow_hook', 'vwf_pair', 'vwf_char', 'plot', 'font_w', 'font_bmp', 'payload_end'):
            print('  %-12s %08X' % (k, syms[k]))
