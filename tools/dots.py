"""Normalize dot runs in the English (proofreading, review_todo [proofread] items).

    python tools/dots.py            dry run: counts and examples
    python tools/dots.py --apply

Convention (docs/AGENT_REVIEW.md): the ordinary ……  (1-3 … characters) is "..."; a longer
run of N … characters (a silence) is ceil(1.5 * N) periods.
Per row, the dot runs in the Japanese (… and ‥ characters, ‥ counting half) are paired in
order with the dot runs in the English (3+ periods or any raw …). When the counts match,
each English run takes the length its Japanese run asks for. When they don't, only raw …
characters are converted (k characters -> "..." or ceil(1.5 * k)) and the row is reported.
"""
import glob
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')
JP_RUN = re.compile('[…‥]+')
EN_RUN = re.compile(r'(?:\.{3,}|…+)(?:\.|…)*')


def jp_len(run):
    return run.count('…') + run.count('‥') / 2


def target(n):
    return '...' if n < 4 else '.' * math.ceil(1.5 * n)


def raw_fix(run):
    if '…' not in run:
        return run
    k = run.count('…') + run.count('.') / 3
    return target(k)


def fix_text(jp, en):
    """Return (new English, mode) for one text (a whole row or one {f} side)."""
    jr = [jp_len(m) for m in JP_RUN.findall(jp)]
    er = list(EN_RUN.finditer(en))
    if len(jr) == len(er):
        out, last = [], 0
        for m, n in zip(er, jr):
            out.append(en[last:m.start()])
            out.append(target(n))
            last = m.end()
        out.append(en[last:])
        return ''.join(out), 'paired'
    # counts differ (a run dropped or split in English): pair only the long runs
    long_jp = [n for n in jr if n >= 4]
    long_en = [m for m in er if len(m.group(0).replace('…', '...')) >= 6]
    if long_en and len(long_jp) == len(long_en):
        tgt = {m.start(): target(n) for m, n in zip(long_en, long_jp)}
        return EN_RUN.sub(lambda m: tgt.get(m.start(), raw_fix(m.group(0))), en), 'long-paired'
    if long_en and not long_jp:      # the source has only ordinary …… here
        return EN_RUN.sub(lambda m: '...' if len(m.group(0).replace('…', '...')) >= 6
                          else raw_fix(m.group(0)), en), 'long-paired'
    return EN_RUN.sub(lambda m: raw_fix(m.group(0)), en), 'unpaired'


def main():
    apply = '--apply' in sys.argv
    changed = paired = unpaired_left = 0
    examples = []
    leftover = []
    for f in sorted(glob.glob(os.path.join(SCENES, 'SCE??.json'))):
        rows = json.load(open(f, encoding='utf-8'))
        dirty = False
        for r in rows:
            en = r.get('en') or ''
            new, mode = fix_text(r['jp'], en)
            if mode == 'unpaired' and re.search(r'\.{6,}', new):
                leftover.append(r['id'])
            if new != en:
                changed += 1
                paired += mode == 'paired'
                if len(examples) < 25:
                    examples.append((r['id'], mode, [m.group(0) for m in EN_RUN.finditer(en)],
                                     [m.group(0) for m in EN_RUN.finditer(new)]))
                r['en'] = new
                dirty = True
        if apply and dirty:
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=1)
                fh.write('\n')
    for e in examples:
        print(e[0], e[1], [len(x) for x in e[2]], '->', [len(x) for x in e[3]])
    print('%d rows changed (%d paired); %d unpaired rows still with 6+ dots: %s'
          % (changed, paired, len(leftover), ' '.join(leftover[:40])))
    print('applied' if apply else 'dry run')


if __name__ == '__main__':
    main()
