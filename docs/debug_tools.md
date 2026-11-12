# Debug tools (SLPS-00404)

General method: `debug_tools_guide.md`. This file lists this game's tools and addresses.

| tool | use |
|---|---|
| `tools/emu.ps1 start <cue> [-StateFile s]`, `stop`, `post "F1:200"` | portable DuckStation in `work/emulator/duckstation` (muted, interpreter CPU, GDB port 2351) |
| `tools/gdbdbg.py run "press circle; wait 60; shot x.png; vram v.png"` | virtual pad + VRAM grabs over GDB (works unfocused) |
| `tools/gdbdbg.py run "mash circle 80029164 8"` | press a button every N frames until the CPU reaches an address (halts there). **Only after the save prompts are passed** (check with a shot): mashing through name entry fills the name, finishes, picks Notes 1 and confirms the overwrite (happened once on 2026-11-11; the card was restored from the copy inside the Nov 10 savestates, the overwritten card is memcards/overwritten_2026-11-11.mcd.bak) |
| `tools/moviegrab.py <prefix> 700,900` | VRAM grabs during movies (no pad reads there): counts LoadImage calls |
| `tools/gdbmem.py read/dumpram/regs` | memory access (`GK_GDB_PORT`, default 2351) |
| `tools/gdbreset.py [--pc]` | clear known breakpoints, resume |
| `tools/ramcanary.py fill/check <start> <end> [label]` | canary test for unused RAM (pattern per address; reports in work/emulator/test/ram_canary/). Back up the memory card first: mashing Circle at a story's end confirms the save prompt |
| `tools/dsstate.py ram/vram <state>` | read savestates offline (py -3.11) |
| `tools/hotreload.py work/emulator/test/kowai_test.bin` | write payload, EXE patches, DIRENTRY records and the loaded script into a running game |
| `tools/mips.py <exe> dis/func/xref` | disassembly |
| `tools/sdata.py check / dump SDATAxx` | script parser / listing |

Always test on `work/emulator/test/kowai_test.cue` (the build copies every image there):
DuckStation reopens the disc a savestate names, so a state made on another image reads the
wrong disc (this caused a crash: the script was loaded from the Japanese DUMMY.BIN).

## Addresses

| what | address |
|---|---|
| pad read end (`nor v0`), frame clock | 0x8003B554 (v0 = ~[0x80184470], no port argument) |
| StoreImage / LoadImage / DrawSync | 0x80033100 / 0x8003309C / 0x80032E74 |
| display buffers | VRAM (384,256) and (704,256), 320x240 |
| text canvas | RAM 0x801914F4 (256x256 4bpp) -> VRAM (0,256) |
| grab stub / scratch | 0x8000B900 / 0x80092000-0x80093D00 (tail of the script buffer; build keeps scripts below 0x80092000) |
| VWF payload | 0x8000C000-0x8000DFFF (must not be used as scratch) |
| script buffer, pc | 0x80063D20, gp+0x3CC |
| text read pointer | gp+0x268 |
| DIRENTRY in RAM | pointer at 0x8015B834 |
| exceptions | BIOS A(40h) loop: catch with a breakpoint at 0x80000080, skip cause 0 (IRQ) and 8 (syscall) |

## Reaching the menus on the test image

The emulator's memory card holds a save, so the title cursor starts on "Continue"; the
order is New Game, Continue, Delete Notes, Copy Notes. **Do not confirm anything on the
Delete / Copy screens or a save prompt** (the save is the only one).

Name entry takes three Starts with the defaults (close the intro, surname -> given name,
finish); check each step with a shot.

Story-teller select from a fresh boot (about 4 minutes, no save written):

    wait 300; press start; wait 90; press up; wait 20; press circle; wait 150;
    press start; wait 90; press start; wait 120;      (name entry: default name)
    press cross; wait 120; press circle; wait 60;     (save prompt: cancel, "continue without saving": yes)
    mash circle 80029164 8; wait 90; shot x.png       (prologue until the teller screen draws)

## Savestates (`work/emulator/states/`)

| state | image | place |
|---|---|---|
| v000_name_entry | Japanese original | name entry |
| v000_select_teller | Japanese original | story-teller select |
| v002_sce29_first_page | test image | Iwashita's story, first page (SCE29) |
| v004_sce29_choice | test image | first choice of SCE29 (choice built with old code) |

Reach the SCE29 choice from v002: 22 x (circle, wait 45).

## Hot reload limits

The strips (built once at boot) and window pitch are not rebuilt; hotreload writes the
pitch byte directly, the strips need a fresh boot. The page already on screen keeps its text.
