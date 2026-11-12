# Menus and UI: survey and plan

Survey of the 0.4.0 build (DuckStation, muted). Screenshots: work/ui/shots/ui_*.png.
String inventory: work/ui/exe_strings.json (121 EXE strings with offsets, byte length and
the room available in place).

## What is still Japanese

| screen | where the text lives | notes |
|---|---|---|
| Title menu (New game / Continue / Delete notes / Copy notes) | EXE strings, UI routine 0x80016240 | horizontal, 14 px fixed pitch, boxed; box width follows the text |
| Memory card messages (~55 lines: checking, format, save/load errors, "insert card") | EXE strings | two-line messages built from pairs of strings |
| Save/load screen (slots "取材メモ １-４", name + gender panel) | EXE strings | 取材メモ = the "interview notes" save files |
| Name entry | EXE kana grid + `SCE00/JISYO.DAT` (kana -> kanji dictionary) | vertical kana grid, kanji candidate list, labels 名字/名前, 選択/決定 |
| Gender question (あなたの性別は？ 男/女) | EXE strings | |
| Story-teller select (誰の話を聞く？, six names, 一話目..六話目) | EXE strings + plate graphics | |
| Default names 坂上 修一 / 倉田 恵美 | EXE (two copies) | also shown inside the English story text through {a} {b} |
| Clock line in the seventh story (the "time left" line) | EXE string with digits patched at run time | |
| Graphics with Japanese (title logo, story-select plates), STR movies | TIM files in the GRPs, MOVIES.GRP | not surveyed yet |

## Plan

1. **UI text renderer.** Done in 0.5.0 for the horizontal screens: the message box / menu
   routine 0x8002F048 (title, memory card, save/load) and the story-teller select
   0x80029164 draw ASCII with the VWF font (proportional) and Shift-JIS as before; sprite,
   box and highlight widths come from the pixel width. 0x80016240 turned out to be unused
   (no callers); see docs/text_system.md "Menu text" for the routine map. The vertical
   screens (name entry 0x8002ADC4/0x8002B044/0x8002B204, gender 0x8002D7AC) move to step 3,
   since they need a horizontal layout.
2. **UI strings.** Done in 0.6.0. `work/translation/en/ui.json`, built by `tools/uitext.py`
   (references from `tools/uiscan.py` -> work/ui/exe_scan.json: pointer words, lui/lo pairs,
   gp-relative). A string that fits its slot is written in place; a longer one is moved into
   the slots of strings no longer used and every reference is repointed; what does not fit
   goes after the VWF payload (160 bytes now). The memory card messages are translated per
   entry of their line table (0x8004BAAC, ids `line00`..`line50`), so lines the Japanese
   shares between messages can read differently. Run-time digits (slot numbers, the clock)
   are `#` in the English; the build moves the game's byte offsets to them and writes ASCII
   digits. Save panel: given name first, "Gender: Male/Female" (hook), "Story N: name"
   lines in bigger slots. Real hardware: the moved strings stay inside the EXE's own data
   except the 160 bytes in the kernel RAM area the payload already uses.
3. **Default names, name entry, gender question.** Done in 0.8.0. Default names
   Sakagami / Shuichi / Kurata / Emi in ASCII (padded to even length with 7F, since names
   enter the story text 2 bytes at a time). Name entry keeps its 5 x 10 grid but shows
   A-Z, `- ' .`, "<-" (delete) and "OK" (finish); a cell adds its letter directly (the
   kanji panel and JISYO.DAT are no longer used); up to 8 letters per name, capitals
   automatic (first letter, after - ' .); names and labels drawn across in the left half.
   Gender question drawn across ("Boy or girl?", "Select", "OK"), icons stacked.
   Map of the routine: docs/text_system.md "Name entry".
4. **Graphics.** Done in 0.9.0 for the screens and short movies (work/ui/gfx_survey.md):
   gender captions (DI2.TIM), title copyright lines and the "Afterwards" subtitle (MDEC
   stills re-encoded by tools/bs.py), the three short "end" movies (video frames
   re-encoded in their own sectors). Open: logo, credits, story props (survey table).
5. **Emulator pass** over every UI screen; screenshots + coordinates in work/ui.

Each step is a build (0.5.0, ...), with the changelog and an xdelta for the previous image.
