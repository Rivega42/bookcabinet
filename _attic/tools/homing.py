#!/usr/bin/env python3
"""
Хоминг каретки BookCabinet.
Алгоритм (как в 3D принтерах):
  1. Быстро едем к концевику
  2. При срабатывании — отъезжаем на BACKOFF шагов
  3. Медленно прижимаемся к концевику снова
  4. Останавливаемся — это HOME
Порядок: сначала X (вправо), потом Y (вниз).
"""
import RPi.GPIO as GPIO
import time
import sys

# === Пины (из config.py) ===
MOTOR_A_STEP = 14
MOTOR_A_DIR  = 15
MOTOR_B_STEP = 19
MOTOR_B_DIR  = 21

SENSOR_RIGHT  = 10   # X home
SENSOR_BOTTOM = 8    # Y home

# === Параметры ===
SPEED_FAST   = 2000  # шагов/сек — быстрый подход
SPEED_SLOW   = 300   # шагов/сек — медленное прижатие
BACKOFF      = 200   # шагов назад после первого касания

def delay(speed):
    return 1.0 / (2 * speed)

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in [MOTOR_A_STEP, MOTOR_A_DIR, MOTOR_B_STEP, MOTOR_B_DIR]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    for pin in [SENSOR_RIGHT, SENSOR_BOTTOM]:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def step(a_dir, b_dir, n, speed, stop_sensor=None):
    """Сделать n шагов. Возвращает кол-во пройденных шагов."""
    GPIO.output(MOTOR_A_DIR, a_dir)
    GPIO.output(MOTOR_B_DIR, b_dir)
    time.sleep(0.001)
    d = delay(speed)
    for i in range(n):
        if stop_sensor is not None and GPIO.input(stop_sensor):
            return i
        GPIO.output(MOTOR_A_STEP, GPIO.HIGH)
        GPIO.output(MOTOR_B_STEP, GPIO.HIGH)
        time.sleep(d)
        GPIO.output(MOTOR_A_STEP, GPIO.LOW)
        GPIO.output(MOTOR_B_STEP, GPIO.LOW)
        time.sleep(d)
    return n

def home_axis(name, fast_dir_a, fast_dir_b, back_dir_a, back_dir_b, sensor):
    """Хоминг одной оси: быстро → отъезд → медленно."""
    print(f"\n[{name}] Быстрый подход...")
    done = step(fast_dir_a, fast_dir_b, 100000, SPEED_FAST, sensor)
    if GPIO.input(sensor):
        print(f"[{name}] Концевик на шаге {done} — отъезжаю {BACKOFF} шагов")
    else:
        print(f"[{name}] ВНИМАНИЕ: концевик не достигнут за 50000 шагов!")
        return False

    # Отъезд
    step(back_dir_a, back_dir_b, BACKOFF, SPEED_FAST)
    time.sleep(0.1)

    # Медленный подход
    print(f"[{name}] Медленное прижатие...")
    done2 = step(fast_dir_a, fast_dir_b, BACKOFF + 50, SPEED_SLOW, sensor)
    if GPIO.input(sensor):
        print(f"[{name}] HOME ✓  (шаг {done2})")
        return True
    else:
        print(f"[{name}] ОШИБКА: концевик не сработал при медленном подходе")
        return False

def main():
    print("=" * 50)
    print("  ХОМИНГ BookCabinet")
    print("  X → RIGHT,  Y → BOTTOM")
    print("=" * 50)

    setup()

    # --- Хоминг X (вправо: A+, B+) ---
    ok_x = home_axis(
        name="X-RIGHT",
        fast_dir_a=GPIO.HIGH, fast_dir_b=GPIO.HIGH,   # вправо
        back_dir_a=GPIO.LOW,  back_dir_b=GPIO.LOW,    # влево
        sensor=SENSOR_RIGHT
    )

    if not ok_x:
        print("\nХоминг X не удался — останавливаемся.")
        GPIO.cleanup()
        sys.exit(1)

    time.sleep(0.3)

    # --- Хоминг Y (вниз: A-, B+) ---
    ok_y = home_axis(
        name="Y-BOTTOM",
        fast_dir_a=GPIO.LOW,  fast_dir_b=GPIO.HIGH,   # вниз
        back_dir_a=GPIO.HIGH, back_dir_b=GPIO.LOW,    # вверх
        sensor=SENSOR_BOTTOM
    )

    GPIO.cleanup()

    if ok_x and ok_y:
        print("\n✓ Хоминг завершён! Каретка в позиции RIGHT+BOTTOM (0,0)")
    else:
        print("\n✗ Хоминг завершён с ошибками")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        GPIO.cleanup()
        print("\nПрервано")
