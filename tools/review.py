"""Review passes over the merged translation (BASE_RULES.md "Shared review workflow").

    python tools/review.py make acc|edit         export review units
    python tools/review.py check acc|edit S012 ... validate an agent's output ('all' = every output)
    python tools/review.py apply acc|edit        merge checked outputs, then tools/fix_terms.py
    python tools/review.py status acc|edit

Stages
  acc   accuracy, per slice S###, Japanese + English (brief docs/AGENT_REVIEW.md)
  edit  editorial, chunks E### of up to EDIT_ROWS consecutive rows inside one scene,
        English only (brief docs/AGENT_EDIT.md); each row may carry `returns`, the
        accuracy stage's RETURN notes for it.
Files: work/translation/en/review/<stage>/<unit>.json (input) and <unit>.out.json (agent):
    {"rows": {"NN:offs": "new English", ...},   only rows the agent changed
     "notes": ["NN:offs: ...", ...]}
apply also collects every unit's notes into review/<stage>/notes.md.
Inputs carry `todo`: the lines of work/translation/en/review_todo.md that name a row,
the unit's slices or its scene.
"""
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_slice import check_row  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN = os.path.join(ROOT, 'work', 'translation', 'en')
SCENES = os.path.join(EN, 'scenes')
SL = os.path.join(EN, 'slices')
TODO = os.path.join(EN, 'review_todo.md')
EDIT_ROWS = 200
ID = re.compile(r'\b\d\d:[0-9a-f]{3,5}\b')


def stage_dir(stage):
    d = os.path.join(EN, 'review', stage)
    os.makedirs(d, exist_ok=True)
    return d


def scene_rows():
    rows = {}
    for f in sorted(glob.glob(os.path.join(SCENES, 'SCE??.json'))):
        for r in json.load(open(f, encoding='utf-8')):
            rows[r['id']] = r
    return rows


def slices():
    return [json.load(open(os.path.join(SL, x['slice'] + '.json'), encoding='utf-8'))
            for x in json.load(open(os.path.join(SL, 'index.json')))]


def todo_lines():
    lines = []
    for ln in open(TODO, encoding='utf-8'):
        if ln.startswith('- '):
            lines.append(ln.rstrip())
        elif ln.startswith('  ') and lines:      # continuation of the item above
            lines[-1] += ' ' + ln.strip()
    return lines


def todo_for(ids, names, scene, lines):
    out = []
    for ln in lines:
        named = set(ID.findall(ln))
        if named & ids or any(re.search(r'\b%s\b' % n, ln) for n in names):
            out.append(ln.strip())
        elif not named and re.search(r'\b(?:SCE|scene |Scene )%s\b' % scene, ln):
            out.append(ln.strip())
    return out


def return_notes():
    """{row id: [RETURN notes]} from the accuracy stage."""
    p = os.path.join(EN, 'review', 'acc', 'notes.md')
    out = {}
    if not os.path.exists(p):
        return out
    for ln in open(p, encoding='utf-8'):
        if 'RETURN' not in ln:
            continue
        for rid in set(ID.findall(ln)):
            out.setdefault(rid, []).append(ln.strip()[2:])
    return out


STAGES = ['acc', 'edit', 'recheck', 'laugh']
RECHECK_ROWS = 120
LAUGH = re.compile(r"\b(?:[Hh]eh(?:[ -]heh)+|[Hh]ehe(?:he)*|[Hh]ee(?:[ -]hee)+|[Hh]m(?:[ -]hm)+|"
                   r"[Ff]u(?:-?fu)+|[Uu]fu(?:-?fu)*|[Oo]oh-hoo(?:-hoo)*|[Kk]uh(?:[ -]kuh)+)\b")
LAUGH_ROWS = 180


def make_laugh(d, rows):
    """Proofreading: one laugh per character. Every row with a chuckle/giggle in the
    English, with the Japanese, for an agent to name the speaker and apply the laugh map
    (docs/AGENT_LAUGH.md)."""
    for p in glob.glob(os.path.join(d, 'L???.json')):
        os.remove(p)
    want = [i for i, r in rows.items() if LAUGH.search(r.get('en') or '')]
    units = [want[k:k + LAUGH_ROWS] for k in range(0, len(want), LAUGH_ROWS)]
    for k, ids in enumerate(units):
        name = 'L%03d' % k
        write(d, name, {'unit': name, 'scenes': sorted({i[:2] for i in ids}), 'todo': [],
                        'rows': [{'id': i, 'op': rows[i]['op'], 'jp': rows[i]['jp'],
                                  'en': rows[i]['en']} for i in ids]})
    print('%d laugh units in %s (%d rows)' % (len(units), os.path.relpath(d, ROOT), len(want)))


