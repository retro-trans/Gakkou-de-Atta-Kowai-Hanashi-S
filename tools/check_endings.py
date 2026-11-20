"""Ending tracker verification; offline by default, --runtime uses the project GDB port.

Runtime checks execute the actual R3000 hooks, intercepting the BIOS write/close
entries before any I/O. No memory-card writes are issued by this tool. Use a
fresh boot of the current build, at its title menu, with the test card.
"""
import argparse
from pathlib import Path
import struct

import build
import endings
from sdata import Script, all_scripts
import vwf


def offline():
    rows = endings.catalog()
    assert rows == endings.catalog()
    assert [r['id'] for r in rows] == list(range(len(rows)))
    ends = {(r['scene'], r['pc']): r['id'] for r in rows}
    choices = build.seen_numbers()
    assert len(choices) <= endings.CHOICE_BYTES * 8
    assert len(rows) <= endings.END_BYTES * 8
    found = []
    for _, original in all_scripts():
        scene = int(original.name[5:7])
        new = build.rebuild_script(original.data, scene, build.load_rows(scene), [], choices, ends)
        parsed = Script(new)
        assert not parsed.errors and len(parsed.insns) == len(original.insns)
        old_code = bytearray(original.data[:original.code_end])
        new_code = bytearray(new[:original.code_end])
        for at, ptr, op in original.pool_refs():
            old_code[at:at + 4] = new_code[at:at + 4] = bytes(4)
            new_ptr = struct.unpack_from('<I', new, at)[0]
            if (scene, at - 1) in ends:
                assert op == 0x4a
                assert new[new_ptr - 4:new_ptr] == endings.TAG + struct.pack('<H', ends[scene, at - 1])
                found.append(ends[scene, at - 1])
            if op == 0x04:
                assert new[new_ptr - 4:new_ptr] == build.SEEN_TAG + struct.pack('<H', choices[scene, ptr])
            if op == 0x31:
                # The Kokkuri-san coin operand must remain untouched text.
                assert original.data[ptr:original.data.index(0, ptr)] == new[new_ptr:new.index(0, new_ptr)]
        assert old_code == new_code, 'non-string bytecode changed in scene %02d' % scene
    assert sorted(found) == list(range(len(rows)))
    widths = vwf.build_font()[0]
    views = endings.pages(rows)
    for page in views:
        assert all(0 <= n < len(views) or n == -1 for n in page['targets'])
        for text, _, _ in page['lines'] + page['items']:
            assert sum(widths[ord(c)] for c in text) <= 240, text
    print('Offline: %d ending tags, %d choice tags, all 71 scripts and coin operands verified.' %
          (len(found), len(choices)))


