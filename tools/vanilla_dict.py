"""Build EN->RU dictionaries from YOUR copy of Skyrim SE (vanilla string tables
of the base game, DLC and the Creation Club content in cc*.bsa).

Bethesda's text is not redistributed in this repo; it is generated locally.

    python tools/vanilla_dict.py "<Skyrim>/Data"

Writes (gitignored):
    vanilla/exact.json  every vanilla EN string -> RU (unambiguous pairs only)
    vanilla/names.json  short EN strings (names, titles; <= 60 chars) -> RU
"""
import collections
import glob
import json
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsa  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'vanilla')
PLUGINS = ('skyrim', 'update', 'dawnguard', 'hearthfires', 'dragonborn')
ARCHIVES = ['Skyrim - Interface.bsa', 'cc*.bsa']


def dec(b):
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('cp1251', errors='replace')


def load_table(path):
    d = open(path, 'rb').read()
    n, _ = struct.unpack_from('<II', d)
    base = 8 + 8 * n
    out = {}
    lstr = not path.endswith('.strings')
    for i in range(n):
        sid, off = struct.unpack_from('<II', d, 8 + 8 * i)
        p = base + off
        if lstr:
            ln = struct.unpack_from('<I', d, p)[0]
            out[sid] = dec(d[p + 4:p + 4 + ln].rstrip(b'\0'))
        else:
            out[sid] = dec(d[p:d.index(b'\0', p)])
    return out


def best(dct):
    out = {}
    for en, counts in dct.items():
        (ru, n), *rest = counts.most_common()
        if not rest or n > rest[0][1]:
            out[en] = ru
    return out


def main(data_dir):
    tmp = tempfile.mkdtemp(prefix='vanilla_strings_')
    for pattern in ARCHIVES:
        for archive in sorted(glob.glob(os.path.join(data_dir, pattern))):
            bsa.extract(archive, lambda p: p.lower().startswith('strings')
                        and ('_english.' in p.lower() or '_russian.' in p.lower()), tmp)
    src = os.path.join(tmp, 'strings')
    cc = sorted({f.split('_english.')[0] for f in os.listdir(src) if f.startswith('cc') and '_english.' in f})
    pairs = collections.defaultdict(collections.Counter)
    names = collections.defaultdict(collections.Counter)
    for plugin in PLUGINS + tuple(cc):
        for ext in ('strings', 'dlstrings', 'ilstrings'):
            en_p = os.path.join(src, f'{plugin}_english.{ext}')
            ru_p = os.path.join(src, f'{plugin}_russian.{ext}')
            if not (os.path.exists(en_p) and os.path.exists(ru_p)):
                continue
            en, ru = load_table(en_p), load_table(ru_p)
            for sid, e in en.items():
                r = ru.get(sid)
                if not r or not e.strip() or r == e:
                    continue
                pairs[e][r] += 1
                if ext == 'strings' and len(e) <= 60:
                    names[e][r] += 1
    os.makedirs(OUT, exist_ok=True)
    exact, nm = best(pairs), best(names)
    json.dump(exact, open(os.path.join(OUT, 'exact.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(nm, open(os.path.join(OUT, 'names.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'exact: {len(exact)}  names: {len(nm)}  -> {OUT}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
