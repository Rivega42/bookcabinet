# RFID Library Self-Service Kiosk (BookCabinet)

**GitHub:** https://github.com/Rivega42/-

## Overview
Система автоматизированной книговыдачи для библиотек на базе Raspberry Pi 4. Управляет шкафом с 126 ячейками (2 ряда × 3 колонки × 21 позиция), поддерживает три роли пользователей (читатель, библиотекарь, администратор), интеграцию RFID для книг (IQRFID-5102) и читательских билетов (ACR1281U-C), mock-интеграцию с IRBIS64.

## User Preferences
Preferred communication style: Simple, everyday language (Русский).

## System Architecture

### Компоненты Python (bookcabinet/)

**Механика (mechanics/):**
- `algorithms.py` - Алгоритмы INIT/TAKE/GIVE с реальным path planning
- `corexy.py` - CoreXY кинематика с расчётом траекторий для 126 ячеек
- `calibration.py` - Калибровочные данные позиций X/Y

**Оборудование (hardware/):**
- `motors.py` - Шаговые моторы CoreXY + лоток
- `servos.py` - Сервоприводы замков
- `shutters.py` - Шторки (внутренняя/внешняя)
- `sensors.py` - Датчики TCST2103 с проверкой концевиков
- `gpio_manager.py` - Управление GPIO через pigpio

**RFID (rfid/):**
- `card_reader.py` - ACR1281U-C для читательских билетов (PC/SC)
- `book_reader.py` - IQRFID-5102 для RFID-меток книг (Serial)

**Бизнес-логика (business/):**
- `auth.py` - Аутентификация с проверкой ролей
- `issue.py` - Выдача книг читателю
- `return_book.py` - Возврат книг
- `load.py` - Загрузка книг (библиотекарь)
- `unload.py` - Изъятие книг

**Сервер (server/):**
- `web_server.py` - aiohttp веб-сервер
- `api_routes.py` - REST API (30+ endpoints)
- `websocket_handler.py` - WebSocket для real-time
- `static/` - Touch-оптимизированный UI 1920×1080

**Мониторинг (monitoring/):**
- `telegram.py` - Уведомления через Telegram Bot API
- `backup.py` - Резервное копирование с ротацией
- `watchdog.py` - Мониторинг состояния (motors, sensors, rfid, database, websocket)

### WebSocket команды

| Action | Commands | Описание |
|--------|----------|----------|
| `motor` | move_xy, move_relative, extend_tray, retract_tray, stop, home, get_position, get_sensors | Управление моторами |
| `servo` | open, close | Управление замками (lock1, lock2) |
| `shutter` | open, close | Управление шторками (inner, outer) |

### Watchdog сервис

Проверяет компоненты каждые 60 секунд:
- motors, sensors, rfid_card, rfid_book, database, websocket
- Порог ошибок: 3 последовательных сбоя
- Интеграция с systemd через NOTIFY_SOCKET

### Роли пользователей

| Роль | Возможности |
|------|-------------|
| **Читатель** | Забрать забронированные книги, вернуть книги |
| **Библиотекарь** | Загрузка книг, изъятие возвращённых, просмотр ячеек, инвентаризация, журнал операций |
| **Администратор** | Все функции + калибровка CoreXY, диагностика оборудования, настройки системы, backup |

### API Endpoints

| Endpoint | Описание |
|----------|----------|
| `POST /api/auth/card` | Авторизация по читательскому билету |
| `POST /api/issue` | Выдача книги читателю |
| `POST /api/return` | Возврат книги |
| `POST /api/load-book` | Загрузка книги в шкаф |
| `POST /api/extract` | Изъятие книги из ячейки |
| `POST /api/extract-all` | Изъятие всех возвращённых книг |
| `POST /api/run-inventory` | Запуск инвентаризации |
| `GET/POST /api/calibration` | Калибровка позиций |
| `GET /api/calibration/export` | Экспорт калибровки JSON |
| `POST /api/calibration/import` | Импорт калибровки JSON |
| `POST /api/calibration/reset` | Сброс калибровки |
| `GET/POST /api/blocked-cells` | Управление заблокированными ячейками |
| `GET /api/diagnostics` | Диагностика оборудования |
| `GET/POST /api/settings` | Настройки системы |
| `POST /api/backup/create` | Создание бэкапа |
| `POST /api/test/*` | Тестирование компонентов |
| `POST /api/quick-test` | Быстрый тест ячейки |

### Calibration Wizard API

| Endpoint | Описание |
|----------|----------|
| `POST /api/wizard/kinematics/start` | Запуск wizard кинематики CoreXY |
| `POST /api/wizard/kinematics/step` | Шаг теста кинематики (action: run/response) |
| `POST /api/wizard/points10/start` | Запуск калибровки 10 точек |
| `POST /api/wizard/points10/save` | Сохранение текущей точки |
| `POST /api/wizard/move` | Движение каретки (direction: WASD, stepIndex) |
| `POST /api/wizard/grab/start` | Запуск калибровки захвата (side: front/back) |
| `POST /api/wizard/grab/adjust` | Регулировка параметра (param, delta) |
| `POST /api/wizard/grab/test` | Тест параметра захвата |

### CalibrationData v2.1 Structure

```json
{
  "version": "2.1",
  "timestamp": "ISO datetime",
  "kinematics": { "x_plus_dir_a": ±1, "x_plus_dir_b": ±1, "y_plus_dir_a": ±1, "y_plus_dir_b": ±1 },
  "positions": { "x": [3 cols], "y": [21 rows] },
  "grab_front": { "extend1": ms, "retract": ms, "extend2": ms },
  "grab_back": { "extend1": ms, "retract": ms, "extend2": ms },
  "speeds": { "xy": steps/s, "tray": steps/s, "acceleration": steps/s² },
  "servos": { "lock1_open": deg, "lock1_close": deg, "lock2_open": deg, "lock2_close": deg },
  "tray": { "extend_steps": int, "retract_steps": int },
  "blocked_cells": { "front": { "col": [rows] }, "back": { "col": [rows] } }
}
```

