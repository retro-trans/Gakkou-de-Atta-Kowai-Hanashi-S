"""English script text: markup <-> game bytes, with word wrap for the VWF.

Markup (used in work/translation/<lang>/*.json and in the extracted source rows):
    \\n          paragraph break (CR LF: the game waits for a key, then starts a new line)
    {p}         page end (wait for a key, clear the window)        = ￥ｐ
    {k}         wait for a key mid-paragraph                       = ￥ｋ
    {w}         short pause                                        = ￥ｗ
    {g}         line break (only if the line is not empty)         = ￥ｇ
    {a} {b}     player's surname / given name                      = ￥ａ ￥ｂ
    {c}         surname for a male player, given name for a female  = ￥ｃ
    {f:A|B}     A for a male player, B for a female player         = ￥ｆA￥B￥

Game encoding (English): every 16-bit unit holds two bytes; printable ASCII 0x20-0x7E,
extra letters 0x01-0x1F (tools/vwf.py EXTRA) and the filler 0x7F that pads a run to an
even length. Control codes stay Shift-JIS (￥ = 81 8F + full-width letter). The
preprocessor (EXE 0x80015294) reads units, so every run must have even length.

Line layout: the window is WIN_W px wide and holds LINES lines at a 17 px pitch
(tools/vwf.py). The builder wraps at spaces and emits {g}.
"""
import re
import struct

from vwf import dialogue_widths, CODE_OF, FILLER

WIN_W = 198            # canvas x 56..254 (tools/vwf.py CANVAS_LEFT), minus the outline
LINES = 12             # lines per page (tools/vwf.py PAGE_LINES)
MAX_UNITS = 24         # the preprocessor auto-wraps after 25 narrow units (0x19)
YEN = b'\x81\x8f'
CTRL = {'p': 'ｐ', 'k': 'ｋ', 'w': 'ｗ', 'g': 'ｇ', 'a': 'ａ', 'b': 'ｂ', 'c': 'ｃ'}
# default names (used to reserve width for {a} {b} {c})
NAMES = {'a': ('Sakagami', 'Kurata'), 'b': ('Shuichi', 'Emi')}

_WIDTHS = None


def widths():
    global _WIDTHS
    if _WIDTHS is None:
        _WIDTHS = dialogue_widths()
    return _WIDTHS


TOKEN = re.compile(r'\{f:([^|{}]*)\|([^{}]*)\}|\{([pkwgabc])\}|\n|[^{\n]+|\{')


def parse(markup):
    """-> list of tokens: ('t', text) ('nl',) ('c', letter) ('f', male, female)."""
    out = []
    for m in TOKEN.finditer(markup):
        s = m.group(0)
        if m.group(1) is not None:
            out.append(('f', m.group(1), m.group(2)))
        elif m.group(3):
            out.append(('c', m.group(3)))
        elif s == '\n':
            out.append(('nl',))
        elif s == '{':
            raise ValueError('stray "{" in %r' % markup)
        else:
            out.append(('t', s))
    return out


def text_bytes(s):
    b = bytearray()
    for ch in s:
        o = ord(ch)
        if 0x20 <= o < 0x7F:
            b.append(o)
        elif ch in CODE_OF:
            b.append(CODE_OF[ch])
        else:
            raise ValueError('no glyph for %r (U+%04X)' % (ch, o))
    return bytes(b)


def pad(b):
    return b + bytes([FILLER]) if len(b) % 2 else b


def ctrl(letter):
    return YEN + CTRL[letter].encode('cp932')


def name_width(letter, gender):
    w = widths()
    if letter == 'c':
        letter = 'a' if gender == 0 else 'b'
    return sum(w[c] for c in NAMES[letter][gender].encode())


# ---- layout ---------------------------------------------------------------------

def atoms(tokens, gender=None):
    """Split a paragraph's tokens into atoms: ('sp',) spaces, ('t', s) text,
    ('c', x) controls/names, ('f', m, f). With gender set, f-tokens are expanded."""
    out = []
    for t in tokens:
        if t[0] == 'f' and gender is not None:
            t = ('t', t[1 + gender])
        if t[0] == 't':
            for part in re.split(r'( )', t[1]):
                if part == ' ':
                    out.append(('sp',))
                elif part:
                    out.append(('t', part))
        else:
            out.append(t)
    return out


