"""Clear the known breakpoints and resume the CPU (after an interrupted debug run).

    python tools/gdbreset.py [--pc]     --pc: print the program counter before resuming
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbmem import Gdb  # noqa: E402

KNOWN = [0x8003B554, 0x80032E74]   # pad_bp, DrawSync (tools/gdbdbg.py)


def main():
    g = Gdb()
    g.s.settimeout(3)
    try:
        g.s.sendall(b'\x03')
        try:
            g._recv_packet()
        except Exception:
            pass
        if '--pc' in sys.argv:
            r = g.cmd('g')
            pc = struct.unpack('<I', bytes.fromhex(r[37 * 8:38 * 8]))[0]
            ra = struct.unpack('<I', bytes.fromhex(r[31 * 8:32 * 8]))[0]
            print('pc %08X ra %08X' % (pc, ra))
        for a in KNOWN + [int(x, 16) for x in sys.argv[1:] if not x.startswith('--')]:
            g.cmd('z0,%x,4' % a)
    finally:
        g.close()
    print('resumed')


if __name__ == '__main__':
    main()