### Path Planning

PathPlanner класс реализует:
- Расчёт координат для 126 ячеек (positions_x, positions_y)
- L-образный путь (сначала Y, потом X) для избежания диагональных движений
- Промежуточные точки каждые 2000 шагов для больших перемещений
- MAX_DIAGONAL_STEP = 500 для определения прямых перемещений
- estimate_time() с учётом пути и параллельного движения CoreXY осей

### Инвентаризация

**run_inventory()** - полная инвентаризация с RFID сканированием:
- Обход всех ячеек: take_shelf → RFID inventory → give_shelf
- Статусы: ok, missing, mismatch, unexpected
- Метаданные RFID: antenna_id, num_tags, rssi_dbm для каждого тега
- Возвращает полный массив results без обрезки

**run_quick_inventory()** - быстрая инвентаризация без RFID:
- Только проверка статусов в базе данных
- Подсчёт: found, empty, needs_extraction

### Валидация калибровки

**validate()** проверяет:
- positions.x: 3 колонки, отсортированные, >= 0
- positions.y: 21 ряд, отсортированные, >= 0
- kinematics: все направления ±1
- speeds: xy/tray (1-10000), acceleration (1-20000)
- servos: углы 0-180°
- grab_front/back: обязательные ключи extend1/retract/extend2 (0-10000)

**update_with_validation()** мержит данные и сохраняет только при valid=True

### Безопасность датчиков

**_safe_move_xy()** - проверка всех 4 концевиков:
- Перед движением: x_begin/x_end, y_begin/y_end в зависимости от направления
- После движения: проверка неожиданных срабатываний
- motors.stop() + _emit_error() при любой ошибке

**_safe_tray_extend/retract()** - проверка датчиков лотка:
- Проверка начального состояния
- 300мс стабилизация после движения
- Верификация конечной позиции

### IRBIS64 интеграция

**Модули (irbis/):**
- `client.py` - Полноценный TCP клиент ИРБИС64 (команды A/B/C/D/K/G)
- `mock.py` - Mock реализация с правильной структурой полей ИРБИС
- `service.py` - LibraryService с автоматическим переключением mock/real

**Конфигурация (config.py):**
```python
IRBIS = {
    'host': '192.168.1.100',
    'port': 6666,
    'username': 'MASTER',
    'password': 'MASTERKEY',
    'database': 'IBIS',
    'readers_database': 'RDR',
    'loan_days': 30,
    'location_code': '09',
    'mock': True,  # IRBIS_MOCK=true для тестирования
}
```

**Структура полей ИРБИС:**
- RDR (читатели): 10=ФИО (^A^B^G), 30=UID карты, 40=выдачи (^A^B^C^D^E^F^H...), 50=категория
- IBIS (книги): 200=название (^A), 700=автор (^A^B^G), 903=шифр, 910=экземпляры (^a^b^c^d^h)

**Индексы поиска:**
- RI= (читатель по UID), EKP= (Единая карта петербуржца)
- H= / HI= (книга по RFID), HIN= (книга выданная читателю)

**Helper функции (utils/irbis_helpers.py):**
- `normalize_rfid()` - нормализация RFID в единый HEX формат
- `make_uid_variants()` - генерация вариантов UID для поиска
- `parse_subfields()` / `format_subfields()` - работа с подполями ^A^B
- `find_exemplar_by_rfid()` - поиск экземпляра в поле 910

### Role-Based Access Control

API endpoints защищены role_check():
- `librarian/admin`: load-book, extract, extract-all, run-inventory
- `admin only`: calibration/*, settings, test/*, backup/*

### Telegram уведомления

- Запуск/остановка системы
- Ошибки и критические события
- Статус ИРБИС
- Заполненность шкафа
- Необходимость изъятия книг

### Резервное копирование

- Автоматическое по расписанию (systemd timer)
- Ротация: 30 дней или 50 бэкапов max
- Включает: база данных + calibration.json
- Метаданные каждого бэкапа

## Развёртывание на Raspberry Pi

```bash
sudo bash bookcabinet/install_raspberry.sh
```

Скрипт настраивает:
- pigpiod, pcscd autostart
- udev правила для RFID (072f:2200)
- Serial порты (UART enabled, console disabled)
- systemd сервисы (bookcabinet, backup timer)
- calibration.json по умолчанию

## Структура проекта

```
/bookcabinet                  # Python backend
  /hardware                   # GPIO, моторы, датчики
  /mechanics                  # Алгоритмы, CoreXY, калибровка
  /rfid                       # Card/Book readers
  /irbis                      # IRBIS64 TCP client + mock
  /utils                      # Helpers (irbis_helpers.py)
  /business                   # Бизнес-логика
  /database                   # SQLite
  /server                     # aiohttp + static UI
  /monitoring                 # Telegram, backup
  main.py                     # Entry point
  config.py                   # Конфигурация
  install_raspberry.sh        # Установка
```

## Design Decisions
- **Python + aiohttp** для async операций с оборудованием
- **SQLite** для локального хранения (126 ячеек, операции, логи)
- **Mock режим** для разработки без Raspberry Pi
- **PathPlanner** для реального планирования траекторий CoreXY
- **WebSocket** для real-time обновлений UI

## External Dependencies
- Python 3.9+, aiohttp
- pigpio (GPIO), pyscard (PC/SC), pyserial
- SQLite3
