"""Build the English disc image.

    python tools/build.py 0.1.0 [--only 29,00] [--report]

Steps
  1. EXE: VWF renderer + hooks (tools/vwf.py), appended boot stub copies the payload.
  2. Scripts: every SDATAxx.BIN whose scene has English rows is rebuilt: the bytecode
     is kept byte for byte, the string pool is rewritten (translated rows encoded by
     tools/textenc.py, all other strings copied) and every string operand repointed.
  3. Disc: rebuilt scripts are written into the sectors of DUMMY.BIN (filler the game
     never reads); their DIRENTRY.DAT records point there (the record holds a sector
     offset from the start of the scene's GRP; the loader adds the GRP's LBA without a
     bounds check). The EXE moves to a reserved area after the end of the image.

Output: work/output/Gakkou de Atta Kowai Hanashi S (English v<ver>).bin/.cue
"""
import argparse
import glob
import json
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_disc import Disc  # noqa: E402
from grp import read_index  # noqa: E402
from sdata import Script  # noqa: E402
import gfx  # noqa: E402
import textenc  # noqa: E402
import vwf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_BIN = os.path.join(ROOT, 'Gakkou de Atta Kowai Hanashi S (Japan).bin')
DISC = os.path.join(ROOT, 'work', 'source', 'disc')
GRP = os.path.join(ROOT, 'work', 'source', 'grp')
TR = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')
OUT = os.path.join(ROOT, 'work', 'output')
SCRIPT_MAX = 0x80092000 - 0x80063D20   # script buffer ends 0x80093D20; the tail is debug scratch
EXE_RESERVE = 200             # sectors reserved for the EXE after the image end


def load_rows(num):
    for name in ('SCE%02d.json' % num, 'SCE%02d.en.json' % num):
        p = os.path.join(TR, name)
        if os.path.exists(p):
            return {r['id']: r['en'] for r in json.load(open(p, encoding='utf-8')) if r.get('en')}
    return {}


