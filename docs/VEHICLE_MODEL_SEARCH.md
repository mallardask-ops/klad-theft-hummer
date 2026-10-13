# Пошук моделей транспорту

Каталог кандидатів під силует GTA III / ранньої PS2. Сторінки дивився 13 жовтня 2026, чотирма проходами. Четвертий прохід розпакував CC0-zip Kenney (човни, завод, дороги) і 3TD Industrial, доміряв `boat-speed-a` і дописав два варіанти Panda, які не є підтвердженим хетчем 141. Жоден архів GTA чи Project Zomboid у цьому проході не завантажено: Liberty City і GTAinside віддають файл через кнопку з токеном або після входу. Тому для машин із `.dff` статус лишається **сторінку переглянуто**. У Blender і в Godot прогнано лише CC0-хетчбек Kenney. `boat-speed-a.glb` імпортовано в Blender, у Godot його не відкривали. Жоден із цих файлів не є Fiat Uno і в гру не підключений.

Поточні машини гри лишаються оригінальними. `docs/models.md` прямо каже, що витягнуті моделі GTA не використовуються. `KVehicle` у `scripts/vehicle.gd` вантажить лише `res://assets/models/sedan.glb` і `res://assets/models/minibus.glb`. Колізія седана зараз `1.65 × 1.15 × 3.95` м, маршрутки по Z `4.8` м. Колеса `Wheel_FL`, `Wheel_FR`, `Wheel_RL`, `Wheel_RR` крутяться навколо локальної X. Фарба седана шукає матеріал `Sedan_Paint`.

Списки Толіка й побічні заняття в `docs/story/missions/side_activities.md` просять окремі силуети: «шістка», «Нива», «Таврія», Lanos, «Богдан», УАЗ-«бобік», УАЗ-«буханка» швидкої, пожежний «ЗІЛ», «ГАЗ-53» з матрацами, скутери, моторний човен, «Хаммер "Клад"».

## Як читати статус

Ланцюжок перевірки: **сторінку переглянуто → архів перевірено → імпорт у Blender перевірено → GLB перевірено**.

Кількість трикутників, склад архіву й ліцензія записані лише там, де їх видно на сторінці або виміряно локально. Решта позначена «не перевірено». Розмір `.dff` / `.txd` у таблицях це текст сторінки, не наш замір.

## Інструменти на цій машині

