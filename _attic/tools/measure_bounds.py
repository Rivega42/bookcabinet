#!/usr/bin/env python3
"""
Определение границ движения каретки.
Запускать ПОСЛЕ хоминга (каретка в RIGHT+BOTTOM).
Едем до LEFT и TOP, считаем шаги — это max_x и max_y.
"""
import RPi.GPIO as GPIO
import time

MOTOR_A_STEP = 14
MOTOR_A_DIR  = 15
MOTOR_B_STEP = 19
MOTOR_B_DIR  = 21

SENSOR_LEFT   = 9
SENSOR_RIGHT  = 10
SENSOR_BOTTOM = 8
SENSOR_TOP    = 11

SPEED_FAST = 2000
SPEED_SLOW = 300
BACKOFF    = 200

def delay(speed):
    return 1.0 / (2 * speed)

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in [MOTOR_A_STEP, MOTOR_A_DIR, MOTOR_B_STEP, MOTOR_B_DIR]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    for pin in [SENSOR_LEFT, SENSOR_RIGHT, SENSOR_BOTTOM, SENSOR_TOP]:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def step(a_dir, b_dir, n, speed, stop_sensor=None):
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

def measure_axis(name, fast_dir_a, fast_dir_b, sensor):
    """Едем до концевика, считаем шаги."""
    print(f"\n[{name}] Едем до концевика...")
    done = step(fast_dir_a, fast_dir_b, 100000, SPEED_FAST, sensor)
    if GPIO.input(sensor):
        print(f"[{name}] Концевик на шаге {done}")
        # Небольшой отъезд чтобы не давить
        step(
            GPIO.LOW if fast_dir_a == GPIO.HIGH else GPIO.HIGH,
            GPIO.LOW if fast_dir_b == GPIO.HIGH else GPIO.HIGH,
            50, SPEED_FAST
        )
        return done
    else:
        print(f"[{name}] ОШИБКА: концевик не найден за 100000 шагов!")
        return None

def main():
    print("=" * 50)
    print("  ИЗМЕРЕНИЕ ГРАНИЦ ДВИЖЕНИЯ")
    print("  Запускать после хоминга!")
    print("=" * 50)

    setup()

    # Убедимся что концевик RIGHT+BOTTOM нажат (мы в home)
    if not GPIO.input(SENSOR_RIGHT) or not GPIO.input(SENSOR_BOTTOM):
        print("\nВНИМАНИЕ: каретка не в позиции HOME (RIGHT+BOTTOM)!")
        print("Сначала запусти homing.py")

    # Измеряем X: едем влево до LEFT
    max_x = measure_axis(
        name="X (RIGHT→LEFT)",
        fast_dir_a=GPIO.LOW, fast_dir_b=GPIO.LOW,  # влево
        sensor=SENSOR_LEFT
    )

    time.sleep(0.3)

    # Измеряем Y: едем вверх до TOP
    max_y = measure_axis(
        name="Y (BOTTOM→TOP)",
        fast_dir_a=GPIO.HIGH, fast_dir_b=GPIO.LOW,  # вверх
        sensor=SENSOR_TOP
    )

    GPIO.cleanup()

    print("\n" + "=" * 50)
    print("  РЕЗУЛЬТАТЫ:")
    if max_x: print(f"  max_x = {max_x} шагов  ({max_x/4000:.1f} мм при 4000 шагов/об)")
    if max_y: print(f"  max_y = {max_y} шагов  ({max_y/4000:.1f} мм при 4000 шагов/об)")
    print("=" * 50)
    print("\nЗапиши эти значения в config.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        GPIO.cleanup()
        print("\nПрервано")
