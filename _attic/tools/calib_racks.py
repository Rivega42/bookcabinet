#!/usr/bin/env python3
"""
calib_racks.py — интерактивная калибровка X-позиций стоек.
Движение: step_pigpio из corexy_pigpio.py.

Управление:
  +500   → вправо 500 шагов
  -500   → влево 500 шагов
  ok     → зафиксировать позицию текущей стойки
  pos    → показать текущую позицию
  q      → выход

Предполагается что хоминг уже выполнен (x=0 = RIGHT).
"""
import sys, os, json, time
sys.path.insert(0, os.path.expanduser("~/bookcabinet/tools"))
import corexy_pigpio as cx

CALIB_FILE = os.path.expanduser("~/bookcabinet/calibration.json")
RACK_COUNT = 3

def move_rel(steps):
    """steps > 0 = влево (от RIGHT к LEFT, x_pos растёт), steps < 0 = вправо"""
    if steps == 0:
        return
    if steps > 0:
        # влево: A=0,B=0
        hit = cx.step_pigpio(0, 0, steps, 500, cx.SENSOR_LEFT)
        if hit:
            print("  ⛔ концевик LEFT!")
    else:
        # вправо: A=1,B=1
        hit = cx.step_pigpio(1, 1, -steps, 500, cx.SENSOR_RIGHT)
        if hit:
            print("  ⛔ концевик RIGHT!")

def main():
    # Загружаем calibration.json для X_TOTAL
    calib = {}
    if os.path.exists(CALIB_FILE):
        with open(CALIB_FILE) as f:
            calib = json.load(f)
    x_total = calib.get("x_total", 20490)

    print("=" * 54)
    print("  CALIB RACKS — калибровка стоек по X")
    print(f"  X_TOTAL={x_total}  (x=0 = RIGHT, x={x_total} = LEFT)")
    print("=" * 54)
    print("\nУправление:")
    print("  +N  → вправо N шагов   (пример: +200)")
    print("  -N  → влево N шагов    (пример: -500)")
    print("  ok  → зафиксировать позицию стойки")
    print("  pos → показать текущую позицию")
    print("  q   → выйти\n")

    # Начинаем с HOME (x=0 = RIGHT)
    # Сдвиг от HOME считаем сами
    x_pos = 0   # шагов от RIGHT (0 = RIGHT, x_total = LEFT)

    rack_positions = {}
    rack_num = 1

    print(f"Текущая позиция: x={x_pos} (RIGHT=0)")
    print(f"\n>>> Наводим на стойку {rack_num}/{RACK_COUNT}")

    while rack_num <= RACK_COUNT:
        try:
            cmd = input("  команда: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if cmd == "q":
            break
        elif cmd == "pos":
            print(f"  x={x_pos} шагов от RIGHT")
        elif cmd == "ok":
            rack_positions[f"rack_{rack_num}"] = x_pos
            print(f"  ✓ Стойка {rack_num} зафиксирована: x={x_pos}")
            rack_num += 1
            if rack_num <= RACK_COUNT:
                print(f"\n>>> Наводим на стойку {rack_num}/{RACK_COUNT}")
        elif cmd.startswith("+") or cmd.startswith("-"):
            try:
                steps = int(cmd)
            except ValueError:
                print("  Ошибка: введи число, например +200 или -500")
                continue
            move_rel(steps)
            x_pos += steps
            print(f"  x={x_pos} шагов от RIGHT")
        else:
            print("  Неизвестная команда. +N / -N / ok / pos / q")

    cx.pi.stop()

    if rack_positions:
        calib["racks"] = rack_positions
        with open(CALIB_FILE, "w") as f:
            json.dump(calib, f, indent=2)
        print("\n" + "=" * 54)
        print("  RACK POSITIONS:")
        for k, v in rack_positions.items():
            print(f"  {k}: x={v} шагов от RIGHT")
        print(f"  Сохранено → {CALIB_FILE}")
        print("=" * 54)
    else:
        print("\nПозиции не сохранены.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cx.pi.wave_tx_stop()
        cx.pi.stop()
        print("\nПрервано")
