# Changelog

## 0.8.1 - 2026-11-14 (fix build, not a release)

Image SHA-1: 23e90a74dc285b6c64a03feaf5d65723326233cb. v0.8.0 (the public release) is kept
as an xdelta3 patch (verified); the oldest patch (v0.6.0) was removed to stay at 10.

Fixed (both reported on v0.8.0, both in tools/uitext.py, the EXE string builder)
- Teller select: at the start only the three tellers on the right could be picked, and
  the cursor started on the fourth. The English prompt "Whose story will you hear?"
  (ui078, 0x80012DE8) is longer than the Japanese and was written in place over the zero
  bytes after it. Those bytes are the screen's "already told" table (0x80012DF8, six
  words copied to the stack at 0x8002A064), so tellers 1-3 counted as told and the cursor
  code (0x8002A6F0, 0x8002A864..0x8002A938) skipped them. A string's room now ends at the
  next address the code references, so the prompt moves elsewhere; freed slots get the
  same limit (the moved prompt's old slot had been reused for other strings over the
  same table). Affected every build since the UI strings went in (0.6.0).
- Save / load panel: the sixth story's line read "There areNozomu Kazama" instead of
  "Story 6: Nozomu Kazama". The builder reused the slot of ui028 "There are no notes."
  for the moved "Story 6: " template (the same text as line31, which moves away, so the
  slot looked free), then wrote ui028 back into it in place. Slots written in place are
  no longer offered as free space, and the build now stops if two UI strings share bytes.

Checked in DuckStation (muted), on this exact image, from a fresh boot: New Game, default
name, save prompt cancelled ("continue without saving"), prologue to the teller select.
The cursor starts on the first teller (Iwashita) as in the Japanese original; right steps
through all six and wraps, left from the first wraps to the sixth. Read from RAM there:
the told table is all zero, and the six save-panel templates "Story 1: ".."Story 6: " each
have their own 28-byte slot (Story 6 at 0x80011228). The save panel with six stories heard
was not reached in play. Shots: work/emulator/shots/v081/. The memory card was not changed.

## 0.8.0 - 2026-11-12 (first public release)

First public release, published as v0.8.0 on GitHub (retro-trans/Gakkou-de-Atta-Kowai-
Hanashi-S). It contains everything up to 0.10.2 plus the in-story menu below. The public
numbering restarts at 0.8.0 as requested. The earlier local builds 0.8.0-0.8.3 are kept
as "v0.8.x-dev" patches in work/output/patches so their names do not clash; the next
build is 0.8.1. All the local builds listed below (0.8.x-dev, 0.9.0, 0.10.x) are older
than this release.

Image SHA-1: 28b810648fa2b542b75c2a84a55fd3fa83fb778b. The title menu shows "v0.8.0".
v0.10.2 is kept as an xdelta3 patch (verified); the v0.10.1 image and the oldest patch
(v0.5.0) were removed. The v0.10.2 image is still in work/output because it is open in
another program; delete it once it is closed.

Release files (work/release/v0.8.0, made with retro-trans-tools' release builder and
validator): the full patch from the Japanese image, BUILD-MANIFEST.json, VALIDATION.json,
SHA256SUMS / SHA1SUMS, README-v0.8.0.txt and CHANGELOG-v0.8.0.txt. The repository is
published without the Japanese script (only `*.en.json` copies) and without game pictures.

Checked in DuckStation (muted), on this exact image: boot and the intro movie, the title
menu with "v0.8.0 / github.com/retro-trans", Continue -> Notes 1 loaded (read-only), the
first page of the story in the 2x font, the in-story Start menu. Shots:
work/emulator/shots/v080/. The memory card was not changed.

Translated
- In-story Start menu: 取材メモを呼び出す / 話の続きを聞く -> "Open the notes" / "Continue
  the story" ("Hear the rest of the story" is 160 px and the menu image is 128 px wide).
  The text is not a string: it is a 128x48 4bpp image (TIM pixel block) inside the EXE at
  0x8004AB2C, uploaded to VRAM (832,128) when a story starts and drawn by the POLY_FT4 at
  0x80063584. tools/gfx.py story_menu_exe() redraws it in the menu font (Kowai Pixel 1x,
  1 px dark outline like the original) and build.py patches it in after the VWF hooks.
  The sprite's screen x moves 2 px left (two `ori` immediates in the start-up code,
  0x80016904 / 0x80016914) so the long line is centred in the highlight bar. Real
  hardware: data and immediates only, same size and VRAM area, no new code.

