"""Read the dialogue page that is on screen, as text, from the running game (2x text).

    python tools/pagetext.py                      print the page
    python tools/pagetext.py auto "<text>" "<a>|<b>" [n]   the same, and at a choice pick the
                                                  option that contains <a> or <b>
    python tools/pagetext.py until "<text>" [n]   press Circle until the page contains
                                                  <text> (at most n presses, default 200)

Works over DuckStation's GDB server like tools/gdbdbg.py. The letters of a page are
sprites in the 2x block (tools/vwf2x.py): each one's texture position gives its glyph, its
screen position its place, so the page can be read back without OCR. `until` stops as soon
as a page has no letters twice in a row (a menu or the save screen is up: never press on).
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdbdbg  # noqa: E402
import gdbmem  # noqa: E402
import vwf  # noqa: E402
import vwf2x  # noqa: E402

_INFO = []


def info():
    if not _INFO:
        chars = vwf.glyph_chars()
        table, adv, sheet, height, rep = vwf2x.build_glyphs(chars)
        blob, syms, rep2, _ = vwf2x.build(chars)
        by_uv = {}
        for code, ch in chars.items():
            u, v, w, h, dx, dy = struct.unpack_from('<BBBBbb', table, code * 8)
            if w:
                by_uv[u, v] = (ch, dx, dy, adv[code])
        _INFO.append((syms['g2_state'], rep2['prims'], by_uv))
    return _INFO[0]


def page(g=None):
    """-> list of lines (top to bottom) of the dialogue page on screen."""
    own = g is None
    g = g or gdbmem.Gdb()
    state, prims, by_uv = info()
    n = struct.unpack('<I', g.read(state, 4))[0]
    letters = []
    if 0 < n <= vwf2x.MAXG:
        raw = g.read(prims, n * 80)
        for i in range(n):
            x, y, u, v = struct.unpack_from('<hhBB', raw, i * 80 + 8)
            dim = raw[i * 80 + 47] == 0x2E
            ch, dx, dy, ad = by_uv.get((u, v), ('?', 0, 0, 6))
            letters.append((y - dy, x - dx, ch, dim, ad))  # line top, pen x
    if own:
        g.close()
    rows = {}
    for y, x, ch, dim, ad in letters:
        key = next((k for k in rows if abs(k - y) <= 3), y)
        rows.setdefault(key, []).append((x, ch, dim, ad))
    out = []
    for k in sorted(rows):
        line, last = '', None
        for x, ch, dim, ad in sorted(rows[k]):
            if last is not None and x - last > 1:
                line += ' '
            line += ch
            last = x + ad                    # where the next letter starts if no space
        if any(r[2] for r in rows[k]):
            line += '   [dim]'
        out.append(line)
    return out


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'until':
        want = sys.argv[2].replace(' ', '')
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 200
        empty = 0
        for k in range(limit):
            lines = page()
            flat = ''.join(lines).replace(' ', '')
            if want in flat:
                print('found after %d presses' % k)
                break
            empty = empty + 1 if not lines else 0
            if empty >= 2:
                print('stopped after %d presses: no dialogue page on screen' % k)
                break
            time.sleep(0.4)        # let the emulator's GDB server drop the last connection
            gdbdbg.run('press circle 1; wait 45')
            time.sleep(0.4)
        else:
            print('not found in %d presses' % limit)
    if len(sys.argv) > 1 and sys.argv[1] == 'auto':
        auto(sys.argv[2], sys.argv[3].split('|'), int(sys.argv[4]) if len(sys.argv) > 4 else 300)
    for line in page():
        print(line)


def auto(want, prefer, limit):
    """Press Circle until the page contains `want`; at a choice pick the first option that
    contains one of `prefer` (else option 1). Prints every choice met."""
    want = want.replace(' ', '')
    empty = 0
    for k in range(limit):
        lines = page()
        flat = ''.join(lines).replace(' ', '')
        if want in flat:
            print('found after %d presses' % k)
            return
        empty = empty + 1 if not lines else 0
        if empty >= 2:
            print('stopped after %d presses: no dialogue page on screen' % k)
            return
        opts = [l for l in lines if len(l) > 2 and l[0].isdigit() and l[1] == '.']
        moves = 0
        if len(opts) >= 2:
            time.sleep(1.0)                  # let the list finish drawing, read it again
            lines = page()
            opts = [l for l in lines if len(l) > 2 and l[0].isdigit() and l[1] == '.']
            pick = next((i for i, o in enumerate(opts) if any(p in o for p in prefer)), 0)
            print('choice:', ' / '.join(opts), '-> picking', pick + 1)
            moves = pick
        time.sleep(0.4)
        gdbdbg.run('; '.join(['press down 1; wait 30'] * moves + ['press circle 1; wait 45']))
        time.sleep(0.4)
    print('not found in %d presses' % limit)


if __name__ == '__main__':
    main()
