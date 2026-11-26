"""Checks that a translation keeps everything the game parses.

Used by build.py; can be run on a batch result:
    python tools/validate.py work/<slug>/batches/001.json work/<slug>/out/001.json
"""
import json
import re
import sys
from collections import Counter

TAG = re.compile(r'<[^<>\n]{1,200}>')          # <Alias=X>, <mag>, <font ...>, <p>, <img ...>
# Latin drop-cap pictures ("<img ...Illuminated_Letters/T_letter.png>hey told") make no sense in
# Russian: the translation writes the whole word and build.py drops the picture.
DROPCAP = re.compile(r"<img[^<>]*Illuminated_Letters/[^<>]*>", re.I)
PAGEBREAK = re.compile(r'\[pagebreak\]', re.I)
FMT = re.compile(r'%[0-9.]*[sdif%]')
CYR = re.compile('[Ѐ-ӿ]')
TECHNICAL = re.compile(r'[A-Za-z0-9_:.\-]*(?:[a-z][A-Z]|_|\d)[A-Za-z0-9_:.\-]*|[A-Z0-9_]+')
LATIN_WORD = re.compile(r'(?<![<\w=\'"/.])[A-Za-z]{4,}(?![\w>])')


def tags(s):
    return Counter(t for t in TAG.findall(s) if not DROPCAP.fullmatch(t))


def strip_tags(s):
    return TAG.sub(' ', s)


def check(en, ru):
    """Return list of problems (empty = ok)."""
    p = []
    if not ru or not ru.strip():
        return ['empty']
    if ru == en and TECHNICAL.fullmatch(en):
        return []  # editor IDs and similar are left as is on purpose
    if tags(en) != tags(ru):
        p.append('tags differ: %s' % tag_diff(en, ru)[:4])
    if len(PAGEBREAK.findall(en)) != len(PAGEBREAK.findall(ru)):
        p.append('pagebreak count')
    if Counter(FMT.findall(en)) != Counter(FMT.findall(ru)):
        p.append('format specifiers')
    if re.search('[A-Za-z]', strip_tags(en)) and not CYR.search(strip_tags(ru)):
        p.append('no cyrillic')
    if en.count('\n') and abs(en.count('\n') - ru.count('\n')) > max(2, en.count('\n') // 3):
        p.append('line breaks %d->%d' % (en.count('\n'), ru.count('\n')))
    return p


def tag_diff(en, ru):
    a, b = tags(en), tags(ru)
    return list((a - b).elements()) + list((b - a).elements())


if __name__ == '__main__':
    src = {u['id']: u['en'] for u in json.load(open(sys.argv[1], encoding='utf-8'))['items']}
    out = json.load(open(sys.argv[2], encoding='utf-8'))
    bad = 0
    for i, en in src.items():
        probs = check(en, out.get(i, ''))
        if probs:
            bad += 1
            print(i, probs, '|', en[:70].replace('\n', ' '))
    print(f'{len(src) - bad}/{len(src)} ok')
    sys.exit(1 if bad else 0)
