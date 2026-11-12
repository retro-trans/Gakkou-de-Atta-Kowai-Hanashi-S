"""Translation memory: rows with identical Japanese (same op, same scene, >= MIN_JP chars)
should read the same in English. Across scenes and for short rows the context differs.

    python tools/unify_tm.py            report groups whose English differs
    python tools/unify_tm.py --apply    rewrite them to the chosen English
    python tools/unify_tm.py --apply --pin work/translation/en/tm_pins.json

Choice per group: a pinned English if tm_pins.json has one for a member id
({"NN:offs": "english"} - the pinned row's English wins for its whole group), else the
most common English, ties broken by the earliest row (scene order). Report goes to
work/translation/en/tm_report.md (English only; Japanese is never printed).
"""
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')
MIN_JP = 15   # short rows (はい, え？) answer different things in different places
REPORT = os.path.join(ROOT, 'work', 'translation', 'en', 'tm_report.md')


def load():
    files = {}
    for f in sorted(glob.glob(os.path.join(SCENES, 'SCE??.json'))):
        files[f] = json.load(open(f, encoding='utf-8'))
    return files


def groups(files):
    by = collections.defaultdict(list)
    for f, rows in files.items():
        for r in rows:
            if r.get('en'):
                if len(r['jp']) >= MIN_JP:
                    by[(r['id'][:2], r['op'], r['jp'])].append(r)
    return [g for g in by.values() if len(g) > 1 and len({r['en'] for r in g}) > 1]


def choose(g, pins):
    for r in g:
        if r['id'] in pins:
            return pins[r['id']]
    cnt = collections.Counter(r['en'] for r in g)
    best = max(cnt.values())
    return next(r['en'] for r in g if cnt[r['en']] == best)


def main():
    apply = '--apply' in sys.argv
    pins = {}
    if '--pin' in sys.argv:
        pins = json.load(open(sys.argv[sys.argv.index('--pin') + 1], encoding='utf-8'))
    files = load()
    gs = groups(files)
    out = ['# Translation memory report', '',
           '%d groups of identical Japanese rows with differing English.' % len(gs), '']
    changed = 0
    for g in sorted(gs, key=lambda g: g[0]['id']):
        pick = choose(g, pins)
        out.append('## ' + ', '.join(r['id'] for r in g))
        for en in sorted({r['en'] for r in g}, key=lambda e: e != pick):
            ids = [r['id'] for r in g if r['en'] == en]
            out.append('- %s `%s` (%s)' % ('**keep**' if en == pick else 'was ', en.replace('\n', '\\n'),
                                            ' '.join(ids)))
        out.append('')
        if apply:
            for r in g:
                if r['en'] != pick:
                    r['en'] = pick
                    changed += 1
    open(REPORT, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    if apply:
        for f, rows in files.items():
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=1)
                fh.write('\n')
    print('%d groups differ; report %s%s' % (len(gs), os.path.relpath(REPORT, ROOT),
                                           '; %d rows rewritten' % changed if apply else ''))


if __name__ == '__main__':
    main()
