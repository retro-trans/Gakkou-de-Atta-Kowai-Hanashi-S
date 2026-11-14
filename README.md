# Gakkou de Atta Kowai Hanashi S — translation project

An open toolchain for translating **Gakkou de Atta Kowai Hanashi S** (PlayStation,
Banpresto 1996, SLPS-00404), plus the English translation built with it.

## Contribute

All the game's text is translated, but we have not played every story and ending
in English yet, and no human has proofread the script against the Japanese yet. If
you want to help with this project or the next one — bug reports, proofreading or
playtesting — please join the Discord:

**[discord.gg/MssepShjmB](https://discord.gg/MssepShjmB)**

## Play it

The latest release is **[v0.8.1](https://github.com/retro-trans/Gakkou-de-Atta-Kowai-Hanashi-S/releases/tag/v0.8.1)**,
for the Japanese release (**SLPS-00404**). It translates all six storytellers'
stories and the seventh story, the menus, the memory card screens, name entry, the
opening movie (subtitled) and the in-game pictures with text. v0.8.1 fixes the
storyteller select (only three tellers could be picked at the start) and the sixth
story's line on the save screen.

### Apply

Use [Retro Trans](https://github.com/retro-trans/retro-trans-tools), or apply the
`.xdelta` with DeltaPatcher or xdelta3. You need your own Japanese disc image as a
single-track BIN/CUE (Redump "Gakkou de Atta Kowai Hanashi S (Japan)"), or the
English v0.8.0 image patched from it for an upgrade.

| Your source image | Patch |
|---|---|
| Japanese release, SLPS-00404, `.bin` | `Gakkou-Kowai-Hanashi-S-English-v0.8.1.xdelta` |
| English v0.8.0 `.bin` | `Gakkou-Kowai-Hanashi-S-English-v0.8.0-to-v0.8.1.xdelta` |

Both patches produce the same image. Check the source hashes in `README-v0.8.1.txt`
if your patcher reports a mismatch; keep checksum verification enabled.

For example:

```
xdelta3 -d -s "Gakkou de Atta Kowai Hanashi S (Japan).bin" Gakkou-Kowai-Hanashi-S-English-v0.8.1.xdelta "Gakkou de Atta Kowai Hanashi S (English v0.8.1).bin"
```

Then copy the original `.cue`, rename it to match, and change the `FILE` line to the
new `.bin` name. If you have a `.chd`, unpack it first with
`chdman extractcd -i game.chd -o "Gakkou de Atta Kowai Hanashi S (Japan).cue"`.

**Boot the new image fresh and load an in-game memory-card save.** Old emulator
save states keep the previous executable and file positions.

## Translate it

Fork it to fix the English, or to take the game into another language. The English
lives in plain JSON, one file per scene:

```sh
python tools/extract_iso.py "Gakkou de Atta Kowai Hanashi S (Japan).bin" work/source/disc
python tools/extract_text.py            # scene rows -> work/source, work/translation
#   ... edit the "en" fields in work/translation/en/scenes/SCExx.en.json ...
python tools/fix_terms.py               # names and fixed terms, run after every edit
python tools/proofcheck.py              # mechanical report: markup, spacing, punctuation
python tools/build.py 0.8.2 --report    # -> work/output/... (English v0.8.2).bin/.cue
```

`build.py` keeps every script's bytecode byte for byte, rewrites only the string pool
and repoints every string operand, so an untouched scene rebuilds identically. The
build reports any line that does not fit its window.

You need your own copy of the game. This repository contains no disc image, no game
data and no dump of the original Japanese script: the working files that hold the
Japanese stay on the translator's machine, and only the English copies
(`*.en.json`, written by `tools/strip_jp.py`) are published. Names and UI terms
appear in Japanese where a tool needs them.

The dialogue font is Skies of Arcadia's Latin font. It is not in this repository:
`tools/skiesfont.py` reads it from a local `../Riot Stars` font cache, built from
your own Skies of Arcadia disc. Without it, set `VWF_2X=0` to build with the 1x
Kowai Pixel dialogue font instead (lines are wrapped to whichever font is built).

## What is here

| Path | Contents |
|---|---|
| `BASE_RULES.md` | portable rules for running a project like this, including the three review passes |
| `tools/` | the pipeline: disc and archive access, script codec, VWF renderer, graphics, movies, build, debug |
| `work/translation/en/scenes/` | the English script — 71 scene files, 16,120 rows |
| `work/translation/en/ui.en.json` | menu and memory card strings of the executable |
| `work/translation/en/movie_subs.en.json` | the opening movie subtitles, with timings |
| `work/translation/en/review/` | per-chunk outputs of the accuracy, editorial and proofreading passes |
| `work/glossary/glossary.json` | characters, terms and style decisions |
| `docs/text_system.md` | how the script engine, the text windows and the RAM map work |
| `docs/ui_plan.md` | menus, name entry and graphics: what was changed and how |
| `docs/debug_tools.md` | driving DuckStation over GDB: virtual pad, screenshots, VRAM grabs |
| `docs/AGENT_*.md` | the briefs used for each translation and review pass |
| `CHANGELOG.md` | every build, what changed, and what broke |

## Using these tools

They expect the raw MODE2/2352 `.bin` you dump yourself from your own copy, and
Python 3.8 or newer with numpy and Pillow. Most read the extracted files under
`work/source/` and only write under `work/`.

```sh
python tools/build.py <version> --report            # build and report layout problems
python tools/proofcheck.py --spell                  # spelling pass over the English
python tools/gdbdbg.py run "wait 300; shot t.png"   # drive the emulator (docs/debug_tools.md)
```

Windows note: anything using `multiprocessing` must be a real file on disk, never a
heredoc — spawned workers re-import the module and cannot import `<stdin>`.

## Do not sell this

This patch is free. Do not sell it, and do not sell anything made with it -
no pre-patched discs or images, no loaded memory cards or consoles, no
paywalled or ad-gated downloads.

It is an unofficial fan translation of a game Bandai Namco owns. Selling it
takes money for work that was given away, and it is the surest way to get a
project like this shut down.

## Credits

The dialogue font is the Latin font of Skies of Arcadia (SEGA), as prepared for the
Riot Stars translation, with alignment fixes and a few new characters drawn in its
style. The menu font, Kowai Pixel, was drawn for this project. Movie subtitles and
the ending text use [Noto Sans](https://fonts.google.com/noto/specimen/Noto+Sans)
(SIL Open Font License).

| Role | |
|---|---|
| Project lead | pow |

Translation passes, tooling and reverse engineering were done with Claude
(Anthropic), directed by pow. The translation is machine-produced and then
edited - see the release notes for what that means in practice.

## Status

The translation is in progress. `CHANGELOG.md` is the honest record, including
the builds that shipped broken and why.

Not translated yet: the title logo and the ending staff credits. A few pictures
stay Japanese on purpose (illegible boards, small print, a page whose point is
that the letters cannot be read); `work/ui/gfx_survey.md` lists them with reasons.
