"""GRP archives and the DIRENTRY.DAT index.

DIRENTRY.DAT layout (little-endian):
  0x00  "CD-DIRI\\0"
  0x08  group table, 24 bytes per group, up to the first sub-table offset:
          name[12] (NUL padded), count u32, table_offset u32, seq u32
  table_offset: count x 20-byte records:
          name[12] (NUL terminated; bytes after the NUL are junk),
          sector u32 (relative to the start of the GRP file), sectors u32

Each sub-file starts on a 2048-byte sector boundary inside its GRP.

Usage:
  python tools/grp.py list  <disc_dir>
  python tools/grp.py unpack <disc_dir> <out_dir>
"""
import json
import os
import struct
import sys

GROUP_DIRS = {}


def read_index(disc):
    d = open(os.path.join(disc, 'DIRENTRY.DAT'), 'rb').read()
    assert d[:8] == b'CD-DIRI\0'
    groups = []
    p = 8
    first_table = struct.unpack_from('<I', d, 8 + 16)[0]
    while p < first_table:
        name = d[p:p + 12].split(b'\0')[0].decode('ascii')
        count, toff, seq = struct.unpack_from('<III', d, p + 12)
        files = []
        for i in range(count):
            r = toff + i * 20
            fname = d[r:r + 12].split(b'\0')[0].decode('ascii')
            sec, n = struct.unpack_from('<II', d, r + 12)
            files.append({'name': fname, 'sector': sec, 'sectors': n, 'rec': r})
        groups.append({'name': name, 'count': count, 'table': toff, 'seq': seq,
                       'entry': p, 'files': files})
        p += 24
    return groups


def grp_path(disc, name):
    for root, _, fs in os.walk(disc):
        if name in fs:
            return os.path.join(root, name)
    raise FileNotFoundError(name)


def main():
    cmd, disc = sys.argv[1], sys.argv[2]
    groups = read_index(disc)
    if cmd == 'list':
        for g in groups:
            for f in g['files']:
                print(f"{g['name']:12s} {f['sector']:6d} {f['sectors']:5d} {f['name']}")
    elif cmd == 'unpack':
        out = sys.argv[3]
        for g in groups:
            src = open(grp_path(disc, g['name']), 'rb').read()
            od = os.path.join(out, g['name'].split('.')[0])
            os.makedirs(od, exist_ok=True)
            for f in g['files']:
                blob = src[f['sector'] * 2048:(f['sector'] + f['sectors']) * 2048]
                with open(os.path.join(od, f['name']), 'wb') as o:
                    o.write(blob)
        with open(os.path.join(out, '_index.json'), 'w') as o:
            json.dump(groups, o, indent=1)


if __name__ == '__main__':
    main()
