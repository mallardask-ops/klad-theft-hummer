# Звуки гри

У грі 31 аудіоасет із CC0-джерел: мікрофонні записи, Foley та готова музична композиція. Це аналоги для атмосфери екшену часів GTA III. Файли GTA не використано. Генератора тонів, шуму й мелодій у збірці більше немає.

Нові джерела перевірено 13 жовтня 2026 року; попередні записи — 12 жовтня. BigSoundBank дозволяє обрізання, обробку, розповсюдження й комерційне використання на [сторінці ліцензії](https://bigsoundbank.com/licenses.html). Трек [Funked Up](https://opengameart.org/content/funked-up) від Joth також опублікований під [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

| Файли у грі | Джерело | Автор |
| --- | --- | --- |
| `step_gravel.wav`, `step_gravel_2.wav` | [Footsteps on gravels #1](https://bigsoundbank.com/steps-on-gravels-s0510.html) | Joseph SARDIN |
| `step.wav`, `step_concrete_2.wav` | [Fast Steps on Concrete](https://bigsoundbank.com/courir-sur-beton-s1319.html) | Joseph SARDIN |
| `swing.wav` | [Whoosh #8](https://bigsoundbank.com/whoosh-8-s1801.html) | Joseph SARDIN |
| `hammer_metal.wav` | [Anvil #2](https://bigsoundbank.com/anvil-2-s3590.html) | Pablo BERGEL |
| `crash_light.wav` | [Hammer fall on concrete](https://bigsoundbank.com/hammer-fall-on-concrete-s1108.html) | Joseph SARDIN |
| `door.wav` | [Car door #3](https://bigsoundbank.com/car-door-3-s1524.html) | Joseph SARDIN |
| `engine_start.wav` | [Small gasoline engine](https://bigsoundbank.com/small-gasoline-engine-s0966.html) | Joseph SARDIN |
| `siren.wav` | [Gendarmerie, Outdoor Siren](https://bigsoundbank.com/siren-french-gendarmerie-s0886.html) | BigSoundBank (page metadata: Joseph Sardin; no individual technical credit) |
| `ambience.wav` | [Paris by Night](https://bigsoundbank.com/paris-by-night-s0680.html) | Joseph SARDIN |
| `river.wav` | [Watercourse 5.2](https://bigsoundbank.com/watercourse-5-2-s3137.html) | Joseph SARDIN |
| `wind.wav` | [Wind in Tall Grass](https://bigsoundbank.com/wind-in-tall-grass-s0908.html) | Joseph SARDIN |
| `radio_static.wav` | [Radio interference #3](https://bigsoundbank.com/radio-interference-3-s2512.html) | Joseph SARDIN |
| `birds.wav` | [Ambient Bird Sounds](https://opengameart.org/content/ambient-bird-sounds) | isaiah658 |
| `hurt.wav` | [Hurt Sound Effects](https://opengameart.org/content/hurt-sound-effects) | EZduzziteh |
| `engine.wav`, `engine_load.wav` | [Damaged muffler (accelerations, parked car)](https://bigsoundbank.com/damaged-muffler-accelerations-parked-car-s0675.html) | Joseph SARDIN |
| `road.wav` | [Car on a Road](https://bigsoundbank.com/car-on-a-road-s1286.html) | Joseph SARDIN |
| `diesel_idle.wav` | [Truck engine](https://bigsoundbank.com/truck-engine-s1145.html) | Joseph SARDIN |
| `tires.wav` | [Screeching Tires #1](https://bigsoundbank.com/screeching-tires-1-s2368.html) | Joseph SARDIN |
| `crash.wav` | [Falling sheet steel bar #4](https://bigsoundbank.com/falling-sheet-steel-bar-4-s1774.html) | Joseph SARDIN |
| `ui.wav`, `ui_accept.wav` | [Raspberry Mouse, Single Click](https://bigsoundbank.com/raspberry-mouse-single-click-s1735.html) | Joseph SARDIN |
| `pickup.wav` | [Coin in cup #1](https://bigsoundbank.com/coin-in-cup-1-s0339.html) | Joseph SARDIN |
| `impact.wav` | [Punch #5](https://bigsoundbank.com/punch-5-s2460.html) | Joseph SARDIN |
| `mission_start.wav`, `fail.wav` | [Vinyl Scratch #18](https://bigsoundbank.com/vinyl-scratch-18-s2875.html) | Joseph SARDIN |
| `radio.ogg`, `mission_pass.wav` | [Funked Up](https://opengameart.org/content/funked-up) | Joth |
| `diesel_load.wav` | [Truck engine, big accelerations](https://bigsoundbank.com/truck-engine-big-accelerations-s1147.html) | Joseph SARDIN |

Бензиновий мотор — запис машини з пошкодженим глушником; дизель — Iveco Daily. Це художні замінники Жигуля й маршрутки. Сирена записана у французької жандармерії. Місто, річка, вітер і птахи також є замінниками, а не польовими записами Коростишева. Сильне зіткнення використовує падіння листового металу; слабке — удар молотка об бетон. Це Foley, а не запис автокатастрофи.

`impact` — глухий удар для людей; `hammer_metal` — молоток по металу для машин. `ui` і `ui_accept` — короткі обрізані клацання миші; `pickup` — монета; початок і провал місії — скретч вінілової платівки; успіх — чотирисекундний музичний фрагмент. Для Punch #5 автор також дякує Kellian F. і Yoann B.

Мікс має шини SFX, UI, Vehicle, Environment і Music та обмежувач Master до −1 dB. Під час їзди окремо змішуються холостий хід, навантаження двигуна, дорога та шини. Зміна висоти імітує оберти й перемикання передач без зміни фізики машини. Сирена, найближчий автомобіль у русі й удари NPC розташовані у 3D. Сигнали місій мають окремий плеєр, приглушують радіо й не обриваються через кроки чи бій. Нульова загальна гучність глушить увесь мікс через шину Game перед лімітером Master.

Оригінали, посилання, ліцензії, SHA-256 і параметри обробки лежать у `assets/audio/recorded/manifest.json`. Нові сторінки джерел збережені у `artifacts/audio_refresh/source-pages/`. Обробка — обрізання, видалення початкової тиші та DC, легкі фільтри, вирівнювання піків і перехресні переходи на петлях. Вона не генерує нові звуки. Радіо містить повний 66-секундний трек у стерео Ogg Vorbis; короткі ефекти — PCM WAV.

Відтворення асетів із наявних оригіналів:

```sh
python3 tools/import_recorded_audio.py
python3 tools/build_audio.py
```

Для відсутніх оригіналів: `python3 tools/fetch_audio_sources.py`. Потрібні Python 3 і ffmpeg. Відсутній або змінений запис зупиняє збірку; синтезованої підміни немає.

Аудіопрогін: `tools/audio_replay.gd`. Записи реального міксу та результати перевірок: `artifacts/audio_refresh/validation/`. Команди й межі перевірки наведені у `artifacts/audio_refresh/README.md`.
