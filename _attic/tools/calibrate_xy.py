#!/usr/bin/env python3
"""
calibrate_xy.py — калибровка каретки BookCabinet.
Движение: step_pigpio из corexy_pigpio.py (wave_chain).
Подсчёт шагов: callback на MOTOR_A_STEP RISING_EDGE.
Остановка на концевике: паттерн fast+backoff+slow (как home_axis).

Алгоритм:
  1. Хоминг → RIGHT + BOTTOM (x=0, y=0)
  2. X: LEFT до концевика → X_TOTAL → возврат RIGHT
  3. Y: TOP до концевика  → Y_TOTAL → возврат BOTTOM
  4. Выходим в X_MID, Y=0
  5. Сохраняем calibration.json
"""
import sys, os, time, json
sys.path.insert(0, os.path.expanduser("~/bookcabinet/tools"))
import corexy_pigpio as cx
import pigpio

CALIB_FILE = os.path.expanduser("~/bookcabinet/calibration.json")
MAX_STEPS  = 80_000

# --- Счётчик шагов через callback на STEP-пин ---
_steps = 0
_step_cb = None

def _count(gpio, level, tick):
    global _steps
    _steps += 1

def start_count():
    global _steps, _step_cb
    _steps = 0
    _step_cb = cx.pi.callback(cx.MOTOR_A_STEP, pigpio.RISING_EDGE, _count)

def stop_count():
    global _step_cb
    if _step_cb:
        _step_cb.cancel()
        _step_cb = None
    return _steps


def move_to_endstop(a_dir, b_dir, back_a, back_b, stop_sensor):
    """
    Едем до концевика паттерном fast+backoff+slow (как home_axis).
    Считаем шаги только на быстрой фазе.
    Возвращает (hit, steps).
    """
    # Быстрый подход
    start_count()
    hit = cx.step_pigpio(a_dir, b_dir, MAX_STEPS, cx.FAST, stop_sensor)
    steps = stop_count()

    if not hit:
        return False, steps

    # Backoff
    time.sleep(0.05)
    cx.step_pigpio(back_a, back_b, cx.BACK, cx.FAST)
    time.sleep(0.1)

    # Медленное прижатие
    hit2 = cx.step_pigpio(a_dir, b_dir, cx.BACK + 50, cx.SLOW, stop_sensor)
    if not hit2:
        print(" WARN: медленное прижатие не сработало", end="")

    return True, steps


def homing():
    if cx.pi.read(cx.SENSOR_RIGHT) == 1 and cx.pi.read(cx.SENSOR_BOTTOM) == 1:
        print("      Уже в HOME, пропускаем")
        return
    if cx.pi.read(cx.SENSOR_RIGHT) == 1:
        print("[INIT] RIGHT нажат -> отъезд влево")
        cx.step_pigpio(0, 0, cx.BACK, cx.FAST)
        time.sleep(0.05)
    if cx.pi.read(cx.SENSOR_BOTTOM) == 1:
        print("[INIT] BOTTOM нажат -> отъезд вверх")
        cx.step_pigpio(1, 0, cx.BACK, cx.FAST)
        time.sleep(0.05)
    cx.home_axis("X->RIGHT",  1, 1, cx.SENSOR_RIGHT,  0, 0)
    time.sleep(0.3)
    cx.home_axis("Y->BOTTOM", 0, 1, cx.SENSOR_BOTTOM, 1, 0)
    time.sleep(0.3)
    print("==> HOME: RIGHT + BOTTOM\n")


def main():
    print("=" * 54)
    print("  CALIBRATION BookCabinet")
    print(f"  FAST={cx.FAST}  SLOW={cx.SLOW}  BACK={cx.BACK}")
    print("=" * 54)

    # 1. Хоминг
    print("\n[1/5] Хоминг...")
    homing()

    # 2. X-калибровка: RIGHT→LEFT→RIGHT
    print("[2/5] X: едем LEFT до концевика...")
    hit, x_total = move_to_endstop(0, 0, 1, 1, cx.SENSOR_LEFT)
    if not hit:
        cx.pi.stop(); sys.exit("Концевик LEFT не найден!")
    print(f"\n      X_TOTAL = {x_total} шагов")
    time.sleep(0.1)

    print("      Возврат к RIGHT...", end=" ", flush=True)
    hit2, _ = move_to_endstop(1, 1, 0, 0, cx.SENSOR_RIGHT)
    print("OK" if hit2 else "WARN: RIGHT не сработал")
    time.sleep(0.3)

    # 3. Y-калибровка: BOTTOM→TOP→BOTTOM
    print("\n[3/5] Y: едем TOP до концевика...")
    hit, y_total = move_to_endstop(1, 0, 0, 1, cx.SENSOR_TOP)
    if not hit:
        cx.pi.stop(); sys.exit("Концевик TOP не найден!")
    print(f"\n      Y_TOTAL = {y_total} шагов")
    time.sleep(0.1)

    print("      Возврат к BOTTOM...", end=" ", flush=True)
    hit2, _ = move_to_endstop(0, 1, 1, 0, cx.SENSOR_BOTTOM)
    print("OK" if hit2 else "WARN: BOTTOM не сработал")
    time.sleep(0.3)

    # 4. Выход в центр
    x_mid = x_total // 2
    print(f"\n[4/5] Перемещение в X_MID = {x_mid} шагов (влево)...")
    cx.step_pigpio(0, 0, x_mid, cx.FAST)
    print(f"      Позиция: X_MID={x_mid}, Y=0 (BOTTOM)")

    # 5. Сохранение
    calib = {
        "x_total": x_total,
        "y_total": y_total,
        "x_mid":   x_mid,
        "home":    "RIGHT+BOTTOM",
        "note":    "x=0 at RIGHT, y=0 at BOTTOM",
    }
    os.makedirs(os.path.dirname(CALIB_FILE), exist_ok=True)
    with open(CALIB_FILE, "w") as f:
        json.dump(calib, f, indent=2)
    print(f"\n[5/5] Сохранено → {CALIB_FILE}")

    cx.pi.stop()

    print("\n" + "=" * 54)
    print(f"  CALIBRATION DONE")
    print(f"  X_TOTAL = {x_total} шагов")
    print(f"  Y_TOTAL = {y_total} шагов")
    print(f"  X_MID   = {x_mid} шагов от RIGHT")
    print("=" * 54)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cx.pi.wave_tx_stop()
        cx.pi.stop()
        print("\nПрервано")
        sys.exit(1)
