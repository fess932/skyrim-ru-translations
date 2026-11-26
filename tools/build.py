"""Assemble translated batches into Dynamic String Distributor files.

    python tools/build.py <mod-dir> [--allow-missing]

Reads  work/<slug>/en/<Plugin>.json, work/<slug>/out/*.json, work/<slug>/auto.json
Writes <mod-dir>/SKSE/Plugins/DynamicStringDistributor/<Plugin>/RU.json
       work/<slug>/build_report.txt

Every string is validated (tags, [pagebreak], format specifiers, Cyrillic).
Invalid or missing translations are left out of the output and listed in the
report, so the game falls back to English for them instead of breaking.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prepare import installed, uid, wanted  # noqa: E402
from validate import DROPCAP, check  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(mod_dir, allow_missing):
    mod = json.load(open(os.path.join(mod_dir, 'mod.json'), encoding='utf-8'))
    work = os.path.join(ROOT, 'work', mod['slug'])
    tr = {}
    for f in sorted(glob.glob(os.path.join(work, 'out', '*.json'))):
        tr.update(json.load(open(f, encoding='utf-8')))
    auto = json.load(open(os.path.join(work, 'auto.json'), encoding='utf-8'))
    _, covered = installed(mod)

    report, total_ok, total = [], 0, 0
    for f in sorted(glob.glob(os.path.join(work, 'en', '*.json'))):
        plugin = os.path.splitext(os.path.basename(f))[0]
        out = []
        for e in json.load(open(f, encoding='utf-8')):
            if not wanted(e, covered):
                continue
            total += 1
            i = uid(e['original'])
            ru = auto.get(i) or tr.get(i)
            if ru and i not in auto:
                ru = DROPCAP.sub('', ru)
            if not ru:
                report.append(f'MISSING {plugin} {e["form_id"]} {e["type"]}: {e["original"][:80]!r}')
                continue
            probs = check(e['original'], ru) if i not in auto else []
            if probs:
                report.append(f'INVALID {plugin} {e["form_id"]} {e["type"]} {probs}: {e["original"][:80]!r}')
                continue
            ru = ru.replace('ё', 'е').replace('Ё', 'Е')  # vanilla book fonts have no glyph for it
            out.append({**{k: v for k, v in e.items() if not k.startswith('_')}, 'string': ru})
            total_ok += 1
        if not out:
            continue
        dst = os.path.join(mod_dir, 'SKSE', 'Plugins', 'DynamicStringDistributor', plugin)
        os.makedirs(dst, exist_ok=True)
        json.dump(out, open(os.path.join(dst, 'RU.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'{plugin}: {len(out)} strings')
    open(os.path.join(work, 'build_report.txt'), 'w', encoding='utf-8').write('\n'.join(report))
    print(f'translated {total_ok}/{total}; problems: {len(report)} (see work/{mod["slug"]}/build_report.txt)')
    if report and not allow_missing:
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], '--allow-missing' in sys.argv)
