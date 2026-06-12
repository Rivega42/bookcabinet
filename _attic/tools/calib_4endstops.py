#!/usr/bin/env python3
"""
calib_4endstops.py — калибровка по 4 концевикам BookCabinet.
Движение: step_pigpio из corexy_pigpio.py (wave_chain, fast+backoff+slow).
Подсчёт шагов: callback на MOTOR_A_STEP RISING_EDGE.

Порядок обхода:
  1. Хоминг → RIGHT + BOTTOM (x=0, y=0)
  2. X: RIGHT → LEFT  → замер X_TOTAL → возврат RIGHT
  3. Y: BOTTOM → TOP  → замер Y_TOTAL → возврат BOTTOM
  4. Выходим в X_MID, Y=0
  5. Сохраняем calibration.json
"""
import sys, os, time, json
sys.path.insert(0, os.path.expanduser("~/bookcabinet/tools"))
import corexy_pigpio as cx
import pigpio

CALIB_FILE = os.path.expanduser("~/bookcabinet/calibration.json")
MAX_STEPS  = 80_000

# ── Счётчик шагов ──────────────────────────────────────────────────────────
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

# ── Движение до концевика (fast + backoff + slow) ──────────────────────────
def touch_endstop(a_dir, b_dir, back_a, back_b, sensor, label):
    """
    Подъезжаем к концевику паттерном fast→backoff→slow.
    Считаем шаги быстрой фазы.
    Возвращает (hit, steps).
    """
    print(f"  [{label}] быстрый подход...", end=" ", flush=True)
    start_count()
    hit = cx.step_pigpio(a_dir, b_dir, MAX_STEPS, cx.FAST, sensor)
    steps = stop_count()
    if not hit:
        print("FAIL (концевик не найден)")
        return False, 0
    print(f"концевик! ({steps} шагов)")

    cx.step_pigpio(back_a, back_b, cx.BACK, cx.FAST)
    time.sleep(0.1)

    print(f"  [{label}] медленное прижатие...", end=" ", flush=True)
    hit2 = cx.step_pigpio(a_dir, b_dir, cx.BACK + 50, cx.SLOW, sensor)
    print("OK" if hit2 else "WARN: не сработало")
    time.sleep(0.1)
    return True, steps

# ── Хоминг ─────────────────────────────────────────────────────────────────
def homing():
    if cx.pi.read(cx.SENSOR_RIGHT) == 1 and cx.pi.read(cx.SENSOR_BOTTOM) == 1:
        print("  Уже в HOME, пропускаем")
        return
    if cx.pi.read(cx.SENSOR_RIGHT) == 1:
        print("  [INIT] RIGHT нажат -> отъезд влево")
        cx.step_pigpio(0, 0, cx.BACK, cx.FAST); time.sleep(0.05)
    if cx.pi.read(cx.SENSOR_BOTTOM) == 1:
        print("  [INIT] BOTTOM нажат -> отъезд вверх")
        cx.step_pigpio(1, 0, cx.BACK, cx.FAST); time.sleep(0.05)
    cx.home_axis("X->RIGHT",  1, 1, cx.SENSOR_RIGHT,  0, 0); time.sleep(0.3)
    cx.home_axis("Y->BOTTOM", 0, 1, cx.SENSOR_BOTTOM, 1, 0); time.sleep(0.3)
    print("  ==> HOME: RIGHT + BOTTOM")

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 56)
    print("  CALIB 4 ENDSTOPS — BookCabinet")
    print(f"  FAST={cx.FAST}  SLOW={cx.SLOW}  BACK={cx.BACK}")
    print("=" * 56)

    # 1. Хоминг
    print("\n[1/6] Хоминг...")
    homing()

    # 2. X: RIGHT → LEFT
    print("\n[2/6] X-ось: RIGHT → LEFT")
    hit, x_total = touch_endstop(0, 0, 1, 1, cx.SENSOR_LEFT, "LEFT")
    if not hit:
        cx.pi.stop(); sys.exit("Ошибка: концевик LEFT не найден")

    # 3. X: LEFT → RIGHT
    print("\n[3/6] X-ось: LEFT → RIGHT")
    hit, _ = touch_endstop(1, 1, 0, 0, cx.SENSOR_RIGHT, "RIGHT")
    if not hit:
        cx.pi.stop(); sys.exit("Ошибка: концевик RIGHT не найден")
    time.sleep(0.3)

    # 4. Y: BOTTOM → TOP
    print("\n[4/6] Y-ось: BOTTOM → TOP")
    hit, y_total = touch_endstop(1, 0, 0, 1, cx.SENSOR_TOP, "TOP")
    if not hit:
        cx.pi.stop(); sys.exit("Ошибка: концевик TOP не найден")

    # 5. Y: TOP → BOTTOM
    print("\n[5/6] Y-ось: TOP → BOTTOM")
    hit, _ = touch_endstop(0, 1, 1, 0, cx.SENSOR_BOTTOM, "BOTTOM")
    if not hit:
        cx.pi.stop(); sys.exit("Ошибка: концевик BOTTOM не найден")
    time.sleep(0.3)

    # 6. Выход в центр X, Y=0
    x_mid = x_total // 2
    print(f"\n[6/6] Перемещение в центр: X_MID={x_mid} шагов (влево)...")
    cx.step_pigpio(0, 0, x_mid, cx.FAST)
    print(f"  Позиция: X_MID={x_mid}, Y=0 (BOTTOM)")

    # Сохранение
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

    cx.pi.stop()

    print("\n" + "=" * 56)
    print("  CALIBRATION DONE")
    print(f"  X_TOTAL = {x_total} шагов  (RIGHT→LEFT)")
    print(f"  Y_TOTAL = {y_total} шагов  (BOTTOM→TOP)")
    print(f"  X_MID   = {x_mid} шагов от RIGHT")
    print(f"  Сохранено → {CALIB_FILE}")
    print("=" * 56)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cx.pi.wave_tx_stop()
        cx.pi.stop()
        print("\nПрервано")
        sys.exit(1)
