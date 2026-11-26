# skyrim-ru-translations

Русские переводы модов Skyrim SE/AE для
[Dynamic String Distributor](https://www.nexusmods.com/skyrimspecialedition/mods/104231)
и инструменты, которыми они сделаны.

Переводы работают без замены плагинов: DSD подменяет строки на лету,
поэтому мод можно обновлять, а перевод не ломает совместимость и порядок загрузки.

## Установка перевода

1. Поставьте мод и **Dynamic String Distributor**.
2. Скопируйте папку `mods/<мод>/SKSE` в игру (или в отдельный мод в MO2/Vortex).
3. Язык игры — русский (`sLanguage=RUSSIAN`).

Строки без перевода остаются английскими, игра от этого не ломается.

## Переводы

| Мод | Версия | Папка |
|---|---|---|
| [Become High King of Skyrim TNG](https://www.nexusmods.com/skyrimspecialedition/mods/142993) | 2.3 | `mods/become-high-king-tng` |

## Как устроен перевод

```
extract  →  prepare  →  next (задание)  →  перевод  →  validate  →  build
плагин      порции      термины+память     нейронка    проверка    DSD JSON
```

- **extract.py** — достаёт строки из `.esp/.esm` в формате DSD
  (`original / form_id / type / index / editor_id`).
- **vanilla_dict.py** — строит словарь из *вашей* копии игры: английские и
  русские строковые таблицы сопоставляются по ID, получается ~24 тыс.
  официальных названий («Whiterun» → «Вайтран»). Тексты Bethesda в репозиторий
  не попадают.
- **prepare.py** — убирает дубликаты, режет на порции, сразу переводит то, что
  совпадает с ванилью, и прикладывает к каждой порции термины, которые в ней
  встречаются.
- **tm.py** — память переводов. Её база — уже готовые переводы в этом
  репозитории (`mods/*/…/RU.json`) и переведённые порции текущего мода.
  К каждому заданию прикладываются самые похожие уже переведённые строки
  (TF-IDF по символьным триграммам), поэтому обороты и стиль одинаковы по всему
  моду и между модами.
- **next.py** — собирает задание на порцию: инструкция
  (`prompts/translate.md`), заметки о моде, термины, примеры из памяти, строки.
  Переводить может кто угодно: человек, агент или любая LLM.
- **validate.py** — проверяет, что перевод не сломал теги `<Alias=…>`, `<mag>`,
  HTML книг, `[pagebreak]`, `%s` и что текст действительно русский.
- **build.py** — собирает готовый `RU.json` для DSD; невалидные строки
  отбрасываются (остаётся английский), всё пишется в отчёт.

## Перевести новый мод

```bash
python tools/vanilla_dict.py "C:/Games/Skyrim Special Edition/Data"   # один раз
mkdir mods/<slug>          # mod.json: slug, name, nexus_id, version, plugins
                           # glossary.json и notes.md — по желанию
python tools/extract.py <Plugin.esp> work/<slug>/en/<Plugin.esp>.json
python tools/prepare.py mods/<slug>
python tools/next.py mods/<slug>          # что осталось
python tools/next.py mods/<slug> 001      # задание → work/<slug>/tasks/001.md
# перевод → work/<slug>/out/001.json   {"id": "перевод"}
python tools/validate.py work/<slug>/batches/001.json work/<slug>/out/001.json
python tools/build.py mods/<slug>
```

Нужен Python 3.10+ и `lz4` (`pip install lz4`) для чтения BSA.

## Лицензия

Инструменты — MIT. Тексты переводов принадлежат авторам оригинальных модов;
переводы публикуются для использования вместе с оригиналом.
