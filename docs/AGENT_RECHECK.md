# Accuracy recheck of editorial changes (agent brief)

Game: *Gakkou de Atta Kowai Hanashi S* (PlayStation 1996), a horror sound novel; first-person
narration by the player, a first-year newspaper-club member. The script was translated,
checked for accuracy, then edited for clarity and voice. BASE_RULES.md ("Shared review
workflow") says: recheck the accuracy of substantive editorial changes before final
proofreading. That is your job. Read docs/AGENT_REVIEW.md first (accuracy rules, player
gender table, do-not-touch terms, markup); it binds you too.

## Your input
`work/translation/en/review/recheck/R###.json` (about 120 rows, read it in parts with an
offset until the last row). Each row: `id`, `op` (text|choice), `jp` (source), `before`
(English after the accuracy review), `en` (current English after the editorial pass),
maybe `edit_notes` (why the editor changed it), maybe `flag: ACC` (someone doubts the
meaning, see the notes / `todo`). Rows are not consecutive: they are only the edited or
flagged rows. When a row needs context (who speaks, what "it" is), read the neighbouring
rows in `work/translation/en/scenes/SCE<NN>.json` (same id format; use the Read tool with an
offset near the row, not the whole file).

## What to check
For every row, compare `en` with `jp`:
- The edit must not change the meaning: nothing lost or added, no new referent, subject,
  gender, tense of events, or certainty ("must have" vs "was"), no softening and no added
  force, no new profanity the source does not earn, imagery kept.
- The player's gender: never added where the line has none (gender table in AGENT_REVIEW).
- If `before` was right and `en` drifted, restore the meaning (keep the editor's better
  wording where it does not hurt). If both are wrong, fix it to the source.
- Rows with `flag: ACC` and every `todo` item: settle them against the source (edit or
  keep) and say which in notes.
- Do not restyle a row that is accurate. Do not touch dot runs, ☆★, codes or fixed terms.

## Output
`work/translation/en/review/recheck/R###.out.json`, only rows you changed:
`{"rows": {"NN:offs": "English"}, "notes": ["NN:offs: FIX - ...", "NN:offs: KEEP - ..."]}`
Tags: FIX (meaning restored, say what), KEEP (a flag/todo you left), UNSURE (could not
settle). Run `python tools/review.py check recheck R###` until it prints OK. Edit no other
file. Do not print long Japanese text to the console.

## Final report (max 6 lines)
`R### rows examined N / rows in unit N; changed M; check OK|FAIL`, then the main points.
