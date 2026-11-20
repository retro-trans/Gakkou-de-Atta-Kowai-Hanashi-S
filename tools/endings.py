"""Discover story conclusions and build the native, spoiler-free ending checklist.

    python tools/endings.py                  read-only catalog summary
    python tools/endings.py --catalog path   write the English/metadata-only catalog

A conclusion is the last narration instruction on a path to FF (scene return).
Different earlier branches which share that final narration share one entry. The
prologue and unreachable narration are excluded. IDs use original scene/bytecode
positions, independent of English wording. No original script text is exported.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from sdata import all_scripts

ROOT = Path(__file__).resolve().parent.parent
TAG = b'\xe7\xed'
CHOICE_BYTES = 352
END_BYTES = 508 - CHOICE_BYTES - 4
GROUPS = ('Shindo', 'Arai', 'Kazama', 'Hosoda', 'Iwashita', 'Fukuzawa', 'Other Stories')


def group(scene):
    if 1 <= scene <= 41 and scene % 7:
        return scene // 7
    return 6


def successors(s):
    """Conservative control flow; choices jump only when op 06 confirms them."""
    out, choices = {}, []
    for pc, op, ln, vals in s.insns:
        targets = [v for _, v, k in vals if k == 'c']
        if op == 0x04:
            choices.extend(targets)
        if op == 0xff:
            dest = []
        elif op == 0x01:
            dest = targets
        elif op == 0x06:
            dest = list(choices)
            choices = []
        else:
            dest = [pc + ln] + ([] if op == 0x04 else targets)
        out[pc] = dest
    return out


def conclusions(s):
    edges = successors(s)
    live, todo = set(), [0]
    while todo:
        pc = todo.pop()
        if pc in live or pc not in edges:
            continue
        live.add(pc)
        todo.extend(edges[pc])
    pred = defaultdict(list)
    ins = {r[0]: r for r in s.insns}
    for pc in live:
        for target in edges[pc]:
            pred[target].append(pc)
    found = defaultdict(set)
    for pc, op, _, _ in s.insns:
        if op != 0xff or pc not in live:
            continue
        todo, visited = list(pred[pc]), set()
        while todo:
            at = todo.pop()
            if at in visited:
                continue
            visited.add(at)
            _, prevop, _, _ = ins[at]
            if prevop == 0x4a:
                found[at].add(s.data[pc + 1])
            elif prevop not in (0x04, 0x06, 0xff, 0x81, 0x82):
                todo.extend(pred[at])
    return found


def catalog():
    rows = []
    for _, s in all_scripts():
        scene = int(s.name[5:7])
        if scene == 0:
            continue
        for ordinal, (pc, outcomes) in enumerate(sorted(conclusions(s).items()), 1):
            rows.append(dict(id=len(rows), scene=scene, pc=pc, ending=ordinal,
                             group=group(scene), outcomes=sorted(outcomes)))
    assert len(rows) <= END_BYTES * 8, 'ending map exceeds the existing save extension'
    return rows


def pages(rows):
    """Page graph, rendered using the game's own message-box and menu routines."""
    pages = []

    def add(lines, items, back=-1, vertical=False):
        p = dict(lines=lines, items=items, targets=[], back=back, vertical=vertical)
        pages.append(p)
        return len(pages) - 1

    def label(text, ids=(), mode=0):
        return (text, tuple(ids), mode)

    ids = lambda entries: [r['id'] for r in entries]
    root = add([label('Endings 000/%03d' % len(rows), ids(rows), 1),
                label('Save Notes to keep progress.')], [], vertical=True)
    for g, name in enumerate(GROUPS):
        entries = [r for r in rows if r['group'] == g]
        scenes = sorted({r['scene'] for r in entries})
        chunks = [scenes[i:i + 5] for i in range(0, len(scenes), 5)]
        story_pages = []
        for chunk in chunks:
            items = []
            for scene in chunk:
                records = [r for r in entries if r['scene'] == scene]
                items.append(label('Story %02d  000/%03d' % (scene, len(records)), ids(records), 1))
            items += [label('Previous'), label('Next'), label('Back')]
            story_pages.append(add([label('%s  000/%03d' % (name, len(entries)), ids(entries), 1),
                                    label('Choose a story')], items, root, True))
        pages[root]['items'].append(label('%s  000/%03d' % (name, len(entries)), ids(entries), 1))
        pages[root]['targets'].append(story_pages[0])
        for si, (sp, chunk) in enumerate(zip(story_pages, chunks)):
            for scene in chunk:
                records = [r for r in entries if r['scene'] == scene]
                detail = []
                for offset in range(0, len(records), 6):
                    lines = [label('Story %02d  000/%03d' % (scene, len(records)), ids(records), 1),
                             label('Page %d/%d' % (offset // 6 + 1, (len(records) + 5) // 6))]
                    for r in records[offset:offset + 6]:
                        lines.append(label('Ending %02d: Unseen' % r['ending'], [r['id']], 2))
                    detail.append(add(lines, [label('Previous'), label('Next'), label('Back')], sp))
                for i, p in enumerate(detail):
                    pages[p]['targets'] = [detail[(i - 1) % len(detail)], detail[(i + 1) % len(detail)], sp]
                pages[sp]['targets'].append(detail[0])
            pages[sp]['targets'] += [story_pages[(si - 1) % len(story_pages)],
                                     story_pages[(si + 1) % len(story_pages)], root]
    pages[root]['items'].append(label('Back'))
    pages[root]['targets'].append(-1)
    for p in pages:
        assert len(p['lines']) <= 8 and len(p['items']) <= 8
        assert len(p['items']) == len(p['targets'])
        for text, _, _ in p['lines'] + p['items']:
            assert len(text.encode('ascii')) < 48
    return pages


def data_asm(rows):
    """Fixed descriptors: header 32 bytes, then sixteen 12-byte label records."""
    views = pages(rows)
    src = ['.align 4', 'end_page_table:']
    src += ['.word end_page_%d' % i for i in range(len(views))]
    labels = []
    for i, p in enumerate(views):
        src += ['end_page_%d:' % i, '.word %d' % p['vertical'],
                '.word %d' % len(p['lines']), '.word %d' % len(p['items']),
                '.half %d' % (p['back'] & 0xffff), '.half 0']
        src += ['.half %d' % (v & 0xffff) for v in p['targets'] + [-1] * (8 - len(p['targets']))]
        records = p['lines'] + [('', (), 0)] * (8 - len(p['lines']))
        records += p['items'] + [('', (), 0)] * (8 - len(p['items']))
        for j, (text, ids, mode) in enumerate(records):
            tag = 'end_label_%d_%d' % (i, j)
            position = text.index('000/') if mode == 1 else text.index('Unseen') if mode == 2 else 0
            src += ['.word ' + tag, '.word ' + tag + '_ids', '.half %d' % len(ids),
                    '.byte %d' % position, '.byte %d' % mode]
            labels += [tag + ':', '.ascii ' + json.dumps(text + '\0'), '.align 2', tag + '_ids:']
            labels += ['.half %d' % v for v in ids]
    src += labels
    src += ['.align 4', 'end_pending:', '.word 0', 'end_page:', '.word 0',
            'end_title:', '.ascii "Endings\\0"', 'end_done:', '.ascii "Done  "',
            '.align 4', 'end_strings:', '.space 768']
    return '\n'.join(src) + '\n'


ASM = r'''
; A newly loaded scene must not inherit the previous scene's pending conclusion.
end_reset:
    sw    zero, 0x3F8(gp)
    sw    zero, 0x410(gp)
    la    t0, end_pending
    sw    zero, 0(t0)
    j     0x8001C498
    nop

; After op 4A has resolved its string, remember a conclusion's tagged ID + 1.
end_row:
    addiu sp, sp, -0x18
    sw    ra, 0x14(sp)
    jal   0x8001D98C
    nop
    move  t0, zero
    lbu   t1, -4(v1)
    ori   t2, zero, 0xE7
    bne   t1, t2, @save
    nop
    lbu   t1, -3(v1)
    ori   t2, zero, 0xED
    bne   t1, t2, @save
    nop
    lhu   t0, -2(v1)
    nop
    sltiu t1, t0, END_COUNT
    bnez  t1, @valid
    nop
    b     @save
    move  t0, zero
@valid:
    addiu t0, t0, 1
@save:
    la    t1, end_pending
    sw    t0, 0(t1)
    lw    ra, 0x14(sp)
    addiu sp, sp, 0x18
    jr    ra
    ori   v0, zero, 5

; FF executes only after the final narration has been acknowledged.
end_finish:
    la    t0, end_pending
    lw    t1, 0(t0)
    sw    zero, 0(t0)
    beqz  t1, @orig
    addiu t1, t1, -1
    sltiu t2, t1, END_COUNT
    beqz  t2, @orig
    srl   t2, t1, 3
    la    t3, end_bits
    addu  t3, t3, t2
    lbu   t4, 0(t3)
    andi  t1, t1, 7
    ori   t2, zero, 1
    sllv  t2, t2, t1
    or    t4, t4, t2
    sb    t4, 0(t3)
@orig:
    lw    v0, 0x3CC(gp)
    li    t0, 0x80063D21
    addu  t0, t0, v0
    lbu   v0, 0(t0)
    j     0x8001CFEC
    nop

; Append a fifth item to the existing title menu, preserving the first four.
end_title_item:
    sw    v0, 0x78(sp)
    la    v0, end_title
    sw    v0, 0x7C(sp)
    ori   v0, zero, 1
    sb    v0, 0xB8(sp)
    j     0x80026FE4
    nop

; Called only by the title menu's caller. The original menu still handles all input.
end_menu:
    addiu sp, sp, -0x20
    sw    ra, 0x1C(sp)
    sw    s0, 0x18(sp)
@title:
    jal   0x80026BDC
    ori   a0, zero, 14
    ori   t0, zero, 4
    bne   v0, t0, @return
    nop
    la    t0, end_page
    sw    zero, 0(t0)
@view:
    jal   0x80026BDC
    ori   a0, zero, 35
    la    t0, end_page
    lw    t1, 0(t0)
    la    t2, end_page_table
    sll   t1, t1, 2
    addu  t2, t2, t1
    lw    t2, 0(t2)
    bltz  v0, @back
    sll   v0, v0, 1
    addu  t2, t2, v0
    lhu   t1, 16(t2)
    b     @target
    nop
@back:
    lhu   t1, 12(t2)
    nop
@target:
    ori   t2, zero, 0xFFFF
    beq   t1, t2, @title
    nop
    b     @view
    sw    t1, 0(t0)
@return:
    lw    ra, 0x1C(sp)
    lw    s0, 0x18(sp)
    jr    ra
    addiu sp, sp, 0x20

; Extend the native message selector with private request 35.
end_message:
    ori   v0, zero, 35
    beq   t0, v0, @custom
    nop
    sltiu v0, t0, 0x23
    j     0x80026C3C
    nop
@custom:
    jal   end_page_build
    addiu a0, sp, 0x30
    j     0x80026FE4
    nop

; a0 = native menu descriptor on its usual stack frame.
end_page_build:
    addiu sp, sp, -0x30
    sw    ra, 0x2C(sp)
    sw    s0, 0x10(sp)
    sw    s1, 0x14(sp)
    sw    s2, 0x18(sp)
    sw    s3, 0x1C(sp)
    sw    s4, 0x20(sp)
    sw    s5, 0x24(sp)
    move  s0, a0
    la    t0, end_page
    lw    t0, 0(t0)
    la    t1, end_page_table
    sll   t0, t0, 2
    addu  t1, t1, t0
    lw    s1, 0(t1)
    nop
    lw    t0, 0(s1)
    lw    t1, 4(s1)
    lw    t2, 8(s1)
    sw    t0, 0(s0)
    sw    t1, 0x14(s0)
    sw    t2, 0x38(s0)
    sw    zero, 0x64(s0)
    ori   t0, zero, 1
    ori   t1, zero, 8
    addiu t2, s0, 0x84
@enabled:
    sb    t0, 0(t2)
    addiu t1, t1, -1
    bnez  t1, @enabled
    addiu t2, t2, 1
    addiu s1, s1, 32
    la    s2, end_strings
    move  s3, zero
@label:
    lw    t0, 0(s1)
    move  t1, s2
@copy:
    lbu   t2, 0(t0)
    addiu t0, t0, 1
    sb    t2, 0(t1)
    bnez  t2, @copy
    addiu t1, t1, 1
    sll   t0, s3, 2
    sltiu t1, s3, 8
    bnez  t1, @pointer
    addiu t0, t0, 0x18
    addiu t0, t0, 4
@pointer:
    addu  t0, s0, t0
    sw    s2, 0(t0)
    lw    t0, 4(s1)
    lhu   t1, 8(s1)
    move  s4, zero
    beqz  t1, @format
    nop
@count:
    lhu   t2, 0(t0)
    la    t3, end_bits
    srl   t4, t2, 3
    addu  t3, t3, t4
    lbu   t3, 0(t3)
    andi  t2, t2, 7
    srlv  t3, t3, t2
    andi  t3, t3, 1
    addu  s4, s4, t3
    addiu t1, t1, -1
    bnez  t1, @count
    addiu t0, t0, 2
@format:
    lbu   t0, 10(s1)
    lbu   t1, 11(s1)
    addu  t0, s2, t0
    ori   t2, zero, 1
    beq   t1, t2, @digits
    ori   t2, zero, 2
    bne   t1, t2, @next
    nop
    beqz  s4, @next
    nop
    la    t1, end_done
    ori   t2, zero, 6
@done:
    lbu   t3, 0(t1)
    addiu t1, t1, 1
    sb    t3, 0(t0)
    addiu t2, t2, -1
    bnez  t2, @done
    addiu t0, t0, 1
    b     @next
    nop
@digits:
    move  t1, zero
@hundreds:
    sltiu t2, s4, 100
    bnez  t2, @tens_init
    nop
    addiu s4, s4, -100
    b     @hundreds
    addiu t1, t1, 1
@tens_init:
    addiu t1, t1, 48
    sb    t1, 0(t0)
    move  t1, zero
@tens:
    sltiu t2, s4, 10
    bnez  t2, @units
    nop
    addiu s4, s4, -10
    b     @tens
    addiu t1, t1, 1
@units:
    addiu t1, t1, 48
    addiu s4, s4, 48
    sb    t1, 1(t0)
    sb    s4, 2(t0)
@next:
    addiu s3, s3, 1
    addiu s1, s1, 12
    sltiu t0, s3, 16
    bnez  t0, @label
    addiu s2, s2, 48
    lw    ra, 0x2C(sp)
    lw    s0, 0x10(sp)
    lw    s1, 0x14(sp)
    lw    s2, 0x18(sp)
    lw    s3, 0x1C(sp)
    lw    s4, 0x20(sp)
    lw    s5, 0x24(sp)
    jr    ra
    addiu sp, sp, 0x30
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--catalog', type=Path)
    args = ap.parse_args()
    rows = catalog()
    print('%d conclusions, %d bytes of %d save bytes, %d menu pages' %
          (len(rows), (len(rows) + 7) // 8, END_BYTES, len(pages(rows))))
    for i, name in enumerate(GROUPS):
        print('  %s: %d' % (name, sum(r['group'] == i for r in rows)))
    if args.catalog:
        args.catalog.parent.mkdir(parents=True, exist_ok=True)
        args.catalog.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
