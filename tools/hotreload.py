"""Write a new build into a running game (savestate made with an older build).

    python tools/hotreload.py <built .bin>

At a safe halt (the pad-read breakpoint, main loop; no return address on the stack
points into a patched routine), it writes:
  1. the VWF payload to kernel RAM (tools/vwf.py PAYLOAD),
  2. every EXE word that differs from the original program (hooks),
  3. the DIRENTRY.DAT sub-file records (sector offsets of rebuilt scripts) into the
     copy the game keeps in RAM (pointer at 0x8015B834); the group headers keep their
     run-time LBAs (+0x14).
The emulator must already run the new disc image (start it with that .cue), so the
scripts loaded later come from the new build. The loaded scene script is replaced by
the built one with the same bytecode; the text read pointer moves to the same
paragraph (the page already on screen stays as it was).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_disc import Disc  # noqa: E402
from gdbdbg import Dbg  # noqa: E402
import vwf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRENTRY_PTR = 0x8015B834      # lw -0x47cc(0x8016): loaded DIRENTRY.DAT
SCRIPT_BUF = 0x80063D20         # scene script buffer (interpreter 0x8001C860)
SCRIPT_SIZE = 0x2E2E0           # up to the debug scratch (tools/gdbdbg.py)
EXE_BASE = 0x80010000
PATCH_RANGES = [(0x80014590, 0x80014640), (0x80014B00, 0x80014DB0), (0x8001A35C, 0x8001A6C0), (0x80015140, 0x80015220), (0x80015294, 0x80015EA0), (0x80015EC0, 0x80015ED0), (0x800160D0, 0x800161D0), (0x80018FF0, 0x800190E0), (0x80029160, 0x80029B30), (0x8002F040, 0x8002F800), (0x80027440, 0x80027B80), (0x8000C000, 0x8000E000),
               (0x80017990, 0x80017B00), (0x80013CE8, 0x80013D0C), (0x801CB000, 0x801F7000)]   # hooked routines


def main():
    img = sys.argv[1]
    d = Disc(img, 'rb')
    exe = d.read_file('SLPS_004.04')
    direntry = d.read_file('DIRENTRY.DAT')
    orig = open(os.path.join(ROOT, 'work', 'source', 'disc', 'SLPS_004.04'), 'rb').read()
    t_size = struct.unpack_from('<I', orig, 0x1C)[0]
    built = vwf.patch_exe(orig)[1]
    payload = built['payload']                      # code + font + UI strings placed after it
    diffs = []
    for o in range(0x800, 0x800 + t_size, 4):
        if exe[o:o + 4] != orig[o:o + 4]:
            diffs.append((EXE_BASE + o - 0x800, exe[o:o + 4]))
    g = Dbg()
    try:
        # safe halt: stopped at the pad read; check pc/ra/stack against patched code
        for attempt in range(300):
            g.step_frame(0)
            r = g.regs()
            stack = g.g.read(r[29], 0x200)
            words = struct.unpack('<128I', stack)
            bad = [w for w in [r[37], r[31]] + list(words)
                   if any(a <= w < b for a, b in PATCH_RANGES)]
            if not bad:
                break
        else:
            raise SystemExit('no safe halt in 300 frames')
        if '--no-payload' not in sys.argv:
            g.g.write(vwf.PAYLOAD, payload)
            if built.get('hi'):                     # 2x text (tools/vwf2x.py); its font sheet
                g.g.write(built['hi_addr'], built['hi'])   # reaches VRAM at the next page
        if '--no-hooks' not in sys.argv:
            for addr, w in diffs:
                g.g.write(addr, w)
            g.g.write(0x80060FC0, bytes([vwf.LINE_H]))   # live window: line pitch
        base = struct.unpack('<I', g.g.read(DIRENTRY_PTR, 4))[0]
        ngroups = struct.unpack_from('<H', direntry, 6)[0]
        first_table = struct.unpack_from('<I', direntry, 8 + 16)[0]
        ram = bytearray(g.g.read(base, len(direntry)))
        assert ram[:6] == direntry[:6], 'DIRENTRY not found in RAM'
        changed = 0
        for o in range(first_table, len(direntry), 20):
            if ram[o:o + 20] != direntry[o:o + 20] and ram[o:o + 12] == direntry[o:o + 12]:
                g.g.write(base + o, direntry[o:o + 20])
                changed += 1
        print('payload %d bytes, %d EXE words, %d DIRENTRY records (groups %d), halt after %d frames'
              % (len(payload), len(diffs), changed, ngroups, attempt + 1))
        if '--no-script' not in sys.argv:
            reload_script(g, d, direntry)
    finally:
        g.close()


def reload_script(g, d, direntry):
    """Replace the loaded scene script with the built one of the same scene (same
    bytecode), and move the text read pointer (gp+0x268) to the same paragraph."""
    from grp import read_index
    from sdata import Script
    ram = g.g.read(SCRIPT_BUF, SCRIPT_SIZE)
    for grp_ in read_index_bytes(direntry):
        rec = [f for f in grp_['files'] if f['name'].startswith('SDATA')]
        if not rec:
            continue
        rec = rec[0]
        gname = grp_['name']
        num = int(gname[3:5])
        grp_lba = d.entries['GROUP%d/%s' % (num // 10, gname)].lba
        lba = grp_lba + rec['sector']
        new = b''.join(d.data(lba + i) for i in range(rec['sectors']))
        snew = Script(new)
        mask = bytearray(ram[:snew.code_end])
        ref = bytearray(new[:snew.code_end])
        for at, v, op in snew.pool_refs():       # string operands differ between builds
            mask[at:at + 4] = ref[at:at + 4] = bytes(4)
        if mask != ref:
            continue
        sold = Script(bytes(ram[:len(new) + 0x10000]))
        if ram[:len(new)] == new:
            print('script SDATA%02d already current' % num)
            return
        gp = g.regs()[28]
        tp = struct.unpack('<I', g.g.read(gp + 0x268, 4))[0] - SCRIPT_BUF
        newtp = None
        for (at, v, op), (_, v2, _) in zip(sold.pool_refs(), snew.pool_refs()):
            end = ram.index(b'\0', v)
            if v <= tp <= end:
                paras = ram[v:tp].count(b'\r\n')
                pos = v2
                for _ in range(paras):
                    pos = new.index(b'\r\n', pos) + 2
                newtp = pos
        g.g.write(SCRIPT_BUF, new)
        if newtp is not None:
            g.g.write(gp + 0x268, struct.pack('<I', SCRIPT_BUF + newtp))
        print('script SDATA%02d replaced (%d bytes), text pointer %s' %
              (num, len(new), '%x -> %x' % (tp, newtp) if newtp is not None else 'not in a string'))
        return
    print('loaded script not found in the build')


def read_index_bytes(direntry):
    import tempfile
    from grp import read_index
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, 'DIRENTRY.DAT'), 'wb').write(direntry)
        return read_index(t)


if __name__ == '__main__':
    main()