def runtime():
    from gdbdbg import Dbg
    _, info = vwf.patch_exe((Path(build.DISC) / 'SLPS_004.04').read_bytes())
    syms = info['symbols']
    d = Dbg()
    d.step_frame()
    regs = d.regs()
    # Capture every byte temporarily borrowed by these synchronous, non-I/O calls.
    regions = [(0x80063d00, 0x220), (0x800a0000, 0x3000),
               (regs[29] - 0x100, 0x140), (regs[28] + 0x3cc, 4),
               (syms['seen_bits'], 508), (syms['end_pending'], 8),
               (syms['end_page_build'], 0)]
    saved = [(a, d.g.read(a, n)) for a, n in regions if n]

    def u32(addr):
        return struct.unpack('<I', d.g.read(addr, 4))[0]

    def write32(addr, v):
        d.g.write(addr, struct.pack('<I', v))

    def call(name, args=(), stop=0x8000b940, extra=None):
        old = d.regs()
        d.g.cmd('Z0,%x,4' % stop)
        try:
            for i, v in enumerate(args):
                d.setreg(4 + i, v)
            if extra:
                for i, v in extra.items():
                    d.setreg(i, v)
            d.setreg(31, stop)
            d.setreg(37, syms[name])
            for _ in range(200):
                d.g.s.sendall(b'$c#63')
                d.g._recv_packet()
                if d.regs()[37] == stop:
                    return d.regs()
            raise AssertionError('hook did not return: ' + name)
        finally:
            d.g.cmd('z0,%x,4' % stop)
            for i in list(range(1, 32)) + [33, 34, 37]:
                d.setreg(i, old[i])

    try:
        assert d.g.read(syms['end_row'], 16) == info['hi'][syms['end_row'] - info['hi_addr']:syms['end_row'] - info['hi_addr'] + 16], 'boot the new build first'
        rows = endings.catalog()
        bits = bytearray(endings.END_BYTES)
        for eid in (0, 1, 8, len(rows) - 1):
            bits[eid // 8] |= 1 << (eid % 8)
        d.g.write(syms['end_bits'], bits)
        views = endings.pages(rows)
        for i, p in enumerate(views):
            write32(syms['end_page'], i)
            call('end_page_build', (0x800a0000,))
            native = d.g.read(0x800a0000, 0x94)
            assert struct.unpack_from('<I', native, 0)[0] == p['vertical']
            assert struct.unpack_from('<I', native, 0x14)[0] == len(p['lines'])
            assert struct.unpack_from('<I', native, 0x38)[0] == len(p['items'])
            for off, labels in ((0x18, p['lines']), (0x3c, p['items'])):
                for j, (text, ids, mode) in enumerate(labels):
                    ptr = struct.unpack_from('<I', native, off + j * 4)[0]
                    actual = d.g.read(ptr, 48).split(b'\0')[0].decode('ascii')
                    count = sum(bool(bits[n // 8] & (1 << (n % 8))) for n in ids)
                    if mode == 1:
                        text = text.replace('000/', '%03d/' % count)
                    elif mode == 2 and count:
                        text = text.replace('Unseen', 'Done  ')
                    assert actual == text, (i, actual, text)
        print('Runtime: all %d native menu pages and completion counters verified.' % len(views))
        for eid in (0, 8, len(rows) - 1):
            d.g.write(syms['end_bits'], bytes(endings.END_BYTES))
            write32(regs[28] + 0x3cc, 0)
            d.g.write(0x80063d20, b'\x4a' + struct.pack('<I', 0x104))
            d.g.write(0x80063e20, endings.TAG + struct.pack('<H', eid) + b'Test\0')
            call('end_row')
            assert u32(syms['end_pending']) == eid + 1
            assert not any(d.g.read(syms['end_bits'], endings.END_BYTES)), 'marked before acknowledgement'
            d.g.write(0x80063d20, b'\xff\x03')
            result = call('end_finish', stop=0x8001cfec)
            assert result[2] == 3 and u32(syms['end_pending']) == 0
            assert d.g.read(syms['end_bits'] + eid // 8, 1)[0] == 1 << (eid % 8)
            call('end_finish', stop=0x8001cfec)
            assert sum(bin(x).count('1') for x in d.g.read(syms['end_bits'], endings.END_BYTES)) == 1
        # Every narration resets a stale candidate; untagged/original scripts count nothing.
        d.g.write(0x80063d20, b'\x4a' + struct.pack('<I', 0x104))
        d.g.write(0x80063e20, bytes(4) + b'Test\0')
        write32(syms['end_pending'], 1)
        call('end_row')
        assert u32(syms['end_pending']) == 0
        print('Runtime: final-page acknowledgement, repeated endings and untagged narration verified.')
        choices = bytes([0x55]) * endings.CHOICE_BYTES
        d.g.write(syms['seen_bits'], choices)
        d.g.write(syms['end_bits'], bits)
        buffer = 0x800a0000
        payload = bytes((i * 17 + 3) & 255 for i in range(8192))
        d.g.write(buffer, payload)
        call('seen_store', (0, buffer, 8192), stop=0x800317f8)
        stored = d.g.read(buffer, 8192)
        assert stored[:0x1e00] == payload[:0x1e00]
        assert stored[0x1e00:0x1e04] == b'SEN1'
        assert stored[0x1e04:0x1f64] == choices
        assert stored[0x1f64:0x1f68] == b'END1'
        assert stored[0x1f68:] == bits
        d.g.write(syms['seen_bits'], bytes(endings.CHOICE_BYTES))
        d.g.write(syms['end_bits'], bytes(endings.END_BYTES))
        call('seen_load', (0,), stop=0x800317e8, extra={17: buffer})
        assert d.g.read(syms['seen_bits'], endings.CHOICE_BYTES) == choices
        assert d.g.read(syms['end_bits'], endings.END_BYTES) == bits
        # A legacy SEN1 save may have arbitrary unused tail bytes: no false clears.
        legacy = bytearray(stored)
        legacy[0x1f64:] = b'\xff' * (8192 - 0x1f64)
        d.g.write(buffer, legacy)
        d.g.write(syms['end_bits'], bytes(endings.END_BYTES))
        call('seen_load', (0,), stop=0x800317e8, extra={17: buffer})
        assert not any(d.g.read(syms['end_bits'], endings.END_BYTES))
        assert d.g.read(syms['seen_bits'], endings.CHOICE_BYTES) == choices
        print('Runtime: save round trip, legacy saves, choice preservation and unchanged notes verified (BIOS I/O intercepted).')
    finally:
        for addr, data in saved:
            d.g.write(addr, data)
        for i in list(range(1, 32)) + [33, 34, 37]:
            d.setreg(i, regs[i])
        d.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', action='store_true')
    args = parser.parse_args()
    offline()
    if args.runtime:
        runtime()
