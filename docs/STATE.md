# BookCabinet — Состояние проекта

> Обновлено 2026-06-13 ПОСЛЕ ВЫКЛАДКИ на шкаф. Что работает / что не доделано / что под вопросом.
> Аппаратные факты — в `docs/HARDWARE.md`. Исторические решения — `docs/DECISIONS.md`, `docs/DEVLOG.md`.
> Подробный лог сессии выкладки и находок — был в `.local-dev/rpi-snapshot-2026-06-13/NOTES.md` (вне git).

## ✅ ВЫЛОЖЕНО на шкаф 2026-06-13 (проверено на железе)

Боевой шкаф (`Shkaf`, Pi 3) переведён на новую систему. Проверено вживую:

```
pigpiod + pcscd-daemon.service (постоянный pcscd для NFC)
  → bookcabinet.service  (python3 -m bookcabinet.main — aiohttp, порт 5000, HOST=127.0.0.1)
  → chromium-kiosk (localhost:5000)
```

- **Боевой сервер — Python aiohttp** (`bookcabinet/main.py` → `server/web_server.py`, отдаёт API + фронт `dist/public`).
  Node/Express (`server/*.ts`) БОЛЬШЕ НЕ боевой — кандидат в `_attic/` (см. «Осталось»).
- **БД — SQLite v2** (`bookcabinet/data/shelf_data.db`, user_version=2). Мигрирована v0→v2 через alembic (0001→0002), данные целы.
  Схема: `database/db.py` (нормализация книга↔ячейка, статусы по физике, транзакции, cells_view). Drizzle/PostgreSQL не используется.
- **Считыватели — все 3 живут:** RRU9816 (книги, `/dev/rfid_book`→ttyUSB0), IQRFID-5102 (ЕКП, `/dev/rfid_uhf_card`→ttyUSB1),
  ACR1281 (NFC билет, через постоянный `pcscd-daemon.service`). udev по реальным USB-портам, config на стабильные имена.
- **Стартовая механика (проверена на железе):** замки→500мкс (held), хоминг XY (LEFT+BOTTOM), калибровка лотка FRONT→BACK→CENTER
  (по `tools/tray_calib_final.py`: двухэтапно, sensor_stable=10 подряд; total≈22523, center≈11261).
- Откат на устройстве: код `/tmp/rollback-code.tgz`, юнит `bookcabinet.service.pre-deploy`, БД `backups/backup_20260613_184658_pre-deploy`.

## Цикл выдачи (как написан в коде)

Два слоя реализации:

1. **`business/issue.py` / `business/return_book.py`** — стейт-машины над БД (БОЕВОЙ путь aiohttp):
   - Выдача: VALIDATE → TAKE_SHELF → WAIT_USER → GIVE_SHELF → UPDATE_DB → CALL_IRBIS → DONE; механика через `mechanics/algorithms.py` (take_shelf/give_shelf: Г-образный путь, двухэтапный захват полки лотком+замком, шторки), при ошибке `_safe_recover()`; БД обновляется одной транзакцией (`*_tx`) только после успешной механики.
   - Возврат: VALIDATE → FIND_CELL (первая пустая) → GIVE_SHELF → UPDATE_DB (awaiting_extraction) → CALL_IRBIS → DONE.
   - ⚠️ Полный цикл захвата полки на ЖЕЛЕЗЕ ещё не прогонялся (подтверждены только хоминг + калибровка лотка). См. «Под вопросом».