| Інструмент | Що перевірено |
| --- | --- |
| Linux, Blender **5.2.2 LTS** (збірка 2026-09-22) | Імпорт glTF, експорт GLB, рендер Workbench. |
| Godot **4.7.2 stable** | Ізольований headless-імпорт пробного GLB. У гру не імпортовано: у каталозі проби лежить `.gdignore`. |
| [DragonFF](https://github.com/Parik27/DragonFF), знімок `master` від 2026-10-11 | Маніфест розширення: версія `1.0.0`, `blender_version_min = 4.2.0`, ліцензія GPL-3.0-or-later. `bl_info` у коді досі `(0, 0, 2)`. На Blender 5.2.2 оператор `import_scene.dff` реєструється. Файл `.dff` не імпортовано. |
| Штатний імпортер FBX | У чистому Blender 5.2.2 увімкнений `io_scene_fbx`. ASCII FBX підтримується з [Blender 4.5](https://developer.blender.org/docs/release_notes/4.5/pipeline_assets_io/). Зразок ASCII FBX із Project Zomboid не імпортовано, тож старий конвертер не підставлявся. |
| [Sollumz](https://docs.sollumz.org/documentation/fragments.yft/vehicle-setup/import-settings) | Не встановлено. Маршрут нижче лише задокументований. |
| [ZomboidImportExport](https://github.com/rundaaa/ZomboidImportExport) | Не встановлено. README: аддон для **Blender 2.79**; порт на 2.8–2.9 автор вважає незакінченим, UV і текстури там не перевіряв. |

## Маршрути

Орієнтація після експорту однакова для всіх джерел. У Blender модель дивиться в **+Y**, верх **+Z**, низ коліс на **Z = 0**. Експортер glTF (`export_yup`) перетворює це на Godot: верх **+Y**, ніс у **−Z**, колеса на **Y = 0**. Так зібрані `sedan.glb` і `minibus.glb`.

| Джерело | Маршрут | Що реально прогнано |
| --- | --- | --- |
| Project Zomboid, новий меш | У моді шукати геометрію в `media/models_X`: `.fbx` або `.glb` без розширення в скрипті, текстура `.png` в `media/textures`. Опис є в [model.rst](https://github.com/PZ-Wiki-Modding/PZ-API-Docs/blob/main/docs/source/scripts/model.rst). Файли транспорту `.txt` це скрипти, не меш. Далі Blender → матеріали glTF → GLB. | Документацію відкрито. Жодного воркшоп-архіву PZ не розпаковано. |
| Старий формат PZ | Спершу визначити розширення. Якщо це не FBX/GLB, дивитися ZomboidImportExport під Blender 2.79. На 5.2 цей аддон не ставити. | Не прогнано. |
| GTA III / VC / SA, `.dff` + `.txd` | DragonFF: імпорт меша й TXD, викинути LOD і биті дублікати, зібрати скло / фари / фарбу окремо, експорт GLB. | Аддон піднявся. Імпорт DFF не прогнано. |
| GTA V, `.yft` + `.ytd` | CodeWalker → XML і текстури → Sollumz → Blender → GLB. Сторінка Sollumz описує імпорт фрагмента авто. Версію Sollumz на машині немає з чого назвати. | Не прогнано. |
| `.blend`, `.obj`, звичайний `.fbx`, готовий `.glb` | Імпорт у Blender 5.2.2, перевірка ієрархії, експорт GLB. | Прогнано на Kenney `hatchback-sports.glb`. |

Адаптація під `KVehicle`, коли з’явиться дозволений меш:

1. Виміряти габарит у метрах і застосувати масштаб. GTA-моди часто пишуть «scale 110%»; це не заміна заміру.
2. Ніс у −Z, верх +Y, протектор на Y = 0.
3. Окремі порожні `Wheel_FL/FR/RL/RR` у центрах коліс, меш дитиною з нульовим локальним зсувом. Вісь колеса має бути локальна X.
4. Кузов `Vehicle_Body`. Скло, фари, задні ліхтарі й фарба окремими матеріалами. Для перефарбування як у `tint_paint()` матеріал фарби треба назвати так, щоб гра його знайшла. Зараз код шукає лише `Sedan_Paint`.
5. Прибрати LOD, пошкоджені копії й невидимі оболонки. Силует, вікна й колеса лишити.
6. Матеріали RenderWare / шейдери PZ (`vehicle`, `vehiclewheel`) перевести на звичайний glTF: фарба, прозоре скло, UV, нормалі.
7. GLB із запакованими текстурами. Godot 4 бере [glTF 2.0](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html).
8. Окремий прогін імпорту: імена, ніс, низ коліс, текстура. Колізію в `KVehicle` підганяти під габарит, не під поточні `1.65 × 3.95`.

## Fiat Uno: PZ проти GTA

Окремого **Fiat Uno** у Workshop Project Zomboid цим пошуком не знайдено.

Картки, які пошук повернув замість Uno:

- [Fiat Spazio 147 1990, Diegus](https://steamcommunity.com/sharedfiles/filedetails/?id=2983702434). Це латиноамериканський Fiat 147 / Spazio, не Uno Mk1 і не Mille.
- [Fiat Fiorino 1992, Diegus](https://steamcommunity.com/sharedfiles/filedetails/?id=2989871420). Фургон на базі Uno, не хетчбек. На картці Fiorino написано: для своїх ігор і серверів можна, у модпаки й передрук не можна, файли мода не розповсюджувати без дозволу.
- [Fiat 600 1970, Diegus](https://steamcommunity.com/sharedfiles/filedetails/?id=3036531689). Інша машина.

[Filibuster Rhymes’ Used Cars, Animation Beta](https://steamcommunity.com/sharedfiles/filedetails/?id=3315561157) (74.278 МБ, Build 42 unstable, Workshop ID саме той, що в завданні) описує близько 60 базових моделей і понад 130 варіантів. На відкритій сторінці немає Fiat, ВАЗ, ЗАЗ, Daewoo, УАЗ чи «Богдана». Автор пише, що працює в The Indie Stone і моделі майже не чіпає. Це американський парк, не коростишівський.

Три сторінки саме Uno:

| | Uno 1995, SA style | Uno Mille Fire 2012/2013, SA style | Uno, висока якість |
| --- | --- | --- | --- |
| Сторінка | [Liberty City 154020](https://libertycity.net/files/gta-san-andreas/154020-fiat-uno-1995-sa-style.html) | [Liberty City 119828](https://libertycity.net/files/gta-san-andreas/119828-fiat-uno-mille-fire-20122013-sa-style.html) | [GTAall 48756](https://www.gtaall.net/gta-san-andreas/cars/48756-fiat-uno.html) |
| Хто підписаний | gtapintarg, RetrKill0, Vermilion093 3D. Хто ліпив, а хто конвертував, сторінка не ділить | RetrKill0, JOOj, BMT | BMEditingTR |
| Гра | GTA San Andreas | GTA San Andreas | GTA San Andreas, заміна Uranus |
| Архів за сторінкою | 139.09 КБ, `peren.dff`, `peren.txd` | 648.90 КБ, `buccanee.dff`, `buccanee.txd` | `uranus.dff` 8.53 МБ, `uranus.txd` 4.25 МБ |
| Стиль | LQ, «не псує атмосферу», пошкодження, VehFuncs | SA style, екстри, тюнінг, свої колізія й тінь. Це вже Mille Fire 2012/2013, не Mk1 | «Висока якість», салон і кузов. Для PS2 заважкий за розміром файлу |
| Умови | Анкети дозволів на сторінці немає. Потрібне уточнення в авторів | Анкети на відкритій сторінці немає. Потрібне уточнення | На сторінці ліцензії немає. Потрібне уточнення |
| Трикутники | не перевірено | не перевірено | не перевірено |

Для силуету початку 90-х ближче **Uno 1995 SA style**: маленький LQ-архів і заміна SA-машини. Mille Fire 2012 це пізніший бразильський фесліфт. Файл на 8.53 МБ з GTAall доведеться сильно різати. У PZ готового Uno немає; Spazio 147 можна тримати лише як запасний силует «маленького Фіата», і теж після дозволу автора.

## Маршрут найкращого Uno

Ціль: [Fiat Uno 1995 (SA style)](https://libertycity.net/files/gta-san-andreas/154020-fiat-uno-1995-sa-style.html). Конвертацію **не** прогнано.

1. Написати gtapintarg, RetrKill0 і Vermilion093 3D. Сторінка не каже, чи можна нести модель в іншу гру.
2. Скачати `1613329875_fiat_uno_1995.7z`. За сторінкою всередині `peren.dff` і `peren.txd`.
3. Blender 5.2.2, DragonFF зі знімка 2026-10-11: Import → GTA DFF, поряд імпорт TXD.
4. Подивитися, чи в DFF сидять LOD, пошкодження й екстри. Сторінка пише «damageable» і VehFuncs. Склад сцени не перевірено.
5. Залишити один кузов. Колеса зняти з кузова, поставити порожні `Wheel_*`, вісь по локальній X.
6. Матеріали SA (бруд, `vehicle` shader, скло) зібрати у фарбу, скло, фари, стопи. Імена під майбутній перефарб.
7. Виміряти довжину. Якщо модель не в метрах, привести до реального Uno й застосувати масштаб. Цифру «скільки метрів у файлі» зараз вигадувати не можна.
8. Експорт GLB, Yup. Перевірити в ізольованому Godot 4.7 так само, як Kenney нижче.
9. У `KVehicle` не підставляти, поки немає дозволу й заміру. Поточна коробка `3.95` м по Z для цієї моделі ще невідома.

## П’ятірка, яку простіше адаптувати

Це технічна черга, не дозвіл класти файл у гру.

1. **Fiat Uno 1995 SA style.** Найменший з переглянутих Uno, уже в стилі SA, два файли DFF+TXD, DragonFF на цій машині піднімається. Ліцензія не написана.
2. **Peugeot 205 LQ**, [Liberty City 150456](https://libertycity.net/files/gta-san-andreas/150456-peugeot-205.html). Автори Th14g0MR, Worth. Архів 88.73 КБ, `blistac.dff` + `blistac.txd`. Той самий клас «LQ, не псує атмосферу». Умови на сторінці не вказані.
3. **ВАЗ-2106 SergeDV**, [Liberty City 118256](https://libertycity.net/files/gta-san-andreas/118256-vaz-2106-lada-1600-low-poly-sa-style.html). Сторінка сама пише «низькополігональна» і «матеріали в стилі GTA SA». Архів 901.08 КБ, `cadrona.dff` + `cadrona.txd`, заміна Cadrona, масштаб на сторінці «110%». Умови не вказані.
4. **ЗАЗ-1102 emexD**, [GTAinside](https://www.gtainside.com/sanandreas/cars/zaz/181772-zaz-1102-tavria-1987-1998-sa-style). Автори emexD, JDM Co. Сторінка: low-poly, салон, двигун, заміна Blista Compact, вініли J3rX і LyoSHeX. Розмір архіву й трикутники не перевірено. Ліцензії на сторінці немає. Варіант DScorp стилістично ще простіший, але автор **заборонив** конверсію в інші ігри. Його в цю п’ятірку не ставити.
5. **Mercedes-Benz W140 low poly, Sallie**, [LC 112673](https://libertycity.net/files/gta-san-andreas/112673-mercedes-benz-w140-low-poly.html). Архів 202 КБ, `elegant.dff` + `.txd`, уже підписаний як lightweight. Умови на сторінці не написані. E34 поруч такий самий маленький, але картка ставить у автори ще й Rockstar Games, тож його в п’ятірку не беру.

Окремо, і це єдина річ, яку вже прогнано до GLB: **Kenney Car Kit 3.1**, CC0. Силует загальний, не Uno. Див. кінець файлу.

## Черга 1. Маленькі старі іномарки й місцевий транспорт

| Машина | Посилання | Автор моделі | Гра | Формат | Текстури | Трикутники | Умови | Шлях | Що адаптувати | Статус |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Fiat Uno 1995, SA style | [LC 154020](https://libertycity.net/files/gta-san-andreas/154020-fiat-uno-1995-sa-style.html) | gtapintarg, RetrKill0, Vermilion093 3D; ролі не розділені | GTA SA | `.dff` + `.txd` (`peren`) | LQ, як пише сторінка; роздільність не перевірено | не перевірено | потрібне уточнення в авторів | DragonFF → Blender 5.2.2 → GLB | колеса, скло, масштаб, викинути damage-дублікати якщо вони в DFF | сторінку переглянуто |
| Fiat Uno Mille Fire 2012/2013 | [LC 119828](https://libertycity.net/files/gta-san-andreas/119828-fiat-uno-mille-fire-20122013-sa-style.html) | RetrKill0, JOOj, BMT | GTA SA | `buccanee.dff` + `.txd` | SA, не перевірено | не перевірено | потрібне уточнення | той самий DragonFF | пізній фесліфт; для «Таврії-сусіда» 90-х слабший за Uno 1995 | сторінку переглянуто |
| Fiat Uno HQ | [GTAall 48756](https://www.gtaall.net/gta-san-andreas/cars/48756-fiat-uno.html) | BMEditingTR | GTA SA, заміна Uranus | `uranus.dff` 8.53 МБ + `uranus.txd` 4.25 МБ | «висока якість» | не перевірено | потрібне уточнення | DragonFF, потім сильно спростити | салон і зайва щільність; силует лишити | сторінку переглянуто |
| Peugeot 205 LQ | [LC 150456](https://libertycity.net/files/gta-san-andreas/150456-peugeot-205.html) | Th14g0MR, Worth | GTA SA | `blistac.dff` + `.txd`, архів 88.73 КБ | LQ | не перевірено | потрібне уточнення | DragonFF → GLB | колеса, скло, фарба | сторінку переглянуто |
| Volkswagen Golf Mk2 | [KI5, Workshop 2516123638](https://steamcommunity.com/sharedfiles/filedetails/?id=2516123638) | мод KI5; окремий автор меша не відділений | PZ, Build 41.73+, файл 5.338 МБ. Автор відсилає на новіший мод [3812024929](https://steamcommunity.com/sharedfiles/filedetails/?id=3812024929), його сторінку не відкрито | очікується FBX або GLB за `model.rst`; файл не відкрито | варіанти кольорів, іржа, бите скло; файли не відкрито | не перевірено | KI5: без дозволу не змінювати й не перепаковувати. «On Lockdown» | якщо дозвіл: FBX/GLB → Blender → спростити до PS2 | 2 і 4 двері, інтер’єр, стани пошкоджень. Для вулиці лишити один кузов | сторінку переглянуто |
| ВАЗ-2106, SA style | [LC 118256](https://libertycity.net/files/gta-san-andreas/118256-vaz-2106-lada-1600-low-poly-sa-style.html) | SergeDV | GTA SA, заміна Cadrona | `cadrona.dff` + `.txd`, 901 КБ | «матеріали в стилі GTA SA» | не перевірено; сторінка каже low-poly | потрібне уточнення | DragonFF → GLB | номери SA або «фіксовані російські», масштаб 110% із сторінки перевірити заміром, тюнінг Cadrona прибрати | сторінку переглянуто |
| ВАЗ-2106 у пакеті LemeS | [P.A.R.C, 2734164805](https://steamcommunity.com/sharedfiles/filedetails/?id=2734164805) | LemeS | PZ 41.78 і 42.20, пакет 420.288 МБ | не перевірено | не перевірено | не перевірено | на сторінці пакета умов переносу немає. Потрібне уточнення в LemeS | FBX/GLB, якщо так лежить у `models_X` | другий кандидат «шістки»; меш у купі з десятками машин | сторінку пакета переглянуто, файл не відкрито |
| ВАЗ-2121 «Нива», KI5 | [Workshop 2422681177](https://steamcommunity.com/workshop/filedetails/?id=2422681177) | мод KI5 | PZ B41.73+, 3.000 МБ, ID `90niva` | не перевірено. Є посилання «On Sketchfab», саму сторінку Sketchfab не відкрито | 8 заводських кольорів, 2 камуфляжі, іржа й биття; не recolorable | не перевірено | «Ask for permission», перепакування заборонене | після дозволу: викинути damage-стани, лишити один кузов | ближче до ізометрії PZ, ніж до PS2; спрощувати | сторінку переглянуто |
| ВАЗ-2121, Bars | [GTAall 62256](https://www.gtaall.com/gta-san-andreas/cars/62256-vaz-2121-niva.html) | Bars | GTA SA, заміна Clover | `clover.dff` 14.68 МБ + `clover.txd` 7.96 МБ | «хороша якість» за сторінкою | не перевірено | потрібне уточнення | DragonFF і сильне спрощення | заважкий файл для цільового силуету | сторінку переглянуто |
| ЗАЗ-1102, DScorp | [LC 202261](https://libertycity.net/files/gta-san-andreas/202261-zaz-1102-tavria-sa-style.html) | DScorp | GTA SA, заміна Manana | `manana.dff` + `.txd`, архів 622.83 КБ | свої текстури кузова плюс стандартні текстури гри, як пише автор | не перевірено; автор пише про малу кількість полігонів, числа немає | **конверсія в інші ігри: «Under no circumstances»**. Редагування й свої файли на базі цього тільки після дозволу. Передрук заборонений | не починати без письмового дозволу | технічно найближчий SA-силует «Таврії», юридично закритий | сторінку переглянуто |
| ЗАЗ-1102, 1987–1998, emexD | [GTAinside 181772](https://www.gtainside.com/sanandreas/cars/zaz/181772-zaz-1102-tavria-1987-1998-sa-style) | emexD, JDM Co.; вініли J3rX, LyoSHeX | GTA SA, заміна Blista Compact | не перевірено | low-poly за описом, AO, салон, двигун | не перевірено | потрібне уточнення. Завантаження на сайті просить вхід | DragonFF → GLB | другий кандидат «Таврії», якщо DScorp не дає дозвіл | сторінку переглянуто |
| ВАЗ-2101, 2107, 2109, ЗАЗ-968М, Москвич-2141 | той самий [P.A.R.C](https://steamcommunity.com/sharedfiles/filedetails/?id=2734164805) | LemeS | PZ | не перевірено | не перевірено | не перевірено | потрібне уточнення в LemeS | як інші моделі пакета | у списку пакета є 2101 / 2104 / 2105 / 2106 / 2107 / 2108 / 2109 / «Ока» / «Нива» і ЗАЗ 966 / 968 / 968М, Москвич 2140 / 2141 | сторінку пакета переглянуто |
| Fiat Panda Van | [LC 134030](https://libertycity.net/files/gta-san-andreas/134030-fiat-panda-van.html) | SerbianMods, JVT | GTA SA | `previon.dff` + `.txd`, архів 1.42 МБ | MQ екстер’єр і салон, оптика SA | не перевірено | потрібне уточнення | DragonFF | сторінка не пише, що це Panda 141. Це фургон, не хетч 141. Масштаб «виправлений» за автором, число не дано | сторінку переглянуто |
| Volkswagen Golf Mk3 | [LC 79031](https://libertycity.net/files/gta-san-andreas/79031-volkswagen-golf-mk3.html) | Dave, SerbianMods | GTA SA, заміна Jester | `jester.dff` + `.txd`, архів 12.03 МБ | «різні кольори», роздільність не вказана | не перевірено | потрібне уточнення | DragonFF і спрощення | файл великий для PS2-силуету. Легший кандидат нижче, «Slawomir» | сторінку переглянуто |
| Opel Astra F Caravan | [GTAinside 52994](https://www.gtainside.com/sanandreas/cars/opel/52994-opel-astra-f-caravan) | Serbian mods, завантажив Marko HR | GTA SA | не перевірено | не перевірено | не перевірено | потрібне уточнення. Завантаження просить вхід | DragonFF, якщо в архіві DFF | універсал, не хетч Astra F. Опису файлів на сторінці немає | сторінку переглянуто |
| Opel Kadett E, 1990, 5 дверей | [LC 114443](https://libertycity.net/files/gta-san-andreas/114443-1990-opel-kadett-e-5-door-europa.html) | Serbian Mods, MERCX | GTA SA | `premier.dff` + `premeir.txd` (так написано на сторінці), архів 1.94 МБ | підкапотка затекстурена; роздільність не вказана | не перевірено. Сторінка: оптимізована під слабкі ПК, є пошкодження | анкети на сторінці немає. Потрібне уточнення | DragonFF | п’ятидверний Kadett E. Число полігонів не дано | сторінку переглянуто |
| Volkswagen Golf III «Slawomir» | [LC 153349](https://libertycity.net/files/gta-san-andreas/153349-volkswagen-golf-iii-slawomir.html) | SerbianMods, GTAPoland | GTA SA | `glenshit.dff` + `.txd`, архів 2.25 МБ | «хороші текстури» | не перевірено | анкети немає. Потрібне уточнення | DragonFF | легший Golf III за Dave (12 МБ). Слот заміни сторінка не називає, лише імена файлів | сторінку переглянуто |
| Fiat Tipo, 1993 | [LC 191402](https://libertycity.net/files/gta-san-andreas/191402-1993-fiat-tipo.html) | Private, Ozan Emre Öztürk | GTA SA | архів 6.04 МБ; імена DFF сторінка не показала | «хороші», є салон | не перевірено | потрібне уточнення | DragonFF, салон прибрати після імпорту | рік 1993 це Tipo I. Щільність невідома | сторінку переглянуто |
| Fiat Punto MK1 Tuning | [GTAinside 54780](https://www.gtainside.com/sanandreas/cars/54780-fiat-punto-mk1-tuning) | roby14 | GTA SA | не перевірено. Опис сторінки: «Un fiat punto» | не перевірено | не перевірено | на сторінці ліцензії немає. Завантаження просить вхід | DragonFF, якщо в архіві DFF | це тюнінг, не стоковий Punto I. Формату й розміру картка не дає | сторінку переглянуто |
| Renault 19, 1991 | [LC 210450](https://libertycity.net/files/gta-san-andreas/210450-1991-renault-19.html) | TheMadeMan | GTA SA | `renault19.dff` + `.txd`, ще `wheel_lr4.dff`, архів 253.24 КБ | не перевірено | не перевірено | **конверсія в інші ігри: «Under no circumstances»**. Свої файли на базі цього тільки після дозволу. Передрук на інші сайти: ні. Платні моди: «Under no circumstances» | не конвертувати | файл маленький, юридично закритий так само, як Таврія DScorp | сторінку переглянуто |
| Fiat Panda, «Supernova» | [GTAinside 112277](https://www.gtainside.com/sanandreas/cars/fiat/112277-fiat-panda-supernova) | Automan | GTA SA, заміна Club | не перевірено. Сторінка не дає розмір архіву | номер `targa`, другий колір салону | не перевірено. Є «Light LOD» і пошкодження всіх частин, числа немає | сторінка: «Open source, files unlocked: only credits required for use it». Завантаження просить вхід | DragonFF після кредиту Automan | покоління на картці не назване. Це не підтверджена Panda 141. Коментар на сторінці: кузов «blocky» | сторінку переглянуто |
| Grotti Flora, April Fools, «Sa Style Fiat Panda» | [LC 236783](https://libertycity.net/files/gta-san-andreas/236783-1980-grotti-flora-sa-style-fiat-panda.html) | gantonswapmeet | GTA SA | архів 283.15 КБ; імена DFF сторінка не показала | не перевірено | не перевірено | анкети немає. Потрібне уточнення | DragonFF | сторінка: жартівливий випуск, «inspired by the classic Fiat Panda», стиль SA. Напис «141» на картці немає. На [GTAinside 216554](https://www.gtainside.com/sanandreas/cars/other/216554-1980-grotti-flora-sa-style-fiat-panda-april-fools-day-special) опис «Based on the Fiat Panda» і потрібен VehFuncs | сторінку LC переглянуто; GTAinside — знімок пошуку |

Стоковий хетч Panda 141 окремою карткою досі не відкритий. Punto I без тюнінгу теж ні: відкрита лише картка roby14. Старіший «Fiat Panda Tuned» (2007) на GTAinside у коментарях сперечається, чий це меш і чи був дозвіл з NFS; сторінку в таблицю не ставив.

## Черга 2. Місто, служба, маршрутки

| Машина | Посилання | Автор моделі | Гра | Формат | Текстури | Трикутники | Умови | Шлях | Що адаптувати | Статус |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Daewoo Lanos | [LC 202304](https://libertycity.net/files/gta-san-andreas/202304-daewoo-lanos.html) | AKBAR_KING | GTA SA | архів 4.59 МБ; імена файлів сторінка не показала | «хороші» | не перевірено | потрібне уточнення | DragonFF, оцінити щільність після імпорту | легший з двох відкритих Lanos | сторінку переглянуто |
| Daewoo Lanos Hatchback 2001, US-spec | [LC 116730](https://libertycity.net/files/gta-san-andreas/116730-daewoo-lanos-hatchback-1.6-16v-2001-us-spec.html) | меш darewnoo, Lazlow555; у GTA V конвертував darewnoo; у GTA SA адаптував Avant | GTA SA, заміна Blista Compact | `blistac.dff` 4.56 МБ + `.txd` 3.95 МБ, архів 6.05 МБ | заводські кольори, салон, двигун | не перевірено | потрібне уточнення. У подяці є Turn 10 / Forza й BeamNG на спорідненій седан-сторінці; на цій картці хетча чужі рушії не перелічені | DragonFF, викинути салон, двигун, екстри, damage-деталі | масштаб на сторінці «110%». Для вуличної «Ланос»-таксі заважкий, доки не зрізаний | сторінку переглянуто |
| Daewoo Matiz | [GTAall 81786](https://www.gtaall.com/gta-san-andreas/cars/81786-daewoo-matiz.html) | saddam | GTA SA, заміна Admiral | `admiral.dff` 1 МБ + `.txd` 0.27 МБ | не перевірено | не перевірено | потрібне уточнення | DragonFF | руки на кермі й салон, якщо вони в меші, прибрати з ігрового кузова | сторінку переглянуто |
| Mercedes-Benz W124, SA style, лише DFF | [LC 229786](https://libertycity.net/files/gta-san-andreas-ios-android/229786-dff-only-mercedes-benz-w124-sa-style.html) | база Athalone; цей файл Hamza Selçuk. Оригінал: [LC 156288](https://libertycity.net/files/gta-san-andreas/156288-mercedes-benz-w124.html), ту сторінку не відкрито | GTA SA mobile | архів 209.60 КБ; автор пише «only 470 kb» і «DFF only» | стандартні, TXD у комплекті немає | не перевірено | **конверсія в інші ігри заборонена**. Передрук заборонений. Редагування тільки після дозволу | не конвертувати | стилістично близько до «Мерс-124», у тому числі до бонуса «Мерс "Швидка"». Брати тільки після нового дозволу | сторінку переглянуто |
| УАЗ-452, Sherbug Roger | [Workshop 3231318931](https://steamcommunity.com/sharedfiles/filedetails/?id=3231318931) | Sherbug Roger | PZ, файл 327.760 КБ | не перевірено | не перевірено | не перевірено | «don't change, modify, reupload without my acception» | після дозволу: FBX/GLB → Blender | автор пише масштаб 1:1, AWD, 1 водій і 1 пасажир. Швидку й мигалку доведеться збирати самим. Формат меша не відкрито | сторінку переглянуто |
| УАЗ «Буханка» | [GTAall 223549](https://www.gtaall.com/gta-san-andreas/cars/223549-uaz-bukhanka.html) | Diamond Studio\|MTA | GTA SA, заміна Moonbeam | `moonbeam.dff` 4.51 МБ + `.txd` 4.5 МБ | «хороша якість», салон | не перевірено | потрібне уточнення | DragonFF і спрощення | другий кандидат буханки; салон для зовнішнього вигляду зайвий | сторінку переглянуто |
| УАЗ-452 / 469 і ГАЗ-24 / 3110 | [P.A.R.C](https://steamcommunity.com/sharedfiles/filedetails/?id=2734164805) | LemeS | PZ | не перевірено | не перевірено | не перевірено | потрібне уточнення | як пакет | на сторінці є УАЗ 452 / 469 / 3302 і ГАЗ 21 / 24 / 2402 / 2410 / 3102. Окремих «міліція / таксі / швидка» в списку Steam немає. Дзеркало Skymods згадує аддон радянських поліцейських перефарбувань; на відкритій сторінці Steam у абзаці аддонів лишився лише Project Chernorussia. Поки не відкрито файли, варіанти служби не підтверджені | сторінку пакета переглянуто |
| Богдан A09202 | [LC 105088](https://libertycity.ru/files/gta-san-andreas/105088-bogdan-a09202.html) | Himmel; завантажив Vadim Panenko | GTA SA, заміна DFT-30 | `dft30.dff` + `.txd`, архів 4.31 МБ | салон, 5 екстр | не перевірено | на цій сторінці анкети немає. Потрібне уточнення | DragonFF → один кузов без екстр салону | довший «Богдан» | сторінку переглянуто |
| Богдан A091 | [LC 105089](https://uk.libertycity.net/files/gta-san-andreas/105089-bogdan-a091.html) | Himmel, Irakly Gedevanishvili | GTA SA, заміна DFT-30 | `dft30.dff` + `.txd`, архів 4.43 МБ | салон, 6 екстр | не перевірено | анкети на сторінці немає. Потрібне уточнення | той самий DragonFF | коротший міський «Богдан», ближче до маршрутки в дворі | сторінку переглянуто |
| Opel Omega A Kombi | [LC 119216](https://libertycity.net/files/gta-san-andreas/119216-opel-omega-a-kombi.html) | SerbianMods, MERCX, Darewnoo. Хто ліпив, а хто переносив, не розділено | GTA SA | `stratum.dff` + `.txd`, архів 3.02 МБ | двигун, номери Сербії, vehiclelights | не перевірено | потрібне уточнення | DragonFF | універсал, не седан Omega A. Сторінка пише «оптимізована під слабкі ПК», числа полігонів немає | сторінку переглянуто |
| ГАЗ-3302 «Газель», 1994, старий передок | [LC 2591](https://libertycity.net/files/gta-san-andreas/2591-gaz-3302-gazelle-1994.html) | JOHN | GTA SA | `blistac.dff` + `.txd`, архів 1.28 МБ | не перевірено | не перевірено | потрібне уточнення | DragonFF | багато «великих» екстр. Для міста лишити один кузов. Заміна Blista Compact дивна для фургона: колізію гри не успадковувати | сторінку переглянуто |
| Mercedes-Benz T1, короткий фургон | [LC 129999](https://libertycity.net/files/gta-san-andreas/129999-mercedes-benz-t1-van-short.html) | SerbianMods, FlorianHeinsberg, Kai Hahn | GTA SA, заміна Burrito | `burrito.dff` + `.txd`, архів 8.64 МБ | MQ, оптика SA, фарбується | не перевірено | потрібне уточнення | DragonFF, 4 екстри розібрати | старий T1, не Sprinter. Файл важчий за «Газель» 1994 | сторінку переглянуто |
| ПАЗ-3205 | [gamemodding 6304](https://gamemodding.com/en/gta-san-andreas/cars/6304-paz-3205.html) | Stanislav, Grif | GTA SA, заміна Camper | не перевірено | не перевірено | не перевірено | потрібне уточнення | DragonFF | другий тип маршрутки, не «Богдан». Руль ліворуч, задній привід, свої handling | сторінку переглянуто |
| РАФ-2203 | [P.A.R.C](https://steamcommunity.com/sharedfiles/filedetails/?id=2734164805) | LemeS | PZ | не перевірено | не перевірено | не перевірено | потрібне уточнення | як пакет | у списку пакета є РАФ-2203. Окремої сторінки моделі не відкрито | сторінку пакета переглянуто |
| Volkswagen Passat B3 | [LC 159624](https://libertycity.net/files/gta-san-andreas/159624-volkswagen-passat-b3.html) | Crecket | GTA SA | архів 3.86 МБ; імена файлів сторінка не показала | «якісні», робоча оптика | не перевірено | анкети немає. Потрібне уточнення | DragonFF | седан B3. Слот заміни не названий | сторінку переглянуто |
| Opel Vectra A, 1991 | [LC 230463](https://libertycity.net/files/gta-san-andreas/230463-opel-vectra-a-1991.html) | SerbianMods, YusufTknz, sase06, ByHakan. Ролі не розділені | GTA SA | архів 5.38 МБ; імена файлів не показані | не перевірено | не перевірено | потрібне уточнення | DragonFF | сторінка сама пише «сімейний седан» | сторінку переглянуто |
| Ford Sierra Kombi 2.3D | [LC 204950](https://libertycity.net/files/gta-san-andreas/204950-ford-sierra-kombi-2.3d.html) | Areek | GTA SA | архів 1.52 МБ; імена файлів не показані | не перевірено | не перевірено | потрібне уточнення | DragonFF | універсал, не седан Sierra. Опису меша майже немає, лише рекламний абзац | сторінку переглянуто |
| Audi 80 B4 Avant | [LC 230542](https://libertycity.net/files/gta-san-andreas/230542-audi-80-b4-avant.html) | Avant, Filip Z M3, Noxx Art, Turn 10 Studios, SerbianMods | GTA SA | архів 4.60 МБ; імена файлів не показані | не перевірено | не перевірено | потрібне уточнення. У списку авторів є Turn 10 Studios, тож меш може бути не лише фанатський | DragonFF після з’ясування, чий кузов | універсал, не седан B4 | сторінку переглянуто |
| Audi 80 B4 RS2 | [LC 205280](https://libertycity.net/files/gta-san-andreas/205280-audi-80-b4-rs2.html) | Aividas | GTA SA | архів 4.59 МБ; імена файлів не показані | не перевірено | не перевірено | потрібне уточнення | DragonFF | спортивний седан, не стокова «вісімдесятка» | сторінку переглянуто |
| Ford Transit, 1986 | [LC 210252](https://libertycity.net/files/gta-san-andreas/210252-ford-transit-1986.html) | byordulu | GTA SA | `bobcat.dff` + `.txd`, архів 2.59 МБ | не перевірено | не перевірено | потрібне уточнення | DragonFF | сторінка зве це вантажівкою. Покоління в назві 1986, склад сцени не відкрито | сторінку переглянуто |
| Volkswagen Transporter T3 | [LC 222174](https://libertycity.net/files/gta-san-andreas/222174-volkswagen-transporter-t3.html) | Yura Pimenov | GTA SA | архів 2.95 МБ; імена файлів не показані | не перевірено | не перевірено | потрібне уточнення | DragonFF | сторінка: мікроавтобус 1979–1992, задній мотор. Слот заміни не названий | сторінку переглянуто |
| Volkswagen Transporter T4 | [LC 222173](https://libertycity.net/files/gta-san-andreas/222173-volkswagen-transporter-t4.html) | Yura Pimenov | GTA SA | архів 1.06 МБ; імена файлів не показані | не перевірено | не перевірено | потрібне уточнення | DragonFF | легший з двох фургонів Pimenov. Кузов (короткий чи довгий) сторінка не уточнює | сторінку переглянуто |

Стоковий седан Audi 80 B4 окремою карткою досі не відкритий: є універсал і RS2. Audi 80 B3 (Komarov Prod) у таблицю не ставив, сторінку не відкривав.

## Черга 3. Вантажівки, дорогі машини, інше

| Машина | Посилання | Автор моделі | Гра | Формат | Текстури | Трикутники | Умови | Шлях | Що адаптувати | Статус |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ГАЗ-53, кунг | [GTAall 20847](https://www.gtaall.com/gta-san-andreas/cars/20847-gaz-53.html) | Du-mont | GTA SA, заміна Rumpo | `rumpo.dff` 1.92 МБ + `.txd` 0.45 МБ | не перевірено | не перевірено | потрібне уточнення | DragonFF | кунг. Для матраців брати борт нижче | сторінку переглянуто |
| ГАЗ-53-12, борт | [LC 11160](https://libertycity.net/files/gta-san-andreas/11160-gaz-53-12-flatbed.html) | Du-Mont | GTA SA | архів 1002.42 КБ; імена DFF сторінка не показала | не перевірено | не перевірено | анкети немає. Потрібне уточнення | DragonFF | заголовок сторінки: flatbed / бортовий. Це кандидат під матраци. Склад кузова не відкрито | сторінку переглянуто |
| ЗІЛ-130 і пожежний АЦ-40, КамАЗ-5410, Урал-4320, трактор МТЗ-80, причіп ММЗ-81021 | [P.A.R.C](https://steamcommunity.com/sharedfiles/filedetails/?id=2734164805) | LemeS | PZ | не перевірено | не перевірено | не перевірено | потрібне уточнення | як пакет | пожежна «ЗІЛ» для «Тліючої стерні» може сісти на АЦ-40, якщо меш справді пожежний. Це написано в списку, файл не відкрито | сторінку пакета переглянуто |
| Hummer H2 | [GTAall 37435](https://www.gtaall.com/gta-san-andreas/cars/37435-hummer-h2.html) | автор меша на сторінці не названий. Додав lada2106. Текст: «Quality envelope of NFS: U2» | GTA SA, заміна Patriot | `patriot.dff` 3.43 МБ + `.txd` 1.63 МБ | HQ | сторінка пише «48.302 polygons (Including dummy, damage, etc.)». Це не наш замір і не розкладка на трикутники | потрібне уточнення. Якщо оболонка з NFS, там ще й чужий меш | DragonFF і сильне спрощення, dummy й damage прибрати | для «Хаммера "Клад"» силует годиться, щільність ні. Спрощення обов’язкове | сторінку переглянуто |
| Range Rover Classic '91 | [KI5, 2409333430](https://steamcommunity.com/sharedfiles/filedetails/?id=2409333430) | мод KI5 | PZ, близько 22 МБ, ID `91range`. Потрібна that DAMN Library | не перевірено | багато варіантів, броня, багажник | не перевірено | той самий текст KI5 «On Lockdown», його видно в знімку сторінки | після дозволу різати до одного кузова | сторінку повністю в браузері не гортали; у каталог входить за знімком пошуку, не як відкритий архів | знімок сторінки, архів не відкрито |
| Скутер | [KI5 Vino 125, 2878374713](https://steamcommunity.com/sharedfiles/filedetails/?id=2878374713) | KI5. Сторінка: «All models, textures and animations were made by me». PizzaBoy це замовлення Greb | PZ B41, 5.792 МБ, ID `vino125` | не перевірено. Автор пише low poly mesh і детальні текстури | кольори, сумки | не перевірено | «On Lockdown», перепакування заборонене | після дозволу | для Опаришів є варіант PizzaBoy, близький до Faggio. Це не мопед і не велосипед | сторінку переглянуто |
| Скутер, Vespa-подібний | [itch, Poki3D](https://poki3d.itch.io/low-poly-vespa) | Poki3D | не гра | `.blend`, `.fbx`, `.glb`, `.obj`, `.stl`. Архів не завантажено | не перевірено | не перевірено. Сторінка пише low poly, числа немає | автор на сторінці: «Feel free to use it for anything (CC0)» | Blender або готовий GLB | переднє колесо крутиться разом із кермом. Це скутер, не мопед із педалями. Тег сторінки: motorcycle, vespa | сторінку переглянуто |
| BMW E34, low poly | [LC 112253](https://libertycity.net/files/gta-san-andreas/112253-bmw-e34-low-poly.html) | сторінка пише «Rockstar Games, Sallie». Хто з них автор меша, не пояснено | GTA SA, заміна Vincent | `vincent.dff` + `.txd`, архів 250.28 КБ | SA-номери, дно затекстурене | не перевірено; сторінка каже lightweight | потрібне уточнення. Ім’я Rockstar на картці означає, що це може бути чужий меш, не лише фанатська ліпка | DragonFF, лише після з’ясування, чий це меш | силует «п’ятірки» близько, файл маленький. У гру не брати, поки не ясно авторство | сторінку переглянуто |
| Mercedes-Benz W140, low poly | [LC 112673](https://libertycity.net/files/gta-san-andreas/112673-mercedes-benz-w140-low-poly.html) | Sallie | GTA SA, заміна Elegant | `elegant.dff` + `.txd`, архів 202.51 КБ | SA-номери | не перевірено | потрібне уточнення. Анкети «в інші ігри не можна» на цій сторінці немає | DragonFF → GLB | найлегший відкритий «Кабан». Damage лишити як окремий стан або прибрати | сторінку переглянуто |
| Toyota Land Cruiser 100 | [LC 180246](https://libertycity.net/files/gta-san-andreas/180246-toyota-land-cruiser-100.html) | Naranbaatar | GTA SA | `rnchlure.dff` + `.txd`, архів 2.38 МБ | «висока якість», робоча оптика, ENB | не перевірено | потрібне уточнення | DragonFF, оцінити щільність після імпорту | другий, важчий «Крузак» на 8.36 МБ (FIST CAR MODS) у пошуку був, сторінку не відкривав | сторінку переглянуто |
| Jeep Cherokee ZJ | [LC 189539](https://libertycity.net/files/gta-san-andreas/189539-jeep-cherokee-zj.html) | Evil Works Production; завантажив Super Prisoner | GTA SA | архів 1.79 МБ; імена DFF сторінка в знімку не показала | HQ салон і екстер’єр, тонування, CCD | не перевірено | потрібне уточнення | DragonFF | знімок сторінки з пошуку, повторно не гортав | знімок сторінки |
| BMW E36 Sedan Low | [LC 139877](https://libertycity.net/files/gta-san-andreas/139877-bmw-e36-sedan-low.html) | Razzvy., ikey07 | GTA SA | `infernus.dff` + `.txd`, архів 3.21 МБ | «висока якість» в англійському тексті; російський на тій самій сторінці пише «хорошие» | не перевірено. «Low» це назва файлу, не замір | анкети немає. Потрібне уточнення | DragonFF | седан E36, заміна Infernus за іменем файлу. Важчий E36 на 12.91 МБ (Резутик, `sultan`) у цей прохід не брав | сторінку переглянуто |
| Велосипед | [OpenGameArt, Clint Bellanger](https://opengameart.org/content/bicycle) | Clint Bellanger | не гра; low-poly toon | zip 249.6 КБ, у описі Blender-матеріали й карти diffuse/spec | UV, риг, анімація педалей. Окремо є спрайтшід PNG на 8 напрямків | сторінка пише **820 tris**. Не міряв | **CC-BY 3.0**: ім’я автора десь у грі | Blender → GLB. Спрайтшід не плутати з мешем | старий міський велосипед для даху маршрутки. Це не мопед | сторінку переглянуто |
| Човни | [Kenney Watercraft Kit 2.0](https://opengameart.org/content/watercraft-kit), zip `kenney_watercraft_kit_0.zip` | Kenney | не гра | FBX, GLB, OBJ. У `License.txt` дата 17-04-2024. GLB у архіві **46** файлів | `colormap.png` лежить окремо в `Models/FBX format/Textures/`, у витягнутий GLB не вшита | `boat-speed-a.glb` у Blender 5.2.2: **156** трикутників, габарит **1.785 × 3.37 × 1.5** м (X, Y, Z), низ на Z = 0. Один меш `boat-speed-a`. Решту не міряв | **CC0**, текст `License.txt` у zip. Кредит не обов’язковий | GLB уже в пакеті. Для Godot покласти поруч `colormap.png`, інакше матеріал порожній | для стрибка №19 брати `boat-speed-a` … `boat-speed-j`. Є ще `boat-fishing-small`, `boat-row-small`, `boat-row-large`. Контейнери: `cargo-container-a/b/c` | архів перевірено; `boat-speed-a` імпортовано в Blender. У Godot цей GLB не ганяв |

Кар’єрний самоскид і КрАЗ у перевірений список не входять. КрАЗ-255 на p3dm.ru у пошуку має підпис «Personal use only» і це ріп із чужої гри. Сторінку не розбирав і в таблицю не ставив. Мопед з педалями окремим мешем не знайдений: є скутер KI5 і Vespa Poki3D.

## Реквізит

Справжній меш, не спрайт:

| Асет | Посилання | Автор | Формат | Текстури | Трикутники | Умови | Шлях | Статус |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Car Kit 3.1: седан, хетч, ван, таксі, поліція, швидка, пожежна, трактор, окремі колеса, конуси, уламки дверей, бампера, шини | [OpenGameArt](https://opengameart.org/content/car-kit), дзеркало zip `kenney_car-kit_3.1.zip` | Kenney | FBX, OBJ, GLB. Архів відкрито | `colormap.png` біля FBX | для `hatchback-sports.glb` виміряно: кузов 760, кожне колесо 332, разом **2088** | **CC0**, текст `License.txt` у архіві. Кредит не обов’язковий | GLB вже є. Для гри: імена коліс і ніс, як у пробі нижче | архів перевірено → імпорт у Blender перевірено → GLB перевірено (лише hatchback-sports) |
| City Kit Roads 2.2 | [OpenGameArt](https://opengameart.org/content/city-kit-roads), zip `kenney_city-kit-roads_2.2.zip` | Kenney | FBX, GLB, OBJ. `License.txt`: 10-10-2026, CC0 | `colormap` за аналогією з іншими паками Kenney; цей png окремо не відкривав | не міряв | **CC0** у `License.txt` | готовий GLB → Godot | архів перевірено |
| Factory Kit 3.0 | [OpenGameArt](https://opengameart.org/content/factory-kit), zip `kenney_factory-kit_3.0.zip` | Kenney | FBX, GLB, OBJ. 143 файли `.fbx`. `License.txt`: 01-05-2026 | png у zip є, окремо не відкривав | не міряв | **CC0** у `License.txt` | GLB `box-small`, `box-large`, `box-long`, `box-wide` | архів перевірено |
| Бочки, ящик, палета, конус, бар’єр, зварювальний балон | [3TD Industrial Pack](https://lpc.opengameart.org/content/3td-industrial-pack), zip `3TD_IndustrialPack.zip` | Ron Kapaun, 3TD Studios | DAE + JPG/PNG. Окремі меші: `3td_Barrel_01`, `3td_Barrel_02`, `3td_Crate01.dae`, `3td_Pallet01.dae`, `RoadBarrier_01.dae`, `SafetyCone01.dae`, `WeldingTank01.dae` | карти кольору, нормалей і спекуляра біля кожного меша | не міряв | сторінка OGA пише CC0. У zip файл `Instructions and License Info.rtf`: використовувати як завгодно, не перепаковувати й не перепродавати пак як свою роботу | Blender імпорт DAE → GLB. У Blender цей zip не імпортовано | архів перевірено |

У zip Factory Kit бочок, палет, бензоколонки й інструменту немає: з ящиків лише `box-small`, `box-large`, `box-long`, `box-wide`. Контейнери є у Watercraft Kit: `cargo-container-a`, `cargo-container-b`, `cargo-container-c`. Дорожні знаки в Roads 2.2 названі файлами: `road-sign-stop`, `road-sign-warning`, `road-sign-street`, `road-sign-empty`, плюс `sign-highway-detailed` і `sign-highway-wide`. `WeldingTank01` це балон, не колонка. Бензоколонки, гаражного інструменту, вагончика й цілого кузова розбитої «шістки» в цих архівах немає. Уламки Car Kit лишаються дверцятами, бампером і шинами. Спрайт велосипеда Clint Bellanger лежить поруч із його мешем; у гру брати меш.

## Пробний GLB

Це **не** Fiat і не конверсія GTA. Вихідник: `Models/GLB format/hatchback-sports.glb` з Kenney Car Kit 3.1.

- Blender 5.2.2 імпортував glTF. Потім модель розвернуто на 180° навколо Z, щоб ніс дивився в +Y.
- Колеса посаджені на порожні `Wheel_FL`, `Wheel_FR`, `Wheel_RL`, `Wheel_RR`. Меш дитини після повторного імпорту має локальний зсув `(0, 0, 0)`.
- Кузов названо `Vehicle_Body`. Скла, фар і окремої фарби в цьому меші немає: один матеріал `colormap` на все.
- Експорт GLB з Yup.

Вимір вершин у Blender після адаптації: **1.3 × 2.85 × 1.1 м** (ширина X, довжина Y, висота Z), низ на Z = 0, трикутників 2088. Файл `artifacts/vehicle_model_research/kenney_hatchback_sports_trial.glb`, 131676 байт.

Godot 4.7.2 в ізольованому проєкті імпортував сцену. Локальні позиції:

- `Wheel_FL` `(-0.3, 0.3, -0.81)`, `Wheel_FR` `(0.3, 0.3, -0.81)`. Ніс у **−Z**, ліве колесо на **−X**.
- `Wheel_RL/RR` на Z `+0.81`.
- Локальний AABB кузова `(1.3, 0.95, 2.85)`. Центри коліс на Y = 0.3, короткий розмір колеса по X = 0.35, тож вісь кочення це локальна X, як у `vehicle.gd`.
- Обертання в тому прогоні не підтверджено: вузол не стояв у дереві сцени, `global_transform` був порожній. Позиції й імена підтверджені.

Прев’ю це Workbench-рендер глини, камера з боку −Y, тобто з корми. Текстуру `colormap` цей кадр не показує.

![Пробний хетчбек Kenney, вид ззаду](/home/mallar2d/Документи/ChatGPT/klad-theft-hummer/artifacts/vehicle_model_research/kenney_hatchback_sports_preview.png)

У `assets/models/` файл не копіювався. `.gdignore` поруч, щоб головний проєкт його не підхопив.

## Завантажено локально

13 жовтня 2026 скачані й розпаковані лише паки, які сайт віддає прямим посиланням. Лежать у `artifacts/vehicle_model_research/`. `.gdignore` у цій теці, тож гра їх не імпортує. У `assets/models/` нічого не копіювалось.

- `downloads/zips/` — архіви як прийшли.
- `downloads/extracted/` — розпаковане дерево автора.
- `sorted/` — хардлінки тих самих файлів по полицях. Текстура Kenney це симлінк `Textures/colormap.png`, бо GLB шукає її поруч із собою.

| Полиця | Що там | Звідки |
| --- | --- | --- |
| `sorted/vehicles/cars` | 20 GLB: седан, хетч, suv, таксі, поліція, швидка, пожежна, ван, вантажівки, трактор | Kenney Car Kit 3.1, CC0 |
| `sorted/vehicles/karts` | 5 GLB | той самий пак |
| `sorted/vehicles/wheels` | 8 GLB коліс | той самий пак |
| `sorted/vehicles/boats` | 25 GLB, серед них `boat-speed-a` … `boat-speed-j` | Kenney Watercraft 2.0, CC0 |
| `sorted/vehicles/ships` | 8 GLB | той самий пак |
| `sorted/props/boxes` | `box-small`, `box-large`, `box-long`, `box-wide` | Kenney Factory 3.0, CC0 |
| `sorted/props/factory` | решта 139 GLB заводу (конвеєри, крани). Бочок там немає | той самий пак |
| `sorted/props/signs` | 11 GLB, зокрема stop / warning / street | Kenney City Kit Roads 2.2, CC0 |
| `sorted/props/barriers` | 23 GLB бар’єрів | той самий пак |
| `sorted/props/traffic_lights` | 6 GLB | той самий пак |
| `sorted/props/roads` | 55 GLB полотна | той самий пак |
| `sorted/props/shipping_containers` | `shipping-container-a/b/c` | Kenney City Kit Industrial 2.0, CC0. Zip у цей прохід відкрито вперше |
| `sorted/props/industrial_buildings` | 20 GLB будівель | той самий пак |
| `sorted/props/containers` | `cargo-container-a/b/c` | Watercraft |
| `sorted/props/debris` | шина, двері, бампер, конуси з Car Kit | Car Kit |
| `sorted/props/barrels` | `3td_Barrel01.Dae` (металева бочка) і `3td_Barrel02.dae` з картами | 3TD Industrial. У rtf: користуватись можна, пак не перепродавати |
| `sorted/props/crates` | `3td_Crate01.dae` | той самий пак |
| `sorted/props/pallets` | `3td_Pallet01.dae` | той самий пак |
| `sorted/props/tanks` | `WeldingTank01.dae`, це балон | той самий пак |
| `sorted/cc-by/bicycle` | `bicycle.blend` і карти | Clint Bellanger, CC-BY 3.0 |
| `sorted/cc-by/gascan` | `Gasoline_can.blend` / `.obj` / `.dae` | Vinrax, CC-BY 3.0. На сторінці 292 трикутники, сам не міряв |
| `sorted/cc-by/barrels_boxes_pallet` | `barrel_metal.blend`, `barrel_wooden.blend`, `box_metal.blend`, `box_wooden.blend`, `shipping_pallet.blend` | Johnathon Williamson, CC-BY 3.0, без текстур |

Liberty City, GTAinside і Steam Workshop у цю теку не лягли. Гостьова кнопка Liberty City спочатку тримає 30 секунд, потім `get_challenge.php` віддає запакований скрипт, який має виконати браузер. Прямого `.7z` у відповіді немає. Таврію DScorp, W124 Hamza і Renault 19 TheMadeMan не качав: автори заборонили конверсію в інші ігри. KI5, LemeS і Sherbug сидять у Steam і без входу не віддаються.

## Підключення до гри, окремо й поки не робити

`_ready()` у `scripts/vehicle.gd` бере шлях `res://assets/models/%s.glb` % `kind`. Новий силует це новий `kind`, інша коробка колізії, інша назва й, для фарби, матеріал, який `tint_paint()` упізнає. Зараз упізнається лише `Sedan_Paint`. Поліція малює сирену кубами в коді, не мешем. Маршрутка має іншу швидкість і довший короб.

Kenney-хетч 2.85 м коротший за поточний седан (кузов у `docs/models.md`: 4.2 м). Підставляти його замість «шістки» або Uno не треба: інший силует і інший габарит. GTA/PZ-меші не копіювати в `assets/`, поки автор не дозволив перенесення. DScorp, Hamza Selçuk і TheMadeMan (Renault 19) уже написали «в інші ігри не можна». KI5 і Sherbug Roger теж просять дозвіл до будь-якої переробки.
