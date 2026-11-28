# skyrim-ru-translations

Русские переводы модов Skyrim SE/AE для
[Dynamic String Distributor](https://www.nexusmods.com/skyrimspecialedition/mods/104231)
и инструменты, которыми они сделаны.

Переводы работают без замены плагинов: DSD подменяет строки на лету,
поэтому мод можно обновлять, а перевод не ломает совместимость и порядок загрузки.

## Установка перевода

1. Поставьте мод и **Dynamic String Distributor**.
2. Скопируйте папки `mods/<мод>/SKSE` (и `Magelight`, если есть) в игру или в отдельный мод в MO2/Vortex с приоритетом выше оригинала.
3. Язык игры — русский (`sLanguage=RUSSIAN`).

Строки без перевода остаются английскими, игра от этого не ломается.

## Переводы

| Мод | Версия | Папка |
|---|---|---|
| [Become High King of Skyrim TNG](https://www.nexusmods.com/skyrimspecialedition/mods/142993) | 2.3 | `mods/become-high-king-tng` (DSD + интерфейс «Королевской книги» в `Magelight/`) |
| BHKS - TNG - Official Patch Collection | 1.0.6 | `mods/bhks-tng-patches` |
| [Guard Dialogue Overhaul Redux](https://www.nexusmods.com/skyrimspecialedition/mods/20791) | 1.8.1 | `mods/guard-dialogue-overhaul` (298 строк из ванильного перевода + 36 новых) |
| Legacy of the Dragonborn Patches (Official): Moonpath to Elsweyr | DBM_Moonpath_Patch | `mods/lotd-moonpath-patch` |
| Legacy of the Dragonborn: патчи, Curator's Companion, CC Patch Hub и пропуски в самом LotD | ~300 плагинов | `mods/lotd-patches` (только то, чего нет в уже установленных переводах; ставится как `RU_lotd-patches.json` рядом с ними) |
| Undeath, Classical Lichdom, Humanoid Dragon Priests, Konahrik's Accoutrements, маски жрецов | 8 плагинов | `mods/undeath-dragon-priests` (недостающие строки, ставится как `RU_undeath-dragon-priests.json`) |
| Atlas Map Markers SE и патчи | 8 плагинов | `mods/atlas-map-markers` (метки карты и компаса, ставится как `RU_atlas-map-markers.json`) |
| Feathers of Kyne - An Alternate Death Mod | 1.x | `mods/feathers-of-kyne` |
| Rogues 'n Raiders, Lawless, OBIS SE | 7 плагинов | `mods/bandits` (имена противников, перки, заклинания, книги; ставится как `RU_bandits.json`) |
| [Everdamned](https://www.nexusmods.com/skyrimspecialedition/mods/162489) | 1.6.3 | `mods/everdamned` (полный перевод вместо машинного + название ветки навыков в `SKSE/Plugins/CustomSkills`) |
| Spell Hotbar 2 | 2.x | `mods/spell-hotbar` (+ ветка навыков "Боевой маг" в `SKSE/Plugins/CustomSkills`) |
| Noct's Trithril Weapon Pack | - | `mods/trithril` (вместо машинного перевода) |
| Companions Dialogue Bundle | - | `mods/companions-dialogue-bundle` (ставится как `RU_companions-dialogue-bundle.json`) |
| Vampire Clans and Bloodlines | - | `mods/vampire-clans` (ставится как `RU_vampire-clans.json`) |
| Nyhus and the border of Cyrodiil | - | `mods/nyhus` (ставится как `RU_nyhus.json`) |
| The Gray Cowl of Nocturnal: дополнения (Дом вора, метки, патчи) | - | `mods/gray-cowl` (недостающие строки поверх готового перевода; `RU_gray-cowl.json`) |
| Vigilant Armors, RCBE Crossbow Integration | - | `mods/armor-weapon-misc` (`RU_armor-weapon-misc.json`) |
| Сгенерированные патчи сборки: ParallaxGen (PG_1.esp), DynDOLOD, Ore Vein Texture Fix | - | `mods/generated-patches` (названия, которые патч перезаписывает английскими; `RU_generated-patches.json`). PG_1.esp пересобирается патчером: после пересборки перепроверить. |
| [Olenveld](https://nexusmods.com/skyrimspecialedition/mods/133579) | - | `mods/olenveld` (`RU_olenveld.json`) |
| Haafstad and the Border of High Rock | - | `mods/haafstad` (Jehanna.esp; `RU_haafstad.json`) |

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
- **serve.py** — страница прогресса на http://localhost:8765: порции (ждёт / в
  работе / готово / с ошибками), процент, свежие переводы. Обновляется сама.

## Одной командой (Claude Code)

В репозитории есть команда `/translate <slug> [агентов]`
(`.claude/commands/translate.md`): поднимает страницу прогресса, готовит порции,
раздаёт их параллельным агентам с проверкой `validate.py`, собирает DSD и
коммитит перевод.

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
