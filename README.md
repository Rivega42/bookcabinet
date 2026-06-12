# BookCabinet

Автоматизированный библиотечный шкаф на Raspberry Pi 3.
RFID/NFC идентификация, CoreXY механика, интеграция с ИРБИС.

## Что это

Физический шкаф с 126 ячейками, управляемый через веб-интерфейс. Читатель прикладывает карту, система идентифицирует, выдаёт/принимает книги механически.

- **Железо:** RPi 3B, CoreXY XY, stepper tray, servo locks, NFC + UHF readers
- **Бэкенд:** Python (aiohttp) + Node.js (Express) через subprocess bridge
- **Фронтенд:** React + TypeScript + Tailwind (ЧБ-тема для outdoor kiosk)
- **Библиотечная система:** ИРБИС64 (TCP :6666)

## Quick Start

Разработка:
```bash
git clone https://github.com/Rivega42/-.git bookcabinet
cd bookcabinet
npm install
cp .env.example .env
MOCK_MODE=true npm run dev
```

Продакшен на RPi:
```bash
sudo bash deploy/install.sh
sudo reboot
```

Подробно — см. [docs/QUICKSTART.md](docs/QUICKSTART.md). Windows-ноутбук без железа — [docs/DEV_WINDOWS.md](docs/DEV_WINDOWS.md).

## Архитектура

См. [CLAUDE.md](CLAUDE.md) — канонический project brief.

## Документация

| Файл | Назначение |
|------|-----------|
| [CLAUDE.md](CLAUDE.md) | Канонический project context для AI и разработчиков |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Быстрый старт и базовые команды |
| [docs/STATE.md](docs/STATE.md) | Состояние проекта: что работает / не доделано / решения |
| [docs/API.md](docs/API.md) | REST/WebSocket API |
| [docs/HARDWARE.md](docs/HARDWARE.md) | GPIO карта, железо |
| [docs/DISASTER_RECOVERY.md](docs/DISASTER_RECOVERY.md) | Аварийные процедуры |
| [docs/SOURCES_OF_TRUTH.md](docs/SOURCES_OF_TRUTH.md) | Авторитетные источники |
| [docs/RFID_READERS.md](docs/RFID_READERS.md) | RFID устройства |
| [docs/IRBIS_INTEGRATION.md](docs/IRBIS_INTEGRATION.md) | Интеграция с ИРБИС |
| [docs/DEVLOG.md](docs/DEVLOG.md) | Журнал разработки |
| [docs/TODO.md](docs/TODO.md) | Текущие задачи |

## Разработка

См. [CONTRIBUTING.md](CONTRIBUTING.md).

## Issues

- [Открытые](https://github.com/Rivega42/-/issues) — бэклог
- Закрытые: ревью + исправления 2026-04

## Лицензия

MIT
