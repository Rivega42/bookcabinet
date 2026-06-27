# Механика шкафа — рабочие команды (field-validated)

> Канонический набор операторских команд, **проверенных Романом на железе** (2026-06).
> Это источник истины по ручному управлению механикой. Запускать ТОЛЬКО при
> остановленном боевом сервисе (`sudo systemctl stop bookcabinet`) — иначе два
> pigpio-клиента на одних пинах (конфликт GPIO). Все пути — `~/bookcabinet/tools/`.

## Хоминг и старт
```bash
# Хоминг XY (только каретка), HOME = LEFT+BOTTOM
python3 tools/homing_pigpio.py

# Хоминг + сразу заезд в позицию
python3 tools/goto.py --home 1.3.5
python3 tools/goto.py --home 800 1.3.5     # со своей скоростью

# Полный startup: хоминг XY + калибровка лотка (FRONT→BACK→CENTER)
python3 tools/startup_sequence.py
```

## Подвод каретки к ячейке
Адрес — `depth.rack.shelf` (depth: 1=front, 2=back). Скорость опциональна (дефолт 800).
```bash
python3 tools/goto.py 1.1.5          # дельтой от текущей позиции (если /tmp/carriage_pos.json есть)
python3 tools/goto.py 800 1.1.5      # со скоростью 800
```
Позиция хранится в `/tmp/carriage_pos.json` (после ребута пропадает → следующий goto хомит).
⚠️ Заблокированные ячейки (`calibration.json: disabled_cells`) goto **отказывается** обслуживать
(«Cell X is disabled»). Известные disabled: `1.1.10`, `1.1.11`, `1.2.7`, `1.2.8`, `1.2.10–18`,
`1.3.10/11`, угловые `*.*.0/21`, и др.

## Полка: извлечь / вернуть (one-shot, перехват замков внутри)
Скрипты делают только tray-операцию при ТЕКУЩЕЙ позиции каретки (XY — это goto отдельно).
```bash
python3 tools/shelf_operations.py extract_front   # из переднего ряда → на каретку (задний замок держит)
python3 tools/shelf_operations.py return_front    # с каретки → в передний ряд + лоток в центр
python3 tools/shelf_operations.py extract_rear    # из заднего ряда → на каретку (передний замок держит)
python3 tools/shelf_operations.py return_rear     # с каретки → в задний ряд
```
Внутри — перехват замков (`LOCK_DISTANCE=12600`, центр) — те же константы, что в
`tools/cross_operations_v2.py` и `motors.cross_handoff`. **Подтверждено прогоном на железе.**

## Полная операция «переставить полку из ячейки A в ячейку B»
```bash
# Пример (взять с переднего 1.1.5 → уложить в передний 1.3.5):
python3 tools/goto.py 800 1.1.5
python3 tools/shelf_operations.py extract_front     # полка на каретке
python3 tools/goto.py 800 1.3.5                      # везём (полка держится замком)
python3 tools/shelf_operations.py return_front       # уложили в 1.3.5

# Кросс-ряд (взять с ЗАДНЕГО A → уложить в ПЕРЕДНИЙ B) — пример Романа:
python3 tools/goto.py 800 1.3.5
python3 tools/shelf_operations.py extract_rear       # из заднего ряда на каретку
python3 tools/goto.py 800 2.1.10
python3 tools/shelf_operations.py return_front       # в передний ряд
```
**Это и есть канонический кросс-рядный паттерн:** `goto A → extract_* → goto B → return_*`.
Каретка перевозит полку, удерживаемую замком; перехват — внутри extract/return.

## Шторки
```bash
python3 tools/shutter.py inner open      # внутренняя
python3 tools/shutter.py outer close     # внешняя
python3 tools/shutter.py both open       # обе сразу
python3 tools/shutter.py both close
python3 tools/shutter.py both state      # проверить положение
python3 tools/shutter.py inner state
```

## Прогон (2026-06): что подтверждено на железе
- Хоминг XY (LEFT+BOTTOM, 800/300), калибровка лотка — ок.
- `extract_front` + транспорт кареткой + `return_front`: полка 1.1.5 → 1.3.5 — ок (перехват замков чисто).
- Все 4 shelf-операции + shutter + goto + startup_sequence — рабочие.

## Связь с приложением (что согласовать)
- Боевой `mechanics/algorithms.py` `take_shelf`/`give_shelf` — **свой** (упрощённый) tray-цикл,
  отлажен для same-row. Кросс-ряд в нём не реализован.
- `motors.cross_handoff` (порт `cross_operations_v2`) и `deliver_to_window` — добавлены, но в
  живой флоу не подключены. **Канон доставки кросс-ряда = `extract_rear`/`return_front`**
  (этот файл), поэтому `deliver_to_window` для заднего ряда стоит свести именно к ним.
- Подробности перехвата — `docs/PEREHVAT.md`, геометрия — `docs/geometry.md`.
