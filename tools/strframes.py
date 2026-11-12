"""Frames of the STR / MV movies (video sectors only; XA audio is not in the GRP extracts).

    python tools/strframes.py list <file>                    frame count, size
    python tools/strframes.py sheet <out.png> <every> <files...>   contact sheet of every Nth frame

Video sector (2048 bytes): 32-byte header (u16 0x0160, u16 0x8001, u16 chunk, u16 chunks,
u32 frame, u32 bytes, u16 w, u16 h, ...) + 2016 bytes of the frame's BS data.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bs  # noqa: E402


def frames(path):
    d = open(path, 'rb').read()
    cur = {}
    info = {}
    for o in range(0, len(d) - 2047, 2048):
        s = d[o:o + 2048]
        if s[0:4] != b'\x60\x01\x01\x80':
            continue
        chunk, chunks, frame, size, w, h = struct.unpack_from('<HHIIHH', s, 4)
        cur.setdefault(frame, {})[chunk] = s[32:]
        info[frame] = (chunks, size, w, h)
    out = []
    for f in sorted(cur):
        chunks, size, w, h = info[f]
        if len(cur[f]) != chunks:
            continue
        data = b''.join(cur[f][i] for i in range(chunks))[:size * 4 if size * 4 > 8 else None]
        out.append((f, w, h, data))
    return out


def main():
    if sys.argv[1] == 'list':
        fr = frames(sys.argv[2])
        print(len(fr), 'frames', fr[0][1:3] if fr else '')
    elif sys.argv[1] == 'sheet':
        from PIL import Image, ImageDraw
        out, every, files = sys.argv[2], int(sys.argv[3]), sys.argv[4:]
        tiles = []
        for f in files:
            fr = frames(f)
            for k in range(0, len(fr), every):
                n, w, h, data = fr[k]
                try:
                    rgb, _ = bs.decode(data, w, h)
                    tiles.append(('%s %d' % (os.path.basename(f), n), Image.fromarray(rgb).resize((128, 77))))
                except Exception as e:      # noqa: BLE001
                    tiles.append(('%s %d ERR' % (os.path.basename(f), n), Image.new('RGB', (128, 77), (90, 0, 0))))
        cols = 12
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * 128, rows * 87), (30, 30, 30))
        dr = ImageDraw.Draw(sheet)
        for i, (lab, im) in enumerate(tiles):
            x, y = (i % cols) * 128, (i // cols) * 87
            sheet.paste(im, (x, y))
            dr.text((x + 2, y + 77), lab[:22], fill=(255, 255, 0))
        sheet.save(out)
        print(len(tiles), 'tiles')


if __name__ == '__main__':
    main()
