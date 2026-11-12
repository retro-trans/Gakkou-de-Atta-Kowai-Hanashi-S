"""Fix names and fixed terms across the English scene files (BASE_RULES: scripts fix names,
agents fix meaning; run this AFTER applying agent output, every time).

    python tools/fix_terms.py           dry run: rows each rule would change
    python tools/fix_terms.py --apply

Each rule: (english regex, replacement, scenes or None, Japanese condition regex or None
[, Japanese exclusion regex]).
A rule only touches rows of the listed scenes whose Japanese matches the condition, so a
word with another meaning elsewhere is left alone. The replacement keeps the first
letter's case. Terms listed here are on the agents' do-not-touch list (docs/AGENT_REVIEW.md).
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENES = os.path.join(ROOT, 'work', 'translation', 'en', 'scenes')

def laugh(m):
    """Ufufu / Fufufu (romanized うふふ) -> Heh heh..., one 'Heh' per 'fu' (at least two)."""
    n = max(2, m.group(0).lower().count('fu'))
    return ' '.join(['Heh'] + ['heh'] * (n - 1))


RULES = [
    (r'\bampule(s?)\b', r'ampoule\1', None, None),
    (r'\bsongstress\b', 'diva', ['06'], '歌姫'),
    (r'\bMaster Hino\b', 'Lord Hino', None, '日野様'),
    (r'\bKuwabata\b', 'Kuwahata', None, '桑畑'),
    (r'\bFilm Society\b', 'Film Research Society', ['12'], '映画研究会'),
    (r'\bjorogumo spider(s?)\b', r'joro spider\1', ['26'], None),
    (r'\bpage-a-day calendar(s?)\b', r'tear-off calendar\1', ['39'], None),
    (r'\bUntamaroan(s?)\b', r'Untamarian\1', ['44'], None),
    (r'\bmolester(s?)\b', r'pervert\1', ['57'], 'チカン|痴漢'),
    (r'\bdetention room(s?)\b', r'reflection room\1', ['68'], '反省室'),
    (r'\bapology essay(s?)\b', r'apology letter\1', None, '反省文'),
    (r'\bindoor slippers\b', 'indoor shoes', None, '上履き|上ばき'),
    (r'\bschool slipper(s?)\b', r'indoor shoe\1', None, '上履き|上ばき'),
    (r'\bremedial class(es)?\b', r'make-up class\1', ['27'], '補習'),
    (r'\bbathroom(s?)\b', r'restroom\1', None, 'トイレ|便所', '浴室|風呂|バス'),
    (r'something like a badge', 'something like a patch', ['44'], 'ワッペン'),
    (r'\bbadge(s?)\b', r'patch\1', ['44'], 'ワッペン'),
    (r'\bstaff room(s?)\b', r'faculty room\1', None, '職員室'),
    (r'\b(?:a|the) lodging facility\b', 'the lodge', ['11'], '宿泊施設'),
    (r'\blodging facility\b', 'lodge', ['11'], '宿泊施設'),
    (r'\b(?:a|the) dormitory\b', 'the lodge', ['11'], '宿泊施設'),
    (r'\bfive-hundred-yen\b', '500-yen', ['17'], None),
    (r'\bsoccer team(s?)\b', r'soccer club\1', None, 'サッカー部'),     # E023/E024
    (r'\b[Ss]even [Mm]ysteries\b', 'seven wonders', None, '七不思議'),
    (r'\b[Ss]ix [Mm]ysteries\b', 'six wonders', None, '六不思議'),       # E082
    (r'\b(?:the )?[Nn]otebook of [Gg]rudges\b', 'the Grudge Notebook', None, '恨み'),
    (r'\b[Oo]rdinary [Pp]erson [Cc]ourse\b', 'Ordinary Folk Course', None, '一般人コース'),
    (r'\b[Uu]?[Ff]u(?:-?fu)+\b', laugh, [str(n) for n in range(29, 35)], 'ふふ'),  # Iwashita's scenes only
    # proofreading unifications (review_todo [proofread] items)
    (r'\b[Ss]earch somewhere else\b', 'Search elsewhere', ['07'], None),
    (r'\bphantom(s?)\b', r'Phantom\1', ['55'], '怪人'),
    (r'\bhour of evil\b', 'witching hour', None, '魔の時'),
    (r'\boshiruko\b', 'red-bean soup', ['35'], 'しるこ'),
    (r'\b(?:on|in) the shel(?:f|ves)\b', 'in the cabinet', ['14'], '棚', '本棚'),
    (r'\bshel(?:f|ves)\b', 'cabinet', ['14'], '棚', '本棚'),
    # scene 07 menu prompts: self-question form (S029 review)
    # (a prompt can start the row or follow a page/line break)
    (r'(?:^|(?<=\{p\})|(?<=\n))Which classroom will you go to\?', 'Which classroom should I go to?', ['07'], 'どの教室に行く'),
    (r'(?:^|(?<=\{p\})|(?<=\n))What will you do\?', 'What should I do?', ['07'], r'(?:^|\}|\n)どうする？'),
    (r'(?:^|(?<=\{p\})|(?<=\n))Where will you go\?', 'Where should I go?', ['07'], r'(?:^|\}|\n)どこ[へに]行く？'),
    (r'(?:^|(?<=\{p\})|(?<=\n))Where will you search\?', 'Where should I search?', ['07'], r'(?:^|\}|\n)どこを捜す？'),
]


def keep_case(m, rep):
    s = rep(m) if callable(rep) else m.expand(rep)
    if m.group(0)[:1].isupper():
        s = s[:1].upper() + s[1:]
    return s


def main():
    apply = '--apply' in sys.argv
    total = 0
    for f in sorted(glob.glob(os.path.join(SCENES, 'SCE??.json'))):
        scene = os.path.basename(f)[3:5]
        rows = json.load(open(f, encoding='utf-8'))
        changed = False
        for r in rows:
            en = r.get('en') or ''
            for pat, rep, scenes, cond, *unless in RULES:
                if scenes and scene not in scenes:
                    continue
                if cond and not re.search(cond, r['jp']):
                    continue
                if unless and re.search(unless[0], r['jp']):
                    continue      # e.g. a row that also has a real bathroom (浴室)
                new = re.sub(pat, lambda m: keep_case(m, rep), en)
                if new != en:
                    print('%s  %s -> %s' % (r['id'], pat, getattr(rep, '__name__', rep)))
                    en = new
                    total += 1
            if en != (r.get('en') or ''):
                r['en'] = en
                changed = True
        if apply and changed:
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=1)
                fh.write('\n')
    print('%d fixes%s' % (total, '' if apply else ' (dry run)'))


if __name__ == '__main__':
    main()
