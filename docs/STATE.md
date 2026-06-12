# BookCabinet — Состояние проекта

> Аудит кода 2026-06-12 (только чтение). Что работает / что не доделано / что под вопросом.
> Аппаратные факты — в `docs/HARDWARE.md`. Исторические решения — `docs/DECISIONS.md`, `docs/DEVLOG.md`, `docs/SOURCES_OF_TRUTH.md`.

## Как система реально устроена (боевая цепочка)

```
pigpiod
  → bookcabinet-calibration.service  (oneshot: tools/startup_calibration.py — замки в нейтраль, хоминг XY, калибровка лотка)
  → bookcabinet-daemon.service       (bookcabinet/services/auth_shutter_daemon.py — опрос NFC+UHF карт, автошторка 30с)
  → bookcabinet-ui.service           (node dist/index.js — Express, порт 5000, ОСНОВНОЙ сервер)
  → chromium-kiosk.service           (киоск на http://localhost:5000)
```

- **Боевой сервер — Node/Express** (`server/routes.ts`, ~100 эндпоинтов + WebSocket). Он вызывает Python субпроцессом: `python3 -m bookcabinet.bridge <команда>` → `business/*` или `workflows/*` → `tools/*.py`.
- **Python aiohttp-сервер (`bookcabinet/main.py`, ~60 эндпоинтов) ни одним systemd-юнитом не запускается.** Это параллельная, более новая реализация всего API. **Решение 2026-06-12: он — целевой; Express доживает до миграции.**
- Фронтенд: React (client/), сборка vite → `dist/public/`. В `bookcabinet/server/static/` закоммичен ещё один (вероятно устаревший) билд для aiohttp.
- БД: **SQLite** `bookcabinet/data/shelf_data.db` (WAL), схема в `bookcabinet/database/db.py` — единственный источник правды. Drizzle/PostgreSQL-схема (`shared/schema.ts`) кодом не используется (Node-сторона держит состояние в памяти + `data/storage.json`).

## Цикл выдачи (как написан в коде)

Два слоя реализации:

1. **`business/issue.py` / `business/return_book.py`** — стейт-машины над БД:
   - Выдача: VALIDATE → TAKE_SHELF → WAIT_USER → GIVE_SHELF → UPDATE_DB → CALL_IRBIS → DONE; механика через `mechanics/algorithms.py` (take_shelf/give_shelf: Г-образный путь, двухэтапный захват полки лотком+замком, шторки), при ошибке `_safe_recover()`; БД обновляется только после успешной механики.
   - Возврат: VALIDATE → FIND_CELL (первая пустая) → GIVE_SHELF → UPDATE_DB (`needs_extraction=True`) → CALL_IRBIS → DONE.
