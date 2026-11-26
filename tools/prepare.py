"""Turn extracted plugin strings into translation batches.

    python tools/prepare.py <mod-dir>          # e.g. mods/become-high-king-tng

Reads  <mod-dir>/mod.json, work/<slug>/en/*.json (from extract.py)
Writes work/<slug>/units.json          unique source strings + context
       work/<slug>/batches/NNN.json    {batch, terms, items:[{id, en, ctx}]}
       work/<slug>/auto.json           strings resolved from vanilla (no LLM needed)

With "reuse_installed": true in mod.json (needs `tools/harvest.py` first):
strings another installed DSD file already translates are skipped, and text
already translated somewhere in the setup is reused as an exact match.
Originals that are already Russian are always skipped.

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_CHARS = 18000
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def uid(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:12]


def load_json(path, default=None):
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    return default


CYR = re.compile('[А-Яа-яЁё]')


def installed(mod):
    """(known, covered) from tools/harvest.py, or empty if the mod doesn't opt in."""
    if not mod.get('reuse_installed'):
        return {}, set()
    known = load_json(os.path.join(ROOT, 'vanilla', 'known.json'))
    covered = load_json(os.path.join(ROOT, 'vanilla', 'covered.json'))
    if known is None or covered is None:
        sys.exit('reuse_installed: run tools/harvest.py first')
    return known, set(covered)


def wanted(e, covered):
    """False for strings that need no DSD entry from us."""
    if CYR.search(e['original']):
        return False
    return record_key(e) not in covered


SPACE = re.compile(r'\s+')
REPLICA = re.compile(r'^(.*\S)\s*\((?:replica|Replica)\)$')


class Exact:
    """Already-translated text: exact match, then the same text with different
    whitespace/line breaks, then "<name> (replica)" from the translated name."""

    def __init__(self, table):
        self.table = table
        self.loose = {}
        for en, ru in table.items():
            self.loose.setdefault(self.norm(en), ru)

    @staticmethod
    def norm(s):
        return SPACE.sub(' ', s).strip()

    def get(self, en):
        ru = self.table.get(en) or self.loose.get(self.norm(en))
        if ru:
            return ru
        m = REPLICA.match(en)
        if m:
            base = self.table.get(m.group(1)) or self.loose.get(self.norm(m.group(1)))
            if base:
                return f'{base} (копия)'
        return None


def record_key(e):
    from harvest import key
    return key(e)


def common_words():
    """Words that vanilla English mostly writes in lowercase = not proper nouns."""
    exact = load_json(os.path.join(ROOT, 'vanilla', 'exact.json'), {})
    lower, upper = {}, {}
    for s in exact:
        for w in WORD.findall(s):
            d = lower if w[0].islower() else upper
            d[w.lower()] = d.get(w.lower(), 0) + 1
    return {w for w, n in lower.items() if n >= 3 and n > upper.get(w, 0)}


def glossary_for(mod_dir, extra_names=None):
    g = {}
    names = {**(extra_names or {}), **load_json(os.path.join(ROOT, 'vanilla', 'names.json'), {})}
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


NAME_TYPES = {'NPC_ FULL', 'NPC_ SHRT', 'CELL FULL', 'LCTN FULL', 'WRLD FULL', 'FACT FULL',
              'ARMO FULL', 'WEAP FULL', 'MISC FULL', 'BOOK FULL', 'SPEL FULL', 'QUST FULL'}


def learned_names(work):
    """Names already translated in this mod (NPCs, places, items) become terms,
    so every later batch spells them the same way."""
    out = {}
    tr = {}
    for f in glob.glob(os.path.join(work, 'out', '*.json')):
        tr.update(load_json(f, {}))
    if not tr:
        return out
    for f in glob.glob(os.path.join(work, 'en', '*.json')):
        for e in json.load(open(f, encoding='utf-8')):
            if e['type'] in NAME_TYPES and len(e['original']) <= 40:
                ru = tr.get(uid(e['original']))
                if ru and e['original'][:1].isupper():
                    out[e['original']] = ru
    return out


def main(mod_dir):
    mod = json.load(open(os.path.join(mod_dir, 'mod.json'), encoding='utf-8'))
    work = os.path.join(ROOT, 'work', mod['slug'])
    known, covered = installed(mod)
    exact = Exact({**known, **load_json(os.path.join(ROOT, 'vanilla', 'exact.json'), {})})
    glossary = learned_names(work)
    # names already translated elsewhere in the setup (reuse_installed) count as terms too
    glossary.update(glossary_for(mod_dir, {k: v for k, v in known.items() if len(k) <= 40}))
    index = TermIndex(glossary)

    units, auto = {}, {}
    for f in sorted(glob.glob(os.path.join(work, 'en', '*.json'))):
        for e in json.load(open(f, encoding='utf-8')):
            if not wanted(e, covered):
                continue
            en = e['original']
            i = uid(en)
            ru = exact.get(en)
            if ru:
                auto[i] = ru
                continue
            first = i not in units
            u = units.setdefault(i, {'id': i, 'en': en, 'ctx': [], 'order': len(units)})
            ctx = e['type']
            if e.get('editor_id'):
                ctx += f" {e['editor_id']}"
            if e.get('_speaker'):
                ctx += f" | говорит: {e['_speaker']}"
            if e.get('_topic') and e['_topic'] != en:
                ctx += f" | ответ на: {e['_topic']}"
            if ctx not in u['ctx'] and len(u['ctx']) < 3:
                u['ctx'].append(ctx)
            if first:
                u['type'] = e['type']

    # keep the plugin's own order inside each record type, so the lines of
    # one conversation stay together; types grouped so batches are uniform
    type_rank = {}
    for u in sorted(units.values(), key=lambda u: u['order']):
        type_rank.setdefault(u['type'], len(type_rank))
    ordered = sorted(units.values(), key=lambda u: (type_rank[u['type']], u['order']))
    batches, cur, size = [], [], 0
    for u in ordered:
        item = {'id': u['id'], 'en': u['en'], 'ctx': '; '.join(u['ctx'])}
        if cur and size + len(u['en']) > BATCH_CHARS:
            batches.append(cur)
            cur, size = [], 0
        cur.append(item)
        size += len(u['en'])
    if cur:
        batches.append(cur)

    bdir = os.path.join(work, 'batches')
    os.makedirs(bdir, exist_ok=True)
    keep = {f'{n:03d}.json' for n in range(1, len(batches) + 1)}
    for old in glob.glob(os.path.join(bdir, '*.json')):
        if os.path.basename(old) not in keep:
            os.remove(old)  # never delete files that are rewritten: agents may be reading them
    for n, b in enumerate(batches, 1):
        terms = {}
        for item in b:
            terms.update(index.find(item['en']))
        doc = {'batch': f'{n:03d}', 'terms': dict(sorted(terms.items())), 'items': b}
        tmp = os.path.join(bdir, f'{n:03d}.json.tmp')
        json.dump(doc, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(bdir, f'{n:03d}.json'))  # atomic
    json.dump(auto, open(os.path.join(work, 'auto.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'units {len(units)}  vanilla-auto {len(auto)}  batches {len(batches)} -> {bdir}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
