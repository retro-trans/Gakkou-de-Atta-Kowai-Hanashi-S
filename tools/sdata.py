"""SDATA*.BIN scene scripts: bytecode + string pool.

Layout: bytecode from offset 0 up to the first string, then a pool of NUL-terminated
Shift-JIS strings (file names, choices, narration). The interpreter (EXE 0x8001C860)
loads the file at 0x80063D20; every operand that points into the pool is a file
offset. Code-target operands (jumps) point into the bytecode, which the build never
resizes, so only pool pointers are rewritten.

Opcode table: (length, [operand offsets of u32 values]) from the handler table at
0x800104D0 (handler return value = instruction length, see docs/script_format.md).

    python tools/sdata.py check            parse every script, report problems
    python tools/sdata.py dump <SDATAxx>   disassembly listing (to stdout)
"""
import glob
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRP = os.path.join(ROOT, 'work', 'source', 'grp')

# op: (length, [(u32 operand offset, kind)]); kind 's' = string pool offset,
# 'c' = bytecode offset (jump target), '?' = u32 of unknown meaning (left untouched).
S, C, U = 's', 'c', '?'
OPS = {
    0x00: (1, []), 0x01: (5, [(1, C)]), 0x03: (6, [(2, C)]), 0x04: (10, [(1, S), (5, C)]),
    0x05: (1, []), 0x06: (1, []), 0x07: (2, []), 0x08: (2, []),
    0x09: (6, [(2, C)]), 0x0a: (6, [(2, C)]), 0x0b: (2, []), 0x0c: (5, [(1, U)]),
    0x0d: (2, []), 0x0e: (3, []), 0x0f: (3, []),
    0x10: (5, [(1, C)]), 0x11: (5, [(1, C)]), 0x12: (5, [(1, C)]), 0x13: (5, [(1, C)]),
    0x14: (3, []), 0x15: (3, []), 0x16: (6, [(2, C)]), 0x17: (6, [(2, C)]),
    0x18: (7, [(3, C)]),
    0x19: (3, []), 0x1a: (5, [(1, U)]), 0x1b: (1, []), 0x1c: (3, []), 0x1d: (3, []),
    0x1e: (1, []), 0x1f: (5, [(1, U)]),
    0x20: (5, [(1, S)]), 0x21: (1, []), 0x22: (1, []), 0x23: (5, [(1, S)]),
    0x24: (5, [(1, S)]), 0x25: (5, [(1, S)]), 0x26: (1, []), 0x27: (1, []),
    0x30: (2, []), 0x31: (5, [(1, U)]), 0x32: (1, []), 0x33: (5, [(1, U)]), 0x34: (1, []),
    0x35: (1, []),
    0x40: (1, []), 0x41: (1, []), 0x42: (5, [(1, S)]), 0x43: (1, []), 0x48: (1, []),
    0x4a: (5, [(1, S)]), 0x4b: (10, [(1, U)]), 0x4c: (2, []), 0x4d: (2, []), 0x4e: (3, []),
    0x4f: (2, []), 0x50: (2, []), 0x51: (2, []), 0x52: (2, []), 0x53: (2, []),
    0x54: (2, []), 0x55: (5, [(1, S)]), 0x56: (1, []), 0x57: (5, [(1, S)]), 0x58: (1, []),
    0x59: (1, []), 0x5a: (4, []), 0x5b: (1, []), 0x5c: (1, []), 0x5d: (6, [(1, S)]),
    0x5e: (1, []), 0x5f: (5, [(1, S)]), 0x60: (5, [(1, S)]), 0x61: (5, [(1, S)]),
    0x80: (2, []), 0x81: (1, []), 0x82: (5, [(1, U)]), 0x83: (1, []), 0x84: (1, []),
    0x85: (1, []), 0xff: (2, []),
}


class Script:
    def __init__(self, data, name=''):
        self.data = data
        self.name = name
        self.insns = []        # (offset, op, length, [(operand_offset, value, kind)])
        self.errors = []
        self.parse()

    def parse(self):
        d = self.data
        pc = 0
        pool = len(d)
        while pc < pool:
            op = d[pc]
            if op not in OPS:
                # junk between the last 'ff' and the 4-aligned pool start
                if self.insns and self.insns[-1][1] in (0xff, 0x00, 0x01) and pool - pc < 16:
                    break
                self.errors.append('unknown op %02x at %x' % (op, pc))
                break
            ln, opers = OPS[op]
            if pc + ln > pool:
                break          # alignment junk in front of the pool
            vals = []
            for o, k in opers:
                v = struct.unpack_from('<I', d, pc + o)[0]
                vals.append((pc + o, v, k))
                if k == S and v < len(d):
                    pool = min(pool, v)
            self.insns.append((pc, op, ln, vals))
            pc += ln
        self.code_end = pc
        self.pool_start = pool
        if pool - pc >= 16:
            self.errors.append('code ends at %x, pool starts at %x' % (pc, pool))

    def strings(self):
        """{offset: bytes} for every string operand."""
        out = {}
        for at, v, op in self.pool_refs():
            end = self.data.index(b'\0', v)
            out[v] = self.data[v:end]
        return out

    def pool_refs(self):
        """[(operand_offset, value, op)] for string operands."""
        return [(at, v, op) for pc, op, ln, vals in self.insns for at, v, k in vals if k == S]

    def code_refs(self):
        return [(at, v, op) for pc, op, ln, vals in self.insns for at, v, k in vals if k == C]


def all_scripts():
    for p in sorted(glob.glob(os.path.join(GRP, 'SCE*', 'SDATA*.BIN'))):
        yield p, Script(open(p, 'rb').read(), os.path.basename(p))


def check():
    from collections import Counter
    use = Counter()
    bad = 0
    for p, s in all_scripts():
        for pc, op, ln, vals in s.insns:
            use[op] += 1
        starts = {pc for pc, *_ in s.insns}
        errs = list(s.errors)
        for at, v, op in s.code_refs():
            if v not in starts:
                errs.append('op %02x at %x: code target %x not an insn start' % (op, at - 1, v))
        for at, v, op in s.pool_refs():
            if v >= len(s.data):
                errs.append('op %02x at %x: ptr %x beyond file' % (op, at - 1, v))
            elif v % 4:
                errs.append('op %02x at %x: pool ptr %x not 4-aligned' % (op, at - 1, v))
        if errs:
            bad += 1
            print(s.name, len(s.insns), 'insns;', '; '.join(errs[:4]))
    print('files with problems:', bad)
    print('op usage:', ' '.join('%02x:%d' % kv for kv in sorted(use.items())))


def dump(name):
    p = glob.glob(os.path.join(GRP, 'SCE*', name if name.endswith('.BIN') else name + '.BIN'))[0]
    s = Script(open(p, 'rb').read(), name)
    for pc, op, ln, vals in s.insns:
        raw = s.data[pc:pc + ln].hex(' ')
        note = ''
        for at, v, k in vals:
            if k == 's':
                txt = s.data[v:s.data.index(b'\0', v)].decode('cp932', 'replace')
                note += ' -> %x "%s"' % (v, txt[:40].replace('\r\n', '/'))
            else:
                note += ' -> code %x' % v
        print('%05x  %-30s%s' % (pc, raw, note))
    print('errors:', s.errors)


if __name__ == '__main__':
    if sys.argv[1] == 'check':
        check()
    elif sys.argv[1] == 'dump':
        sys.stdout.reconfigure(encoding='utf-8')
        dump(sys.argv[2])
