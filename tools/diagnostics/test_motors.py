#!/usr/bin/env python3
"""
Тест шаговых моторов каретки (CoreXY)

Motor A: GPIO 2 (STEP), GPIO 3 (DIR)
Motor B: GPIO 19 (STEP), GPIO 21 (DIR)
Tray:    GPIO 24 (STEP), GPIO 25 (DIR)

+ Мониторинг всех концевиков для проверки наводок
"""
import time
import sys

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("ERROR: RPi.GPIO not found. Run on Raspberry Pi!")
    sys.exit(1)

# Конфигурация моторов
MOTOR_A_STEP = 2
MOTOR_A_DIR = 3
MOTOR_B_STEP = 19
MOTOR_B_DIR = 21
TRAY_STEP = 24
TRAY_DIR = 25

DIR_FORWARD = GPIO.HIGH
DIR_BACKWARD = GPIO.LOW

STEP_DELAY = 0.001  # 1ms

# Конфигурация датчиков
SENSORS = {
    'X_BEGIN': 10,
    'X_END': 9,
    'Y_BEGIN': 11,
    'Y_END': 8,
    'TRAY_BEGIN': 7,
    'TRAY_END': 20,
}

THRESHOLDS = {
    'X_BEGIN': {'high': 95, 'low': 85},
    'X_END': {'high': 95, 'low': 85},
    'Y_BEGIN': {'high': 95, 'low': 85},
    'Y_END': {'high': 95, 'low': 85},
    'TRAY_BEGIN': {'high': 95, 'low': 85},
    'TRAY_END': {'high': 95, 'low': 85},
}

SAMPLES = 50


def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Моторы
    for pin in [MOTOR_A_STEP, MOTOR_A_DIR, MOTOR_B_STEP, MOTOR_B_DIR, TRAY_STEP, TRAY_DIR]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    
    # Датчики
    for pin in SENSORS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def read_sensor_percent(pin, samples=SAMPLES):
    """Читает датчик и возвращает % HIGH"""
    high_count = sum(1 for _ in range(samples) if GPIO.input(pin) == GPIO.HIGH)
    return int(high_count * 100 / samples)


def get_sensor_state(name, percent):
    """Определяет состояние датчика по порогам"""
    th = THRESHOLDS.get(name, {'high': 95, 'low': 85})
    if percent >= th['high']:
        return '🔴'
    elif percent <= th['low']:
        return '⚪'
    else:
        return '🟡'


def print_sensors(prefix=""):
    """Вывести состояние всех датчиков"""
    parts = []
    for name, pin in SENSORS.items():
        pct = read_sensor_percent(pin)
        state = get_sensor_state(name, pct)
        parts.append(f"{name}:{state}{pct:3d}%")
    print(f"{prefix}[{' | '.join(parts)}]")