The menu was first checked in DuckStation (muted) on a private test build (scratchpad, version label 0.10.3,
nothing written to work/output): Notes 1 loaded read-only, Start opened the menu, both
highlight positions look right, "Continue the story" closes it. Shots:
work/ui/story_menu/. The memory card was not changed.

## After 0.10.2 (no new build)

- GitHub social preview (1280x640) in the retro-trans style: tools/social_preview.py ->
  work/release/social-preview.png. The art panel is made from the game's own stills (the
  six storytellers' portraits and the title logo, SCE00/*.BS) read from the extracted files.

## 0.10.2 - 2026-11-12 (font fix build, not a release)

Image SHA-1: 645d2ab44285e3169a60d5d16164e4ee9ca58437. v0.10.1 is kept as an xdelta3
patch (verified); the oldest patch (v0.4.0) was removed to stay at 10. The v0.10.1 image
is still in work/output because it is open in another program; delete it once it is closed.

Fixed
- Dialogue font: the bowls of g, p and q sat one screen pixel above the baseline (and p, q
  started one row above the x-height). The Skies font squeezes its descenders into two
  rows by ending those bowls early. Their bowls are now stretched by repeating straight
  middle rows so they run from the x-height to the baseline like o, and the descenders
  go one row deeper (tools/skiesfont.py, 'remap' fix). y and j were already right. Advance
  widths are unchanged, so no line wraps differently.

Checked in DuckStation (muted), on this exact image, from New Game through the opening
movie to the prologue page "Six? From what my upperclassman had told me..." at 4x (D3D11)
and 1x (Software): upperclassman / people / supposed sit on the baseline. Preview:
work/ui/font/descenders/before_after.png, shots work/emulator/shots/v0102/. The memory
card was not changed.

## 0.10.1 - 2026-11-12 (credit + subtitle build, not a release)

Image SHA-1: 29220fa6fcd75da1d1537fffd3cc6b45fd21bf3f. v0.10.0 is kept as an xdelta3
patch (verified); the oldest patch (v0.3.0) was removed to stay at 10. The v0.10.0 image
itself is still in work/output because it was open in another program; delete it once
it is closed.

Added
- Title menu credit: "v<version>" over "github.com/retro-trans" at the bottom right, in
  the menu font with a black outline (tools/gfx.py title_credit, drawn into HAIKEI1.BS;
  tools/build.py passes the build version). The same picture is behind name entry and
  the save / load screens, so the credit shows there too.

Changed
- Opening movie subtitles (MOVIES/SEXMOVIE.STR) redrawn in Noto Sans 13 px, antialiased,
  white with a dark outline and soft shadow (no band). The old game-font hardsubs were
  blurred by the encoder cutting coefficients to fit each frame's sectors. Now only the
  macroblocks under the text are re-encoded, at full precision. The bytes come from faint
  fine detail elsewhere in the frame, or one qscale step up (about 26% of frames). Every
  frame keeps the same sector count, so the XA audio and timing are untouched. Preview:
  work/ui/movie_subs/opening_subs_sheet.png. Details: docs/text_system.md (Graphics,
  Subtitles).

Checked in DuckStation (muted), on this exact image: boot, title menu with the credit
(work/ui/shots/ui_title_credit_en.png); from New Game through the whole opening movie:
all 18 subtitles show, timed to the narration, and the movie continues into the prologue
(work/emulator/shots/v0101/). The memory card was not changed.

## 0.10.0 - 2026-11-12 (2x font build, not a release)

Dialogue in the Riot Stars font at double resolution. Image SHA-1:
f4d901b753956fb823312890037ad318b4943336. v0.8.3 is kept as an xdelta3 patch (verified);
the oldest patch (v0.2.0) was removed to stay at 10. Numbered 0.10.0 because 0.8.x and
0.9.0 were both in use.

Changed
- Dialogue text uses the Riot Stars font (Skies of Arcadia's Latin font, as in
  ../Riot Stars and the Rayblade translation) at 2 texels per screen pixel: letters are
  half-size sprites, so emulators rendering above 1x show the full detail. Same outline,
  baseline, 198 px lines and 12 lines a page; about 25 % more text fits on a line than
  with Kowai Pixel, and every scene was re-wrapped to the new widths.
- Alignment fixes over the Riot Stars glyphs (tools/skiesfont.py, edits only): all digits
  and capitals on the same lines (the round digits' overshoot rows removed, A's apex, J,
  V, W), a, f, v, the dots of . ! ? : ; on the baseline, quotes on the cap line, % & # /.
  The ellipsis and curly quotes are built from Skies' own period and quote marks (Riot
  Stars takes them from another font), and ☆ ★ ♪ · – è é ï ü are new drawings in the same
  style (tools/fonts/skies-extra/glyphs2x.txt).