def make_recheck(d, rows, lines):
    """Accuracy recheck of the editorial changes (BASE_RULES: recheck substantive
    editorial changes before proofreading). One unit R### per <= RECHECK_ROWS edited rows
    of consecutive scenes: jp, the English before and after the editorial pass, its note."""
    ed = stage_dir('edit')
    before, notes, flagged = {}, {}, set()
    for p in sorted(glob.glob(os.path.join(ed, 'E???.json'))):
        for r in json.load(open(p, encoding='utf-8'))['rows']:
            before[r['id']] = r['en']
    changed = set()
    for p in sorted(glob.glob(os.path.join(ed, 'E???.out.json'))):
        out = json.load(open(p, encoding='utf-8'))
        changed |= set(out.get('rows', {}))
        for n in out.get('notes', []):
            for rid in set(ID.findall(n)):
                notes.setdefault(rid, []).append(n)
                if ' ACC' in n:
                    flagged.add(rid)
    words = lambda s: re.findall(r"[A-Za-z']+", s.lower())
    todo = [ln for ln in lines if '[acc review]' in ln or '[recheck]' in ln]
    for ln in todo:
        flagged |= set(ID.findall(ln))
    order = list(rows)          # scene order
    want = [i for i in order if (i in changed and words(before[i]) != words(rows[i]['en']))
            or i in flagged]
    for p in glob.glob(os.path.join(d, 'R???.json')):
        os.remove(p)        # inputs only; outputs (.out.json) are kept
    units, cur = [], []
    for i in want:
        if len(cur) >= RECHECK_ROWS:
            units.append(cur)
            cur = []
        cur.append(i)
    if cur:
        units.append(cur)
    for k, ids in enumerate(units):
        name = 'R%03d' % k
        doc = {'unit': name, 'scenes': sorted({i[:2] for i in ids}),
               'todo': todo_for(set(ids), [name], None, todo),
               'rows': [dict({'id': i, 'op': rows[i]['op'], 'jp': rows[i]['jp'],
                              'before': before.get(i, rows[i]['en']), 'en': rows[i]['en']},
                             **({'flag': 'ACC'} if i in flagged else {}),
                             **({'edit_notes': notes[i]} if i in notes else {}))
                        for i in ids]}
        write(d, name, doc)
    print('%d recheck units in %s (%d rows)' % (len(units), os.path.relpath(d, ROOT), len(want)))


def make(stage):
    d = stage_dir(stage)
    rows = scene_rows()
    lines = todo_lines()
    if stage == 'recheck':
        return make_recheck(d, rows, lines)
    if stage == 'laugh':
        return make_laugh(d, rows)
    if stage == 'acc':
        n = 0
        for sl in slices():
            ids = {r['id'] for r in sl['rows']}
            doc = {'slice': sl['slice'], 'scene': sl['scene'], 'narrator_hint': sl['narrator_hint'],
                   'prev': sl['prev'], 'next': sl['next'],
                   'todo': todo_for(ids, [sl['slice']], sl['scene'], lines),
                   'rows': [dict(r, en=rows[r['id']]['en']) for r in sl['rows']]}
            write(d, sl['slice'], doc)
            n += 1
        print('%d review slices in %s' % (n, os.path.relpath(d, ROOT)))
        return
    # edit: merge consecutive slices of a scene into chunks of <= EDIT_ROWS rows
    rets = return_notes()
    chunks, cur = [], None
    for sl in slices():
        if cur and cur['scene'] == sl['scene'] and len(cur['rows']) + len(sl['rows']) <= EDIT_ROWS:
            cur['rows'] += sl['rows']
            cur['slices'].append(sl['slice'])
        else:
            cur = {'scene': sl['scene'], 'narrator_hint': sl['narrator_hint'],
                   'slices': [sl['slice']], 'rows': list(sl['rows'])}
            chunks.append(cur)
    for i, c in enumerate(chunks):
        name = 'E%03d' % i
        ids = {r['id'] for r in c['rows']}
        doc = {'chunk': name, 'scene': c['scene'], 'narrator_hint': c['narrator_hint'],
               'slices': c['slices'],
               'prev': 'E%03d' % (i - 1) if i else None,
               'next': 'E%03d' % (i + 1) if i + 1 < len(chunks) else None,
               'todo': todo_for(ids, c['slices'], c['scene'], [ln for ln in lines if 'editorial' in ln.lower()]),
               'rows': [dict({'id': r['id'], 'op': r['op'], 'en': rows[r['id']]['en']},
                             **({'follows_choice': r['follows_choice']} if 'follows_choice' in r else {}),
                             **({'returns': rets[r['id']]} if r['id'] in rets else {}))
                        for r in c['rows']]}
        write(d, name, doc)
    print('%d editorial chunks in %s (%d rows)' % (len(chunks), os.path.relpath(d, ROOT),
                                                   sum(len(c['rows']) for c in chunks)))


