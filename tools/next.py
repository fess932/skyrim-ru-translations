"""Build the translator's task for one batch (instructions + terms + memory).

    python tools/next.py <mod-dir>            # status: which batches are left
    python tools/next.py <mod-dir> 007        # write work/<slug>/tasks/007.md

The task file is everything a translator (human, agent or any LLM) needs:
style guide, mod notes, required terms, similar lines already translated,
and the strings. The answer goes to work/<slug>/out/007.json as {"id": "ru"}.
Memory examples are retrieved at this moment, so later batches see the
translations of earlier ones.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def status(work):
    batches = sorted(os.path.basename(p)[:3] for p in glob.glob(os.path.join(work, 'batches', '*.json')))
    done = {os.path.basename(p)[:3] for p in glob.glob(os.path.join(work, 'out', '*.json'))}
    left = [b for b in batches if b not in done]
    print(f'done {len(done)}/{len(batches)}; next: {" ".join(left[:20])}')


def task(mod_dir, work, n):
    doc = json.load(open(os.path.join(work, 'batches', f'{n}.json'), encoding='utf-8'))
    memory = tm.Memory(tm.load_pairs(os.path.basename(work)))
    examples = tm.examples_for([i['en'] for i in doc['items']], memory)
    guide = open(os.path.join(ROOT, 'prompts', 'translate.md'), encoding='utf-8').read()
    notes_p = os.path.join(mod_dir, 'notes.md')
    notes = open(notes_p, encoding='utf-8').read() if os.path.exists(notes_p) else ''
    out_path = os.path.join(work, 'out', f'{n}.json')
    parts = [
        guide,
        '## Об этом моде\n\n' + notes if notes else '',
        '## Обязательные термины (EN → RU)\n\n```json\n'
        + json.dumps(doc['terms'], ensure_ascii=False, indent=1) + '\n```',
        '## Как уже переведены похожие строки (держи единый стиль)\n\n```json\n'
        + json.dumps(examples, ensure_ascii=False, indent=1) + '\n```' if examples else '',
        f'## Строки для перевода (порция {n}, {len(doc["items"])} шт.)\n\n```json\n'
        + json.dumps(doc['items'], ensure_ascii=False, indent=1) + '\n```',
        f'## Куда писать ответ\n\n`{out_path}` — JSON-объект `{{"id": "перевод", ...}}` для КАЖДОГО id.\n'
        f'Проверка: `python tools/validate.py {os.path.join(work, "batches", n + ".json")} {out_path}`',
    ]
    os.makedirs(os.path.join(work, 'tasks'), exist_ok=True)
    os.makedirs(os.path.join(work, 'out'), exist_ok=True)
    path = os.path.join(work, 'tasks', f'{n}.md')
    open(path, 'w', encoding='utf-8').write('\n\n'.join(p for p in parts if p) + '\n')
    print(f'{path}  ({len(doc["items"])} strings, {len(doc["terms"])} terms, {len(examples)} memory examples)')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    mod_dir = sys.argv[1]
    slug = json.load(open(os.path.join(mod_dir, 'mod.json'), encoding='utf-8'))['slug']
    work = os.path.join(ROOT, 'work', slug)
    if len(sys.argv) == 2:
        status(work)
    else:
        task(mod_dir, work, sys.argv[2].zfill(3))
