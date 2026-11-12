"""English menu / UI strings of the EXE (work/translation/en/ui.json).

    python tools/uitext.py status        what is translated, in place, moved, still Japanese
    python tools/uitext.py init          create ui.json from work/ui/exe_strings.json

ui.json rows: {id, jp, en, note}
  id  uiNNN   a string of the inventory (work/ui/exe_strings.json); written in place when it
              fits its slot, otherwise moved and every reference repointed (pointer words,
              lui/lo pairs found by tools/uiscan.py)
      lineNN  entry NN of the memory card message line table (0x8004BAAC): the entry gets
              its own new string, so lines the Japanese shares can read differently
  en  ASCII (menu font, tools/vwf.py ui_text); '#' marks a digit the game writes at run time
      (slot numbers, the clock), see DIGITS / CLOCK
  enc "dialogue": encode with tools/textenc.py (the string is shown in the story window)
  raw hex bytes written as is (e.g. the name separator)
  min_size  slot size to reserve when moved (templates the game appends to)

Moved strings go into the slots the Japanese no longer uses (strings whose every reference
was repointed); what does not fit goes after the VWF payload in kernel RAM (tools/vwf.py).
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INV = os.path.join(ROOT, 'work', 'ui', 'exe_strings.json')
TR = os.path.join(ROOT, 'work', 'translation', 'en')
EXE_BASE = 0x80010000
LINES = 0x8004BAAC              # memory card message lines: 51 pointers

# run-time digits: '#' number k of a string -> instructions whose 16-bit immediate becomes
# the byte offset of that '#' (sb rt, off(rs)); the digit value code is in DIGIT_VALUE
DIGITS = {
    'line24': [(0x80027FD8, 0)],                    # "Notes # will be erased."
    'line25': [(0x8002823C, 0)],                    # copy: source slot
    'line26': [(0x8002824C, 0)],                    # copy: destination slot
    'line48': [(0x8002825C, 0), (0x800285E0, 0)],   # "Notes # will be overwritten."
    'ui071': [(0x800281E0, 0)],                     # "Copy Notes # to which notes?"
}
# slot + 0x50 (low byte of Shift-JIS １) -> slot + 0x31 (ASCII '1')
DIGIT_VALUE = {0x80027FC0: 'line24', 0x800281CC: 'line25', 0x8002822C: 'line26', 0x800285D0: 'line48'}
# copy message: the destination digit goes into line 26 (was the second １ of line 25)
FIXED = {0x80028244: ('imm', (LINES + 4 * 26) & 0xFFFF)}    # lw v0, %lo(line 26)(v0)


def inventory():
    return {s['id']: s for s in json.load(open(INV, encoding='utf-8'))}


def load():
    for name in ('ui.json', 'ui.en.json'):
        p = os.path.join(TR, name)
        if os.path.exists(p):
            return json.load(open(p, encoding='utf-8'))
    return []


def encode(r):
    if r.get('raw'):
        return bytes.fromhex(r['raw'])
    en = r['en']
    if r.get('enc') == 'dialogue':
        import textenc
        warn = []
        b = textenc.encode(en, warn)
        if warn:
            raise SystemExit('%s: %s' % (r['id'], warn))
        return b
    try:
        return en.encode('ascii')
    except UnicodeEncodeError:
        return en.encode('shift_jis')


def set_imm(exe, addr, value):
    o = addr - EXE_BASE + 0x800
    w = struct.unpack_from('<I', exe, o)[0]
    struct.pack_into('<I', exe, o, (w & 0xFFFF0000) | (value & 0xFFFF))


def build(exe, extra_base, extra_max):
    """Patch exe (bytearray) in place. -> (extra blob for extra_base, report lines)"""
    import uiscan
    from mips import Exe
    inv = inventory()
    e = Exe(os.path.join(ROOT, 'work', 'source', 'disc', 'SLPS_004.04'))
    refs = uiscan.refs(e)
    rows = [r for r in load() if r.get('en') or r.get('raw')]
    rep = []
    in_place, moves = [], []     # moves: (row, raw, size, [ref words / pairs])
    covered = {}                 # pointer word -> new owner (for freeing slots)
    for r in rows:
        raw = encode(r)
        marks = [i for i, c in enumerate(raw) if c == 0x23]     # '#' digit marks
        if r['id'].startswith('line'):
            n = int(r['id'][4:])
            word = LINES + 4 * n
            moves.append((r, raw, max(len(raw) + 1, r.get('min_size', 0)), [(word, 'ptr')], marks))
            covered[word] = r['id']
            continue
        s = inv[r['id']]
        addr = int(s['ram'], 16)
        if len(raw) <= s['room'] and not r.get('min_size'):
            in_place.append((r, raw, addr, marks))
            continue
        rf = refs.get(addr, [])
        bad = [k for _, k in rf if k == 'gp']
        if not rf or bad:
            rep.append('%s: needs moving but has %s references; left Japanese' % (r['id'], 'gp' if bad else 'no'))
            continue
        moves.append((r, raw, max(len(raw) + 1, r.get('min_size', 0)), rf, marks))
        for site, _ in rf:
            covered[site] = r['id']
    # free slots: inventory strings whose every reference is now covered by a move
    free = []
    for s in inv.values():
        addr = int(s['ram'], 16)
        rf = refs.get(addr, [])
        if rf and all(site in covered for site, _ in rf) and \
                not any(refs.get(addr + k) for k in range(1, s['bytes'] + 1)):
            free.append([addr, s['room'] + 1])
    for addr, size in free:
        o = addr - EXE_BASE + 0x800
        exe[o:o + size] = bytes(size)
    free.sort()
    placed = {}
    extra = bytearray()
    for r, raw, size, rf, marks in sorted(moves, key=lambda m: -m[2]):
        for slot in free:
            if slot[1] >= size:
                at = slot[0]
                slot[0] += size
                slot[1] -= size
                o = at - EXE_BASE + 0x800
                exe[o:o + len(raw) + 1] = raw + b'\0'
                break
        else:
            at = extra_base + len(extra)
            extra += raw + bytes(size - len(raw))
            if len(extra) > extra_max:
                raise SystemExit('UI strings: no room left (%d > %d bytes)' % (len(extra), extra_max))
        placed[r['id']] = (at, marks, raw)
        for site, kind in rf:
            if kind == 'ptr':
                struct.pack_into('<I', exe, site - EXE_BASE + 0x800, at)
            else:                                       # lui/lo:<lui address>
                lui = int(kind.split(':')[1], 16)
                op = struct.unpack_from('<I', exe, site - EXE_BASE + 0x800)[0] >> 26
                if op == 0x0D:                          # ori: no carry
                    set_imm(exe, lui, at >> 16)
                else:
                    set_imm(exe, lui, (at + 0x8000) >> 16)
                set_imm(exe, site, at & 0xFFFF)
    for r, raw, addr, marks in in_place:
        s = inv[r['id']]
        o = addr - EXE_BASE + 0x800
        exe[o:o + max(len(raw) + 1, s['bytes'] + 1)] = raw + bytes(max(1, s['bytes'] + 1 - len(raw)))
        placed[r['id']] = (addr, marks, raw)
    # run-time digits
    for rid, sites in DIGITS.items():
        if rid not in placed:
            continue
        at, marks, raw = placed[rid]
        for site, k in sites:
            set_imm(exe, site, marks[k])
        for m in marks:
            if extra_base <= at < extra_base + len(extra):
                extra[at - extra_base + m] = 0x31
            else:
                exe[at - EXE_BASE + 0x800 + m] = 0x31
    for site, rid in DIGIT_VALUE.items():
        if rid in placed:
            set_imm(exe, site, 0x31)
    if 'line26' in placed:
        for site, (_, v) in FIXED.items():
            set_imm(exe, site, v)
    if 'ui101' in placed:
        clock(exe, placed['ui101'])
    return bytes(extra), rep, placed


def clock(exe, placed):
    """Seventh-story clock line: '#' = hours, minute tens, minute ones (ASCII digits)."""
    at, marks, raw = placed
    assert len(marks) == 3, 'clock line needs three # marks'
    h, m1, m2 = marks
    base = at + h
    set_imm(exe, 0x8001E1C0, (base + 0x8000) >> 16)     # lui v1
    set_imm(exe, 0x8001E1C4, base & 0xFFFF)             # addiu v1
    set_imm(exe, 0x8001E1D4, m1 - h)                    # sb a0, minutes tens
    set_imm(exe, 0x8001E1DC, m2 - h)                    # sb v0, minutes ones
    for a in (0x8001E1C8, 0x8001E1D0, 0x8001E1D8):      # digit + 0x4F (Shift-JIS) -> + 0x30
        set_imm(exe, a, 0x30)
    set_imm(exe, 0x8001E1F0, -h)                        # text pointer = line start
    o = at - EXE_BASE + 0x800
    for m in marks:
        exe[o + m] = 0x30


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    p = os.path.join(TR, 'ui.json')
    if cmd == 'init':
        if os.path.exists(p):
            raise SystemExit('ui.json exists')
        rows = [{'id': s['id'], 'jp': s['jp'], 'en': '', 'note': ''} for s in inventory().values()]
        json.dump(rows, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('wrote', p)
        return
    exe = bytearray(open(os.path.join(ROOT, 'work', 'source', 'disc', 'SLPS_004.04'), 'rb').read())
    extra, rep, placed = build(exe, 0x8000D800, 0x800)
    inv = inventory()
    moved = [k for k, v in placed.items() if k.startswith('line') or v[0] != int(inv[k]['ram'], 16)]
    # strings no longer used (every reference repointed to a new string, e.g. the message lines)
    o = lambda a: a - EXE_BASE + 0x800
    orig = open(os.path.join(ROOT, 'work', 'source', 'disc', 'SLPS_004.04'), 'rb').read()
    unused = [k for k, s in inv.items() if k not in placed
              and exe[o(int(s['ram'], 16)):o(int(s['ram'], 16)) + s['bytes']] != orig[o(int(s['ram'], 16)):o(int(s['ram'], 16)) + s['bytes']]]
    left = [k for k in inv if k not in placed and k not in unused]
    print('%d strings placed (%d moved, %d bytes after the payload); %d replaced through the line table;'
          ' %d left Japanese:' % (len(placed), len(moved), len(extra), len(unused), len(left)))
    print('  ' + ' '.join('%s %s' % (k, inv[k]['jp']) for k in left))
    for line in rep:
        print('  ' + line)


if __name__ == '__main__':
    main()