def rebuild_script(data, num, rows, report):
    s = Script(data)
    assert not s.errors, s.errors
    out = bytearray(data[:s.code_end])
    out += bytes(-len(out) % 4)
    newoff = {}
    shared = {}     # identical strings are stored once (the pool is read-only)
    for at, v, op in s.pool_refs():
        if v in newoff:
            continue
        raw = data[v:data.index(b'\0', v)]
        rid = '%02d:%04x' % (num, v)
        if rid in rows:
            warn = []
            enc = textenc.encode_choice if op == 0x04 else textenc.encode
            raw = enc(rows[rid], warn)
            report.extend('%s: %s' % (rid, w) for w in warn)
        if raw in shared:
            newoff[v] = shared[raw]
            continue
        newoff[v] = shared[raw] = len(out)
        out += raw + b'\0'
        out += bytes(-len(out) % 4)
    for at, v, op in s.pool_refs():
        struct.pack_into('<I', out, at, newoff[v])
    if len(out) > SCRIPT_MAX:
        raise SystemExit('SDATA%02d.BIN is %d bytes (max %d)' % (num, len(out), SCRIPT_MAX))
    # sanity: same bytecode, every string reachable
    s2 = Script(bytes(out))
    assert not s2.errors and len(s2.insns) == len(s.insns), (num, s2.errors)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('version')
    ap.add_argument('--only', help='comma separated scene numbers to rebuild')
    ap.add_argument('--report', action='store_true', help='print layout warnings')
    a = ap.parse_args()
    out_bin = os.path.join(OUT, 'Gakkou de Atta Kowai Hanashi S (English v%s).bin' % a.version)
    os.makedirs(OUT, exist_ok=True)

    exe, info = vwf.patch_exe(open(os.path.join(DISC, 'SLPS_004.04'), 'rb').read())
    exe = gfx.story_menu_exe(exe)    # in-story Start menu image (embedded in the EXE)
    print('EXE: payload %d bytes, boot at %08X, %d UI strings' % (info['payload_size'], info['boot'], len(info['ui'])))
    for line in info['ui_report']:
        print('  UI ' + line)

    only = {int(x) for x in a.only.split(',')} if a.only else None
    scripts = {}
    report = []
    for p in sorted(glob.glob(os.path.join(GRP, 'SCE*', 'SDATA*.BIN'))):
        num = int(os.path.basename(p)[5:7])
        if only is not None and num not in only:
            continue
        rows = load_rows(num)
        if not rows:
            continue
        scripts[num] = rebuild_script(open(p, 'rb').read(), num, rows, report)
        print('SDATA%02d: %d rows, %d -> %d bytes' % (num, len(rows), os.path.getsize(p), len(scripts[num])))
    if report:
        print('%d layout warnings' % len(report))
        if a.report:
            for r in report:
                print('  ' + r)

    d = Disc.open_copy(SRC_BIN, out_bin)
    groups = {g['name']: g for g in read_index(DISC)}
    direntry = bytearray(d.read_file('DIRENTRY.DAT'))
    dummy = d.entries['DUMMY.BIN']
    next_sec = 0
    for num, blob in sorted(scripts.items()):
        gname = 'SCE%02d.GRP' % num
        g = groups[gname]
        grp_lba = d.entries['GROUP%d/%s' % (num // 10, gname)].lba
        rec = [f for f in g['files'] if f['name'] == 'SDATA%02d.BIN' % num][0]
        n = (len(blob) + 2047) // 2048
        assert next_sec + n <= (dummy.size + 2047) // 2048, 'DUMMY.BIN full'
        lba = dummy.lba + next_sec
        d.write_file_sectors('DUMMY.BIN', {next_sec + i: blob[i * 2048:(i + 1) * 2048].ljust(2048, b'\0')
                                           for i in range(n)})
        struct.pack_into('<II', direntry, rec['rec'] + 12, lba - grp_lba, n)
        next_sec += n
    # graphics (tools/gfx.py): in place inside their GRP when they fit, else in DUMMY.BIN
    gfx.VERSION = a.version          # title menu credit shows the build version
    for key, blob in sorted(gfx.build_all().items()):
        gdir, fname = key.split('/')
        gname = gdir + '.GRP'
        g = groups[gname]
        rec = [f for f in g['files'] if f['name'] == fname][0]
        gpath = [p for p in d.entries if p.endswith('/' + gname)][0]
        n = (len(blob) + 2047) // 2048
        chunks = {i: blob[i * 2048:(i + 1) * 2048].ljust(2048, b'\0') for i in range(n)}
        if n <= rec['sectors']:
            d.write_file_sectors(gpath, {rec['sector'] + i: c for i, c in chunks.items()})
            print('GFX %s: in place (%d bytes)' % (key, len(blob)))
        else:
            grp_lba = d.entries[gpath].lba
            assert next_sec + n <= (dummy.size + 2047) // 2048, 'DUMMY.BIN full'
            d.write_file_sectors('DUMMY.BIN', {next_sec + i: c for i, c in chunks.items()})
            struct.pack_into('<II', direntry, rec['rec'] + 12, dummy.lba + next_sec - grp_lba, n)
            next_sec += n
            print('GFX %s: moved to DUMMY.BIN (%d bytes)' % (key, len(blob)))
    # movies (tools/gfx.py GFX_SECTORS): re-encoded video sectors, in place
    for key, secs in sorted(gfx.build_sectors().items()):
        gdir, fname = key.split('/')
        gname = gdir + '.GRP'
        rec = [f for f in groups[gname]['files'] if f['name'] == fname][0]
        gpath = [p for p in d.entries if p.endswith('/' + gname)][0]
        d.write_file_sectors(gpath, {rec['sector'] + i: s for i, s in secs.items()})
        print('GFX %s: %d video sectors' % (key, len(secs)))
    d.write_file_sectors('DIRENTRY.DAT', {i: bytes(direntry[i * 2048:(i + 1) * 2048]).ljust(2048, b'\0')
                                          for i in range((len(direntry) + 2047) // 2048)})
    d.replace('SLPS_004.04', exe, reserve=EXE_RESERVE)
    d.close()
    write_cue(out_bin)
    print('wrote', out_bin)
    # fixed path for the test emulator: DuckStation reopens the disc a savestate names,
    # so states made on this image keep working across builds (tools/hotreload.py)
    test = os.path.join(ROOT, 'work', 'emulator', 'test', 'kowai_test.bin')
    os.makedirs(os.path.dirname(test), exist_ok=True)
    shutil.copyfile(out_bin, test)
    write_cue(test)


def write_cue(path):
    with open(path[:-4] + '.cue', 'w') as f:
        f.write('FILE "%s" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n' % os.path.basename(path))


if __name__ == '__main__':
    main()
