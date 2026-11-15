"""Offline page layout check of the English script (no emulator).

    python tools/layoutcheck.py            every scene, rows laid out as tools/build.py does
    python tools/layoutcheck.py --old      the same rows encoded one by one (before 0.8.2)

Replays the encoded bytes of every text row the way the game draws them (per player
gender): pen x in pixels, line on the page, {g} / CR LF / {p}. Rows the script runs
straight into (build.text_runs) are replayed as one page. Reports letters drawn past the
window's right edge and lines drawn below the last line of the page.
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402
import textenc  # noqa: E402
from sdata import Script  # noqa: E402

YEN = textenc.YEN
FW = {'ｐ': 'p', 'ｋ': 'k', 'ｗ': 'w', 'ｇ': 'g', 'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｆ': 'f'}


def replay(data, gender, pen, problems, rid):
    """pen = [x, row]; -> pen after the row."""
    w = textenc.widths()
    x, row = pen
    i = 0

    def draw(width):
        nonlocal x
        if row >= textenc.LINES:
            problems.add((rid, 'below the page'))
        x += width
        if x > textenc.WIN_W:
            problems.add((rid, 'past the right edge'))

    while i < len(data):
        if data[i:i + 2] == b'\r\n':
            x, row = 0, row + 1
            i += 2
        elif data[i:i + 2] == YEN:
            c = FW[data[i + 2:i + 4].decode('cp932')]
            i += 4
            if c == 'p':
                x, row = 0, 0
            elif c == 'g':
                if x:
                    x, row = 0, row + 1
            elif c in 'abc':
                draw(max(textenc.name_width(c, g) for g in (0, 1)))
            elif c == 'f':
                a = data.index(YEN, i)
                b = data.index(YEN, a + 2)
                for ch in (data[i:a], data[a + 2:b])[gender]:
                    if ch != 0x7F:
                        draw(w[ch])
                i = b + 2
        else:
            if data[i] != 0x7F:
                draw(w[data[i]])
            i += 1
    return [x, row]


def main():
    old = '--old' in sys.argv
    problems = set()
    rows_n = runs_n = 0
    for p in sorted(glob.glob(os.path.join(build.GRP, 'SCE*', 'SDATA*.BIN'))):
        num = int(os.path.basename(p)[5:7])
        rows = build.load_rows(num)
        if not rows:
            continue
        s = Script(open(p, 'rb').read())
        nxt = build.text_runs(s, num, rows)
        follows = set(nxt.values())
        order = [vals[0][1] for pc, op, ln, vals in s.insns if op == 0x4A]
        state, pens = {}, {}
        for v in order:
            rid = '%02d:%04x' % (num, v)
            if rid not in rows:
                continue
            rows_n += 1
            if old:
                raw, end = textenc.encode(rows[rid]), None
            else:
                follow = rows['%02d:%04x' % (num, nxt[v])] if v in nxt else None
                ahead = textenc.first_lines(follow) if follow and rows[rid].endswith('\n') else 0
                raw, end = textenc.encode_row(rows[rid], None, state.get(v), ahead)
                if v in nxt and end:
                    state[nxt[v]] = end
            for g in (0, 1):
                pen = pens.get((v, g), [0, 0]) if v in follows else [0, 0]
                pen = replay(raw, g, pen, problems, rid)
                if v in nxt:
                    pens[nxt[v], g] = pen
            runs_n += v in nxt
    print('%d rows, %d run straight into the next row' % (rows_n, runs_n))
    kinds = {}
    for rid, what in sorted(problems):
        kinds.setdefault(what, []).append(rid)
    for what, ids in kinds.items():
        print('%s: %d rows  %s%s' % (what, len(ids), ' '.join(ids[:12]), ' ...' if len(ids) > 12 else ''))
    if not problems:
        print('no letter past the right edge, no line below the page')


if __name__ == '__main__':
    main()
