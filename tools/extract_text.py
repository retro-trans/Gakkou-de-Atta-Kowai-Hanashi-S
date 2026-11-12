"""Extract the script text into translation working files.

    python tools/extract_text.py            -> work/translation/en/scenes/SCExx.json

One row per string operand that holds player-visible text, in bytecode order:
    {"id": "29:0864", "op": "text" | "choice", "jp": <markup>, "en": ""}
id = scene number : string offset in the original SDATAxx.BIN (hex).
Markup is described in tools/textenc.py. Existing "en" values are kept (the file is
merged, never overwritten). The working files hold Japanese and are git-ignored;
tools/strip_jp.py writes the .en.json copies that may be committed.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sdata import all_scripts  # noqa: E402
from textenc import jp_to_markup  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')
KIND = {0x4A: 'text', 0x04: 'choice'}


def scene_rows(s):
    num = int(s.name[5:7])
    rows = []
    seen = set()
    for at, v, op in s.pool_refs():
        if op not in KIND or v in seen:
            continue
        seen.add(v)
        raw = s.data[v:s.data.index(b'\0', v)]
        rows.append({'id': '%02d:%04x' % (num, v), 'op': KIND[op], 'jp': jp_to_markup(raw), 'en': ''})
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for p, s in all_scripts():
        name = 'SCE%s.json' % s.name[5:7]
        path = os.path.join(OUT, name)
        rows = scene_rows(s)
        old = {}
        for src in (path, path[:-5] + '.en.json'):
            if os.path.exists(src):
                for r in json.load(open(src, encoding='utf-8')):
                    if r.get('en'):
                        old.setdefault(r['id'], r['en'])
        for r in rows:
            r['en'] = old.get(r['id'], '')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
            f.write('\n')
        total += len(rows)
    print('%d rows written to %s' % (total, OUT))


if __name__ == '__main__':
    main()
