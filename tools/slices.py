"""Cut the scene rows into translation slices (BASE_RULES.md: 80 consecutive rows).

    python tools/slices.py make        -> work/translation/en/slices/S###.json + index.json
    python tools/slices.py status      -> slices with / without a checked output

A slice never crosses a scene. Each slice file:
    {"slice": "S012", "scene": "05", "narrator_hint": "...", "prev": "S011", "next": "S013",
     "rows": [{"id", "op", "jp"}...]}
Agents write work/translation/en/slices/S###.out.json: {"rows": {id: en}, "notes": [...]}
"""
import glob
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')
OUT = os.path.join(ROOT, 'work', 'translation', 'en', 'slices')
SIZE = 80

HINT = {}
for a, b, who in ((1, 6, 'Makoto Shindo (storyteller)'), (8, 13, 'Shoji Arai (storyteller)'),
                  (15, 20, 'Nozomu Kazama (storyteller)'), (22, 28, 'Tomoharu Hosoda (storyteller)'),
                  (29, 34, 'Akemi Iwashita (storyteller)'), (36, 41, 'Reiko Fukuzawa (storyteller)')):
    for n in range(a, b + 1):
        HINT[n] = who
HINT[0] = 'prologue: the protagonist arrives at the newspaper club room'
for n in (7, 14, 21, 35) + tuple(range(42, 71)):
    HINT.setdefault(n, 'seventh-storyteller / ending routes: several characters; work out the speaker from context')


def make():
    os.makedirs(OUT, exist_ok=True)
    index = []
    k = 0
    plan = []
    for f in sorted(glob.glob(os.path.join(SCENES, 'SCE??.json'))):
        scene = os.path.basename(f)[3:5]
        rows = json.load(open(f, encoding='utf-8'))
        n = math.ceil(len(rows) / SIZE)
        size = math.ceil(len(rows) / n)
        for i in range(n):
            part = rows[i * size:(i + 1) * size]
            plan.append((scene, part))
    follow = choice_targets()
    for i, (scene, part) in enumerate(plan):
        name = 'S%03d' % i
        doc = {'slice': name, 'scene': scene, 'narrator_hint': HINT[int(scene)],
               'prev': 'S%03d' % (i - 1) if i else None,
               'next': 'S%03d' % (i + 1) if i + 1 < len(plan) else None,
               'rows': [dict({'id': r['id'], 'op': r['op'], 'jp': r['jp']},
                             **({'follows_choice': follow[r['id']]} if r['id'] in follow else {}))
                        for r in part]}
        with open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8') as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
            fh.write('\n')
        index.append({'slice': name, 'scene': scene, 'rows': len(part),
                      'chars': sum(len(r['jp']) for r in part)})
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w'), indent=1)
    print('%d slices, %d rows' % (len(index), sum(x['rows'] for x in index)))


def choice_targets():
    """{text row id: [choice ids that jump to it]} from the bytecode (op 04 target)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sdata import all_scripts
    follow = {}
    for _, s in all_scripts():
        num = int(s.name[5:7])
        ins = s.insns
        idx = {pc: i for i, (pc, *_r) in enumerate(ins)}
        for pc, op, ln, vals in ins:
            if op != 0x04 or vals[1][1] not in idx:
                continue
            for j in range(idx[vals[1][1]], min(idx[vals[1][1]] + 40, len(ins))):
                o = ins[j]
                if o[1] == 0x4A:
                    follow.setdefault('%02d:%04x' % (num, o[3][0][1]), []).append(
                        '%02d:%04x' % (num, vals[0][1]))
                    break
                if o[1] in (0x04, 0x01, 0xFF):
                    break
    return follow


def status():
    idx = json.load(open(os.path.join(OUT, 'index.json')))
    done = [x['slice'] for x in idx if os.path.exists(os.path.join(OUT, x['slice'] + '.out.json'))]
    print('%d/%d slices have output' % (len(done), len(idx)))
    print('missing:', ' '.join(x['slice'] for x in idx if x['slice'] not in done))


if __name__ == '__main__':
    {'make': make, 'status': status}[sys.argv[1]]()
