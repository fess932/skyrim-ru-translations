"""Mine lore terms from the official translation: proper nouns that appear inside
sentences and books (not only as short names), with the Russian form the
official translators used for them.

    python tools/lore_terms.py            # writes vanilla/lore.json (gitignored)

How: for every capitalised English phrase (1-3 words) that occurs in at least
MIN_HITS different vanilla strings, look at the aligned Russian strings and pick
the capitalised Russian word sequence that occurs in nearly all of them.
The result is a hint list for prepare.py, so batches get the same term the game uses.
"""
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prepare import common_words, load_json  # noqa: E402

MIN_HITS = 4
MIN_SHARE = 0.6
EN_PHRASE = re.compile(r"\b([A-Z][a-z'\-]+(?:[ \-](?:of|the|de|and)?[ ]?[A-Z][a-z'\-]+){0,2})\b")
RU_WORD = re.compile(r"[А-ЯЁа-яё][а-яё'\-]+")
TAG = re.compile(r'<[^>]*>|\[pagebreak\]', re.I)
STOP = {'The', 'A', 'An', 'I', 'You', 'He', 'She', 'It', 'We', 'They', 'My', 'Your', 'His', 'Her',
        'Our', 'Their', 'This', 'That', 'What', 'Who', 'Why', 'How', 'Where', 'When', 'If', 'But',
        'And', 'Or', 'So', 'No', 'Yes', 'Not', 'In', 'On', 'At', 'To', 'For', 'With', 'By', 'From',
        'As', 'All', 'One', 'There', 'Here', 'Now', 'Then', 'Well', 'Oh', 'Ah', 'Do', 'Is', 'Are'}


# first-letter sanity check for transliterated names: "Sithis" -> "Ситис" passes,
# "Alright" -> "Ладно" (a common word that slipped through) does not
FIRST = {'a': 'аэ', 'b': 'б', 'c': 'ксцч', 'd': 'д', 'e': 'эеи', 'f': 'ф', 'g': 'гдж', 'h': 'хг', 'i': 'иай',
         'j': 'дйж', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'оа', 'p': 'п', 'q': 'к', 'r': 'р', 's': 'сшз',
         't': 'тс', 'u': 'уюа', 'v': 'в', 'w': 'ву', 'x': 'кз', 'y': 'йиюы', 'z': 'зц'}


def looks_transliterated(en, ru):
    return ru[:1].lower() in FIRST.get(en[:1].lower(), '')


def stem(w):
    return w.lower()[:max(4, len(w) - 3)]


def main():
    exact = load_json(os.path.join(ROOT, 'vanilla', 'exact.json'), {})
    common = common_words()
    occ = collections.defaultdict(list)
    for en, ru in exact.items():
        if len(en) < 20:
            continue  # short names are already covered by names.json
        en_t, ru_t = TAG.sub(' ', en), TAG.sub(' ', ru)
        seen = set()
        for m in EN_PHRASE.finditer(en_t):
            p = m.group(1)
            words = p.split()
            if words[0] in STOP or any(w.lower() in common for w in words) or p.endswith(('-', "'s")):
                continue
            if p not in seen:
                seen.add(p)
                occ[p].append(ru_t)
    # how common each Russian word sequence is in the whole game text: a term's
    # translation must be specific to it, not a frequent word like "Не" or "Он"
    df = collections.Counter()
    all_ru = list(exact.values())
    for ru in all_ru:
        words = RU_WORD.findall(TAG.sub(' ', ru))
        df.update({' '.join(stem(w) for w in words[i:i + n])
                   for n in (1, 2, 3) for i in range(len(words) - n + 1)})
    total = len(all_ru)
    vocab = collections.Counter(w for ru in all_ru for w in RU_WORD.findall(TAG.sub(' ', ru)) if w[0].isupper())
    names = load_json(os.path.join(ROOT, 'vanilla', 'names.json'), {})

    def base_form(en, ru):
        # official short name wins; else strip a case ending if that word exists in the game text
        if names.get(en):
            return names[en]
        words = ru.split()
        last = words[-1]
        for end in ('ами', 'ому', 'ого', 'ой', 'ом', 'ах', 'а', 'у', 'е', 'ы', 'и', 'ю'):
            cand = last[:-len(end)]
            if last.endswith(end) and len(cand) >= 3 and vocab[cand] >= 2:
                return ' '.join(words[:-1] + [cand])
        return ru
    out = {}
    for en, rus in occ.items():
        if len(rus) < MIN_HITS:
            continue
        cnt = collections.Counter()
        forms = collections.defaultdict(collections.Counter)
        for ru in rus:
            words = RU_WORD.findall(ru)
            seen = set()
            for n in (1, 2, 3):
                for i in range(len(words) - n + 1):
                    seq = words[i:i + n]
                    key = ' '.join(stem(w) for w in seq)
                    if key in seen:
                        continue
                    seen.add(key)
                    cnt[key] += 1
                    forms[key][' '.join(seq)] += 1
        n_en = len(en.split())
        best = None
        for key, c in cnt.most_common():
            if c / len(rus) < MIN_SHARE:
                break
            if len(key.split()) != n_en:
                continue
            if (c / len(rus)) / (df[key] / total) < 30:
                continue  # not specific to this term  # "High Rock" must map to two words, not to "Хай"
            if not any(f[0].isupper() for f in forms[key]):
                continue  # a proper noun is capitalised at least sometimes
            best = key
            break
        if best and not all(looks_transliterated(e, r) for e, r in zip(en.split(), best.split())):
            best = None
        if best:
            # base form: the shortest frequent capitalised variant ("Этериус", not "Этериуса")
            fs = [(f, n) for f, n in forms[best].items() if f[0].isupper()]
            top = max(fs, key=lambda x: x[1])[0]
            # base form: the shortest variant the most frequent one starts with
            # ("Этериус" for "Этериуса"); otherwise the most frequent one
            out[en] = base_form(en, min((f for f, _ in fs if top.startswith(f) and len(f) >= len(top) - 3), key=len, default=top))
    # drop sub-phrases already explained by a longer term with the same Russian
    os.makedirs(os.path.join(ROOT, 'vanilla'), exist_ok=True)
    json.dump(dict(sorted(out.items())), open(os.path.join(ROOT, 'vanilla', 'lore.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)
    print(f'{len(out)} lore terms -> vanilla/lore.json')


if __name__ == '__main__':
    main()
