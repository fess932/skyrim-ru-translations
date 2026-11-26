"""Collect Russian translations that are already installed in a mod setup, so
they are reused instead of translated again.

    python tools/harvest.py <mods-dir> [<modlist.txt>]

Scans every SKSE/Plugins/DynamicStringDistributor/<Plugin>/*.json under the
active mods (all mods if no modlist.txt is given) and writes, into vanilla/
(gitignored - this is other people's text, used locally only):

  known.json    {english original: russian}  - reused by prepare.py as exact matches
  covered.json  ["form_id|TYPE|index", ...]  - strings some installed DSD file
                already translates; prepare.py skips them

Files identical to one this repo builds (mods/*/SKSE/.../*.json) are ignored,
so re-running never mistakes our own output for someone else's coverage.
"""
import glob
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CYR = re.compile('[А-Яа-яЁё]')


def key(e):
    return f"{(e.get('form_id') or '').lower()}|{e.get('type')}|{e.get('index')}"


def digest(path):
    return hashlib.sha1(open(path, 'rb').read()).hexdigest()


def own_files():
    pattern = os.path.join(ROOT, 'mods', '*', 'SKSE', 'Plugins', 'DynamicStringDistributor', '*', '*.json')
    return {digest(f) for f in glob.glob(pattern)}


def main(mods_dir, modlist=None):
    if modlist:
        names = [l[1:].strip() for l in open(modlist, encoding='utf-8') if l.startswith('+')]
    else:
        names = sorted(os.listdir(mods_dir))
    mine = own_files()
    known, covered, files = {}, set(), 0
    for m in reversed(names):  # modlist.txt is highest priority first; let winners overwrite
        d = os.path.join(mods_dir, m, 'SKSE', 'Plugins', 'DynamicStringDistributor')
        if not os.path.isdir(d):
            continue
        for plugin in os.listdir(d):
            for f in glob.glob(os.path.join(d, plugin, '*.json')):
                if digest(f) in mine:
                    continue
                try:
                    data = json.load(open(f, encoding='utf-8-sig'))
                except (ValueError, UnicodeDecodeError):
                    continue
                if not isinstance(data, list):
                    continue
                files += 1
                for e in data:
                    s, o = e.get('string'), e.get('original')
                    if not s or not CYR.search(s):
                        continue
                    covered.add(key(e))
                    if o:
                        known[o] = s
    os.makedirs(os.path.join(ROOT, 'vanilla'), exist_ok=True)
    json.dump(known, open(os.path.join(ROOT, 'vanilla', 'known.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(sorted(covered), open(os.path.join(ROOT, 'vanilla', 'covered.json'), 'w', encoding='utf-8'))
    print(f'{files} files: {len(known)} known strings, {len(covered)} covered records')


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
