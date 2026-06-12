# tools/ — скрипты железа

⚠️ Эти скрипты НЕ поддерживают мок-режим: на машине с pigpiod они двигают реальное железо.
Железные правила — в корневом CLAUDE.md. Перед любым движением: разрешение в сессии, хоминг, таймаут.

## Живое ядро (используется продом)

| Скрипт | Назначение | Кто вызывает |
|---|---|---|
| corexy_motion_v2.py | канонический слой XY-движения (wave_chain, концевики, хоминг) | motors.py, goto.py, startup_sequence.py |
| homing_pigpio.py | операторская обёртка хоминга | вручную |
| tray_platform.py | калибровка/движение лотка | вручную, startup |
| goto.py | движение к адресу ячейки без повторного хоминга | workflows, move_shelf.py |
| calibration.py | резолвер адресов depth.rack.shelf → шаги (читает calibration.json) | goto.py, book_sequences.py |
| position.py | персистенция позиции каретки (/tmp/carriage_pos.json) | goto.py, book_sequences.py |
| book_sequences.py | полные последовательности выдачи/возврата | bridge.py |
| shelf_operations.py | захват/возврат полки (front/rear) | workflows, move_shelf.py |
| shutter.py | управление шторками | workflows |
| move_shelf.py | высокоуровневый перенос полки (goto + shelf_operations) | вручную |
| startup_sequence.py | хоминг XY + калибровка лотка | вручную |
| startup_calibration.py | стартовая калибровка | systemd bookcabinet-calibration.service |
| calibrate.py / calibrate_all.py | калибровочные мастера (актуальный слой движения) | вручную |

## diagnostics/

Ручные диагностические утилиты (моторы, датчики, шторки, замки, GPIO, RFID-протоколы).
Запуск только на RPi по согласованию. Сюда же перенесены бывшие bookcabinet/test_*.py.

## Куда делось остальное

Устаревшие скрипты (эпоха corexy_pigpio/RIGHT+BOTTOM, RPi.GPIO) — в `_attic/tools/`, см. `_attic/README.md`.
⚠️ На RPi могут лежать более свежие рабочие версии скриптов — сверить при доступе (docs/STATE.md, чеклист).