def atom_width(a, gender):
    w = widths()
    if a[0] == 't':
        return sum(w[c] for c in text_bytes(a[1]))
    if a[0] == 'sp':
        return w[0x20]
    if a[0] == 'c' and a[1] in 'abc':
        # reserve the widest default name for both genders (players may rename)
        return max(name_width(a[1], g) for g in (0, 1))
    if a[0] == 'f':
        return max(atom_width(('t', a[1 + g]), g) for g in (0, 1))
    return 0


def line_units(line):
    """16-bit units the preprocessor adds to its column counter for a line: one per
    pair unit (narrow), two per unit of an inserted name (8 letters max), none for
    control codes. Gender options count the longer one."""
    n = 0
    run = 0
    for a in line:
        if a[0] == 't':
            run += len(text_bytes(a[1]))
        elif a[0] == 'sp':
            run += 1
        else:
            n += (run + 1) // 2
            run = 0
            if a[0] == 'c' and a[1] in 'abc':
                n += 8
            elif a[0] == 'f':
                n += max((len(text_bytes(x)) + 1) // 2 for x in a[1:])
    return n + (run + 1) // 2


def wrap(ats, gender):
    """Greedy word wrap -> list of lines (lists of atoms); spaces at breaks dropped."""
    words, cur = [], []
    for a in ats:
        if a[0] == 'sp' or (a[0] == 'c' and a[1] == 'g'):
            if cur:
                words.append(cur)
            words.append([a])
            cur = []
        else:
            cur.append(a)
    if cur:
        words.append(cur)
    words = [p for wd in words for p in split_wide(wd, gender)]
    lines, line, lw = [], [], 0
    for wd in words:
        if wd[0][0] == 'c' and wd[0][1] == 'g':
            continue        # source {g} placed Japanese column breaks; English wraps itself
        ww = sum(atom_width(a, gender) for a in wd)
        if wd[0][0] == 'sp':
            if line:
                line.append(wd[0])
                lw += ww
            continue
        if line and (lw + ww > WIN_W or line_units(line + wd) > MAX_UNITS):
            while line and line[-1][0] == 'sp':
                lw -= atom_width(line.pop(), gender)
            lines.append(line)
            line, lw = [], 0
        line.extend(wd)
        lw += ww
    while line and line[-1][0] == 'sp':
        line.pop()
    lines.append(line)
    return lines


def split_wide(word, gender):
    """A word wider than a line (e.g. a long run of dots) is cut into pieces that fit."""
    if sum(atom_width(a, gender) for a in word) <= WIN_W:
        return [word]
    if all(a[0] == 't' for a in word):
        return [[('t', p)] for p in _cut(''.join(a[1] for a in word))]
    # codes attached to a long run (e.g. "......{w}"): cut the wide text pieces only
    out, cur = [], []
    for a in word:
        if a[0] == 't' and atom_width(a, gender) > WIN_W:
            pieces = _cut(a[1])
            for p in pieces[:-1]:
                out.append(cur + [('t', p)])
                cur = []
            cur.append(('t', pieces[-1]))
        else:
            cur.append(a)
    out.append(cur)
    return out


def _cut(text):
    w = widths()
    out, cur, cw = [], '', 0
    for ch in text:
        cwid = w[text_bytes(ch)[0]]
        if cur and cw + cwid > WIN_W:
            out.append(cur)
            cur, cw = '', 0
        cur += ch
        cw += cwid
    out.append(cur)
    return out


def line_width(line, gender=None):
    return sum(atom_width(a, gender) for a in line)


def encode_atoms(ats):
    """Encode atoms; text runs between controls are padded to an even length."""
    out = bytearray()
    run = bytearray()

    def flush():
        out.extend(pad(bytes(run)))
        run.clear()
    for a in ats:
        if a[0] == 't':
            run.extend(text_bytes(a[1]))
        elif a[0] == 'sp':
            run.append(0x20)
        elif a[0] == 'c':
            flush()
            out.extend(ctrl(a[1]))
        elif a[0] == 'f':
            flush()
            out.extend(YEN + 'ｆ'.encode('cp932') + pad(text_bytes(a[1])) + YEN
                       + pad(text_bytes(a[2])) + YEN)
    flush()
    return bytes(out)


def line_key(lines):
    return [len(l) for l in lines]


def encode_paragraph(tokens, report=None):
    """Wrap one paragraph (no 'nl' tokens) and encode it."""
    has_f = any(t[0] == 'f' for t in tokens)
    ats = atoms(tokens)
    if not has_f:
        lines = wrap(ats, None)
        check(lines, report)
        return join_lines([encode_atoms(l) for l in lines])
    # compact form: f-tokens as atomic words; valid if both genders break identically
    per = [wrap(ats, g) for g in (0, 1)]
    fits = all(line_width(l, g) <= WIN_W for g in (0, 1) for l in per[g])
    if fits and line_key(per[0]) == line_key(per[1]):
        check(per[0], report)
        return join_lines([encode_atoms(l) for l in per[0]])
    # per-line gender branches (the options are free to wrap differently). The game
    # allows no control code inside a branch: trailing waits ({p} {k} {w}) are moved
    # after the last line, and a line's other controls must match between genders.
    tail = []
    while tokens and tokens[-1][0] == 'c' and tokens[-1][1] in 'pkw':
        tail.insert(0, tokens[-1])
        tokens = tokens[:-1]
    lm = wrap(atoms(tokens, 0), 0)
    lf = wrap(atoms(tokens, 1), 1)
    check(lm, report)
    check(lf, report)
    out = []
    for i in range(max(len(lm), len(lf))):
        tm, cm = split_ctrl(lm[i] if i < len(lm) else [])
        tf, cf = split_ctrl(lf[i] if i < len(lf) else [])
        if cm != cf:
            raise ValueError('codes in a line that wraps differently per gender: %r' % (tokens,))
        line = bytearray()
        for j in range(len(tm)):
            bm, bf = encode_atoms(tm[j]), encode_atoms(tf[j])
            if bm or bf:
                line += YEN + 'ｆ'.encode('cp932') + bm + YEN + bf + YEN
            if j < len(cm):
                line += ctrl(cm[j][1])
        out.append(bytes(line))
    return join_lines(out) + b''.join(ctrl(t[1]) for t in tail)


def split_ctrl(line):
    """-> (text runs, controls between them); len(runs) == len(controls) + 1."""
    runs, ctrls, cur = [], [], []
    for a in line:
        if a[0] == 'c':
            runs.append(cur)
            ctrls.append(a)
            cur = []
        else:
            cur.append(a)
    runs.append(cur)
    return runs, ctrls


def join_lines(parts):
    """Lines joined by {g}; a paragraph longer than a page gets a {p} (wait, clear page)
    after every LINES lines. The source uses {p} mid-paragraph (1,103 times), and four
    source paragraphs already run past one page (44:11198, 44:11c84, 44:1257c, 47:bdb0)."""
    pages = [parts[i:i + LINES] for i in range(0, len(parts), LINES)] or [[]]
    return ctrl('p').join(ctrl('g').join(pg) for pg in pages)


def check(lines, report):
    if report is None:
        return
    for l in lines:
        if line_width(l) > WIN_W:
            report.append('word wider than the window: %r' % (l,))


def encode(markup, report=None):
    """Markup -> game bytes (no NUL). report: list that collects layout warnings."""
    tokens = parse(markup)
    paras, cur = [], []
    for t in tokens:
        if t[0] == 'nl':
            paras.append(cur)
            cur = []
        else:
            cur.append(t)
    paras.append(cur)
    # Page layout: a row is assumed to start on a fresh page (almost every row before it
    # ends with {p}). When the next paragraph would not fit on the lines left, its CR LF
    # becomes {p} (wait, clear page) so the page breaks between paragraphs; otherwise the
    # engine breaks it mid-sentence by itself (checked in DuckStation, v0.2.0).
    out = b''
    used = 0
    # a row ending in CR LF is usually followed by choices drawn on the same page
    last = max([i for i, p in enumerate(paras) if p] or [0])
    tail_room = CHOICE_RESERVE if markup.endswith('\n') else 0
    for i, p in enumerate(paras):
        pieces = page_pieces(p)
        first = piece_lines(pieces[0])
        room = LINES - (tail_room if i == last and len(pieces) == 1 else 0)
        if i:
            if used and used + first > room and first <= room:
                out += ctrl('p')
                used = 0
            else:
                out += b'\r\n'
        out += encode_paged(p, report)
        used += first
        for pc in pieces[1:]:
            used = piece_lines(pc)
        if used > LINES:
            used = used % LINES or LINES
        if pieces[-1] and pieces[-1][-1] == ('c', 'p'):
            used = 0
    return out


def page_pieces(tokens):
    pieces, cur = [], []
    for t in tokens:
        cur.append(t)
        if t[0] == 'c' and t[1] == 'p':
            pieces.append(cur)
            cur = []
    if cur or not pieces:
        pieces.append(cur)
    return pieces


def piece_lines(tokens):
    """Lines a page piece takes (the larger gender variant)."""
    if not any(t[0] in 't f' for t in tokens):
        return 0
    n = len(wrap(atoms(tokens), None))
    if any(t[0] == 'f' for t in tokens):
        n = max(n, *(len(wrap(atoms(tokens, g), g)) for g in (0, 1)))
    return n


def encode_paged(tokens, report=None):
    """{p} clears the page and the text after it starts at the top-left again, so
    each piece between page breaks is wrapped on its own."""
    pieces, cur = [], []
    for t in tokens:
        cur.append(t)
        if t[0] == 'c' and t[1] == 'p':
            pieces.append(cur)
            cur = []
    if cur or not pieces:
        pieces.append(cur)
    return b''.join(encode_paragraph(pc, report) for pc in pieces)


CHOICE_BREAK = bytes([FILLER, 0x0A])   # tools/vwf.py choice_brk: new line + 2 spaces
CHOICE_INDENT = 30                     # two full-width spaces (13 px glyph + 2 spacing)
CHOICE_LINES = 3
CHOICE_RESERVE = 4                     # lines kept free for choices after a row ending in \n



def encode_choice(markup, report=None):
    """Choice text: the game copies it unit by unit after a "1. " prefix, without
    interpreting control codes. Long choices wrap at spaces with the 7F 0A unit."""
    if re.search(r'[{}\n]', markup):
        raise ValueError('control code in a choice: %r' % markup)
    w = widths()
    first = WIN_W - sum(w[c] for c in b'1. ')
    rest = WIN_W - CHOICE_INDENT
    lines, cur = [], ''
    for word in markup.split(' '):
        cand = (cur + ' ' + word) if cur else word
        room = first if not lines else rest
        if cur and sum(w[c] for c in text_bytes(cand)) > room:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    lines.append(cur)
    if report is not None:
        if len(lines) > CHOICE_LINES:
            report.append('choice needs %d lines (max %d)' % (len(lines), CHOICE_LINES))
        for i, l in enumerate(lines):
            if sum(w[c] for c in text_bytes(l)) > (first if i == 0 else rest):
                report.append('word wider than a choice line: %r' % l)
    return CHOICE_BREAK.join(pad(text_bytes(l)) for l in lines)


# ---- Japanese source -> markup (for the extracted rows) --------------------------

def jp_to_markup(b):
    """Shift-JIS script string -> markup (Japanese text kept)."""
    s = b.decode('cp932')
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if s.startswith('\r\n', i):
            out.append('\n')
            i += 2
            continue
        if ch == '￥' and i + 1 < len(s):
            c = s[i + 1]
            if c == 'ｆ':
                j = s.index('￥', i + 2)
                k = s.index('￥', j + 1)
                out.append('{f:%s|%s}' % (s[i + 2:j], s[j + 1:k]))
                i = k + 1
                continue
            inv = {v: k for k, v in CTRL.items()}
            if c in inv:
                out.append('{%s}' % inv[c])
                i += 2
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def markup_to_jp(m):
    """Inverse of jp_to_markup (round-trip check)."""
    out = []
    for t in parse(m):
        if t[0] == 'nl':
            out.append('\r\n')
        elif t[0] == 'c':
            out.append('￥' + CTRL[t[1]])
        elif t[0] == 'f':
            out.append('￥ｆ%s￥%s￥' % (t[1], t[2]))
        else:
            out.append(t[1])
    return ''.join(out).encode('cp932')
