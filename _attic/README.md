# _attic — чердак

Сюда перемещается (НЕ удаляется) всё мёртвое и легаси при реорганизации репозитория
(ветка refactor/structure, 2026-06-12). Структура внутри повторяет исходные пути.

Правило проекта: отладочные/калибровочные скрипты не удалять, пока их знания
не перенесены в доки. Если что-то отсюда снова понадобилось — возвращать через PR.

| Что | Откуда | Почему здесь |
|---|---|---|
| `attached_assets/` | корень | вендорные DLL/.cs/.pas для RRU9816 (Windows), пасты логов 2025-09, скриншоты; alias `@assets` кодом не использовался |
| `automation repozitories .zip` | корень | назначение неизвестно (Роман, 2026-06-12) |
| `.replit`, `replit.md` | корень | наследие Replit-разработки |
| `rru9816-sidecar/` | корень | .NET-мост RRU9816 для старого Node-стека (ws://:8081); целевое решение — питоновский `bookcabinet/hardware/rru9816_driver.py` |
| `docs/ESP32_ARCHITECTURE.md` | docs/ | ESP32 в проекте не используется |
| `tools/corexy_pigpio.py` | tools/ | устаревший слой движения (эпоха RIGHT+BOTTOM); вытеснен corexy_motion_v2.py |
| `tools/homing.py` | tools/ | легаси-хоминг; актуален homing_pigpio.py |
| `tools/calibrate_xy.py`, `tools/calib_4endstops.py`, `tools/calib_racks.py` | tools/ | импортируют устаревший corexy_pigpio |
| `tools/measure_bounds.py` | tools/ | эпоха RPi.GPIO (до pigpio) |
| `bookcabinet/test_sensors.py` | bookcabinet/ | эпоха RPi.GPIO (до pigpio); актуален tools/diagnostics/test_sensors.py |
| `bookcabinet/tools/` | bookcabinet/ | разошедшиеся дубли корневого tools/ (diff ≠ 0); прод использует корневой tools/ (workflows/_TOOLS_DIR) |
| `client/pages/rfid-dashboard.tsx` | client/src/pages/ | страница /rfid эпохи RFIDIntegrator, в киоск-флоу не использовалась |
| `client/components/{connection,log,tag-data}-panel.tsx` | client/src/components/ | панели страницы /rfid |
| `client/ui/` (33 компонента) | client/src/components/ui/ | shadcn-компоненты, не используемые транзитивно (этап 3, 2026-06-12) |
| `drizzle.config.ts` | корень | PostgreSQL/drizzle-kit не используются (БД — SQLite в Python) |

⚠️ Перед окончательным удалением чего-либо отсюда — сверить с RPi: по словам Романа,
на устройстве есть рабочие скрипты механики, которых нет/которые новее, чем в репо.