def write(d, name, doc):
    with open(os.path.join(d, name + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write('\n')


def check(stage, name, src_rows=None):
    d = stage_dir(stage)
    unit = json.load(open(os.path.join(d, name + '.json'), encoding='utf-8'))
    p = os.path.join(d, name + '.out.json')
    if not os.path.exists(p):
        return ['%s: no output file' % name]
    try:
        out = json.load(open(p, encoding='utf-8'))
    except ValueError as e:
        return ['%s: bad JSON: %s' % (name, e)]
    allrows = src_rows or scene_rows()      # the Japanese source comes from the scene files
    ids = {r['id'] for r in unit['rows']}
    probs = []
    for rid, en in out.get('rows', {}).items():
        if rid not in ids:
            probs.append('%s: unknown id %s' % (name, rid))
            continue
        probs += ['%s %s: %s' % (name, rid, pr) for pr in check_row(allrows[rid], en)]
    if not isinstance(out.get('notes', []), list):
        probs.append('%s: notes must be a list' % name)
    return probs


def outputs(stage):
    return sorted(os.path.basename(p)[:4] for p in glob.glob(os.path.join(stage_dir(stage), '[SERL]???.out.json')))


def units(stage):
    return sorted(os.path.basename(p)[:4] for p in glob.glob(os.path.join(stage_dir(stage), '[SERL]???.json')))


def apply(stage):
    later = [s for s in STAGES[STAGES.index(stage) + 1:] if outputs(s)]
    if later and '--force' not in sys.argv:
        raise SystemExit('refusing: stage %s has outputs; re-applying %s would revert them '
                         '(pass --force if that is really wanted)' % (' '.join(later), stage))
    d = stage_dir(stage)
    allrows = scene_rows()
    updates, notes, skipped = {}, [], []
    for n in outputs(stage):
        if check(stage, n, allrows):
            skipped.append(n)
            continue
        out = json.load(open(os.path.join(d, n + '.out.json'), encoding='utf-8'))
        updates.update(out.get('rows', {}))
        notes += ['## %s' % n] + ['- ' + x for x in out.get('notes', [])] + ['']
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
    open(os.path.join(d, 'notes.md'), 'w', encoding='utf-8').write('\n'.join(notes) + '\n')
    print('%d rows changed from %d outputs; skipped (failed checks): %s'
          % (changed, len(outputs(stage)) - len(skipped), ' '.join(skipped) or 'none'))
    # BASE_RULES: agent fixes first, the name script after
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'fix_terms.py'), '--apply'], check=True)


def main():
    cmd, stage = sys.argv[1], sys.argv[2]
    if cmd == 'make':
        make(stage)
    elif cmd == 'check':
        names = sys.argv[3:]
        if names == ['all']:
            names = outputs(stage)
        bad = 0
        allrows = scene_rows()
        for n in names:
            probs = check(stage, n, allrows)
            bad += bool(probs)
            print('\n'.join(probs) if probs else '%s OK' % n)
        sys.exit(1 if bad else 0)
    elif cmd == 'apply':
        apply(stage)
    elif cmd == 'status':
        done = outputs(stage)
        alln = units(stage)
        print('%d/%d outputs' % (len(done), len(alln)))
        print('missing:', ' '.join(s for s in alln if s not in done))


if __name__ == '__main__':
    main()
