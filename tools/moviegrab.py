"""Grab VRAM during a movie (no pad reads there): count LoadImage calls, grab the whole VRAM.

    python tools/moviegrab.py <out prefix> 700,900,1100     -> <prefix>_<count>.png
"""
import sys
import time
sys.path.insert(0, 'tools')
from gdbdbg import Dbg, write_png  # noqa: E402

out = sys.argv[1]
counts = [int(x) for x in sys.argv[2].split(',')]
LOADIMAGE = 0x8003309C
for attempt in range(30):
    try:
        d = Dbg()
        break
    except Exception as e:  # noqa: BLE001
        time.sleep(1)
g = d.g
g.cmd('z0,%x,4' % d.bp)
n = 0
try:
    for target in counts:
        g.cmd('Z0,%x,4' % LOADIMAGE)
        while n < target:
            g.s.sendall(b'$c#63')
            g._recv_packet()
            if d.regs()[37] == LOADIMAGE:
                n += 1
        g.cmd('z0,%x,4' % LOADIMAGE)
        pix = b''
        for yy in range(0, 512, 64):
            pix += d.grab(0, yy, 1024, 64)
        write_png('%s_%d.png' % (out, target), 1024, 512, pix)
        print('grabbed at', target, flush=True)
finally:
    d.close()
