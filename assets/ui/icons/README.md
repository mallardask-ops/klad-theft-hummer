# Аркуші іконок Klad Theft Hummer

Фінальний напрям: строгі прості форми GTA III, спільна охристо-чорна палітра, мінімум внутрішніх деталей. Статусні символи зберігають кольори з брифу.

Усі PNG мають прозорість і розмір 1024×1024. Для аркушів 4×4 клітинка 256×256, для радіо 2×2 клітинка 512×512. Порожні клітинки пропускаються. Порядок: зліва направо, зверху вниз.

| Аркуш | Сітка | Іконок | Порядок id |
|---|---|---:|---|
| [sheet_a_weapons.png](sheet_a_weapons.png) | 4×4 | 11 | fist, hammer, pan, bat, crowbar, makarov, sawnoff, ak, uzi, molotov, grenade |
| [sheet_b_hud.png](sheet_b_hud.png) | 4×4 | 4 | health, armor, wanted_on, wanted_off |
| [sheet_c_services.png](sheet_c_services.png) | 4×4 | 10 | safehouse, respray, gunshop, bombshop, hospital, police, cafe, market, busstation, fuel |
| [sheet_c_activities.png](sheet_c_activities.png) | 4×4 | 9 | marshrutka, vigilante, ambulance, delivery, race, cliffjump, fishing, rampage, package |
| [sheet_d_pickups.png](sheet_d_pickups.png) | 4×4 | 4 | health, armor, package, rampage |
| [sheet_e_radio.png](sheet_e_radio.png) | 2×2 | 4 | kodlo, cast, shanson, barista |
| [sheet_f_mission_items.png](sheet_f_mission_items.png) | 4×4 | 5 | gold_box, sugar, donor_phone, debt_journal, cashbox |
| [app_icon.png](app_icon.png) | 1×1 | 1 | app |

Префікси після нарізки: weapon_, hud_, blip_, pickup_, radio_, item_. Емблема вже окремо: app_icon.png. Для HUD і радара після вирізання клітинки зменшити іконку до 128×128; зброя, пікапи й предмети лишаються 256×256, радіо 512×512.

[manifest.json](manifest.json) містить прямокутник кожної клітинки й очікувану назву PNG. [Перегляд у 24/32/64 px](../../../artifacts/gpt_icons_brief/preview.html), [повні промпти](../../../artifacts/gpt_icons_brief/PROMPTS.json), [референси](../../../artifacts/gpt_icons_brief/RESEARCH.md).

Згенеровано вбудованим imagegen. ImageMagick використано для технічного експорту на точну сітку 1024×1024 зі збереженням альфа-каналу: іконки вписано в клітинки з відступом близько 10% та вирівняно по центру. Натуральний розмір кожного згенерованого джерела збережено в artifacts/gpt_icons_brief/generated_native/.

Перевірка: **PASS**, 48 позицій, 8 PNG, точні розміри, прозорість і відступи. [Машинний звіт](../../../artifacts/gpt_icons_brief/VALIDATION.json), [antislop Delivery Gate](../../../artifacts/gpt_icons_brief/DELIVERY_GATE.md).
