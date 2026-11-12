"""Scan the EXE for Shift-JIS strings and every reference to them.

    python tools/uiscan.py            -> work/ui/exe_scan.json (+ summary)

A string: starts 4-byte aligned, Shift-JIS double-byte characters and printable ASCII,
NUL-terminated, at least one double-byte character. References: 32-bit words equal to an
address inside the string (pointer tables) and lui + addiu/ori/load/store pairs that form
it (code). A string whose only references point at its start can be moved safely.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mips import Exe  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'work', 'source', 'disc', 'SLPS_004.04')
OUT = os.path.join(ROOT, 'work', 'ui', 'exe_scan.json')
GP = 0x80060A50          # lui gp 0x8006 / addiu gp 0xA50 at 0x8003177C
LOAD_OPS = (0x09, 0x0D, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B)   # addiu ori lb lh lw lbu lhu sb sh sw


def lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


def strings(body, base):
    out = []
    a = 0
    n = len(body)
    while a < n:
        if a % 4 or (a and body[a - 1] != 0):
            a += 1
            continue
        i, dbl = a, 0
        while i < n and body[i]:
            c = body[i]
            if lead(c) and i + 1 < n and 0x40 <= body[i + 1] <= 0xFC and body[i + 1] != 0x7F:
                i += 2
                dbl += 1
            elif 0x20 <= c < 0x7F:
                i += 1
            else:
                break
        if i < n and body[i] == 0 and dbl and i > a:
            raw = body[a:i]
            try:
                txt = raw.decode('shift_jis')
            except UnicodeDecodeError:
                txt = None
            if txt:
                out.append((base + a, raw, txt))
            a = i + 1
        else:
            a += 1
    return out


def refs(e):
    """-> {address: [(site, kind)]} for every pointer word and lui/lo pair in the EXE."""
    n = len(e.body) // 4
    w = struct.unpack_from('<%dI' % n, e.body)
    out = {}
    for i, x in enumerate(w):
        a = e.base + i * 4
        if e.base <= x < e.base + len(e.body):
            out.setdefault(x, []).append((a, 'ptr'))
        op = x >> 26
        if op in LOAD_OPS and (x >> 21) & 31 == 28:          # gp-relative
            lo = x & 0xFFFF
            t = (GP + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF
            out.setdefault(t, []).append((a, 'gp'))
        elif op in LOAD_OPS:
            rs = (x >> 21) & 31
            lo = x & 0xFFFF
            for k in range(1, 16):
                if i - k < 0:
                    break
                p = w[i - k]
                if p >> 26 == 0x0F and (p >> 16) & 31 == rs:
                    hi = (p & 0xFFFF) << 16
                    t = (hi + (lo if op == 0x0D else (lo - 0x10000 if lo & 0x8000 else lo))) & 0xFFFFFFFF
                    out.setdefault(t, []).append((a, 'lui/lo:%08X' % (e.base + (i - k) * 4)))
                    break
                # stop at another write to rs
                if ((p >> 26) in (0x09, 0x0D, 0x0F, 0x23) and (p >> 16) & 31 == rs) or \
                   (p >> 26 == 0 and (p >> 11) & 31 == rs):
                    break
    return out


def main():
    e = Exe(EXE)
    rf = refs(e)
    rows = []
    for addr, raw, txt in strings(e.body, e.base):
        start = rf.get(addr, [])
        inner = [(a + k, s, kind) for k in range(1, len(raw) + 1) for a in [addr] for s, kind in rf.get(addr + k, [])]
        rows.append({'ram': '0x%08X' % addr, 'bytes': len(raw), 'jp': txt,
                     'refs': ['%08X %s' % r for r in start],
                     'inner_refs': ['+%d %08X %s' % (t - addr, s, k) for t, s, k in inner]})
    # room: bytes up to the next string or non-zero data
    for r in rows:
        a = int(r['ram'], 16) - e.base + r['bytes']
        while a < len(e.body) and e.body[a] == 0:
            a += 1
        r['room'] = a - (int(r['ram'], 16) - e.base) - 1
    json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    noref = [r for r in rows if not r['refs']]
    inner = [r for r in rows if r['inner_refs']]
    print('%d strings, %d without a start reference, %d with inner references' % (len(rows), len(noref), len(inner)))
    print('wrote', os.path.relpath(OUT, ROOT))


if __name__ == '__main__':
    main()
