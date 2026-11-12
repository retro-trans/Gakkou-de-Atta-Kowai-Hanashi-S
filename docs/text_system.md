# Text system and English renderer (SLPS-00404)

Gakkou de Atta Kowai Hanashi S, PlayStation, Banpresto / Pandora Box 1996.
Single data track, MODE2/2352. EXE `SLPS_004.04` loads at 0x80010000, entry 0x800316FC.

## Disc and archives

- `DIRENTRY.DAT` ("CD-DIR" + u16 group count 0x49 = 73): 24-byte group entries
  (name[12], count, table offset, run-time LBA), then 20-byte file records
  (name[12], sector offset from the GRP start, sector count). Parsed by `tools/grp.py`.
- Groups: `GROUP0..7/SCExx.GRP` (one per scene, 71), `GROUP9/SYSTEM.GRP` (`FONT.DAT`,
  `ICON.TIM`), `GROUP9/MOVIES.GRP` (STR). `DUMMY.BIN` (36 MB) is filler the game never reads.
- Loader (EXE 0x800236B0 / 0x80023768): LBA = group LBA (CdSearchFile at boot) + record
  sector. No bounds check, so a record may point outside its GRP. The English build puts
  rebuilt scripts into `DUMMY.BIN` and repoints their records (`tools/build.py`).
- There is **no encyclopedia/library** in this game. `SCE00/JISYO.DAT` is the kana->kanji
  dictionary of the name-entry screen.

## Scene scripts (`SCExx/SDATAxx.BIN`)

Bytecode from offset 0, then a pool of NUL-terminated strings (4-byte aligned, junk between).
Interpreter: EXE 0x8001C860, buffer 0x80063D20 (192 KB, up to 0x80093D20), pc at gp+0x3CC;
handlers return the instruction length (stored in gp+0x3D0). Opcode lengths and operand kinds
are in `tools/sdata.py` (all 71 scripts parse; every jump lands on an instruction).

| op | meaning | string operand |
|---|---|---|
| 4A | text (narration/dialogue) | yes, 13,326 rows |
| 04 | choice entry (text, jump target, byte) | yes, 2,794 rows |
| 20/23/24/25 | sound files | file name |
| 42/60 | background (.BG) | file name |
| 55 | movie (.MV), 57 face (.kao), 5D animation | file name |
| 01/03/09/0A/10-13/16-18 | jumps (code targets) | - |
| FF xx | scene exit | - |

The build keeps the bytecode byte for byte and only rewrites the pool and the pool operands.

## Text codes (Shift-JIS)

Text is CR LF separated paragraphs. Control codes start with ￥ (81 8F):

| code | markup | meaning |
|---|---|---|
| ￥ｐ | `{p}` | wait, clear page |
| ￥ｇ | `{g}` | new line/column if the current one is not empty |
| ￥ｋ | `{k}` | wait for a key |
| ￥ｗ | `{w}` | pause (6 x FF04) |
| ￥ａ ￥ｂ | `{a}` `{b}` | player's surname / given name |
| ￥ｃ | `{c}` | surname (male player) or given name (female) |
| ￥ｆA￥B￥ | `{f:A|B}` | male / female text |
| CR LF | `\n` | wait for a key, new line |

Rows must keep the source's trailing `\n` / `{p}`: a row followed by a choice ends with `\n`.

## Original rendering

- Preprocessor EXE 0x80015294: one paragraph -> 16-bit codes in 0x80061058, column wrap
  after 13 characters (counter gp+0x2C0 in half-units, threshold 0x19), 10 columns per page
  (gp+0x2C4, `sltiu 9` x 9 sites), page buffer 0x80061858.
- Typewriter loop 0x80014FB0: glyph lookup 0x80013C8C (`FONT.DAT`, 13x13 1bpp), blit
  0x80013D0C into a 256x256 4bpp RAM canvas (0x801914F4), uploaded to VRAM (0,256).
  Window struct 0x80060FB0: canvas, x 2, y 2, w 204, h 216, cursor cx/cy, column pitch 20,
  spacing 2, colours 1 / 15. Columns run right to left.