def step_motor(step_pin, steps, delay=STEP_DELAY):
    """Сделать N шагов"""
    for _ in range(steps):
        GPIO.output(step_pin, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(step_pin, GPIO.LOW)
        time.sleep(delay)


def move_motor_a(steps, direction=DIR_FORWARD):
    """Двигать мотор A"""
    GPIO.output(MOTOR_A_DIR, direction)
    time.sleep(0.001)
    step_motor(MOTOR_A_STEP, abs(steps))
    print_sensors("  Sensors: ")


def move_motor_b(steps, direction=DIR_FORWARD):
    """Двигать мотор B"""
    GPIO.output(MOTOR_B_DIR, direction)
    time.sleep(0.001)
    step_motor(MOTOR_B_STEP, abs(steps))
    print_sensors("  Sensors: ")


def move_tray(steps, direction=DIR_FORWARD):
    """Двигать платформу"""
    GPIO.output(TRAY_DIR, direction)
    time.sleep(0.001)
    step_motor(TRAY_STEP, abs(steps))
    print_sensors("  Sensors: ")


def move_xy_corexy(x_steps, y_steps):
    """CoreXY движение"""
    # Движение по X
    if x_steps != 0:
        dir_val = DIR_FORWARD if x_steps > 0 else DIR_BACKWARD
        GPIO.output(MOTOR_A_DIR, dir_val)
        GPIO.output(MOTOR_B_DIR, dir_val)
        time.sleep(0.001)
        
        for _ in range(abs(x_steps)):
            GPIO.output(MOTOR_A_STEP, GPIO.HIGH)
            GPIO.output(MOTOR_B_STEP, GPIO.HIGH)
            time.sleep(STEP_DELAY)
            GPIO.output(MOTOR_A_STEP, GPIO.LOW)
            GPIO.output(MOTOR_B_STEP, GPIO.LOW)
            time.sleep(STEP_DELAY)
    
    # Движение по Y
    if y_steps != 0:
        dir_a = DIR_FORWARD if y_steps > 0 else DIR_BACKWARD
        dir_b = DIR_BACKWARD if y_steps > 0 else DIR_FORWARD
        GPIO.output(MOTOR_A_DIR, dir_a)
        GPIO.output(MOTOR_B_DIR, dir_b)
        time.sleep(0.001)
        
        for _ in range(abs(y_steps)):
            GPIO.output(MOTOR_A_STEP, GPIO.HIGH)
            GPIO.output(MOTOR_B_STEP, GPIO.HIGH)
            time.sleep(STEP_DELAY)
            GPIO.output(MOTOR_A_STEP, GPIO.LOW)
            GPIO.output(MOTOR_B_STEP, GPIO.LOW)
            time.sleep(STEP_DELAY)
    
    print_sensors("  Sensors: ")


def test_single_motor(name, step_fn):
    """Тест одного мотора"""
    print(f"\n{'='*60}")
    print(f"  Testing {name}")
    print(f"{'='*60}")
    
    steps = 200
    print_sensors("  Before: ")
    
    input(f"Press Enter to move {name} FORWARD ({steps} steps)...")
    print(f"  Moving {name} forward...")
    step_fn(steps, DIR_FORWARD)
    
    input(f"Press Enter to move {name} BACKWARD ({steps} steps)...")
    print(f"  Moving {name} backward...")
    step_fn(steps, DIR_BACKWARD)
    
    print(f"  {name} test complete!")


def interactive_mode():
    """Интерактивный режим"""
    print("\n" + "="*60)
    print("  INTERACTIVE MODE")
    print("="*60)
    print("Commands:")
    print("  a+ / a-   — Motor A forward/backward (200 steps)")
    print("  b+ / b-   — Motor B forward/backward")
    print("  t+ / t-   — Tray forward/backward")
    print("  x+ / x-   — CoreXY X axis")
    print("  y+ / y-   — CoreXY Y axis")
    print("  a:500     — Motor A 500 steps forward")
    print("  a:-500    — Motor A 500 steps backward")
    print("  d:0.002   — Set step delay (slower)")
    print("  s         — Show sensors")
    print("  q         — Quit")
    print()
    
    global STEP_DELAY
    default_steps = 200
    
    print_sensors("Initial: ")
    
    while True:
        try:
            cmd = input("Command: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
        
        if cmd == 'q':
            break
        elif cmd == 's':
            print_sensors("Sensors: ")
        elif cmd == 'a+':
            print(f"  Motor A forward {default_steps} steps...")
            move_motor_a(default_steps, DIR_FORWARD)
        elif cmd == 'a-':
            print(f"  Motor A backward {default_steps} steps...")
            move_motor_a(default_steps, DIR_BACKWARD)
        elif cmd == 'b+':
            print(f"  Motor B forward {default_steps} steps...")
            move_motor_b(default_steps, DIR_FORWARD)
        elif cmd == 'b-':
            print(f"  Motor B backward {default_steps} steps...")
            move_motor_b(default_steps, DIR_BACKWARD)
        elif cmd == 't+':
            print(f"  Tray forward {default_steps} steps...")
            move_tray(default_steps, DIR_FORWARD)
        elif cmd == 't-':
            print(f"  Tray backward {default_steps} steps...")
            move_tray(default_steps, DIR_BACKWARD)
        elif cmd == 'x+':
            print(f"  CoreXY X+ {default_steps} steps...")
            move_xy_corexy(default_steps, 0)
        elif cmd == 'x-':
            print(f"  CoreXY X- {default_steps} steps...")
            move_xy_corexy(-default_steps, 0)
        elif cmd == 'y+':
            print(f"  CoreXY Y+ {default_steps} steps...")
            move_xy_corexy(0, default_steps)
        elif cmd == 'y-':
            print(f"  CoreXY Y- {default_steps} steps...")
            move_xy_corexy(0, -default_steps)
        elif cmd.startswith('d:'):
            try:
                STEP_DELAY = float(cmd[2:])
                print(f"  Step delay = {STEP_DELAY} sec")
            except ValueError:
                print("  Invalid delay value")
        elif ':' in cmd:
            try:
                motor, steps = cmd.split(':')
                steps = int(steps)
                direction = DIR_FORWARD if steps >= 0 else DIR_BACKWARD
                steps = abs(steps)
                
                if motor == 'a':
                    print(f"  Motor A {steps} steps...")
                    move_motor_a(steps, direction)
                elif motor == 'b':
                    print(f"  Motor B {steps} steps...")
                    move_motor_b(steps, direction)
                elif motor == 't':
                    print(f"  Tray {steps} steps...")
                    move_tray(steps, direction)
                else:
                    print("  Unknown motor. Use a, b, or t")
            except ValueError:
                print("  Invalid format. Use: a:500 or t:-200")
        else:
            print("  Unknown command")


def main():
    print("="*60)
    print("  STEPPER MOTOR TEST + SENSOR MONITOR")
    print("="*60)
    print(f"Motor A: STEP=GPIO{MOTOR_A_STEP}, DIR=GPIO{MOTOR_A_DIR}")
    print(f"Motor B: STEP=GPIO{MOTOR_B_STEP}, DIR=GPIO{MOTOR_B_DIR}")
    print(f"Tray:    STEP=GPIO{TRAY_STEP}, DIR=GPIO{TRAY_DIR}")
    print(f"Step delay: {STEP_DELAY} sec")
    print(f"Sensors: {', '.join(SENSORS.keys())}")
    
    setup()
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == '-i':
            interactive_mode()
        else:
            test_single_motor("Motor A", move_motor_a)
            test_single_motor("Motor B", move_motor_b)
            test_single_motor("Tray", move_tray)
            
            print("\n" + "="*60)
            print("  Run with -i for interactive mode")
            print("="*60)
    finally:
        GPIO.cleanup()
        print("\nGPIO cleanup done.")


if __name__ == '__main__':
    main()