- Menus (title, memory card, save, name entry, teller select) keep the 1x Kowai Pixel font.

How (tools/vwf2x.py, docs/text_system.md "2x dialogue text")
- Each dialogue letter becomes two POLY_FT4 (outline pass, letter pass with 50 %
  see-through edge texels) in a chain that is built once per letter and linked into the
  window strips' OT slot each frame; a page clear empties it and uploads the font sheet
  (VRAM 960,32, 64x132) and CLUTs (960,224). Hooks: 0x80017A3C (strip loop), 0x80013CE8
  (window clear); vwf_char takes its advances from the new table.
- Code, tables and font sheet (18.9 KB) plus the sprite buffer (900 letters, 72 KB) live at
  0x801CB000, the start-up heap the game abandons (canary-tested free, docs/text_system.md
  "Main RAM map"); the boot stub copies them there. `VWF_2X=0` builds the old 1x dialogue.
- Tools: tools/ramcanary.py (free-RAM test), tools/fontcompare_riot.py (previews),
  tools/hotreload.py also writes the new block.

Checked in DuckStation (muted), on this exact image: boot and intro movies, Continue /
load, the first story played through to its save prompt (scene changes, animations,
★ in the text, full 12-line pages, typewriter), the font sheet and CLUTs in VRAM unchanged
over 500 page turns; at 4x (D3D11) the letters show full detail; the first choice of
scene 29 (hot reload): highlight bar behind the text. The memory card was restored after
the run's end-of-story save. Not seen: the seventh story's clock line, names typed by the
player inside dialogue, the end movies followed by text.

Known issues
- Real PS1 / 1x emulators: the GPU samples every other texel of a half-size sprite, so
  letters look rougher there than Kowai Pixel did (e.g. f can read like t). Accepted for
  the sharper upscaled look.
- The Skies glyph pixels are SEGA artwork; the build reads them from ../Riot Stars (its
  cache of the user's own Skies disc). Nothing of them is in this project's files, but they
  are inside the built image and its xdelta: keep that in mind before any release.
- Real hardware: no new risk at the RAM / VRAM boundaries (ordinary main RAM below the stack
  reserve; VRAM rows 32-223 of page x=960, free in every screen checked). Not tried on a
  console.

## 0.8.3 - 2026-11-12 (choice fix build, not a release)

Image SHA-1: 51a098d384b7b1e90384017a43a616666385739f. v0.8.2 is kept as an xdelta3
patch (verified); the oldest patch (v0.1.0) was removed to stay at 10.

Fixed
- Choices broke in the middle of words (e.g. "2. Leave her alone for no / w" in scene
  36). The game's copy loop jumps back to 0x80014C18, one instruction past the hook that
  removes its "new line every 13 characters" rule, so from the second unit on the old
  rule ran with a half-overwritten constant and inserted breaks at odd places. The loop
  branch (0x80014CF0) now goes back through the hook: choices break only where the
  encoder put a break, at a space. This affected every build since 0.1.0.
- The highlight bar of a choice that wraps started one line too low (it used first line
  + lines - 1). It now starts at the choice's first line.

Checked in DuckStation (muted), with the test choice of scene 29 temporarily made
longer (two and three lines, restored afterwards): words stay whole, continuation lines
are indented, the bar covers exactly the selected choice on both options. The build
reports no choice layout warnings.

## After 0.8.2 (no new build)

- Every movie checked for spoken lines: the opening (subtitled in 0.8.2) is the only one
  with speech. The two ending movies have music only; all other movies have no audio
  track. tools/xa.py now decodes stereo XA as well. Details: work/ui/gfx_survey.md.

## 0.8.2 - 2026-11-12 (opening subtitles build, not a release)

Image SHA-1: e46314069ec96a955062931ebe4b16798e0749b0. v0.8.1 is kept as an xdelta3 patch
(verified). work/output/patches now holds 10 patches (the limit).

Added
- English subtitles for the spoken opening movie (MOVIES/SEXMOVIE.STR, played after the
  name entry): 18 lines, from the club president's "Let's do a feature on our school's
  seven wonders..." to "...wanted to see something scary." Game font with an outline over
  a translucent dark band, timed to the narration.
- How: the movie's two XA audio channels (boy / girl narrator: same words, 僕 / 私) were
  decoded (tools/xa.py) and transcribed locally with the faster-whisper large-v3 model
  already on this machine. The lines are in work/translation/en/movie_subs.json (Japanese +
  English, times in seconds = sector / 150). One English track serves both narrators.
- Only the bottom three macroblock rows of each subtitled frame are re-encoded; the rest of
  the picture keeps its original coefficients bit for bit (tools/bs.py decode_levels /
  encode_blocks / reencode_rows). In busy frames the subtitle strip keeps fewer
  coefficients to fit the frame's sectors.

Checked
- In DuckStation (muted), on this exact image: New Game -> the opening movie shows the
  subtitles (three points grabbed during playback). The save prompt was cancelled;
  nothing was written.
- Offline: all 1,410 frames inside a spoken line carry their subtitle, no others changed.
- Accuracy review of the 18 lines against both narrators' Japanese.

Known issues
- Not heard: the subtitle timing comes from the audio sector positions and the speech
  recognizer's timestamps; it was not checked by ear.
- The girl's narration is about 0.3 s earlier in places (subtitles follow the boy's).

