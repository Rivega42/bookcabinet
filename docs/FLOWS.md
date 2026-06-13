# BookCabinet — два боевых флоу (аудит когерентности)

> Составлено 2026-06-13 по фактическому коду aiohttp-бэкенда (боевой) + React-клиента.
> Express (`server/*.ts`) — легаси, в этом разборе игнорируется.
> Каждый шаг подтверждён чтением кода; ссылки вида `файл:строка`. Где значение
> не проверялось на железе — помечено ❓. Источник истины при конфликте — код.

Легенда: ✅ связано корректно · ⚠️ разрыв/несогласованность · ❓ нужно решение Романа/проверка на железе.

---

## Карта вызова (оба флоу)

```
Клиент (React, киоск/админ)
  → HTTP /api/* + WebSocket            client/src, server/websocket_handler.py
  → server/api_routes.py               (роуты, role_check, _KioskProgress, with_mech_lock)
  → business/*  (стейт-машины)         auth, issue, return_book, load, unload
      → database/db.py  (*_tx)         атомарные транзакции статусов
      → irbis/service.py               ИРБИС (+ offline-очередь sync_queue)
      → mechanics/algorithms.py        take_shelf / give_shelf / wait_for_user
          → hardware/motors,servos,shutters,sensors
```

Подтверждено: все четыре сервиса ходят в механику **через `mechanics/algorithms.py`**
(`business/issue.py:102,111,115`, `business/return_book.py:95`, `business/load.py:53`,
`business/unload.py:29,33,35,125,131`). Слой `workflows/*` + `tools/shelf_operations.py`
(с RFID-верификацией) aiohttp-сервер **не вызывает** — он параллельный и спящий.

---

## ФЛОУ 1 — Пользователь: выдача / возврат

### 1.1 Авторизация (касание билета)
- Карта → `unified_reader` → `main.py:on_card_detected` → broadcast `card_detected` (WS).
- Параллельно `api_routes._on_card_detected` (`api_routes.py:~106`) зовёт
  `auth_service.authenticate(uid)` и шлёт `auth_result` (WS).
- `business/auth.py:authenticate`: тест-юзеры → ИРБИС (RDR, роль из поля 50) →
  фоллбек `db.get_user_by_rfid` (`database/db.py:300`). Роль: `reader|librarian|admin`.
- Клиент по `auth_result` роутит экран (`client/src/pages/kiosk.tsx`).
- ✅ Цепочка связана.
- ⚠️ При офлайн-ИРБИС роль берётся из локальной БД — если в ИРБИС роль изменилась,
  локальная копия устаревает (ресинка нет). Для киоска некритично.

### 1.2 Выдача
- Киоск: `ReaderScreens.tsx` BookList → `onIssue(rfid, userRfid)` → `POST /api/book/issue`
  (алиас; есть и `/api/issue`) → `api_routes.post_book_issue` (под `with_mech_lock`).
- `business/issue.py:issue_book` — стейт-машина:
  1. VALIDATE: `db.get_book_by_rfid`, проверка статуса/брони.
  2. `algorithms.take_shelf(row,x,y)` — полку с книгой к окну (`issue.py:102`).
  3. `algorithms.wait_for_user()` — ждём, пока заберут (`issue.py:111`).
  4. `algorithms.give_shelf(row,x,y)` — пустую полку обратно в ячейку (`issue.py:115`).
  5. `db.issue_book_tx` — `status=issued, cell_id=NULL` (`database/db.py:374`).
  6. `irbis.issue_book` — иначе в `sync_queue` (`irbis/service.py`).
- ✅ Связано. ⚠️ см. 1.4 (wait_for_user слепой), 1.5 (ИРБИС).

### 1.3 Возврат
- Книга в окне → `book_reader` (RRU9816) → `main.py:on_book_detected` →
  broadcast `book_read {data:{rfid,title}}` (подключено в PR #96; **раньше событие
  никто не эмитил → авто-возврат был мёртв**).
- `ReaderScreens.tsx:243` ловит `book_read`/`book_detected` → `startReturnSequence(rfid)`
  → `POST /api/book/return` → `api_routes.post_book_return` (под `with_mech_lock`).
- `business/return_book.py:return_book`:
  1. VALIDATE (нет в БД → попытка создать из ИРБИС).
  2. `db.find_empty_cell()` — **любая** пустая ячейка (`database/db.py`).
  3. `algorithms.give_shelf(row,x,y)` — полку в выбранную ячейку (`return_book.py:95`).
  4. `db.return_book_tx` — `status=awaiting_extraction` (`database/db.py:389`).
  5. `irbis.return_book` — иначе в очередь.
