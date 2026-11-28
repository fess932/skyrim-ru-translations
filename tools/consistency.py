"""Find glossary terms that a translation renders differently from the glossary.

    python tools/consistency.py mods/<slug> [mods/<slug> ...]   # or: all

For every glossary term (vanilla names, lore terms, curated and mod glossaries)
that occurs in an English source string, the Russian string should contain the
glossary rendering (any case form: compared by word stems). Mismatches are
grouped by term, most frequent first, with a few examples - so drift like
"Зеленый Договор" vs "Зеленый пакт" shows up after a batch run.
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prepare import ROOT, TermIndex, common_words, glossary_for, learned_names, load_json, uid  # noqa: E402

CYR = re.compile('[А-Яа-яЁё]')
WORD = re.compile(r"[\w'\-]+")


def stems(text):
    return [w.lower()[:max(3, len(w) - 3)] for w in WORD.findall(text)]


def contains(ru, term_ru):
    """True if every word of term_ru appears (by stem) in ru, in order-insensitive way."""
    have = set()
    for w in WORD.findall(ru.lower()):
        have.add(w)
    for t in WORD.findall(term_ru.lower()):
        st = t[:max(3, len(t) - (4 if len(t) >= 8 else 3))]  # tolerate case endings
        if not any(h.startswith(st) for h in have):
            return False
    return True


def check(mod_dir):
    mod = json.load(open(os.path.join(mod_dir, 'mod.json'), encoding='utf-8'))
    work = os.path.join(ROOT, 'work', mod['slug'])
    tr = {}
    for f in glob.glob(os.path.join(work, 'out', '*.json')):
        tr.update(load_json(f, {}))
    glossary = learned_names(work)
    glossary.update(glossary_for(mod_dir))
    common = common_words()
    # only proper nouns: everyday words ("Hold", "Steel", "Thank") have many valid renderings
    glossary = {k: v for k, v in glossary.items()
                if v[:1].isupper() and not all(w.lower() in common for w in WORD.findall(k))
                and len(WORD.findall(k)) <= 4}
    index = TermIndex(glossary)
    bad = collections.defaultdict(list)
    seen = set()
    for f in glob.glob(os.path.join(work, 'en', '*.json')):
        for e in json.load(open(f, encoding='utf-8')):
            en = e['original']
            i = uid(en)
            if i in seen or i not in tr or not CYR.search(tr[i]):
                continue
            seen.add(i)
            for term, ru in index.find(en).items():
                if not CYR.search(ru) or len(term) < 4:
                    continue
                if not contains(tr[i], ru):
                    bad[(term, ru)].append((en, tr[i], i))
    return mod['slug'], bad


def main(args):
    if args == ['all']:
        args = sorted(os.path.dirname(p) for p in glob.glob(os.path.join(ROOT, 'mods', '*', 'mod.json')))
    for mod_dir in args:
        if not os.path.isdir(os.path.join(ROOT, 'work', os.path.basename(mod_dir.rstrip('/\\')))):
            continue
        slug, bad = check(mod_dir)
        total = sum(len(v) for v in bad.values())
        print(f'== {slug}: {total} strings where a glossary term looks translated differently')
        for (term, ru), items in sorted(bad.items(), key=lambda x: -len(x[1]))[:25]:
            en, tr, i = items[0]
            print(f'  {len(items):4}  {term} -> {ru}   e.g. [{i}] {tr[:110]!r}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