## 0.8.1 - 2026-11-11 (story props build, not a release)

Numbered 0.8.1 at the user's request; it follows 0.9.0 and contains everything in it.
Image SHA-1: 154bd91187267d046a22d6b5d51b06a90fa0c16f. v0.9.0 is kept as an xdelta3
patch (verified).

Added
- Text photographed into 21 backgrounds (15 pictures, some used in several scenes) is
  now in English, worded as the script words it (table in work/ui/gfx_survey.md):
  - the name cards (Yosuke Akasaka, Toru Hatanaka);
  - the Newspaper Club door plate and the Class 1-E plate;
  - the tear-off calendar (MAY / FRI);
  - the ticket note ("Please come. I might be no good anymore...");
  - the three red notes of scene 60;
  - the Kokkuri-san boards (YES / NO; the kana chart stays, as the script describes it);
  - the scratched words on the restroom wall;
  - the headlines of the two school newspapers.
- tools/props.py: lettering mask, fill from the surroundings (numpy, no OpenCV), English
  drawn straight, rotated or in perspective, with a rough marker style for handwriting.
  tools/gfx.py PROPS lists the edits; every background file with the same bytes gets the
  new picture.

Checked
- All 21 files read back from the built image byte for byte and decode as intended.
  Before / after previews: work/ui/shots/props/.
- The background path was proven in the emulator in 0.9.0 (00A01). These pictures sit
  deep inside stories and were not viewed in-game.

Left Japanese on purpose (reasons in the survey): the "unknown letters" page (14A15),
the driver's licence, the postbox (says POST), illegible note boards, small print.
Still open: title logo, ending credits.

## 0.9.0 - 2026-11-11 (graphics build, not a release)

Step 4 of docs/ui_plan.md. Image SHA-1: e5de3ba4d262b0fcca676309f5da1e4d220c88df.
v0.8.0 is kept as an xdelta3 patch (verified).

Added
- Survey of every image and movie for Japanese text: work/ui/gfx_survey.md (what is done,
  what is open).
- Gender screen captions 男子 / 女子 -> "Boy" / "Girl" (DI2.TIM).
- Title still and title background: "© パンドラ ボックス" -> "© PANDORA BOX"; the brush
  logo 学校であった怖い話 is kept. The "Afterwards" title (47A44): red その後の ->
  "Afterwards".
- End movies: the closing line -> "And so the terror begins again...", the end card -> "The End"
  (THEEND.STR, 47D01.MV); the closing line -> "And then, it was all over..."
  (BADEND.STR). Same fades and left-to-right reveal as the Japanese, frame by frame.
- Tools: tools/bs.py (MDEC still decoder/encoder, BS v3), tools/strframes.py (movie
  frames), tools/gfx.py (replacements; `preview <dir>`), tools/moviegrab.py (VRAM grabs
  during movies). The build writes graphics in place in their GRPs and movie video
  sectors in place.

Checked in DuckStation (muted):
- on this exact image: boot, the gender screen with Boy / Girl;
- on test builds with the same encoder (`GFX_TEST=1`): unchanged re-encodes of the boot
  logo movie PBROGO.MV (plays cleanly; this found the missing end-of-frame code that
  crashed the first try), DANJO.BS and the prologue's first background 00A01.BG.
- Not seen in the emulator: the title still and the three end movies themselves (they
  use the same proven paths; frames checked by decoding the built image).

Known issues / open
- Logo, ending staff credits, Kokkuri-san boards, handwritten notes and signs in photos
  are still Japanese (decision needed, see work/ui/gfx_survey.md).
