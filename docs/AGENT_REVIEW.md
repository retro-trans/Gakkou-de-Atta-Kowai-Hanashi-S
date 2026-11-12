# Accuracy review of one slice (agent brief)

Game: *Gakkou de Atta Kowai Hanashi S* (PlayStation 1996), a horror sound novel. A
first-year newspaper-club member (the player; default Shuichi Sakagami, or Emi Kurata for
a girl) interviews six students after school; each tells a ghost story with branching
choices. Narration is first person (the player). The whole script has a first-pass English
translation; you are the **accuracy** stage (BASE_RULES.md "Shared review workflow" and
"When reviewing translation accuracy"). Editorial polish and proofreading are later stages:
do not rewrite lines that are accurate just because you would phrase them differently.

## Read first
1. `BASE_RULES.md`: "When translating dialogue", "When translating any kind of text",
   "Shared review workflow", "When reviewing translation accuracy". Binding.
2. `work/glossary/glossary.json` and `work/translation/en/terms_live.md` (names and terms).
3. Your slice `work/translation/en/review/acc/S###.json`: rows with `jp` (source) and `en`
   (current English), plus `todo` (open items for this slice). For context read the end of
   the previous slice and the start of the next (`prev` / `next`, same folder).
   `follows_choice` on a row lists the choice id(s) that jump to it.

## What to check, row by row, in scene order
- Full meaning: nothing missing, nothing added (no glosses or explanations the source
  doesn't have), no softening, emotional force and imagery kept.
- Who speaks to whom; established referents; subjects and verbs restored where the scene
  settles them (BASE_RULES pro-drop rule); ambiguity kept only where the scene leaves it.
- The player's gender: rows with `{f:A|B}` serve both. Scenes with no `{f}` codes are
  single-gender routes; use the gender the scene shows (see the table) and never infer
  gender from a name.
- Deliberate fragments, pauses and interruptions kept. Dot runs: the ordinary …… (2
  characters) is "..." everywhere; a longer run (4+ … characters, e.g. a silence) gets 3
  dots per 2 characters, so restore any that were shortened (they wrap by themselves now).
  Don't shorten a run that is already longer.
- ☆ and ★ are kept where the source has them (the font has both).
- Choices: the full meaning of the source choice, up to 3 lines (~30 characters each): restore
  any choice that was trimmed. The rows that follow a choice must fit what the player chose.
- Nothing needs shortening to fit a page: long paragraphs break into pages by themselves.
- Settle every `todo` item of your slice: fix the rows, or say in `notes` why not.

## Do not touch (fixed by script, tools/fix_terms.py)
ampoule, the diva (歌姫), Lord Hino (日野様), Kuwahata (桑畑), the Film Research Society,
joro spider, tear-off calendar, Untamarian(s), pervert (チカン), the reflection room (反省室),
indoor shoes (上履き), make-up class (補習), restroom (トイレ), patch (ワッペン),
faculty room (職員室), soccer club (サッカー部), seven/six wonders,
the Phantom (scene 55 怪人), witching hour (魔の時刻), red-bean soup drink (scene 35),
the cabinet (scene 14 棚), "Search elsewhere" (scene 07). Laughs: docs/AGENT_LAUGH.md.
Other standards: 反省文 = apology letter; 進行役 = the host; 宿泊施設 (scene 11) = the lodge;
ルーベライズ = Rubelize; 旅立つ motif in scene 10 = "set off on a journey"; Hirai to Kondo:
"Mr. Kondo"; 花子さん = Hanako-san (legend name). Teachers keep a title (Mr. Sakurai,
Ms. Sasaki); if the gender is unknown, use the name alone. Students: no honorifics;
the player's full name is "{b} {a}". Senpai: keep only in the Taguchi route (scene 47).

## Player gender
Many branches are written for one gender only, with no `{f}` codes; the game splits by
gender before them. Scenes with NO `{f}` code at all: 02 03 04 06 07 11 12 15 20 21 23 29 30
32 33 37 41 42 43 45 46 47 51-70. Scenes with codes can still contain single-gender
branches. In every row without `{f}`, take the player's gender from the scene itself
(the player's 僕/俺 vs 私 with feminine endings, how others address or describe the
player) and keep it consistent; where nothing shows it, use no gendered word. Report the
evidence as UNSURE when you rely on it. First-pass findings for later scenes: male 45 46 47
54 55 64; female 53 56-58 60-63 65-70; scene 03 (late part) female.

## Markup (unchanged from translation; the checker compares with the source)
`\n` paragraph end (same count and same ending as the source), `{p}` page end, `{k}` wait,
`{w}` pause, `{g}` line break, `{a}` `{b}` `{c}` names, `{f:A|B}` male|female (same count, no
`\n` or codes inside). Choices are plain text. Characters: printable ASCII except `{` `}`,
plus … — – ‘ ’ “ ” é è ï ü · ♪ ☆ ★.

## Output
Write `work/translation/en/review/acc/S###.out.json` (UTF-8), **only the rows you changed**:
```
{"rows": {"29:0b30": "corrected English...", ...},
 "notes": ["29:0b30: FIX meaning - source says X, English said Y",
           "29:0c10: UNSURE - referent of 彼 inferred as Hino from 29:0bf0",
           "29:0d00: KEPT OMISSION - subject left open; scene does not settle who"]}
```
Each note starts with the row id and one tag: FIX (what was wrong), TODO (how a todo item
was settled), UNSURE (a call you had to make), KEPT OMISSION (BASE_RULES: flag every line
where you kept the source's omission), RETURN (a voice/tone issue for the editorial stage).
Then run `python tools/review.py check acc S###` until it prints OK. Edit no other file;
do not print long Japanese text to the console (read files with the Read tool).

## Final report (max 6 lines)
`S### rows examined N / rows in slice N; changed M; check OK|FAIL`, then the 2-4 most
important findings (row id + one line).