- ✅ Связано (после PR #96).
- ⚠️ Ячейка возврата — первая свободная по id, без привязки к исходной/ряду.
  Для проверки на железе: устраивает ли (балансировка рядов, путь каретки).

### 1.4 Механика выдачи (`mechanics/algorithms.py`)
- `take_shelf` (`:369`): retract лотка → XY к ячейке → grab (extend1→замок→retract→
  открыть→extend2→замок→полный retract) → **XY к окну** (`get_window_position`) →
  открыть внутреннюю шторку → выдвинуть в окно → открыть внешнюю шторку (`:412–424`).
- `give_shelf` (`:434`): закрыть внешнюю → retract → закрыть внутреннюю → XY к ячейке →
  вернуть полку → освободить лоток.
- **Глубина (ряд):** XY ячейки от ряда НЕ зависит — `get_cell_position` использует
  только `positions_x[x]`/`positions_y[y]` (`:33–37`). Ряд влияет на:
  (а) `grab_params = calibration.get('grab_front'|'grab_back', …)` (`:386`) — дальность
  выдвижения лотка; (б) `lock = 'lock1' if row=='FRONT' else 'lock2'` (`:393,463`).
  Полка ВСЕГДА доставляется в **передний** окно (`window` из `config.CABINET`,
  FRONT,1,9). То есть «взять из любого ряда → выдать в переднее окно» структурно есть.
- ✅ **wait_for_user детектит «книгу забрали» по RRU9816** (`:492`, реализовано 2026-06-13
  по решению Романа): ждём, пока метка книги перестанет видеться в окне
  (`book_reader.is_present` ← `current_tags` из цикла опроса). Таймаут — всегда верхняя
  граница; если метку ни разу не увидели (ридер не добивает/мок) — фоллбек на старое
  поведение (досыпает до таймаута). ❓ Требует валидации на железе: добивает ли антенна
  RRU9816 до окна выдачи.

### 1.5 ИРБИС офлайн
- DB-транзакция коммитится ДО вызова ИРБИС. Если ИРБИС недоступен — операция
  считается успешной локально, запись уходит в `irbis/sync_queue.py` (повтор каждые
  300 с, до 10 попыток; периодик стартует `main.py:185`).
- ⚠️ Пользователь всегда видит «успех», даже если ИРБИС ещё не знает о выдаче/возврате.
  Это сознательная offline-first модель, но статус синка наружу не виден.

---

## ФЛОУ 2 — Библиотекарь: веб + загрузка/изъятие

### 2.1 Роль и гейтинг
- Роли: `reader|librarian|admin` (`database/models.py`; права — там же).
- Бэкенд: `role_check('librarian','admin')` на `/api/load-book`, `/api/extract`,
  `/api/extract-all`, `/api/run-inventory` (`api_routes.py`). ✅ серверный гейт есть.
- ❓/⚠️ Фронтовый гейт админ-UI (`client/src/pages/admin.tsx`) — по карте агента
  роль на фронте не проверяется (косметика; бэкенд всё равно режет). Перепроверить.

### 2.2 Веб-интерфейс библиотекаря
- Экраны библиотекаря живут в киоске под ролевыми экранами
  (`client/src/components/kiosk/screens/LibrarianMenu|LoadBooks|ExtractBooks` —
  по карте агента) + админ-вкладки (`client/src/components/admin/*`).
- LoadBooks → `POST /api/load-book`; ExtractBooks → `GET /api/cells` +
  `POST /api/extract`; тест ридеров → SSE `/api/rfid-test/{id}` (добавлен в PR #96).

### 2.3 Загрузка книги (`business/load.py`)
- `POST /api/load-book` → `role_check` → `load_service.load_book`:
  поиск/создание книги (опц. тянет название из ИРБИС) → verify в ИРБИС →
  выбор ячейки (`cellId` или `db.find_empty_cell`) → `algorithms.give_shelf` →
  `db.load_book_tx` (`status=in_cabinet, cell_id=…`).
- ⚠️ RFID книги вводится/сканируется **вручную** в форме, RRU9816 при загрузке метку
  НЕ читает. Рассинхрон «метка ↔ запись» возможен; ловится только инвентаризацией.

### 2.4 Изъятие книги (`business/unload.py`)
- `POST /api/extract` (и `/api/extract-all`) → `role_check` →
  `unload_service.extract_book(cell_id)`: проверка ячейки → `algorithms.take_shelf` →
  `wait_for_user` (библиотекарь забирает) → `algorithms.give_shelf` (пустую полку назад) →
  verify в ИРБИС → `db.extract_book_tx` (`status=extracted, cell_id=NULL`).
- ⚠️ При изъятии метка книги повторно НЕ сканируется (`book_reader.inventory`) — доверие
  записи в БД. Отдельная операция инвентаризации (`unload.py:~82`) метки сверяет.

### 2.5 Очередь на изъятие
- `cells_view` вычисляет статус ячейки из книги; `needs_extraction=1` когда книга
  `awaiting_extraction` (вернули, но физически ещё в шкафу). `/api/cells/extraction`
  отдаёт очередь. ✅ Согласовано: возврат → awaiting_extraction → очередь → extract → extracted.

---

## ⚠️ ГЛАВНОЕ ДЛЯ РОМАНА — два разных файла калибровки

Самый важный вывод аудита (проверено чтением кода, не агентом):

**Боевое приложение (aiohttp → algorithms.py) и скрипты `tools/` читают РАЗНЫЕ файлы
калибровки с РАЗНЫМИ схемами.**

| | Файл | Схема (ключи) | Кто читает |
|---|---|---|---|
| Приложение | `bookcabinet/calibration.json` | `positions.x/y`, `grab_front`, `grab_back`, `kinematics`, `speeds`, `servos` | `mechanics/calibration.py` → `algorithms.py`, `corexy.py` |
| Скрипты | `calibration.json` (корень) | `racks` (65/10205/20360), `shelves.anchors`, `depth.back_y_offset`, `tray` | `tools/calibration.py` (резолвер адресов tools/-слоя) |

Факты:
- `bookcabinet/calibration.json` **в репозитории ОТСУТСТВУЕТ** → `mechanics/calibration.py._load()`
  отдаёт `_default_data()`: `positions.x=[1891,6392,10894]`, `grab_front`==`grab_back`=
  `{extend1:1900,retract:1500,extend2:3100}` (`mechanics/calibration.py:39–63`).
  Фоллбек в самом `algorithms.py` ещё другой — `[0,4500,9000]` (`algorithms.py:29`).
- Значит до запуска **внутреннего мастера калибровки** (эндпоинты
  `/api/calibration/wizard/{kinematics,points10,grab}/…`, `api_routes.py`) приложение
  ездит по ДЕФОЛТНЫМ XY, **не** по полевым `racks`/`shelves` из корневого `calibration.json`.
- `grab_front` и `grab_back` в дефолте **одинаковые** → глубинная разница (передний/задний
  ряд) у приложения по умолчанию НЕ выставлена, хотя в корневом файле `depth.back_y_offset=30` есть.

Что это значит для «полного флоу со шкафа»:
1. ❓ На развёрнутом шкафу нужно проверить, **существует ли `bookcabinet/calibration.json`**
   и заполнен ли он реальными значениями (если мастер калибровки в админке прогоняли —
   да; если нет — приложение на дефолтах).
2. ❓ Front→front / back→back, что отлаживались, гонялись через `tools/`-скрипты
   (корневой `calibration.json`) или через приложение (`bookcabinet/calibration.json`)?
   От этого зависит, переносится ли отладка на боевой флоу.
3. Варианты решения (НЕ выполнял — меняет цели движения, нужно явное «ок» и проверка на железе):
   - (A) Прогнать встроенный мастер калибровки в админке на шкафу → заполнит `bookcabinet/calibration.json`.
   - (B) Мост: при старте читать полевые `racks`/`shelves.anchors`/`depth` из корневого
     `calibration.json` и транслировать в схему приложения (`positions.x/y`, `grab_*`).
   - (C) Свести оба слоя к одному файлу/резолверу (большая работа, после миграции на aiohttp).

Безопасная аддитивная мера (предлагаю, не делал): на старте логировать WARNING, если
`bookcabinet/calibration.json` отсутствует — чтобы на шкафу было видно, что механика на дефолтах.

---

## Сводка разрывов

| # | Где | Разрыв | Severity | Решение |
|---|---|---|---|---|
| 1 | mechanics/calibration.py:34 vs tools/calibration.py | Два файла калибровки, две схемы; app-файл в репо отсутствует → дефолты | ⚠️ высокий | за Романом: мастер / мост / унификация |
| 2 | algorithms.py:492 | `wait_for_user` детектит «забрали» по RRU9816 (реализовано) | ✅/❓ | валидировать антенну на железе |
| 3 | issue.py/return_book.py + irbis | DB коммитится до ИРБИС; «успех» всегда, статус синка не виден | ⚠️ | offline-first, ок; опц. показывать очередь |
| 4 | return_book.py + db.find_empty_cell | Ячейка возврата — первая свободная, без привязки к ряду/исходной | ⚠️ | проверить на железе |
| 5 | load.py | RFID книги вводится вручную, RRU9816 при загрузке не читает | ⚠️ | опц.: читать метку при загрузке |
| 6 | unload.py extract | При изъятии метку повторно не сверяет | ⚠️ | опц.: verify через inventory |
| 7 | client/src/pages/admin.tsx | Фронтовый ролевой гейт админки (по карте агента) — косметика | ❓ | перепроверить; бэкенд режет |

Связанное: [[rpi-deployment-reality]] · docs/STATE.md (раздел «часть 4») · CLAUDE.md (железные правила механики).