- The English end-movie text is plain Noto Sans, not a brush hand like the Japanese.
- Test incident: while checking, a run of repeated button presses went through name entry
  into the save screen and overwrote Notes 1 on the emulator's memory card. The card was
  restored from the copy stored in the Nov 10 savestates (checked on the save screen);
  the overwritten card is kept as memcards/overwritten_2026-11-11.mcd.bak.
  docs/debug_tools.md now says when mashing is safe.
- Real hardware: graphics stay inside their original files' size and MDEC buffer size;
  no change to code or RAM use.

## 0.8.0 - 2026-11-11 (name entry build, not a release)

Step 3 of docs/ui_plan.md. Built on 0.7.0 (Kowai Pixel font). Image SHA-1:
746e5ff9dcc9b1352b1e49f0b9d7f075d4537048. v0.7.0 is kept as an xdelta3 patch (verified).

Added
- Default names in English: Shuichi Sakagami (boy), Emi Kurata (girl). Names are stored
  as ASCII, padded to an even length with the 7F filler, so they show in the story text
  through {a} {b} {c} like the rest of the English.
- Name entry in Latin letters: the grid shows A-Z, `- ' .`, "<-" (delete) and "OK"
  (finish). A cell adds its letter straight away (no kanji list), up to 8 letters per
  name, capitals automatic (first letter, and after `- ' .`). Delete on an untouched
  default clears it. Names and labels ("Enter your name.", "Surname", "Given name") are
  drawn across in the left half, with a cursor after the last letter.
- Gender question in English: "Boy or girl?", d-pad "Select" over circle "OK".
- Code map of both screens: docs/text_system.md "Name entry".

Checked in DuckStation (muted), on this exact image:
- the gender question;
- name entry with the defaults;
- clearing and typing a surname and given name (automatic capitals), delete, finish;
- the names stored in RAM (padding);
- the prologue line "Yes. I'm A Owbm, from the newspaper club." with the typed name;
- the save prompt (cancelled; nothing saved).

Screenshots work/ui/shots/ui_gender_en.png, ui_name_entry_en.png,
ui_name_entry_typed_en.png, ui_name_in_story_en.png.

Known issues
- The captions 男子 / 女子 on the gender screen are part of its pictures (DANJO.BS):
  graphics step.
- Not checked: the girl's path (Emi Kurata in the story text), the after-game "Change
  Name" menu, names in a save made with the Japanese game.
- Real hardware: no new risk; the payload is now 7,696 of 8,192 bytes (same kernel RAM
  area, 0x8000C000-0x8000DFFF), so little room is left for further code there.

## 0.7.0 - 2026-11-11 (font build, not a release)

New dialogue/menu font. Image SHA-1: 17dd35053cea38006dfb09ee924a6b8ee95a73c3.
v0.6.0 is kept as an xdelta3 patch (verified).

Changed
- The VWF font is now Kowai Pixel, hand drawn pixel by pixel
  (`tools/fonts/kowai-pixel/glyphs.txt`) instead of Noto Sans 12 px thresholded to 1bpp.
  1 px strokes, even curves and corners, so it stays clean when the emulator scales the
  picture up. Same cell (16 rows, baseline row 12, cap height 9, x-height 7), same outline
  pass and renderer; every letter is 2 px from the next (one outline column each).
  Lookalikes told apart: serif `I`, tailed `l`, footed `1`, rounder `D` than `O`.
- About 7% narrower overall; scripts re-wrap automatically (tools/textenc.py reads the
  widths), so lines break differently from 0.6.0 and no page gets longer.
- `tools/pixfont.py`: loads the glyph file (`vwf.build_font` now returns it; the old font
  stays as `vwf.build_font_noto`), `check` lists width changes, `preview <dir>` writes
  before/after images (work/ui/font/preview/).

Checked in DuckStation (muted), on this exact image: story 1 dialogue pages after a
hot reload (new wrapping, outline, ellipsis, apostrophes, `1-E`) and the title menu after
a fresh boot. Screenshots work/emulator/shots/v070/. Not re-checked: teller select,
load/save/copy/delete screens (text only got narrower, nothing else changed there).

Known issues
- Real hardware: no new risk; the payload is the same size (6,080 bytes, same place).

## 0.6.0 - 2026-11-11 (UI strings build, not a release)

Step 2 of docs/ui_plan.md. Image SHA-1: 4898426cf4005560e767cf2570ce7417f2d8b1a2.
v0.5.0 is kept as an xdelta3 patch (verified).

