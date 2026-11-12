"""Canary test for RAM the game might not use: fill a range with a pattern unique to every
word, play, then list every byte range the game changed.

    python tools/ramcanary.py fill  <start> <end>            (hex, end exclusive)
    python tools/ramcanary.py check <start> <end> [label]    -> changed ranges, + json report

The pattern is a hash of the word's address, so a copy of canary data to another
place still counts as a change there. Works over DuckStation's GDB server (the CPU is
halted while the tool is connected, so the fill is atomic for the game).
Reports go to work/emulator/test/ram_canary/<label>.json.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbmem import Gdb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'emulator', 'test', 'ram_canary')
MERGE = 64          # changed words closer than this are reported as one range


def pattern(start, end):
    n = (end - start) // 4
    return struct.pack('<%dI' % n, *(((((start >> 2) + i) * 0x9E3779B1) + 0x6B43A9B5) & 0xFFFFFFFF
                                     for i in range(n)))


def fill(start, end):
    g = Gdb()
    try:
        g.write(start, pattern(start, end))
        ok = g.read(start, 64) == pattern(start, start + 64)
    finally:
        g.close()
    print('filled %08X-%08X (%d KB), readback %s' % (start, end, (end - start) // 1024, 'ok' if ok else 'FAILED'))


def check(start, end, label=None):
    g = Gdb()
    try:
        got = g.read(start, end - start)
    finally:
        g.close()
    want = pattern(start, end)
    ranges = []
    for i in range(0, end - start, 4):
        if got[i:i + 4] != want[i:i + 4]:
            a = start + i
            if ranges and a - ranges[-1][1] <= MERGE:
                ranges[-1][1] = a + 4
            else:
                ranges.append([a, a + 4])
    changed = sum(e - s for s, e in ranges)
    rep = []
    for s, e in ranges:
        blob = got[s - start:e - start]
        kind = 'zeroed' if not any(blob) else 'data'
        rep.append({'start': '%08X' % s, 'end': '%08X' % e, 'bytes': e - s, 'kind': kind})
    print('%08X-%08X: %d bytes changed in %d ranges' % (start, end, changed, len(ranges)))
    for r in rep[:40]:
        print('  %s-%s %7d %s' % (r['start'], r['end'], r['bytes'], r['kind']))
    if len(rep) > 40:
        print('  ... %d more' % (len(rep) - 40))
    # largest untouched runs
    free, prev = [], start
    for s, e in ranges + [[end, end]]:
        if s - prev > 0:
            free.append((prev, s))
        prev = e
    free.sort(key=lambda r: r[0] - r[1])
    print('largest untouched runs:', ', '.join('%08X-%08X (%d KB)' % (s, e, (e - s) // 1024) for s, e in free[:5]))
    if label:
        os.makedirs(OUT, exist_ok=True)
        json.dump({'range': ['%08X' % start, '%08X' % end], 'changed_bytes': changed, 'ranges': rep,
                   'untouched': [['%08X' % s, '%08X' % e] for s, e in free]},
                  open(os.path.join(OUT, label + '.json'), 'w'), indent=1)
    return ranges


if __name__ == '__main__':
    op, a, b = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
    if op == 'fill':
        fill(a, b)
    elif op == 'check':
        check(a, b, sys.argv[4] if len(sys.argv) > 4 else None)
