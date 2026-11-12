# Translating one slice (agent brief)

Game: *Gakkou de Atta Kowai Hanashi S* (PlayStation 1996), a horror sound novel. A
first-year newspaper-club member (the player; default Shuichi Sakagami, or Emi Kurata
if the player chose a girl) interviews six students in the club room after school; each
tells a ghost story, with branching choices. Narration is first person (the player).

## Read first
1. `BASE_RULES.md` — "When translating dialogue" and "When translating any kind of text".
   They are binding: one row in, one row out; restore subjects and verbs; do not soften;
   don't infer gender from a name; read neighbouring rows before deciding who speaks.
2. `work/glossary/glossary.json` — exact spellings and style (Hepburn without macrons,
   Western name order "Akemi Iwashita", no honorifics; characters call each other by surname).
3. Your slice `work/translation/en/slices/S###.json`. For context, read the end of the
   previous slice and the start of the next one (`prev` / `next`). `narrator_hint` tells you
   whose story the scene belongs to.

A text row may carry `follows_choice`: the choice id(s) whose selection jumps to it
(read the choice text to know what the player just answered).

## Markup (keep every code; the checker compares them with the source)
- `\n` — end of a paragraph: the game waits for a key and starts a new line. Keep the same
  number of `\n` and the same ending as the Japanese (rows often end with `{p}` or `\n`).
- `{p}` page end, `{k}` wait, `{w}` pause, `{g}` line break — keep in place.
- `{a}` surname, `{b}` given name, `{c}` the player's name as others address them — keep.
- `{f:A|B}` — A shown to a male player, B to a female player. Keep every `{f:..|..}` (same
  count); translate both sides, even when they come out identical (`{f:I|I}`). Use it for
  gender-dependent words (`{f:he|she}`, `{f:boy|girl}`). No `\n` or other codes inside it.
- Honorific after a name, `{a}{f:君|さん}`: keep the code with both sides empty, `{a}{f:|}`.
  Teachers keep a title: 桜井先生 = Mr. Sakurai, 佐々木先生 = Ms. Sasaki.
- Choices (`"op": "choice"`): plain text only. Keep the full meaning: the build wraps a
  long choice onto up to 3 lines (about 30 characters each), so never trim content to fit.

## Characters you may use
Printable ASCII except `{` `}`, plus … — – ‘ ’ “ ” é è ï ü · ♪ ☆ ★ (keep ☆/★ where the source uses them). Prefer straight quotes:
「…」 -> "…", 『…』 -> '…' (inside dialogue). Use "..." or … for ……. No Japanese, no
full-width letters. Don't shorten or reword to fit (long dot runs wrap, text after {p} starts a new page and is wrapped separately): the build wraps lines (≈33 characters per line,
12 lines per page; a longer paragraph continues on a new page by itself, so never squeeze a long speech).

## Style
Spoken, natural English for dialogue; each storyteller keeps a consistent voice (e.g.
Iwashita: calm, elegant, coldly menacing; feminine Japanese speech becomes poised English,
not "girly"). Narration: plain past tense, atmospheric, no added explanation. Keep horror and
cruelty at full strength. Translate sound effects and onomatopoeia as English words.

## Output
Write `work/translation/en/slices/S###.out.json` (UTF-8):
```
{"rows": {"29:0864": "English...", ...},
 "notes": ["29:0a4c: kept 'you' for the listener; unsure whether ...", ...]}
```
Every id of the slice must be present. Then run
`python tools/check_slice.py S###` and fix every problem it reports until it prints OK.

## Names and terms
Read `work/translation/en/terms_live.md` first and reuse its renderings. For each new
story-specific name, nickname or recurring term, append ONE line to that file with a single
shell command (`echo "- 原語 = English (gender/role) [S###]" >> work/translation/en/terms_live.md`)
as soon as you decide it, and also list it in `notes` as `TERM: ...`. Check the neighbouring
slices' `.out.json` (if they exist) too.
Known so far: 飴玉ばあさん = the Candy Granny; ばあさん = the old lady / granny (address);
佐久間 = Sakuma (m); 片桐里子 = Satoko Katagiri (f); 原恵理子 = Eriko Hara (f);
吉岡 = Yoshioka (m); 目黒 = Keiko Meguro (f) (Shindo's story); 旧校舎 = the old school building.
Scene 07 (Hino's route): 殺人クラブ = the Murder Club; アンプル = the ampoule; 日野様 = Lord Hino.
Shindo's stories: 大倉 = Okura (m); 歌姫 = the diva; 赤坂洋介 = Yosuke Akasaka (m); 畑中徹 = Toru Hatanaka (m);
田所芳樹 = Yoshiki Tadokoro (m); 川口 = Kawaguchi.
Shindo: Class 3-D, rough casual male speech (俺) -> blunt, laid-back English.

## Final report (keep it short, max 6 lines)
`S### rows examined N / rows in slice N; check OK|FAIL`; then the 2–4 most important
uncertainties (row id + one line). Details belong in `notes`.
