"""Turn extracted plugin strings into translation batches.

    python tools/prepare.py <mod-dir>          # e.g. mods/become-high-king-tng

Reads  <mod-dir>/mod.json, work/<slug>/en/*.json (from extract.py)
Writes work/<slug>/units.json          unique source strings + context
       work/<slug>/batches/NNN.json    {batch, terms, items:[{id, en, ctx}]}
       work/<slug>/auto.json           strings resolved from vanilla (no LLM needed)

A unit = one unique English string. Identical lines are translated once.
`terms` = glossary entries that literally occur in the batch's strings (base
glossary, mod glossary, vanilla proper nouns) - lexical retrieval, listed once
per batch so it costs little context.
"""
import glob
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_CHARS = 18000
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def uid(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:12]


def load_json(path, default=None):
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    return default


def common_words():
    """Words that vanilla English mostly writes in lowercase = not proper nouns."""
    exact = load_json(os.path.join(ROOT, 'vanilla', 'exact.json'), {})
    lower, upper = {}, {}
    for s in exact:
        for w in WORD.findall(s):
            d = lower if w[0].islower() else upper
            d[w.lower()] = d.get(w.lower(), 0) + 1
    return {w for w, n in lower.items() if n >= 3 and n > upper.get(w, 0)}


def glossary_for(mod_dir):
    g = {}
    names = load_json(os.path.join(ROOT, 'vanilla', 'names.json'), {})
    common = common_words()
    # vanilla names: proper nouns only (capitalised, short, not an everyday word)
    for en, ru in names.items():
        words = WORD.findall(en)
        if not (2 < len(en) <= 40 and en[0].isupper() and 0 < len(words) <= 5):
            continue
        if en.isupper() or not en[-1].isalpha() or (len(words) == 1 and len(en) <= 4):
            continue  # "BOOKS", "Windhelm.", "Yes"
        if all(w.lower() in common for w in words):
            continue
        g[en] = ru
    g.update(load_json(os.path.join(ROOT, 'glossary', 'base.json'), {}))
    g.update(load_json(os.path.join(mod_dir, 'glossary.json'), {}))
    return {k: v for k, v in g.items() if v}


class TermIndex:
    def __init__(self, glossary):
        self.g = glossary
        self.by_first = {}
        for term in glossary:
            words = WORD.findall(term)
            if words:
                self.by_first.setdefault(words[0].lower(), []).append(term)
        for v in self.by_first.values():
            v.sort(key=len, reverse=True)

    def find(self, text):
        hits = {}
        low = text.lower()
        for w in set(x.lower() for x in WORD.findall(text)):
            for term in self.by_first.get(w, ()):
                if term in hits:
                    continue
                if re.search(r'(?<![A-Za-z])' + re.escape(term.lower()) + r'(?![A-Za-z])', low):
                    hits[term] = self.g[term]
        # drop terms fully contained in a longer hit ("Jarl" inside "Jarl Balgruuf")
        keys = sorted(hits, key=len, reverse=True)
        out = {}
        for k in keys:
            if not any(k != o and k.lower() in o.lower() for o in out):
                out[k] = hits[k]
        return out


def main(mod_dir):
    mod = json.load(open(os.path.join(mod_dir, 'mod.json'), encoding='utf-8'))
    work = os.path.join(ROOT, 'work', mod['slug'])
    exact = load_json(os.path.join(ROOT, 'vanilla', 'exact.json'), {})
    index = TermIndex(glossary_for(mod_dir))

    units, auto = {}, {}
    for f in sorted(glob.glob(os.path.join(work, 'en', '*.json'))):
        for e in json.load(open(f, encoding='utf-8')):
            en = e['original']
            i = uid(en)
            if en in exact:
                auto[i] = exact[en]
                continue
            u = units.setdefault(i, {'id': i, 'en': en, 'ctx': set()})
            ctx = e['type']
            if e.get('editor_id'):
                ctx += f" {e['editor_id']}"
            if len(u['ctx']) < 3:
                u['ctx'].add(ctx)

    ordered = sorted(units.values(), key=lambda u: (sorted(u['ctx'])[0], u['en']))
    batches, cur, size = [], [], 0
    for u in ordered:
        item = {'id': u['id'], 'en': u['en'], 'ctx': '; '.join(sorted(u['ctx']))}
        if cur and size + len(u['en']) > BATCH_CHARS:
            batches.append(cur)
            cur, size = [], 0
        cur.append(item)
        size += len(u['en'])
    if cur:
        batches.append(cur)

    bdir = os.path.join(work, 'batches')
    os.makedirs(bdir, exist_ok=True)
    for old in glob.glob(os.path.join(bdir, '*.json')):
        os.remove(old)
    for n, b in enumerate(batches, 1):
        terms = {}
        for item in b:
            terms.update(index.find(item['en']))
        doc = {'batch': f'{n:03d}', 'terms': dict(sorted(terms.items())), 'items': b}
        json.dump(doc, open(os.path.join(bdir, f'{n:03d}.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    json.dump(auto, open(os.path.join(work, 'auto.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'units {len(units)}  vanilla-auto {len(auto)}  batches {len(batches)} -> {bdir}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
