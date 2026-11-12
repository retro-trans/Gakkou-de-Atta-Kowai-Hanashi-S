# Graphics with Japanese text (survey for step 4)

Every image file was decoded and looked at: 8 TIM, 13 BS stills, 1,674 unique BG
backgrounds (2,251 files), 65 movies (STR / MV, every 8th-60th frame). Tools: tools/bs.py,
tools/tim.py, tools/strframes.py. Replacements are built by tools/gfx.py.

## Next build (after 0.10.2)

| file | text | English |
|---|---|---|
| SLPS_004.04 at 0x8004AB2C (128x48 4bpp image in the EXE; the survey above only looked at files) | in-story Start menu 取材メモを呼び出す / 話の続きを聞く | Open the notes / Continue the story (tools/gfx.py story_menu_exe) |

The EXE holds only one other image (0x80049514, 256x16 4bpp, VRAM (768,0)): pointer hands,
arrows and box icons, no text.

## Done in 0.9.0

| file | text | English |
|---|---|---|
| SCE00/DI2.TIM | 男子 / 女子 (gender screen captions) | Boy / Girl |
| SCE00/TITLE.BS, SCE00/TITLE.BG | © パンドラ ボックス | © PANDORA BOX (brush logo kept) |
| SCE47/47A44.BG | その後の (the "Afterwards" title) + © line | Afterwards, © PANDORA BOX |
| SCE00/THEEND.STR, SCE47/47D01.MV | closing line / end card | And so the terror begins again... / The End |
| SCE00/BADEND.STR | closing line | And then, it was all over... |

## Done in 0.8.1 (story props, tools/props.py + tools/gfx.py PROPS)

| background (copies) | Japanese | English |
|---|---|---|
| 04A26 / 04A27 | name cards 赤坂 陽介 / 畑中 亨 | Yosuke Akasaka / Toru Hatanaka |
| 07A06 (+18A06, 46A04, 47A04, 69A08, 70A03) | door plate 新聞部 | Newspaper Club |
| 30A13 | class plate 1年E組 | Class 1-E |
| 39A02 | calendar 五月 … 金 | MAY … FRI (13 and 友引 kept) |
| 51A17 | handwritten note (two lines) | Please come. / I might be no good anymore... (51:1ba4 "no good") |
| 60A05 / 60A06 / 60A10 | three handwritten red notes | It's not fair / You're coming with me too / And you said there was no such thing as curses... (60:17a4, 60:191c, 60:220c) |
| 17A02, 26A23, 20A05 | Kokkuri-san board はい / いいえ | YES / NO (the kana stay: the script says the board has the kana syllabary) |
| 22A23 | wall graffiti (columns cut off by the frame) | Running away alone / I called for help so many times / I was killed / Dragged in here (22:a9a4) |
| 66A07 | school paper: masthead, "seven wonders" box and four headlines | SCHOOL NEWS, 7 WONDERS, GIRL STUDENT MISSING, CLUB MEMBER WHO COVERED THE 7 WONDERS, SEARCH ON - INFO WANTED, THE 7TH STORY: A BIZARRE CASE |
| 18A08 (+47A37) | wall paper: 学校新聞, 風間望 | SCHOOL NEWS, KAZAMA |

Left as is, on purpose: 14A15 (the story calls it "letters I had never seen before"),
23A50 driver's licence (tiny print; the teacher's given name is not in the script),
33A43-45 postbox (already says POST), 60A15 / 60A20 / 60A22 (illegible scribbles, marked
test paper), 47A06 (tiny newspaper on a desk), 17A04 (board seen at an angle, labels a few
pixels), HAIKEI.BS box label, small print in the newspapers.

## Movie subtitles (0.8.2)

| movie | speech | English |
|---|---|---|
| MOVIES/SEXMOVIE.STR (opening, after name entry) | narration, XA channel 1 boy / 2 girl | 18 burnt-in subtitles (work/translation/en/movie_subs.json); Noto Sans antialiased since 0.10.1, preview work/ui/movie_subs/ |

All other movies were checked (2026-11-12): only MOVIES/GOODEND.STR and MOVIES/BADEND.STR
have audio besides the opening (stereo XA, decoded with tools/xa.py), and it is music with
no speech (Whisper's voice filter finds nothing; without it, it only produces its usual
"thanks for watching" hallucination). DEMO.STR, TITLE.STR, THEEND.STR, SCE00/BADEND.STR,
PBROGO.MV and all 56 scene MV clips have no audio sectors (their sound comes from the
sequencer). Nothing else to subtitle; the ending staff credits are text (see below).

## Open (decision needed)

| what | files | note |
|---|---|---|
| title logo 学校であった怖い話 | TITLE.BS/BG, 47A44.BG, TITLE.STR (logo animation) | kept as the brand; an English logo would also mean re-making the 68-frame animation |
| ending staff credits (vertical Japanese) | MOVIES/BADEND.STR, MOVIES/GOODEND.STR | names would need verified romanisations |
| developer placeholders | 35D01.MV ("dummy movie"), 11A65, 25A41, 25A50, 63A16 (欠番) | probably never shown |

No Japanese in: KAO faces, the other TIMs (START "PUSH START BUTTON", ICON, DIGITS, COIN,
MINIFAC2), DEMO.STR, SEXMOVIE.STR, the scene MV clips other than 35D01 and 47D01.