- The window is shown as 10 POLY_FT4 strips (0x800628CC, built at 0x80018FF8): strip k =
  canvas u 55+20k..75+20k at screen x 15+30k.
- Choices (0x80014B20): "１・" prefix (table 0x80049D7C) + text, appended as new columns;
  highlight bar POLY_F4 0x800633BC, x from table 0x8004B72A; Left/Right select.

## English renderer (tools/vwf.py)

English text is stored as **ASCII byte pairs** in the 16-bit units the preprocessor already
handles (any unit < 0x8000; 0x7F pads a run to even length, bytes 0x01-0x1F hold extra
letters). Control codes stay Shift-JIS, so all game logic (gender, names, waits) is unchanged.

| site | change |
|---|---|
| 0x80015158 | pair codes -> `vwf_pair` (draws 2 letters horizontally, outline like the original) |
| 0x80015EC4 | pairs count as narrow (1 unit per line slot, so ~50 letters before the game's own wrap) |
| 0x800145E4 | line pitch 17 (was column pitch 20) |
| 9 x `sltiu 9` in 0x80015294 | 12 lines per page |
| 0x8001905C-0x80019074 | strips 20 px apart at screen x 105: one 200 px text area |
| 0x800160DC | wait icon after the pen (English) |
| 0x8001A56C | choice bar: from the choice's first line (0x80063B0D) over its lines (0x80063B0C) |
| 0x80014C14 + 0x80014CF0 | choices break only at a 7F 0A unit; the loop branch must return to the hook at 0x80014C14 (the original returns to 0x80014C18) |
| 0x8001A394/3DC | Up/Right = previous choice, Down/Left = next |
| 0x80049D7C | choice prefixes "1. " |

Payload (code + Kowai Pixel 1bpp font, hand drawn in tools/fonts/kowai-pixel/glyphs.txt; ~5 KB) at kernel RAM 0x8000C000, copied by a boot
stub appended to the EXE (new entry 0x80061000 -> FlushCache -> 0x800316FC).
**Real hardware note:** 0x8000C000-0x8000DFFF is unused kernel RAM here (zero in every state
checked); the EXE grows into BSS only before crt0 runs. Not yet verified on a console.

### 2x dialogue text (tools/vwf2x.py, since 0.10.0)

Dialogue letters are the Riot Stars font (Skies of Arcadia's Latin font, decoded from the
user's Skies disc by ../Riot Stars; alignment fixes and extra glyphs in tools/skiesfont.py)
drawn as half-size sprites: 2 texels per screen pixel, so upscaling emulators show the full
detail. Menus keep the 1x canvas font (Kowai Pixel). `VWF_2X=0` builds the old 1x dialogue.

| site / place | what |
|---|---|
| `vwf_char` (payload) | advance from `font2_w`, then `text2x_rec`: two POLY_FT4 per letter (outline pass opaque black, letter pass semi-transparent) appended to a prebuilt chain (outlines first, then letters); nothing is plotted into the canvas |
| 0x80017A3C | the window's strip loop -> `text2x_strips`: the 10 strips as before, then the chain linked into the last strip's OT slot (drawn only while the window shows: gp+0x33C == 1, gp+0x318 == 0) |
| 0x80013CE8 | window clear -> `clear2x`: for the dialogue window (0x80060FB0) the chain is emptied and the font sheet + CLUTs are uploaded (LoadImage), so they are back after movies / other screens |
| RAM 0x801CB000 | code, glyph table (u, v, w, h, dx, dy, advance), CLUTs, font sheet (copied by the boot stub); sprite buffer after it (900 letters x 80 bytes), all inside the free area (see "Main RAM map") |
| VRAM (960,32) 64x132 | font sheet, 4bpp: 0 empty, 1 outline, 2 faint ink, 3 ink; cells with a 2-texel border |
| VRAM (960,224) / (976,224) | CLUT outline pass (1-3 black, 0x8000) / letter pass (2 white + STP = 50 %, 3 white) |

Screen position: canvas x + 50, canvas y + 15 (the strips map canvas u 55+20k to x 105+20k
and v 0..239 to y 15..254). The baseline matches the old font (cell row 12), the pen starts
1 px in. Real PS1 / 1x: the GPU samples every other texel of a half-size sprite, so letters
look rougher there (accepted: see the font comparison in work/ui/font/compare_riotstars).

The builder (`tools/textenc.py`) wraps words at 198 px, inserts `{g}`, splits lines per
gender when the two variants wrap differently, reserves width for names (default names).
Choices wrap to at most 3 lines (unit 7F 0A).

Pages: the engine holds 12 lines; when a page fills it waits and continues on a new page
by itself, even mid-paragraph (seen in DuckStation). The builder assumes each row starts on
a fresh page and turns a paragraph's CR LF into `￥ｐ` when that paragraph would not fit
on the lines left (4 lines kept free at the end of a row ending in CR LF, for choices);
a paragraph longer than 12 lines gets `￥ｐ` every 12 lines. `￥ｐ` inside a paragraph is
used by the original script 1,103 times.

The build stores identical strings of a script once (the pool is read-only); this keeps
SDATA07 (the largest script) under the 189,152-byte limit.

## Menu text (EXE UI strings)

Menus do not use the dialogue window. Each screen has its own drawing loop that calls the
glyph lookup 0x80013C8C and blit 0x80013D0C per Shift-JIS character into the 256x256
canvas (0x801914F4) and then shows parts of it as sprites whose size comes from the
character count. 0x80016240 (the routine first suspected) has no callers.

| routine | screen | layout | English (tools/vwf.py) |
|---|---|---|---|
| 0x8002F048 | message box / menu: title menu, memory card messages, save/load lists | lines and items, 16 px pitch, canvas x 0 | `msg_line`, `msg_item`: proportional, sprite width in px; the box is sized from it |
| 0x80029164 | story-teller select: 一話目.., six names, prompt | horizontal, 16 px | `teller_num/name/title`; prompt x = min(148, 312 - width) (`prompt_x` at 0x80029800) |
| 0x8002ADC4, 0x8002B044, 0x8002B204 | name entry labels, kana grid, entered name | vertical (18 px) | not yet (step 3: needs a new layout) |
| 0x8002D7AC | gender question | vertical (16 px) | not yet (step 3) |
| 0x80015F4C | {a}{b}{c} names inside dialogue | dialogue window | not yet (step 3: ASCII default names) |

`ui_text` (payload) draws a menu string: bytes < 0x80 are letters (VWF, the dialogue font,
3 px higher than the Shift-JIS glyph top, `UI_DY`), anything else is a Shift-JIS character
drawn by the game's blit at the site's pitch, so a half-translated string still shows.

### UI strings (tools/uitext.py)

| what | where | English build |
|---|---|---|
| memory card messages | id table 0x8004BB9C (start, count) -> line table 0x8004BAAC (51 pointers) | each line entry gets its own string (`lineNN`) |
| slot digits in messages | code writes `slot + 0x50` at +9 / +0x1B: 0x80027FD8, 0x800281E0, 0x8002823C, 0x8002824C, 0x8002825C, 0x800285E0 | offsets moved to the `#` marks, value `slot + 0x31`; the copy message's destination digit goes into line 26 (lw at 0x80028244) |
| clock line (seventh story) | 0x8004B740, shown in the story window; digits written at 0x8001E1C0..0x8001E1F0 | dialogue encoding, `#:##`, offsets and ASCII digits patched |
| save panel name | 0x80027444 formats surname + "　" + given name | given name first (0x800278E4/EC), separator " " + 7F (0x80060C28) |
| save panel gender | template 0x80011C8C + 男/女 bytes at +6 | "Gender: " + `gender_fill` hook (0x80027904) writes Male/Female |
| save panel stories heard | templates 0x80011CA0.. (pointer table 0x80011D18), strcpy name at +8 | "Story N: " in 28-byte slots, name at +9 (0x800279E4) |
| storytellers | table 0x8004B820 (index 1-6) | full names (teller select, save panel) |
| teller bar | number sprite x 152, name x 216 | "1st".."6th", name at x 180 (0x800296C0, 0x80029734) |

Kept in Japanese on purpose: the memory card save title 0x8004B8B0 (the console's own
memory card screen shows it), 0x80060C20 (name formatter's dash table), 0x80060C2C (unused).

## Name entry (0x8002BBAC) and gender question (0x8002DD10)

Flow: 0x8001F518 gender question -> 0x8001F538 name entry (a0 = gender). Files from the
table at 0x8004B7D4: SCE00/JISYO.DAT (kanji lists, unused in English), HAIKEI1.BS,
DANJO.BS (boy/girl pictures with the Japanese captions 男子/女子, a graphics item),
DI2.TIM.

Original: names are 4 Shift-JIS characters, position s6 0-3 surname / 4-7 given name;
a grid cell opens the kanji list for that kana. Edit buffers 0x80012F14 / 0x80012F20
(12 bytes), final names 0x8015B558 / 0x8015B564 (12 bytes; the save record keeps 9).

English (tools/vwf.py, "name entry" hooks):

| site | change |
|---|---|
| 0x8002BA74 put_char -> `nm_put` | 1 byte per letter, s6 0-7 / 8-15, automatic capitals; first edit of a field clears the default |
| 0x8002C524 / C484 / C498 -> `nm_add` | letter under the grid cursor goes straight in (no kanji panel); blank cells buzz |
| 0x8002C4BC, C4D0, C654, C668 | "name full" check: position 15, given[7] |
| 0x8002C6A0 -> `nm_start` | Start: surname -> given name, given name -> finish (non-empty names only) |
| 0x8002C7D8 -> `nm_del` | backspace; on an untouched default it clears the field |
| 0x8002B044 -> `nm_fields` | both names across at canvas (2, 4) / (2, 24), sprite = text width |
| 0x8002B460 layout | labels x 28 y 44 / 100, fields x 36 y 60 / 116, cursor 8 px after the last letter (`nm_cursor`) |
| 0x8002AEA4 -> `grid_glyph` | grid cells: letter + 7F, or two letters ("OK", "<-"), centred |
| 0x8002AF28 -> `label_h` | title / Surname / Given name across (canvas rows 0x60, 0x74, 0x88) |
| 0x8002BC58 / BC6C `copy_no7f`, 0x8002D764 / D770 `nm_store_s/g` | 7F fillers dropped for editing, added back (even length) when the names are stored |
| grid strings 0x80012E74.. (`_grid`) | 10 strips x 5 cells; strip = 2x + lower block, x = 0 is the right column |
| 0x8002D808 -> `gender_text`, 0x8002DA20-DB0C | gender prompt and hints across, icons stacked at x 240 |

Test tool note: `gdbdbg.py press` holds a button for N pad reads; a screen that stops
reading the pad leaves the rest for the next screen (a press on "New Game" could pick
"male" or add a letter). Use `press circle 1` there, and wait ~25 frames between grid
moves/adds (the screen ignores input for a while after each).

## Graphics (tools/gfx.py, tools/bs.py)

- TIM: tools/tim.py. DI2.TIM = gender captions, 4bpp, palette 1-6 red, 7-12 blue, 15 black.
- MDEC stills: `.BS` (no size in the file; sizes from the macroblock count: portraits
  128x128, DANJO 128x256, TITLE/HAIKEI 320x192, BAN 320x240) and `.BG` backgrounds
  (4-byte prefix: u8 1, u8 height, u16 width, then BS). BS v3 as libavcodec mdec.c reads
  it; header word 0 = MDEC codes / 2 rounded up to 32 (the decode buffer size); every
  stream ends with ten 1-bits (end of frame; the movie player crashes without it).
  `bs.encode_fit` re-encodes with the finest qscale that keeps the file size and code count
  of the original.
- Movies (STR / MV): video sectors = 32-byte header (0x0160 0x8001, chunk, chunks, frame,
  frame bytes rounded to 4, w, h, copy of the BS header) + 2016 bytes. A replaced frame is
  re-encoded into the same number of sectors and written in place (XA audio untouched).
- Movie audio: XA ADPCM 4-bit mono 37.8 kHz, interleaved; tools/xa.py decodes it from the
  raw sectors (the GRP extracts lose Form 2 sectors). Movies play 150 sectors a second, so
  sector i of the file is at i / 150 s; that maps speech times to video frames.
- Subtitles (gfx.py movie_subs, since 0.10.1): Noto Sans 13 px drawn at 4x and box-filtered
  (antialiased), white with a 1.5 px dark outline and a soft shadow, no band; smooth edges
  need far fewer DCT coefficients than 1-bit pixel letters. bs.reencode_overlay re-encodes
  only the macroblocks the text touches, at full precision; the bytes come from the rest of
  the frame: first faint fine detail of the other macroblocks is dropped (|level| 1-2 at
  high zigzag positions, bs.OVERLAY_TRIMS), then the frame's qscale goes up a step (whole
  frame requantised; DC is independent of qscale), and only as a last resort the text gets a
  dead zone. Opening movie: all 1,410 frames keep full-precision text; 405 untouched
  elsewhere, ~26% one qscale step up. The encode takes ~12 min and is cached in work/cache/
  (keyed on the movie, cues, font and encoder code). Before 0.10.1: game font, rows 9-11
  re-encoded with AC coefficients cut (bs.reencode_rows), which blurred the letters.
- Build: files are written into their GRP in place when they fit (else DUMMY.BIN +
  DIRENTRY repoint); movie sectors in place. `GFX_TEST=1` adds unchanged re-encodes of
  DANJO.BS, 00A01.BG and PBROGO.MV to check the paths in the emulator.

## Main RAM map (canary-tested 2026-11-12)

| range | use |
|---|---|
| 0x80010000-0x80061000 | EXE (code + data) |
| 0x80060CB8-0x801CAEC0 | BSS, zeroed by the start-up code (0x800316FC) |
| 0x80063D20-0x80093D20 | scene script buffer |
| 0x80094178-0x80143178 | the game's heap: `InitHeap(0x80094178, 0xAF000)` at 0x8001FE9C (malloc 0x800313C4, free 0x800315F8). Scene graphics fill it upward; one story reached 0x801401C0 |
| 0x801891F0-0x8018B3C0, 0x8018D600-0x801914A0 | written during stories |
| 0x801914F4 | text canvas (256x256 4bpp) |
| **0x801CAEC4-0x801F7FF0** | **free (~180 KB)**: the start-up heap (`InitHeap` at 0x80031788), abandoned when the game re-inits its heap at 0x80094178; nothing allocates or writes there afterwards. Header word at 0x801CAEC4 |
| 0x801F7FF0-0x801FFFF0 | stack (32 KB reserved, [0x80060098]); deepest seen ~0x801FAC20 |

Free-RAM evidence (tools/ramcanary.py, a per-address pattern checked after play):
0x801CAEC8-0x801F9000 unchanged from the game's entry point through boot, the intro
movies, New Game, name entry, "continue without saving", the prologue and opening movie
to the teller select, and (filled at a later point) loading a save, a whole story to its
end and repeated memory card saves. Not covered: the end movies (BADEND.STR etc.), the
seventh story. Real hardware: ordinary main RAM inside the 2 MB, no boundary concern.
Use it from 0x801CB000 with room left below 0x801F7FF0.

## Not yet handled

- Graphics: see work/ui/gfx_survey.md (logo, credits, story props open).
- SDATA07 (176 KB) has only ~2.2 English letters per Japanese character of room.
