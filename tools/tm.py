"""Translation memory: retrieve already-translated lines similar to new ones.

The memory is the repo itself: every published mods/*/.../RU.json plus the
in-progress work/*/out/*.json. No separate database.

Similarity = TF-IDF cosine over character 3-grams of the lowercased text
(robust to small wording changes, no embeddings needed).
"""
import glob
import json
import math
import os
import re
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r'<[^<>\n]{1,200}>')


def grams(s):
    s = ' ' + re.sub(r'\s+', ' ', TAG.sub(' ', s.lower())).strip() + ' '
    return Counter(s[i:i + 3] for i in range(len(s) - 2))


def load_pairs(slug=None):
    """EN->RU pairs from published translations and current work."""
    pairs = {}
    for f in glob.glob(os.path.join(ROOT, 'mods', '*', 'SKSE', 'Plugins', 'DynamicStringDistributor', '*', 'RU.json')):
        for e in json.load(open(f, encoding='utf-8')):
            if e.get('string'):
                pairs.setdefault(e['original'], e['string'])
    for work in glob.glob(os.path.join(ROOT, 'work', '*')):
        batches = {}
        for b in glob.glob(os.path.join(work, 'batches', '*.json')):
            for it in json.load(open(b, encoding='utf-8'))['items']:
                batches[it['id']] = it['en']
        for o in glob.glob(os.path.join(work, 'out', '*.json')):
            for i, ru in json.load(open(o, encoding='utf-8')).items():
                if i in batches and ru:
                    pairs[batches[i]] = ru
    return pairs


class Memory:
    def __init__(self, pairs):
        self.items = [(en, ru) for en, ru in pairs.items() if 3 <= len(en) <= 600]
        self.vecs = []
        df = Counter()
        for en, _ in self.items:
            g = grams(en)
            self.vecs.append(g)
            df.update(g.keys())
        n = max(len(self.items), 1)
        self.idf = {g: math.log(n / c) + 1 for g, c in df.items()}
        self.norm = []
        self.inv = defaultdict(list)
        for k, v in enumerate(self.vecs):
            w = {g: c * self.idf[g] for g, c in v.items()}
            self.vecs[k] = w
            self.norm.append(math.sqrt(sum(x * x for x in w.values())) or 1)
            for g in w:
                self.inv[g].append(k)

    def search(self, text, k=3, min_score=0.45, rare_grams=40):
        q = grams(text)
        qw = {g: c * self.idf.get(g, 1) for g, c in q.items()}
        qn = math.sqrt(sum(x * x for x in qw.values())) or 1
        # candidates via the rarest grams only (fast, still accurate)
        rare = sorted((g for g in qw if g in self.inv), key=lambda g: len(self.inv[g]))[:rare_grams]
        cand = set()
        for g in rare:
            cand.update(self.inv[g])
        scored = []
        for c in cand:
            v = self.vecs[c]
            dot = sum(qw[g] * v[g] for g in qw if g in v)
            s = dot / (qn * self.norm[c])
            if s >= min_score and self.items[c][0] != text:
                scored.append((s, c))
        scored.sort(reverse=True)
        return [(round(s, 2), *self.items[c]) for s, c in scored[:k]]


def examples_for(texts, memory, per_item=2, limit=20):
    """Best memory examples for a set of new strings, deduplicated."""
    best = {}
    for t in texts:
        for s, en, ru in memory.search(t, k=per_item):
            if en not in best or best[en][0] < s:
                best[en] = (s, ru)
    top = sorted(best.items(), key=lambda x: -x[1][0])[:limit]
    return [{'en': en, 'ru': ru, 'score': s} for en, (s, ru) in top]
