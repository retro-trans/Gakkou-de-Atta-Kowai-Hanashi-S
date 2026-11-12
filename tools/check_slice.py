"""Validate a translated slice before it is merged.

    python tools/check_slice.py S012 [S013 ...]      (or 'all')

Checks per row: every id translated; markup parses; only letters the font has
(tools/vwf.py); the same control codes as the source ({p} {k} {w} {g} {a} {b} {c},
{f:..|..} count, number of \\n) and the same ending; no Japanese left; encodes and fits
(no over-wide word; a choice in 3 lines; long paragraphs get page breaks). Prints problems; exit 1 if any.
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textenc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SL = os.path.join(ROOT, 'work', 'translation', 'en', 'slices')
JP = re.compile('[぀-ヿ一-鿿＀-￯]')


def tokens(m):
    c = Counter()
    for t in textenc.parse(m):
        if t[0] == 'c':
            c['{%s}' % t[1]] += 1
        elif t[0] == 'f':
            c['{f}'] += 1
        elif t[0] == 'nl':
            c['\\n'] += 1
    return c


def ending(m):
    for e in ('{p}\n', '{p}', '\n'):
        if m.endswith(e):
            return e
    return ''


def check_row(r, en):
    probs = []
    if not isinstance(en, str) or not en.strip():
        return ['missing translation']
    if JP.search(en):
        probs.append('Japanese left in the English')
    try:
        src, dst = tokens(r['jp']), tokens(en)
    except ValueError as e:
        return ['markup: %s' % e]
    if r['op'] == 'choice':
        if dst:
            probs.append('choice must be plain text (no codes, no line breaks)')
    else:
        for k in set(src) | set(dst):
            if src[k] != dst[k]:
                probs.append('%s: source has %d, translation %d' % (k, src[k], dst[k]))
        if ending(r['jp']) != ending(en):
            probs.append('ending differs: source %r, translation %r' % (ending(r['jp']), ending(en)))
    for t in textenc.parse(en):
        if t[0] == 'f' and ('\n' in t[1] or '\n' in t[2]):
            probs.append('line break inside {f:...}')
    warn = []
    try:
        if r['op'] == 'choice':
            textenc.encode_choice(en, warn)
        else:
            textenc.encode(en, warn)
    except ValueError as e:
        probs.append(str(e))
    return probs + warn


def check(name):
    sl = json.load(open(os.path.join(SL, name + '.json'), encoding='utf-8'))
    p = os.path.join(SL, name + '.out.json')
    if not os.path.exists(p):
        return ['%s: no output file' % name]
    try:
        out = json.load(open(p, encoding='utf-8'))
    except ValueError as e:
        return ['%s: bad JSON: %s' % (name, e)]
    rows = out.get('rows', {})
    probs = []
    for r in sl['rows']:
        for pr in check_row(r, rows.get(r['id'])):
            probs.append('%s %s: %s' % (name, r['id'], pr))
    extra = set(rows) - {r['id'] for r in sl['rows']}
    if extra:
        probs.append('%s: unknown ids %s' % (name, sorted(extra)[:5]))
    return probs


def main():
    names = sys.argv[1:]
    if names == ['all']:
        names = [x['slice'] for x in json.load(open(os.path.join(SL, 'index.json')))]
    bad = 0
    for n in names:
        probs = check(n)
        if probs:
            bad += 1
        for p in probs:
            print(p)
        if not probs:
            print('%s OK' % n)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