2. **`workflows/issue.py` / `workflows/return_book.py`** — боевые 18/19-шаговые сценарии (issues #79/#80): субпроцессы к `tools/goto.py`, `tools/shelf_operations.py`, `tools/shutter.py`, проверка RFID книги на шаге 7, таймауты (шторка 15с, забор книги 30с, возврат 60с, retry при несовпадении RFID 61с). Вызываются из Node через `bridge.py`.

ИРБИС при выдаче/возврате: запись в поле 40 RDR + статус экземпляра 910^A; при недоступности — офлайн-очередь `irbis/sync_queue.py`.

## ✅ Что работает (подтверждено кодом и журналами сессий)

- Хоминг XY к LEFT+BOTTOM на живом шкафу (2026-04-10, 2026-04-16), движение к ячейкам по формуле calibration.json (проверены 1.1.9, 1.2.9, 2.1.9).
- Канонический слой движения `tools/corexy_motion_v2.py`: wave_chain, glitch-фильтры, стабильное детектирование концевиков, таймауты.
- Калибровка: calibration.json v2026-04-27 с реальными измерениями (стойки X, якоря Y, лоток).
- Опрос карт: ACR1281U-C (NFC) + IQRFID-5102 (UHF ЕКП) через `unified_card_reader`, debounce, нормализация UID.
- ИРБИС-клиент: полный TCP-протокол, поиск читателя по карте и книги по `IN=` подтверждён реальными данными 14.04.2026; мок-режим; офлайн-очередь.
- Киоск-UI: стейт-машина из 14 экранов (читатель/библиотекарь/админ), WebSocket-прогресс, автологаут 60с.
- БД-слой: 6 таблиц, инициализация 126 ячеек, журнал операций, бэкапы (`monitoring/backup.py`).
- Деплой: цепочка systemd-юнитов + chromium-киоск.

## 🔨 Что не доделано

- **RRU9816 (метки книг) не подключён к живому опросу** — драйвер `hardware/rru9816_driver.py` написан и протестирован, но `main.py`/daemon его не инстанцируют. Шаг «проверка RFID книги» в workflows зависит от него.
- **Двоевластие бэкендов**: Node Express (прод) и Python aiohttp (полный, но не задеплоенный). Логика выдачи существует в 2 вариантах (business/ и workflows/), эндпоинты дублируются (`/api/issue` vs `/api/book/issue`).
- **Мок-режим дырявый**:
  - `MOCK_MODE` принимается только как `true`; `.env.example` советует `MOCK_MODE=1`, который код НЕ понимает;
  - `tools/*.py` про мок не знают вообще — workflows/bridge на машине с pigpiod будут крутить реальное железо при любом MOCK_MODE.
- **ИРБИС не проверен с реального шкафа**: креды только из env, кодировка UTF-8 vs cp1251 не подтверждена, сетевая доступность 172.29.67.70 из библиотечной сети под вопросом.
- **Безопасность** (CODE_REVIEW.md, 2026-04-10): SQL-инъекция в db.py, RCE через spawn() в Node-роутах, отсутствие auth-middleware на части эндпоинтов, `throw err` роняет сервер, хардкод путей `/home/admin42/...`.
- **Тесты почти отсутствуют**: CI — только tsc и py_compile; vitest покрывает 2 киоск-компонента; pytest-тесты есть (`bookcabinet/tests/`), в CI не запускаются.
- **Таймауты из config не применяются** в `hardware/motors.py` (move/tray); нет детекции застрявшего мотора; границы поля не проверяются.
- Железо: LOCK_FRONT сломан; GPIO 20 шумит (#41); серво-PWM роняет шторку (#40).

## ✅ Решения (ответы Романа, 2026-06-12)

- **Платформа: Raspberry Pi 3** (упоминания Pi 4 — ошибочны).
- **Целевой бэкенд: Python aiohttp** (`bookcabinet/main.py`); Node Express остаётся боевым до проверенной миграции, затем — в `_attic/`. Решение делегировано и принято по итогам ревизии (аргументы: subprocess-спавн python3 на каждую операцию включая аварийный стоп, дублирование состояния и схемы, RAM Pi 3).
- **RRU9816 нужен в проде** — подключить питоновский драйвер в живой опрос; sidecar — легаси.
- **Замки исправны** — пометки «BROKEN» в calibration.json устарели.
- **ИРБИС `172.29.67.70:6666` — боевой**, тестового контура нет.
- `automation repozitories .zip` — назначение Роману неизвестно → `_attic/`.
- MOCK-режим: оставить имя `MOCK_MODE`, научить код принимать `1/true/yes`, починить `.env.example` (решение делегировано).

## 📋 К проверке при доступе к RPi

- [ ] **Забрать с устройства рабочие скрипты механики** — по словам Романа, на RPi есть вполне рабочие скрипты управления механикой, которых нет/которые новее, чем в репо. До сверки считать репо-версии tools/* потенциально отстающими.
- [ ] Сверить вообще задеплоенный код с репо (diff /home/admin42/bookcabinet ↔ git).
- [ ] Состав считывателей: физически «2 одинаковых + 1 другой» (Роман) — сверить модели и порты с config.py/udev.
- [ ] ИРБИС: реальное подключение, кодировка (client.py шлёт UTF-8, доки говорят cp1251).
- [ ] Обновить calibration.json: статусы замков, back_y_offset-противоречие.
- [ ] Проверить glitch-фильтр 5000 мкс на GPIO 20 (#41) — внедрён ли на устройстве.

## Опись репозитория (вердикты)

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

## Схема БД (SQLite, v2 — 2026-06-12, ветка feature/db-v2)

- `books`: rfid (uniq), title, author, isbn, **status по физике** (`in_cabinet`/`issued`/`awaiting_extraction`/`extracted`, CHECK: статус ↔ наличие cell_id), cell_id (FK, **уникальный** — две книги в ячейке невозможны), reserved_by (резерв — отдельное поле, не статус), issued_to/issued_at/due_date
- `cells`: только физика — row (FRONT/BACK), x, y, blocked. Состояние (`empty`/`occupied`/`blocked`, needs_extraction, book_rfid…) вычисляет представление **cells_view** — форма строк совместима с v1, читающий код не менялся
- `users`, `operations` (+индекс по timestamp), `system_logs` (+индекс), `settings`
- **Каждый переход физического мира — одна транзакция** вместе с журналом: `db.issue_book_tx / return_book_tx / load_book_tx / extract_book_tx`; FOREIGN KEY включены
- Ретеншен: system_logs 90 дн., operations 365 дн. (`db.cleanup_old_logs()`, вызывается на старте aiohttp)
- Мок-данные сеются **только при MOCK_MODE** (раньше тестовые карты, включая админскую ADMIN99, попадали и в боевую БД)
- `PRAGMA user_version=2`: v2-код отказывается работать со старой схемой; **деплой на шкаф: бэкап → `alembic upgrade head`** (миграция `0002_schema_v2` переносит данные со сверкой связей, покрыта тестом)
- Тесты: `bookcabinet/tests/test_database_v2.py` — 9 интеграционных на реальном SQLite (жизненный цикл, атомарность/откаты, инварианты схемы, миграция 0001→0002 через alembic)

### Известный gap (для этапа 3)

`mechanics/algorithms` в MOCK_MODE не проходит `take_shelf` («Проверка лотка» — мок датчиков неполон), поэтому бизнес-путь `bridge issue/return` в моке падает на механике; UI ходит через `_mock_sequence` в bridge.py. При консолидации на aiohttp мок надо доделать на уровне algorithms/sensors.
