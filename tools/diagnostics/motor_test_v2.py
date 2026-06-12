#!/usr/bin/env python3
"""
Motor Test v2 — использует pigpio + config.py
Интерактивное тестирование моторов и датчиков BookCabinet
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pigpio

from bookcabinet.config import GPIO_PINS, MOTOR_SPEEDS

# Пины из конфига
PINS = GPIO_PINS
pi = pigpio.pi()

if not pi.connected:
    print("❌ pigpiod не запущен! sudo systemctl start pigpiod")
    sys.exit(1)

# Настройка выходов (моторы)
for name in ['MOTOR_A_STEP', 'MOTOR_A_DIR', 'MOTOR_B_STEP', 'MOTOR_B_DIR', 'TRAY_STEP', 'TRAY_DIR']:
    pi.set_mode(PINS[name], pigpio.OUTPUT)
    pi.write(PINS[name], 0)

# Настройка входов (датчики)
SENSORS = {
    'X_BEGIN':    PINS['SENSOR_X_BEGIN'],
    'X_END':      PINS['SENSOR_X_END'],
    'Y_BEGIN':    PINS['SENSOR_Y_BEGIN'],
    'Y_END':      PINS['SENSOR_Y_END'],
    'TRAY_BEGIN': PINS['SENSOR_TRAY_BEGIN'],
    'TRAY_END':   PINS['SENSOR_TRAY_END'],
}
for pin in SENSORS.values():
    pi.set_mode(pin, pigpio.INPUT)
    pi.set_pull_up_down(pin, pigpio.PUD_UP)

STEP_DELAY = 0.001  # 1ms default


def read_sensors():
    """Прочитать все датчики"""
    results = {}
    for name, pin in SENSORS.items():
        # Среднее 50 чтений
        high = sum(1 for _ in range(50) if pi.read(pin))
        pct = high * 2  # из 50 → %
        if pct >= 95:
            icon = '🔴'
        elif pct <= 85:
            icon = '⚪'
        else:
            icon = '🟡'
        results[name] = (pct, icon)
    return results


def print_sensors(prefix=""):
    sensors = read_sensors()
    parts = [f"{n}:{icon}{pct:3d}%" for n, (pct, icon) in sensors.items()]
    print(f"{prefix}[{' | '.join(parts)}]")


def step_motor(step_pin, dir_pin, steps, direction, delay=STEP_DELAY):
    """Шагнуть мотором"""
    pi.write(dir_pin, 1 if direction > 0 else 0)
    time.sleep(0.001)
    for i in range(abs(steps)):
        pi.write(step_pin, 1)
        time.sleep(delay)
        pi.write(step_pin, 0)
        time.sleep(delay)
        if (i + 1) % 100 == 0:
            # Каждые 100 шагов проверяем датчики
            pass


def move_motor_a(steps, direction=1):
    step_motor(PINS['MOTOR_A_STEP'], PINS['MOTOR_A_DIR'], steps, direction)
    print_sensors("  Sensors: ")


def move_motor_b(steps, direction=1):
    step_motor(PINS['MOTOR_B_STEP'], PINS['MOTOR_B_DIR'], steps, direction)
    print_sensors("  Sensors: ")


def move_tray(steps, direction=1):
    step_motor(PINS['TRAY_STEP'], PINS['TRAY_DIR'], steps, direction)
    print_sensors("  Sensors: ")


def move_corexy_x(steps):
    """CoreXY: X = оба мотора в одну сторону"""
    d = 1 if steps > 0 else 0
    pi.write(PINS['MOTOR_A_DIR'], d)
    pi.write(PINS['MOTOR_B_DIR'], d)
    time.sleep(0.001)
    for _ in range(abs(steps)):
        pi.write(PINS['MOTOR_A_STEP'], 1)
        pi.write(PINS['MOTOR_B_STEP'], 1)
        time.sleep(STEP_DELAY)
        pi.write(PINS['MOTOR_A_STEP'], 0)
        pi.write(PINS['MOTOR_B_STEP'], 0)
        time.sleep(STEP_DELAY)
    print_sensors("  Sensors: ")


def move_corexy_y(steps):
    """CoreXY: Y = моторы в разные стороны"""
    if steps > 0:
        dir_a, dir_b = 1, 0
    else:
        dir_a, dir_b = 0, 1
    pi.write(PINS['MOTOR_A_DIR'], dir_a)
    pi.write(PINS['MOTOR_B_DIR'], dir_b)
    time.sleep(0.001)
    for _ in range(abs(steps)):
        pi.write(PINS['MOTOR_A_STEP'], 1)
        pi.write(PINS['MOTOR_B_STEP'], 1)
        time.sleep(STEP_DELAY)
        pi.write(PINS['MOTOR_A_STEP'], 0)
        pi.write(PINS['MOTOR_B_STEP'], 0)
        time.sleep(STEP_DELAY)
    print_sensors("  Sensors: ")


def main():
    global STEP_DELAY
    default_steps = 200

    print("=" * 60)
    print("  MOTOR TEST v2 (pigpio + config.py)")
    print("=" * 60)
    print(f"Motor A: STEP=GPIO{PINS['MOTOR_A_STEP']}, DIR=GPIO{PINS['MOTOR_A_DIR']}")
    print(f"Motor B: STEP=GPIO{PINS['MOTOR_B_STEP']}, DIR=GPIO{PINS['MOTOR_B_DIR']}")
    print(f"Tray:    STEP=GPIO{PINS['TRAY_STEP']}, DIR=GPIO{PINS['TRAY_DIR']}")
    print(f"Sensors: {', '.join(f'{n}=GPIO{p}' for n, p in SENSORS.items())}")
    print(f"Step delay: {STEP_DELAY}s ({int(1/STEP_DELAY/2)} steps/sec)")
    print()
    print("Commands:")
    print("  s          — Show sensors")
    print("  a+ / a-    — Motor A fwd/bwd (200 steps)")
    print("  b+ / b-    — Motor B fwd/bwd")
    print("  t+ / t-    — Tray fwd/bwd")
    print("  x+ / x-    — CoreXY X axis")
    print("  y+ / y-    — CoreXY Y axis")
    print("  a:500      — Motor A 500 steps (negative = backward)")
    print("  x:1000     — CoreXY X 1000 steps")
    print("  d:0.002    — Set step delay")
    print("  n:100      — Set default steps")
    print("  q          — Quit")
    print()
    
    print_sensors("Initial: ")
    print()
    
    while True:
        try:
            cmd = input("» ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
        
        if not cmd:
            continue
        elif cmd == 'q':
            break
        elif cmd == 's':
            print_sensors("Sensors: ")
        elif cmd == 'a+':
            print(f"  Motor A → {default_steps} steps")
            move_motor_a(default_steps, 1)
        elif cmd == 'a-':
            print(f"  Motor A ← {default_steps} steps")
            move_motor_a(default_steps, -1)
        elif cmd == 'b+':
            print(f"  Motor B → {default_steps} steps")
            move_motor_b(default_steps, 1)
        elif cmd == 'b-':
            print(f"  Motor B ← {default_steps} steps")
            move_motor_b(default_steps, -1)
        elif cmd == 't+':
            print(f"  Tray → {default_steps} steps")
            move_tray(default_steps, 1)
        elif cmd == 't-':
            print(f"  Tray ← {default_steps} steps")
            move_tray(default_steps, -1)
        elif cmd == 'x+':
            print(f"  CoreXY X+ {default_steps} steps")
            move_corexy_x(default_steps)
        elif cmd == 'x-':
            print(f"  CoreXY X- {default_steps} steps")
            move_corexy_x(-default_steps)
        elif cmd == 'y+':
            print(f"  CoreXY Y+ {default_steps} steps")
            move_corexy_y(default_steps)
        elif cmd == 'y-':
            print(f"  CoreXY Y- {default_steps} steps")
            move_corexy_y(-default_steps)
        elif cmd.startswith('d:'):
            try:
                STEP_DELAY = float(cmd[2:])
                print(f"  Delay = {STEP_DELAY}s ({int(1/STEP_DELAY/2)} steps/sec)")
            except ValueError:
                print("  ❌ Invalid value")
        elif cmd.startswith('n:'):
            try:
                default_steps = int(cmd[2:])
                print(f"  Default steps = {default_steps}")
            except ValueError:
                print("  ❌ Invalid value")
        elif ':' in cmd:
            try:
                motor, steps_str = cmd.split(':', 1)
                steps = int(steps_str)
                direction = 1 if steps >= 0 else -1
                steps = abs(steps)
                if motor == 'a':
                    print(f"  Motor A {'→' if direction > 0 else '←'} {steps} steps")
                    move_motor_a(steps, direction)
                elif motor == 'b':
                    print(f"  Motor B {'→' if direction > 0 else '←'} {steps} steps")
                    move_motor_b(steps, direction)
                elif motor == 't':
                    print(f"  Tray {'→' if direction > 0 else '←'} {steps} steps")
                    move_tray(steps, direction)
                elif motor == 'x':
                    print(f"  CoreXY X {'→' if direction > 0 else '←'} {steps} steps")
                    move_corexy_x(steps * direction)
                elif motor == 'y':
                    print(f"  CoreXY Y {'→' if direction > 0 else '←'} {steps} steps")
                    move_corexy_y(steps * direction)
                else:
                    print("  ❌ Unknown motor (a/b/t/x/y)")
            except ValueError:
                print("  ❌ Format: a:500 or x:-1000")
        else:
            print("  ❌ Unknown command. Try: s, a+, b-, x:500, q")

    pi.stop()
    print("\n✅ GPIO cleanup done.")


if __name__ == '__main__':
    main()