2. **`workflows/issue.py` / `workflows/return_book.py`** — боевые 18/19-шаговые сценарии: субпроцессы к `tools/goto.py`, `tools/shelf_operations.py`, `tools/shutter.py`. Это наследие Node-пути (через `bridge.py`); на aiohttp основной путь — business/*.

ИРБИС при выдаче/возврате: запись в поле 40 RDR + статус экземпляра 910^A; при недоступности — офлайн-очередь `irbis/sync_queue.py`.

## Цикл выдачи (как написан в коде)

Два слоя реализации:

1. **`business/issue.py` / `business/return_book.py`** — стейт-машины над БД:
   - Выдача: VALIDATE → TAKE_SHELF → WAIT_USER → GIVE_SHELF → UPDATE_DB → CALL_IRBIS → DONE; механика через `mechanics/algorithms.py` (take_shelf/give_shelf: Г-образный путь, двухэтапный захват полки лотком+замком, шторки), при ошибке `_safe_recover()`; БД обновляется только после успешной механики.
   - Возврат: VALIDATE → FIND_CELL (первая пустая) → GIVE_SHELF → UPDATE_DB (`needs_extraction=True`) → CALL_IRBIS → DONE.
2. **`workflows/issue.py` / `workflows/return_book.py`** — боевые 18/19-шаговые сценарии (issues #79/#80): субпроцессы к `tools/goto.py`, `tools/shelf_operations.py`, `tools/shutter.py`, проверка RFID книги на шаге 7, таймауты (шторка 15с, забор книги 30с, возврат 60с, retry при несовпадении RFID 61с). Вызываются из Node через `bridge.py`.

ИРБИС при выдаче/возврате: запись в поле 40 RDR + статус экземпляра 910^A; при недоступности — офлайн-очередь `irbis/sync_queue.py`.

## ✅ Что работает (проверено на железе 2026-06-13, если не указано иное)

- Боевой aiohttp-сервер `main.py` на шкафу; БД v2 (миграция выполнена, данные целы); киоск отдаётся (200).
- **Все 3 считывателя живут:** RRU9816 (книги), IQRFID-5102 (ЕКП), ACR1281 (NFC билет). NFC — через постоянный `pcscd-daemon.service` (дубли pcscd убраны).
- Стартовая механика: замки→500мкс, хоминг XY (LEFT+BOTTOM), **калибровка лотка FRONT→BACK→CENTER** (по `tools/tray_calib_final.py`).
- Канонический слой движения `tools/corexy_motion_v2.py`; calibration.json с полевыми измерениями.
- ИРБИС-клиент: полный TCP-протокол, поиск по карте и `IN=` подтверждён данными 14.04.2026 (но с боевого шкафа сейчас сеть ИРБИС недоступна — см. ниже).
- Киоск-UI: 14 экранов, WebSocket-прогресс, автологаут 60с (kiosk.tsx распилен на экраны, admin.tsx — на вкладки).
- БД-слой v2: нормализация, транзакционные переходы, FK+индексы, ретеншен, миграция alembic; pytest 21/21.
- CI гоняет pytest + vitest + build; Telegram-алёрты на сбои операций; замок параллельных операций.

## 🔨 Что не доделано / следующие шаги

- 🔴 **Полный цикл выдачи/возврата на ЖЕЛЕЗЕ не прогонялся** — подтверждены только хоминг + калибровка лотка. Захват полки (выдвижение лотка в ячейку, замок, cross-row) на реальной машине не проверен. Нужен сухой цикл под наблюдением. См. также вопрос move_tray ниже.
- 🟡 **Node/Express стек (`server/*.ts`) — мёртв** (python теперь прод), но ещё в активном дереве. Кандидат в `_attic/` + правка `package.json` build на vite-only. Используется только dev-стендом 5000 в docker-compose.
- 🟡 **`/api/rfid-readers`**: книжный ридер показывается `connected:False` (захардкожено) — косметика.
- 🟡 **NFC-ретрай в коде** — pcscd-daemon решил гонку старта, но ленивое переподключение NFC в опросе добавило бы устойчивости к переподключению ридера.
- 🟡 **ИРБИС с боевого шкафа не проверен**: сеть 172.29.67.70 из текущего сегмента недоступна; кодировка UTF-8 vs cp1251 не подтверждена. Ждёт доступа в библиотечную сеть.
- 🟢 **Безопасность**: авторизация — синглтон-сессия (current_user в auth_service), требует ревью; `HOST=127.0.0.1` уже выставлен (API не наружу). Старые Node-уязвимости уходят с ретайром server/.
- 🟢 Старт ~40с из-за двухэтапной калибровки лотка — можно ускорить осторожно (механика).
- Тач-плёнка не подключена; touch-калибровка — когда подключат панель.

## 📋 RPi-чеклист (итог сессии 2026-06-13)

- [x] **Забрать рабочие скрипты механики с устройства** — захвачены (bundle+tar), сведены в канон (PR #90).
- [x] Сверить задеплоенный код с репо — сверено; выложен main.
- [x] Состав считывателей — RRU9816(ttyUSB0)/IQRFID-5102(ttyUSB1)/ACR1281(PC/SC); порты в udev/config поправлены.
- [ ] **ИРБИС: реальное подключение + кодировка** — НЕ закрыто (сеть недоступна с шкафа).
- [ ] **Прогнать сухой цикл выдачи/возврата на железе** — НЕ сделано (нужен Роман у машины).
- [ ] **Проверить направление лотка** (см. move_tray ниже) во время сухого цикла.

### ⚠️ Вопрос: модель лотка `motors.move_tray` vs реальная кросс-рядная механика
Анализ (read-only, 2026-06-13):
- Направление подтверждено полевым `shelf_operations.py` (`tray_to_endstop`: `DIR=1→BACK`, `DIR=0→FRONT`).
- `motors.move_tray`: `extend → DIR=1` (=BACK), `retract → DIR=0` (=FRONT) — простая модель «выдвинул/задвинул».
- **НО реальный шкаф кросс-рядный:** `shelf_operations.py` гоняет лоток в FRONT или BACK как позиции
  передачи полки для ДВУХ рядов (front handoff / rear handoff), а не «extend/retract». Конкретные ходы
  (16800/12600 шагов к FRONT/BACK) зависят от ряда. Простая extend/retract-модель `move_tray` этому не соответствует.
- Следствие: бизнес-путь (`business/issue` → `mechanics/algorithms` → `motors.extend_tray/retract_tray`) для
  захвата полки, вероятно, НЕ совпадает с проверенной механикой. Проверенный захват — в `shelf_operations.py`
  (его использует workflows-путь через subprocess).
- **К сухому циклу:** прогонять через workflows-путь (shelf_operations), а бизнес-путь захвата полки на
  железе считать НЕ проверенным. Возможно, `mechanics/algorithms` нужно переориентировать на cross_operations_v2/
  shelf_operations вместо простого move_tray. Решать с Романом после наблюдения на машине.

### Решения Романа 2026-06-12 (исторически, все реализованы)
Pi 3; целевой бэкенд aiohttp (✅ выложен); RRU9816 нужен (✅ подключён); замки исправны;
ИРБИС 172.29.67.70 боевой; MOCK_MODE принимает 1/true/yes (✅).

## Опись репозитория (вердикты)

> ⚠️ Историческая — снимок ДО реорганизации (этап 1). Многое уже сделано: мёртвое в `_attic/`,
> `tools/` реорганизован, дубли `bookcabinet/tools/` убраны, attached_assets/sidecar/replit в `_attic/`.
> Актуальный остаток — `server/*.ts` (Node, кандидат в `_attic/`). Оставлено для контекста.

| Зона | Что это | Вердикт |
|---|---|---|
| `bookcabinet/` (business, workflows, mechanics, hardware, rfid, irbis, database, monitoring, server, services) | Python-ядро | 🟢 живое; `server/` (aiohttp) — параллельный незадеплоенный стек; `rfid/card_reader.py`, `rfid/book_reader.py` вытеснены `unified_card_reader.py` |
| `bookcabinet/tools/` (2 файла) | Копии из `tools/` | 🔴 **разошедшиеся дубли** (diff ≠ 0); прод использует корневой `tools/` (`workflows/_TOOLS_DIR`) |
| `bookcabinet/test_*.py` (5 шт. в корне пакета) | Ручная диагностика железа | 🟡 живые утилиты, место им в tools/diagnostics |
| `tools/` (37 скриптов) | Железные скрипты | 🟢 ядро: corexy_motion_v2, homing_pigpio, tray_platform, goto, calibration, position, book_sequences, shelf_operations, shutter, move_shelf, startup_*; 🟡 калибровочные эксперименты (calib_*, calibrate*, measure_bounds, move_diagonal, test_*); 🔴 устаревшие: corexy_pigpio.py, homing.py |
| `client/` + `shared/` + vite/tailwind/tsconfig | React-фронт | 🟢 живой; `pages/rfid-dashboard.tsx`, connection/log/tag-панели — наследие RFIDIntegrator, в киоске не используются |
| `server/` (TS) | Express — боевой сервер | 🟢 живой; `services/pcscService.ts`, `rfidService.ts`, `irbisService.ts`, `operationQueue.ts` — в основном вытеснены Python |
| `shared/schema.ts` + `drizzle.config.ts` | Drizzle/PostgreSQL | 🔴 не используется (только типы); БД-правда — SQLite в Python |
| `rru9816-sidecar/` | .NET-мост RRU9816 | 🔴 легаси, к питону не подключён |
| `bookcabinet/server/static/` | Закоммиченный билд фронта | 🟡 вероятно устаревший дубль `dist/public` |
| `attached_assets/` (~120 файлов, 11.6 МБ) | Вендорные DLL/.cs/.pas, скриншоты, пасты логов | 🔴 хлам/история; alias `@assets` кодом не используется |
| `automation repozitories .zip` | Набор для автоматизации репо | ❓ назначение неясно |
| `docs/` + корневые .md | Документация | 🟡 смешанная свежесть; ESP32_ARCHITECTURE.md — мертво; свежайшие: SOURCES_OF_TRUTH.md, SESSION_2026-04-16.md, DEVLOG, CHANGELOG |
| `deploy/`, `.github/` | systemd + CI | 🟢 живые |
| `.replit`, `replit.md` | Реплит-наследие | 🔴 история |

## Схема БД (SQLite, v2 — в main, выложена на шкаф 2026-06-13)

- `books`: rfid (uniq), title, author, isbn, **status по физике** (`in_cabinet`/`issued`/`awaiting_extraction`/`extracted`, CHECK: статус ↔ наличие cell_id), cell_id (FK, **уникальный** — две книги в ячейке невозможны), reserved_by (резерв — отдельное поле, не статус), issued_to/issued_at/due_date
- `cells`: только физика — row (FRONT/BACK), x, y, blocked. Состояние (`empty`/`occupied`/`blocked`, needs_extraction, book_rfid…) вычисляет представление **cells_view** — форма строк совместима с v1, читающий код не менялся
- `users`, `operations` (+индекс по timestamp), `system_logs` (+индекс), `settings`
- **Каждый переход физического мира — одна транзакция** вместе с журналом: `db.issue_book_tx / return_book_tx / load_book_tx / extract_book_tx`; FOREIGN KEY включены
- Ретеншен: system_logs 90 дн., operations 365 дн. (`db.cleanup_old_logs()`, вызывается на старте aiohttp)
- Мок-данные сеются **только при MOCK_MODE** (раньше тестовые карты, включая админскую ADMIN99, попадали и в боевую БД)
- `PRAGMA user_version=2`: v2-код отказывается работать со старой схемой; **деплой на шкаф: бэкап → `alembic upgrade head`** (миграция `0002_schema_v2` переносит данные со сверкой связей, покрыта тестом)
- Тесты: `bookcabinet/tests/test_database_v2.py` — 9 интеграционных на реальном SQLite (жизненный цикл, атомарность/откаты, инварианты схемы, миграция 0001→0002 через alembic)

### ~~Известный gap~~ — закрыт (этап 3, 2026-06-12)

Причиной падения бизнес-пути в моке был не мок датчиков, а **боевой баг колбэков**:
`algorithms._emit_progress` делал `await` на результате колбэка, а bridge передаёт
синхронный — TypeError после первого же события (на Pi бизнес-путь через bridge
падал так же; вероятно, поэтому прод ушёл на issue_sequence). Исправлено
(`_call_cb` принимает sync и async). Полные циклы issue/return в моке проходят.

## Этап 3 (web-aiohttp) — статус

Сделано (ветка feature/web-aiohttp):
- Паритет API с Express под фактические вызовы киоска: `/api/book/issue`,
  `/api/book/return` (c WS-событиями operation_started/completed/failed и
  прогрессом в «механической шкале» киоска — транслятор `_KioskProgress`),
  `/api/books`, `/api/users`, `/api/rfid-readers`; camelCase-алиасы полей.
- `web_server.py` отдаёт свежий vite-билд `dist/public` (фоллбек — старый static/).
- Два стенда в docker-compose: 5000 Express (как на шкафу), 5001 aiohttp (целевой).
- vite proxy `/api`+`/ws` для HMR-разработки против python-бэкенда.
- E2E через aiohttp проверен: auth → issue → WS-прогресс 1–13 с таймером шторки → completed.

Сделано в части 2 (2026-06-12):
- Паритет админ-экранов: `/api/calibration/wizard/*` (алиасы на /api/wizard/*),
  blocked-cells/quick-test, `/api/auth/logout`, `/api/emergency-stop`,
  `/api/shutter/close-all`, `/api/maintenance` (хранится в settings, отражается
  в /api/status), `/api/test/tray`, `/api/test/servo`,
  `/api/calibration/test-suite` и `/api/calibration/test/{name}` (честные прогоны
  motors/tray/locks/shutters/sensors с длительностями). Всё проверено через
  докер-стенд 5001 с авторизацией ADMIN99.
- Чистка клиента: страница `/rfid` + 3 панели → `_attic/`; 33 из 47 ui-компонентов
  (транзитивный анализ) → `_attic/`; 39 мёртвых зависимостей + drizzle-kit/db:push +
  drizzle.config.ts убраны (~80 → 28 пакетов, −102 пакета в node_modules;
  бандл: index 193→168 КБ, radix 115→97 КБ).

Сделано в части 3 (2026-06-12):
- kiosk.tsx 2372 → 871 строка: 9 экранов в `components/kiosk/screens/*`;
  admin.tsx 590 → ~110: вкладки в `components/admin/*`. Смоук puppeteer на живом стенде.
- Замок параллельных операций (`with_mech_lock`): двойной клик «выдать» больше
  не запускает второй механический цикл — 409 «Шкаф занят» (проверено).
- CI гоняет pytest + vitest + build (раньше — только синтаксис).
- Деплой-пакет для Pi: `deploy/migrate.sh` (бэкап → alembic → рестарт → проверка),
  install.sh больше не мигрирует без бэкапа и не глотает ошибки,
  `HOST=127.0.0.1` в юнитах (киоск локальный; 0.0.0.0 открывал бы API сети
  с синглтон-авторизацией), подготовлен `deploy/bookcabinet-api.service`
  (python-бэкенд, инструкция переключения в шапке юнита).
- Telegram-алёрты на сбои выдачи/возврата и аварийный стоп (`_alert` в api_routes).

Осталось:
- SSE `/api/rfid-test/{readerId}` (консоль RFID-теста в админке) — пока только на Express.
- Снять Express с прода (после проверки на Pi): переключить юнит на bookcabinet-api.service, Node — в `_attic/`.
- Auth/sessions: в aiohttp та же синглтон-модель, что в Express (current_user в auth_service); для локального киоска достаточно, но требует ревью на этапе безопасности.
