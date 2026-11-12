"""Merge checked slice outputs into the scene working files.

    python tools/apply_slices.py [--force] [S012 ...]   (default: every slice with output)

Only slices that pass tools/check_slice.py are merged unless --force. Then run
tools/strip_jp.py to refresh the .en.json copies.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_slice import check, SL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')


def main():
    # after the first pass, review fixes, unify_tm and fix_terms live only in the scene
    # files: re-merging first-pass output would undo them
    if os.path.isdir(os.path.join(ROOT, 'work', 'translation', 'en', 'review')) \
            and '--first-pass' not in sys.argv:
        raise SystemExit('review has started: use tools/review.py apply (or pass --first-pass)')
    force = '--force' in sys.argv
    names = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not names:
        names = sorted(os.path.basename(p)[:4] for p in glob.glob(os.path.join(SL, 'S???.out.json')))
    updates = {}
    skipped = []
    for n in names:
        probs = check(n)
        if probs and not force:
            skipped.append(n)
            continue
        out = json.load(open(os.path.join(SL, n + '.out.json'), encoding='utf-8'))['rows']
        updates.update({k: v for k, v in out.items() if isinstance(v, str) and v.strip()})
    changed = 0
    for f in sorted(glob.glob(os.path.join(SCENES, 'SCE??.json'))):
        rows = json.load(open(f, encoding='utf-8'))
        dirty = False
        for r in rows:
            if r['id'] in updates and r['en'] != updates[r['id']]:
                r['en'] = updates[r['id']]
                dirty = True
                changed += 1
        if dirty:
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=1)
                fh.write('\n')
    print('%d rows updated from %d slices; skipped (failed checks): %s'
          % (changed, len(names) - len(skipped), ' '.join(skipped) or 'none'))


if __name__ == '__main__':
    main()
