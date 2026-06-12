# Разработка на Windows-ноутбуке (мок-режим)

Цель: тестировать экраны и логику (читатель / библиотекарь / админ) без шкафа и железа.
Проверено 2026-06-12 на Windows 11, Node 22, Python 3.14, Docker Desktop 27.

## Вариант 1 — Docker (рекомендуется)

```powershell
docker compose -f docker-compose.dev.yml up --build -d
```

Поднимаются **два стенда** с одним и тем же UI:

| Порт | Бэкенд | Что это |
|---|---|---|
| **http://localhost:5000** | Node Express + bridge | как сейчас на шкафу (боевой) |
| **http://localhost:5001** | Python aiohttp | целевой бэкенд (решение 2026-06-12); выдача/возврат идут через настоящий business-слой и БД v2, механика в моке |

Админка: `/admin` на обоих. На 5001 клиент собирается при старте контейнера (~1 мин).

- Node + Python собраны в один образ (`Dockerfile.dev`), все мок-переменные уже выставлены.
- Исходники `client/`, `server/`, `shared/`, `bookcabinet/`, `tools/` примонтированы:
  правки клиента подхватываются на лету (vite HMR), правки сервера — `docker compose -f docker-compose.dev.yml restart`.
- Сброс тестовых данных: `docker compose -f docker-compose.dev.yml down -v && docker compose -f docker-compose.dev.yml up -d`.
- Логи: `docker compose -f docker-compose.dev.yml logs -f`.

## Вариант 2 — нативно (npm + venv)

### Установка (один раз)

```powershell
npm install
py -3 -m venv .venv
.venv\Scripts\python -m pip install aiohttp alembic pytest pyserial
```

### Запуск aiohttp-стенда нативно

```powershell
npm run build   # собрать клиент в dist/public (aiohttp отдаёт его сам)
$env:PYTHONIOENCODING='utf-8'; $env:MOCK_MODE='true'; $env:IRBIS_MOCK='true'
$env:DATABASE_PATH="$PWD\.local-dev\shelf_data.db"; $env:PORT='5001'; $env:HOST='127.0.0.1'
.venv\Scripts\python -m bookcabinet.main
```

Для живой правки клиента против python-бэкенда: `npx vite` (порт 5173, HMR) —
vite проксирует `/api` и `/ws` на `VITE_API_TARGET` (по умолчанию http://localhost:5000;
для aiohttp: `$env:VITE_API_TARGET='http://localhost:5001'`).

### Запуск

```powershell
$env:MOCK_MODE = 'true'
$env:IRBIS_MOCK = 'true'
$env:DATABASE_PATH = "$PWD\.local-dev\shelf_data.db"   # папка создастся при первом запуске тестов; можно создать руками
$env:PYTHON_BIN = "$PWD\.venv\Scripts\python.exe"
npm run dev
```

Открыть **http://localhost:5000** — киоск. `http://localhost:5000/admin` — админка.
Сервер в dev-режиме слушает только 127.0.0.1.

## Тестовые карты

На экране приветствия есть тестовые кнопки (эмуляция прикладывания карты):

| Карта | Кто | Роль |
|---|---|---|
| CARD001 | Иванов И.И. (зарезервирована «Война и мир») | читатель |
| CARD002 | Петрова М.С. | читатель |
| ADMIN01 | Козлова А.В. | библиотекарь |
| ADMIN99 | Администратор | админ |

## Что работает в моке

- Все экраны киоска и админки, авторизация по тестовым картам, таймаут сессии.
- **Выдача и возврат целиком**: Express → `bridge.py` → имитация механической
  последовательности (14 шагов с прогрессом по WebSocket, `_mock_sequence` в
  `bookcabinet/bridge.py`) → успех. Шторка «открыта» 10 секунд.
- Экраны библиотекаря (загрузка/изъятие/инвентарь) и админа (дашборд, диагностика — частично).
- Тесты: `npm test` (vitest 13) и
  `$env:DATABASE_PATH="$PWD\.local-dev\shelf_data.db"; $env:MOCK_MODE='true'; .venv\Scripts\python -m pytest bookcabinet/tests/ -q` (pytest 10).

## Ограничения мока

- RFID-считыватели не опрашиваются — карты только тестовыми кнопками.
- Механика имитируется на уровне bridge (скрипты `tools/*.py` мок не поддерживают и на ноутбуке не вызываются).
- Витрина Node-сервера живёт в `data/storage.json` (это НЕ боевая БД шкафа);
  сброс данных = удалить `data/storage.json` и `.local-dev/shelf_data.db`, перезапустить.
- ИРБИС — мок (`bookcabinet/irbis/mock.py`).
- Эндпоинты, дергающие `sudo`/GPIO напрямую (`/api/shutter/*` и т.п.), на Windows вернут ошибку — это ожидаемо.

## Если порт 5000 занят после аварийного завершения

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen | % { Stop-Process -Id $_.OwningProcess -Force }
```
