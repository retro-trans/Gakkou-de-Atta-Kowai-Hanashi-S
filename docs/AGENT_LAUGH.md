# Laugh pass (proofreading, agent brief)

Game: *Gakkou de Atta Kowai Hanashi S* (PlayStation 1996), a horror sound novel. Different
translators wrote the same laughs differently, and "Heh heh" (Akemi Iwashita's signature
laugh) leaked onto other characters. Your job: for every laugh in your rows, find who laughs
and give that laugh the form from the map below. Nothing else.

## Input
`work/translation/en/review/laugh/L###.json`: rows with `id`, `op`, `jp` (source) and `en`
(current English), each containing at least one chuckle/giggle. Read the file in parts with an
offset until the last row. To find the speaker, read the rows around it in
`work/translation/en/scenes/SCE<NN>.json` (Read with an offset near the row, not the whole
file). Storytellers by scene: 01-06 Shindo, 08-13 Arai, 15-20 Kazama, 22-28 Hosoda,
29-34 Iwashita, 36-41 Fukuzawa; 00, 07, 14, 21, 35, 42-70 are the seventh-story / ending
routes (anyone, read the context; Taguchi appears in 47).

## Laugh map (by speaker, then by the Japanese form)
- **Iwashita** (any ふふ / うふふ / くすくす / ふっ): "Heh heh" (one "heh" per ふ, at least two;
  "Heh..." alone for a single ふっ). Only Iwashita uses "Heh heh".
- **Fukuzawa, Taguchi, other girls and women** (ふふ / うふふ / くすくす): "Hee hee".
- **Hosoda** (ふふ / うひひ / えへへ / へへ): "Hee hee" for ふふ / うひひ, "Ehehe" for えへへ / へへ.
- **Kazama** (ふふ / ふっふっふ / くっくっく): "Hm hm hm" (smug); うふふ: "Ooh-hoo-hoo".
- **Arai, Hino, Shindo, other men and boys** (ふふ / ふっふっふ): "Hm hm"; くくく / くっくっく:
  "Kuh kuh kuh"; へへ / へっへっへ: "Heh" or "Hehheh" (never "Heh heh").
- ひひひ / いひひ / ひっひっひ (cackle, anyone but Iwashita): "Hee hee hee"; the old woman in
  scene 02 keeps "Ee-hee-hee".
- はは / ははは / あはは: "Ha ha" / "Ha ha ha" / "Ah ha ha" (no change needed if already so).
- Keep the number of syllables the Japanese has (ふふふ = three), the punctuation, dots, ☆★
  and codes around it. Keep a laugh the English describes in words ("she giggled") as words,
  but "giggle" is not for Iwashita (use "laughed softly").
- If the speaker cannot be settled from the scene, change nothing and note UNSURE.

## Output
`work/translation/en/review/laugh/L###.out.json`, only rows you changed:
`{"rows": {"NN:offs": "English"}, "notes": ["NN:offs: LAUGH - Kazama, ふふふ -> Hm hm hm", ...]}`.
Run `python tools/review.py check laugh L###` until it prints OK. Edit no other file. Do not
print long Japanese text to the console.

## Final report (max 6 lines)
`L### rows examined N / rows in unit N; changed M; check OK|FAIL`, the last row id you checked,
and a count of laughs per speaker you set.
