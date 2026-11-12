# Editorial pass of one chunk (agent brief)

Game: *Gakkou de Atta Kowai Hanashi S* (PlayStation 1996), a horror sound novel. A
first-year newspaper-club member (the player) interviews six storytellers after school;
narration is first person (the player). The English has been translated and then checked
against the Japanese for accuracy. You are the **editorial** stage (BASE_RULES.md "Shared
review workflow" and "When doing an editorial pass"). Read both sections first; they bind.

## Your input
`work/translation/en/review/edit/E###.json` (up to 200 rows: the file is long, so read it in
several parts with an offset until you reach the last row): consecutive rows of one scene in play order
(`id`, `op` text|choice, `en`, maybe `follows_choice`, maybe `returns` = notes the accuracy
reviewer left for you on that row), plus `todo` (editorial items for this chunk).
For context read the end of the previous chunk and the start of the next (`prev`/`next`).
The Japanese is in `work/translation/en/review/acc/S###.json` (the chunk's `slices`): look
at it only when a line seems wrong or a `returns` note needs it.

## What to do
Read the chunk as a player would, in order. Change a row only for an identifiable problem:
- Clarity: a line that is hard to follow, ambiguous where the scene is not, or clumsy
  ("Stop this joke.", "It seems I've tricked you", "even more, more beautiful").
- Spoken dialogue: it must sound like a person talking, in that character's voice (below).
  Narration: plain past tense, atmospheric, keeps the source's imagery. A deliberate
  switch to present tense in the source stays.
- Register and tone: the force of insults, fear, sarcasm, tenderness as the scene has it.
  No added profanity ("the hell", "damn") unless the line already earns it; do not soften.
- Consistency inside the chunk and with its neighbours: the same thing called the same
  way, a repeated choice worded the same as its echo, the same laugh for the same person.
- Every `returns` note and `todo` item: settle it (edit or keep) and say which in notes.

Fix what is wrong; leave what is merely different. Do not add explanations or details, do
not soften, do not replace distinctive imagery with generic prose, do not shorten (long
lines and long speeches are fine: the game pages them by itself). Meaning is settled: if a
line's meaning looks wrong, do not rewrite it, note it as ACC.

## Voices
- Player (narrator): polite junior to the storytellers; plain, observant narration.
- Makoto Shindo (3rd year, m): blunt, rough, laid-back tough guy (俺); short punchy lines.
- Shoji Arai (2nd year, m): gloomy, polite (です/ます), soft-spoken and eerie; calm
  courtesy that unsettles. Few contractions.
- Nozomu Kazama (3rd year, m): flamboyant, smug, theatrical joker; teases and bluffs,
  flirts with a female player; alien/occult nonsense delivered with total confidence.
- Tomoharu Hosoda (2nd year, m): polite but awkward, clingy, eager to be liked, nervous
  laugh, oddly fond of restrooms.
- Akemi Iwashita (3rd year, f): calm, elegant, coldly menacing; poised, never girly.
  Laugh: "Heh heh".
- Reiko Fukuzawa (1st year, f): cheerful, chatty, gossip- and romance-loving; bright but
  not saccharine.
- Sadao Hino (3rd year, m): the club senior who set up the meeting; assured, in charge.
Other characters: keep the voice the scene gives them (rough 俺 speech -> blunt English,
polite speech -> polite English).

## Do not touch
- Codes: `\n` (count and the row ending), `{p}` `{k}` `{w}` `{g}` `{a}` `{b}` `{c}`,
  `{f:male|female}` (same count; both sides translated; no `\n` or codes inside).
  Choices are plain text (they wrap to 3 lines of ~30 characters).
- Fixed terms (tools/fix_terms.py re-applies them): ampoule, the diva, Lord Hino,
  Kuwahata, the Film Research Society, joro spider, tear-off calendar, Untamarian(s),
  pervert, the reflection room, apology letter, indoor shoes, make-up class, restroom,
  patch, faculty room, the lodge, 500-yen, Ordinary Folk Course, seven wonders,
  Hanako-san, the scene 07 "should I" menu prompts, soccer club, seven/six wonders,
  "Search elsewhere" (07), the Phantom (55), witching hour (魔の時刻), red-bean soup drink
  (35), the cabinet (scene 14 棚). Laughs: docs/AGENT_LAUGH.md. Names as in work/glossary/glossary.json
  and work/translation/en/terms_live.md; the player's full name is "{b} {a}".
- Honorifics: students by surname; teachers Mr./Ms. + surname (name alone if gender
  unknown); "Senpai" only in Taguchi's route (scene 47) - leave existing uses as they are.
- The player's gender: lines without `{f}` follow the route's gender; never add he/she
  for the player where the line has none.
- Dot runs and the raw … character: leave them (proofreading normalizes them by script).
  ☆ and ★ stay where they are.

## Output
Write `work/translation/en/review/edit/E###.out.json` (UTF-8), **only rows you changed**:
```
{"rows": {"29:0b30": "edited English...", ...},
 "notes": ["29:0b30: EDIT - stiff 'It seems I've tricked you' -> natural apology",
           "29:0c10: KEEP - returns note on 'creepy grin': already consistent",
           "29:0d00: ACC - English says X, scene implies Y; not changed"]}
```
Tags: EDIT (what and why), KEEP (a returns/todo item you decided to leave), ACC (meaning
doubt for the accuracy stage), VOICE (an unresolved voice/tone question).
Run `python tools/review.py check edit E###` until it prints OK. Edit no other file; do
not print long Japanese text to the console.

## Final report (max 6 lines)
`E### rows examined N / rows in chunk N; changed M; check OK|FAIL`, then the 2-4 most
important points.
