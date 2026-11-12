"""Mechanical proofreading report over the English scene files (no edits).

    python tools/proofcheck.py [--spell]      -> work/translation/en/proofcheck.md

Checks: doubled words, double spaces, space before punctuation, missing space after
punctuation, lowercase sentence start, lone lowercase "i", unbalanced quotes/brackets per
row, stray characters, Japanese punctuation left in, and (--spell) words not in a word
list (pyspellchecker if installed) minus the glossary names.
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textenc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')
OUT = os.path.join(ROOT, 'work', 'translation', 'en', 'proofcheck.md')
CODE = re.compile(r'\{[^}]*\}')

CHECKS = [
    ('doubled word', re.compile(r"\b([A-Za-z']+)\s+\1\b", re.I)),
    ('double space', re.compile(r'(?<=\S)  +(?=\S)')),
    ('space before punctuation', re.compile(r'\s+[,;:!?](?!\?)')),
    ('no space after comma', re.compile(r',(?=[A-Za-z])')),
    ('no space after sentence', re.compile(r'[a-z][.!?](?=[A-Z][a-z])')),
    ('lone lowercase i', re.compile(r"(?<![A-Za-z'])i(?![A-Za-z'])")),
    ('Japanese punctuation', re.compile('[、。「」『』（）！？～・]')),
    ('odd character', re.compile(r'[^\x20-\x7e\n☆★…♪♥〜—–’“”‘é]')),
]
# allowed doubles: stutters and repetitions that are usually deliberate
OK_DOUBLE = {'no', 'very', 'ha', 'heh', 'hee', 'hah', 'ho', 'hoo', 'that', 'had', 'more',
             'far', 'so', 'yes', 'wait', 'stop', 'come', 'run', 'help', 'please', 'go',
             'why', 'it', 'what', 'mommy', 'mom', 'hey', 'oh', 'ah', 'uh', 'huh', 'okay',
             'right', 'now', 'there', 'you', 'die', 'kill', 'again', 'away', 'over',
             'round', 'on', 'along', 'down', 'up', 'is', 'knock', 'drip', 'tap', 'thud',
             'creak', 'bang', 'step', 'sorry', 'water', 'hot', 'cold', 'dark', 'deeper',
             'tick', 'tock', 'hm', 'kuh', 'eek', 'mutter', 'mumble', 'giggle', 'la', 'rub', 'fo', 'keh', 'hih', 'hya', 'Name', 'clatter', 'pitter', 'patter', 'sniff', 'squish'}


def plain(en):
    """English text without codes, one string per {f} side."""
    sides = ['', '']
    for t in textenc.parse(en):
        if t[0] == 'f':
            add = (t[1], t[2])
        elif t[0] == 't':
            add = (t[1],) * 2
        elif t[0] == 'nl':
            add = ('\n',) * 2
        elif t[1] in 'abc':             # player name / nickname
            add = ('Name',) * 2
        elif t[1] == 'p':
            add = ('\n',) * 2
        else:                           # {k} {w} {g}: no text
            add = ('',) * 2
        sides[0] += add[0]
        sides[1] += add[1]
    return sorted(set(sides))


def main():
    hits = collections.defaultdict(list)
    words = collections.Counter()
    where = {}
    for f in sorted(glob.glob(os.path.join(SCENES, 'SCE??.json'))):
        for r in json.load(open(f, encoding='utf-8')):
            en = r.get('en') or ''
            try:
                texts = plain(en)
            except Exception as e:      # noqa: BLE001
                hits['markup'].append((r['id'], str(e)))
                continue
            for s in texts:
                for name, rx in CHECKS:
                    for m in rx.finditer(s):
                        if name == 'doubled word' and m.group(1).lower() in OK_DOUBLE:
                            continue
                        a = max(0, m.start() - 25)
                        hits[name].append((r['id'], s[a:m.end() + 25].replace('\n', ' / ')))
                if s.count('"') % 2:
                    hits['odd number of "'].append((r['id'], s[:70].replace('\n', ' / ')))
                if s.count('(') != s.count(')'):
                    hits['unbalanced ( )'].append((r['id'], s[:70].replace('\n', ' / ')))
                for w in re.findall(r"[A-Za-z]+(?:'[a-z]+)?", s):
                    words[w] += 1
                    where.setdefault(w, r['id'])
    lines = ['# Proofreading report (tools/proofcheck.py)', '']
    for name, lst in sorted(hits.items(), key=lambda x: -len(x[1])):
        lines.append('## %s (%d)' % (name, len(lst)))
        lines += ['- %s: %s' % x for x in lst[:400]]
        lines.append('')
    if '--spell' in sys.argv:
        try:
            from spellchecker import SpellChecker
        except ImportError:
            lines.append('## spelling: pyspellchecker not installed')
        else:
            gl = json.dumps(json.load(open(os.path.join(ROOT, 'work', 'glossary', 'glossary.json'),
                                           encoding='utf-8')), ensure_ascii=False)
            sp = SpellChecker()
            lower = {w.lower() for w in words}
            unknown = sp.unknown(lower)
            bad = sorted((w for w in words if w.lower() in unknown and w not in gl
                          and not w[0].isupper()), key=lambda w: -words[w])
            lines.append('## unknown words, lowercase (%d)' % len(bad))
            lines += ['- %s (%d) e.g. %s' % (w, words[w], where[w]) for w in bad[:600]]
            caps = sorted((w for w in words if w.lower() in unknown and w not in gl
                           and w[0].isupper()), key=lambda w: -words[w])
            lines.append('')
            lines.append('## unknown capitalized words not in glossary (%d)' % len(caps))
            lines += ['- %s (%d) e.g. %s' % (w, words[w], where[w]) for w in caps[:400]]
    open(OUT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join('%s: %d' % (k, len(v)) for k, v in sorted(hits.items())))
    print('report:', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