Added
- English for the program's menu text (104 strings, `work/translation/en/ui.json`): title
  menu, save/load/copy/delete prompts and lists, all memory card messages (written per line
  so each message reads as a sentence), Yes/No, the storytellers' full names (Western
  order), "Whose story will you hear?", the save panel, the hidden after-game menu, and
  the seventh story's countdown line ("I looked at the clock. I only had 0:00 left.").
- `tools/uiscan.py`: every Shift-JIS string in the program with its references (pointer
  tables, lui/lo pairs, gp-relative) -> work/ui/exe_scan.json.
- `tools/uitext.py` builds them: in place when they fit, otherwise moved into slots the
  Japanese no longer uses with every reference repointed; 160 bytes go after the VWF payload.
- Slot numbers and the clock digits the game writes at run time now land in the English
  text (`#` marks; the build moves the code's byte offsets and writes ASCII digits).
- Save panel: name shown given name first, "Gender: Male/Female", "Story N: <teller>".
- Teller bar: "1st".."6th" + name (the name moved left so "Tomoharu Hosoda" fits).
- `tools/hotreload.py` writes the full payload (with the UI strings after it).

Checked in DuckStation (muted), on this exact image: title menu, load list + save panel,
Delete Notes and Copy Notes prompts with their slot digits (answered No; the save is
untouched), the "continue without saving" prompt, story-teller select (Fukuzawa, Arai,
Hosoda). Screenshots work/ui/shots/ui_*_en.png. Not seen in the emulator: memory card
error messages (they need a missing/full/damaged card), the hidden after-game menu and the
seventh-story clock line (checked in the built program: digit offsets and pointers).

Known issues
- "Tomoharu Hosoda" on the portrait plate touches the plate's slanted edge.
- Still Japanese: name entry, gender question, default names (step 3), graphics (step 4).
  The memory card save title stays Japanese on purpose (shown by the console's own
  memory card screen).
- Real hardware: no new risk beyond 0.5.0 (the 160 extra bytes sit in the same kernel RAM
  area as the payload, 6,080 of 8,192 bytes used).

## 0.5.0 - 2026-11-11 (menu renderer build, not a release)

Step 1 of docs/ui_plan.md (menus and UI). Image SHA-1:
10f18b1d4a7142759ff33540b25e933e04e0a773. v0.4.0 is kept as an xdelta3 patch (verified).

Added
- English menu text: the message box / menu routine (title menu, memory card messages,
  save/load lists, EXE 0x8002F048) and the story-teller select (0x80029164) draw ASCII
  with the story font, proportional, and Shift-JIS as before; sprite, box and highlight
  widths now follow the text's pixel width (the box shrinks or grows to fit).
- Teller select: the prompt moves left when it is too long for the screen.
- `work/translation/en/ui.json` + `tools/uitext.py`: English UI strings, written into the EXE
  when they fit their slot. 31 strings so far: the title menu (New Game, Continue, Delete
  Notes, Copy Notes), some memory card and load-screen lines, "Notes 1-4", "Story 1-6",
  "Whose story will you hear?", and the six storytellers by surname only (full names do not
  fit their slots until step 2 moves the strings).
- `tools/gdbdbg.py mash`: press a button until the CPU reaches an address (used to stop at
  the teller screen after the prologue). docs/debug_tools.md: how to reach the menus
  without touching the memory card save.

Changed
- The story text renderer was split so the same letter drawing serves the dialogue window
  and the menus (no change in how dialogue looks; checked on the prologue pages).

Checked in DuckStation (muted), on this exact image: title menu, Delete Notes list and its
Yes/No prompt (cancelled), Continue/load list, the save prompt (cancelled, nothing
written), prologue text, story-teller select (two tellers). Screenshots:
work/ui/shots/ui_*_en.png (+ `_labels.png`, coordinates in work/ui/shots_en_bbox.json).

Still Japanese: most memory card messages, the save panel (name, "性別" gender line,
stories heard), name entry and gender screens (vertical layouts, step 3), names in the
story text, graphics. Real hardware: no new risk (code hooks in the EXE; the payload grew
to 5,828 bytes, still inside the kernel RAM area 0x8000C000-0x8000DFFF noted in 0.1.0).

## 0.4.0 - 2026-11-11 (reviewed build, not a release)

All three review stages are done (accuracy in 0.3.0, editorial and proofreading below).
Image SHA-1: ce32cdce916a284b4511939c765f62b05f3bd36d. v0.3.0 is kept as an xdelta3 patch
(work/output/patches, verified byte for byte).

Checked in DuckStation (muted): Iwashita's story (SCE29) opening pages with the 0.4.0
script: "seven wonders", her "Heh heh heh...", wrapping and page breaks.

### Editorial pass

Review stage 2 of 3 (BASE_RULES.md: editorial) done for all 124 chunks / 16,120 rows
(docs/AGENT_EDIT.md, `tools/review.py ... edit`): 1,572 rows edited, every chunk passes
`review.py check`. Agent notes are in work/translation/en/review/edit/notes.md
(7 ACC = meaning doubts, 20 VOICE = open tone questions, for proofreading).

Changed
- Clumsy, literal or garbled lines made natural; dangling references and tense slips fixed.
- Lines and choices with identical Japanese now read the same across branches and routes.
- Added profanity removed where the source has none (e.g. しまった "Damn it" -> "Oh no");
  kept where the source is rough.
- Voices: Arai polite with few contractions; Iwashita poised; laughs: Iwashita "Heh heh",
  Fukuzawa / Taguchi "Hee hee", others moved off Iwashita's laugh where noticed.
- Scene 47: bare 先輩 for the player is "Senpai" throughout.
- tools/fix_terms.py: soccer team -> soccer club (サッカー部), Seven/Six Mysteries ->
  seven/six wonders in any case; terms_live.md now lists "the Grudge Notebook".

Checked: every script still fits the 189,152-byte buffer (largest SDATA07 184,524 bytes),
no layout warnings. Not built or tested in the emulator yet.

### Proofreading

Review stage 3 of 3 (BASE_RULES.md: proofreading), after an accuracy recheck of the
editorial changes.
- Accuracy recheck (docs/AGENT_RECHECK.md, `review.py ... recheck`): all 1,562 rows the
  editorial pass changed (and the open ACC items) compared with the Japanese again;
  37 rows restored where an edit had shifted meaning (dropped hedges, added certainty,
  wrong referent, lost words), e.g. 32:3678 "Y-you bitch" -> "Y-you bastard" (この野郎),
  44:8ed8 mutual embrace, 12:6830 "Something ordinary, then...".
- Dot runs (`tools/dots.py`): 475 rows normalized to the convention: ordinary …… = "...",
  a run of N >= 4 … = ceil(1.5 N) periods, no raw … left (one row, 10:61b8, left as is).
- Laughs (docs/AGENT_LAUGH.md, `review.py ... laugh`): 130 rows; "Heh heh" is now only
  Iwashita's. Kazama "Hm hm hm" / "Ooh-hoo-hoo", Fukuzawa, Taguchi and other girls
  "Hee hee", Hosoda "Hee hee" / "Ehehe", other men "Hm hm" / "Kuh kuh kuh". The fix_terms
  "Fufu" rule now only runs in Iwashita's scenes (29-34).
- Terms by script (tools/fix_terms.py, added to the agents' do-not-touch lists): "Search
  elsewhere" (scene 07), the Phantom (scene 55), witching hour (魔の時刻), red-bean soup
  drink (scene 35), the cabinet (scene 14 棚); scene 07 glass 戸棚 = "cabinet".
- `review.py apply` refuses to re-apply an earlier stage once a later one has outputs.
- Mechanical report `tools/proofcheck.py` (doubled words, spacing, punctuation, Japanese
  punctuation, stray characters): no real problems left.

- Spelling (`tools/proofcheck.py --spell`, pyspellchecker 0.8.4): every unknown word
  reviewed; fixed two words glued together across codes (17:2360 female branch "If
  youwant" -> "If you want", 38:4144 "huge{g}fans"). The rest are names, sound effects,
  stretched words and deliberate cut-offs; no near-duplicate name spellings found.

Checked: all 16,120 rows pass the markup/encoding check; every script fits (largest
SDATA07 184,140 bytes); no layout warnings. Not yet: the emulator checks, menus/UI.

## 0.3.0 - 2026-11-11 (accuracy-reviewed build, not a release)

Review stage 1 of 3 (BASE_RULES.md: accuracy) done for all 240 slices / 16,120 rows:
each slice was checked against the Japanese (docs/AGENT_REVIEW.md, tools/review.py).
Agent notes per slice are collected in work/translation/en/review/acc/notes.md.

Changed
- Meaning fixes across the script: wrong subjects/referents, guesses stated as facts,
  hearsay dropped, added glosses and details removed, softened lines restored, gender
  slips fixed, trimmed choices restored to full meaning, long silences and dot runs
  restored, ☆/★ put back where the source has them.
- Term script `tools/fix_terms.py` (runs after every merge): ampoule, Lord Hino, Kuwahata,
  Film Research Society, joro spider, tear-off calendar, Untamarian, pervert, reflection
  room, apology letter, indoor shoes, make-up class, restroom (not for real bathrooms),
  patch, faculty room, the lodge, 500-yen, Ordinary Folk Course, seven wonders, scene 07
  menu prompts in "should I" form, Iwashita's laugh "Heh heh" (was romanized "Ufufu").
- Scene 55: quote marks around Arai's speech made consistent across the three branches.
- Glossary: Hanako-san, teacher titles, Lord Hino, the ampoule.

Still to do: editorial pass, proofreading (dot-run normalization, raw … characters),
honorific decision (Senpai), the items in work/translation/en/review_todo.md, menus/UI.

## 0.2.0 - 2026-11-10 (first-pass translation build, not a release)

All 16,120 script rows (13,326 text, 2,794 choices) in all 71 scenes are in English
(first pass by 240 slices, docs/AGENT_SLICE.md). The review passes (accuracy, editorial,
proofreading per BASE_RULES.md) have not been done yet; open items are in
work/translation/en/review_todo.md.

Changed
- Page layout (tools/textenc.py): when the next paragraph does not fit on the 12 lines
  left, its line break becomes a page break, so pages break between paragraphs (the engine
  would otherwise continue mid-sentence on a new page); 4 lines are kept free for choices
  after a row that ends in a line break; a paragraph longer than a page gets a page break
  every 12 lines (no text has to be shortened to fit).
- Long dot runs with a wait/pause code attached now wrap too.
- Build: identical strings in a script are stored once (SDATA07 was 220,952 bytes, over
  the 189,152 limit; now 182,560).
- Translation memory (tools/unify_tm.py): repeated rows inside a scene (same Japanese,
  15+ characters) use one English wording (160 rows unified).

Checked in DuckStation: Iwashita's story (SCE29) from the first page through the first
choice and the bullying pages: wrapping, paragraph page breaks, wait icons, choice.

Known issues
- Not reviewed yet; term conflicts and restorations listed in review_todo.md.
- Menus, memory card screens, name entry, story-select screen and graphics are still Japanese.
- Per-gender split lines and 3-line choices are not yet checked in the emulator.
- v0.1.0 is kept as an xdelta3 patch (work/output/patches, verified byte for byte); xdelta3
  3.1.0 (jmacd/xdelta-gpl release) is in tools/bin/xdelta3.

## 0.1.0 - 2026-11-10 (technical build, not a release)

First English engine build. Only six test rows of Iwashita's first story (SCE29) are in
English; everything else is still Japanese.

Added
- Disc tools: ISO extract, GRP/DIRENTRY parser (`tools/grp.py`), scene script parser for
  all 71 scripts (`tools/sdata.py`), text extraction to `work/translation/en/scenes/`
  (16,120 rows: 13,326 text, 2,794 choices).
- Variable-width font (Noto Sans 12 px, outlined like the original) and a horizontal,
  left-to-right renderer (`tools/vwf.py`); English stored as ASCII pairs, all control codes kept.
- Window shown as one 200 px text area (was 10 spread columns), 17 px lines, 12 lines a page.
- Choices: one line each with "1. " prefixes, horizontal highlight bar, Up/Down select.
- Build (`tools/build.py`): scripts rebuilt with relocated string pools, stored in DUMMY.BIN
  sectors; no byte budget per string (only the 192 KB script buffer).
- Debug kit: GDB pad/screenshots, hot reload (payload, EXE, DIRENTRY, loaded script),
  savestates; see `docs/debug_tools.md`.
- Glossary `work/glossary/glossary.json`.

Checked in DuckStation: boot, Iwashita's first pages, wrapping, page breaks, wait icon,
choice display and selection.

Known issues
- Menus, memory card screens, name entry, story-select screen and graphics are Japanese.
- Untranslated Japanese text shows with columns closer together and may run past 10 columns.
- Not tested on real hardware (payload in kernel RAM 0x8000C000).

## Translation in progress (after 0.1.0)
- First-pass translation by slices (tools/slices.py, docs/AGENT_SLICE.md, tools/check_slice.py,
  tools/apply_slices.py). Progress: `python tools/slices.py status`. Resume by launching agents for
  the missing slices with the same prompt; merge with tools/apply_slices.py.
- Encoder fixes: choices wrap to 3 lines (engine hook 7F 0A), per-gender wrapping, {p} starts a new
  page for wrapping, over-wide words hard-break, source {g} ignored, names reserve widest default.
- Review items collected in work/translation/en/review_todo.md; live terms in work/translation/en/terms_live.md.
