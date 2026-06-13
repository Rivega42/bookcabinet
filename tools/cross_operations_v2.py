#!/usr/bin/env python3
"""
Оптимизированные кросс-рядные операции BookCabinet.
front_to_rear_v2 / rear_to_front_v2 — 8 шагов вместо 17.

Использование:
    python3 cross_operations_v2.py front_to_rear
    python3 cross_operations_v2.py rear_to_front
"""
import pigpio
import time
import sys
import os

# === КОНСТАНТЫ ===
TRAY_STEP = 18
TRAY_DIR = 27
TRAY_EN1 = 25
TRAY_EN2 = 26
TRAY_FREQ = 12000

ENDSTOP_FRONT = 7
ENDSTOP_BACK = 20

LOCK_FRONT = 12
LOCK_REAR = 13

LOCK_DISTANCE = 12600
TRAY_CENTER = 11300

LOCK_GRAB_PWM = 1200
LOCK_RELEASE_PWM = 500

# === ИНИЦИАЛИЗАЦИЯ ===
pi = pigpio.pi()
step_counter = 0

def setup():
    for pin in [TRAY_STEP, TRAY_DIR, TRAY_EN1, TRAY_EN2]:
        pi.set_mode(pin, pigpio.OUTPUT)
    pi.set_mode(ENDSTOP_FRONT, pigpio.INPUT)
    pi.set_mode(ENDSTOP_BACK, pigpio.INPUT)
    pi.set_pull_up_down(ENDSTOP_FRONT, pigpio.PUD_UP)
    pi.set_pull_up_down(ENDSTOP_BACK, pigpio.PUD_UP)

def cleanup():
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)

def step(msg):
    global step_counter
    step_counter += 1
    print(f"\n[{step_counter}] {msg}")
    input(f"    Press Enter to execute...")

# === ЗАМКИ ===
def lock_grab(pin):
    name = "FRONT" if pin == LOCK_FRONT else "REAR"
    os.system(f"pigs s {pin} {LOCK_GRAB_PWM}")
    time.sleep(0.5)
    os.system(f"pigs s {pin} 0")
    print(f"    {name} lock: GRAB")

def lock_release(pin, strong=False):
    name = "FRONT" if pin == LOCK_FRONT else "REAR"
    if strong:
        for _ in range(3):
            os.system(f"pigs s {pin} {LOCK_RELEASE_PWM}")
            time.sleep(0.5)
        os.system(f"pigs s {pin} 0")
    else:
        os.system(f"pigs s {pin} {LOCK_RELEASE_PWM}")
        time.sleep(0.5)
        os.system(f"pigs s {pin} 0")
    print(f"    {name} lock: RELEASE")

# === ДВИЖЕНИЕ ===
def sensor_stable(pin, required=5, interval=0.001):
    count = 0
    for _ in range(required * 2):
        if pi.read(pin) == 1:
            count += 1
            if count >= required:
                return True
        else:
            count = 0
        time.sleep(interval)
    return False

def tray_move(steps, direction):
    period_us = int(1000000 / TRAY_FREQ)
    pulse_us = period_us // 2
    
    pi.wave_clear()
    pi.wave_add_generic([
        pigpio.pulse(1 << TRAY_STEP, 0, pulse_us),
        pigpio.pulse(0, 1 << TRAY_STEP, pulse_us)
    ])
    wave_id = pi.wave_create()
    
    pi.write(TRAY_EN1, 0)
    pi.write(TRAY_EN2, 0)
    pi.write(TRAY_DIR, direction)
    time.sleep(0.01)
    
    dir_name = "BACK" if direction == 1 else "FRONT"
    print(f"    Moving {steps} steps to {dir_name}...")
    
    pi.wave_send_repeat(wave_id)
    time.sleep(steps / TRAY_FREQ)
    pi.wave_tx_stop()
    
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)
    pi.wave_delete(wave_id)
    print(f"    Done")

def tray_to_endstop(endstop_pin):
    direction = 1 if endstop_pin == ENDSTOP_BACK else 0
    dir_name = "BACK" if direction == 1 else "FRONT"
    
    period_us = int(1000000 / TRAY_FREQ)
    pulse_us = period_us // 2
    
    pi.wave_clear()
    pi.wave_add_generic([
        pigpio.pulse(1 << TRAY_STEP, 0, pulse_us),
        pigpio.pulse(0, 1 << TRAY_STEP, pulse_us)
    ])
    wave_id = pi.wave_create()
    
    pi.write(TRAY_EN1, 0)
    pi.write(TRAY_EN2, 0)
    pi.write(TRAY_DIR, direction)
    time.sleep(0.01)
    
    # Fast approach
    print(f"    Moving to {dir_name} (fast)...", end=" ", flush=True)
    pi.wave_send_repeat(wave_id)
    while not sensor_stable(endstop_pin):
        time.sleep(0.001)
    pi.wave_tx_stop()
    print("hit!", end=" ", flush=True)
    
    # Backoff
    pi.write(TRAY_DIR, 1 - direction)
    time.sleep(0.01)
    print("backoff...", end=" ", flush=True)
    pi.wave_send_repeat(wave_id)
    time.sleep(1500 / TRAY_FREQ)
    pi.wave_tx_stop()
    
    # Slow approach
    pi.wave_delete(wave_id)
    
    slow_freq = 1500
    slow_period = int(1000000 / slow_freq)
    slow_pulse = slow_period // 2
    
    pi.wave_clear()
    pi.wave_add_generic([
        pigpio.pulse(1 << TRAY_STEP, 0, slow_pulse),
        pigpio.pulse(0, 1 << TRAY_STEP, slow_pulse)
    ])
    slow_wave = pi.wave_create()
    
    pi.write(TRAY_DIR, direction)
    time.sleep(0.01)
    pi.wave_send_repeat(slow_wave)
    
    slow_steps = 0
    while not sensor_stable(endstop_pin):
        time.sleep(1 / slow_freq)
        slow_steps += 1
    pi.wave_tx_stop()
    
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)
    pi.wave_delete(slow_wave)
    
    print(f"OK (slow: {slow_steps} steps)")


# === ОПТИМИЗИРОВАННЫЕ ОПЕРАЦИИ ===

def front_to_rear_v2():
    """
    Переложить полочку из передней стойки в заднюю.
    8 шагов вместо 17.
    """
    global step_counter
    step_counter = 0
    
    print("\n" + "="*50)
    print("FRONT TO REAR v2 (оптимизированный)")
    print("="*50)
    setup()
    
    step("Tray -> FRONT endstop (передний замок под полочкой)")
    tray_to_endstop(ENDSTOP_FRONT)
    
    step("FRONT lock GRAB (захватили из передней стойки)")
    lock_grab(LOCK_FRONT)
    
    step(f"Tray -> {LOCK_DISTANCE} шагов к BACK (задний замок встаёт под прорезь)")
    tray_move(LOCK_DISTANCE, 1)
    
    step("FRONT lock RELEASE (отпускаем передний)")
    lock_release(LOCK_FRONT)
    
    step("REAR lock GRAB (перехватили задним)")
    lock_grab(LOCK_REAR)
    
    step("Tray -> BACK endstop (везём в заднюю стойку — точно по концевику!)")
    tray_to_endstop(ENDSTOP_BACK)
    
    step("REAR lock RELEASE (положили в ячейку)")
    lock_release(LOCK_REAR, strong=True)
    
    step(f"Tray -> CENTER ({TRAY_CENTER} шагов к FRONT)")
    tray_move(TRAY_CENTER, 0)
    
    cleanup()
    print("\n" + "="*50)
    print("DONE: Полочка перемещена из передней стойки в заднюю")
    print("="*50)


def rear_to_front_v2():
    """
    Переложить полочку из задней стойки в переднюю.
    8 шагов вместо 17.
    """
    global step_counter
    step_counter = 0
    
    print("\n" + "="*50)
    print("REAR TO FRONT v2 (оптимизированный)")
    print("="*50)
    setup()
    
    step("Tray -> BACK endstop (задний замок под полочкой)")
    tray_to_endstop(ENDSTOP_BACK)
    
    step("REAR lock GRAB (захватили из задней стойки)")
    lock_grab(LOCK_REAR)
    
    step(f"Tray -> {LOCK_DISTANCE} шагов к FRONT (передний замок встаёт под прорезь)")
    tray_move(LOCK_DISTANCE, 0)
    
    step("REAR lock RELEASE (отпускаем задний)")
    lock_release(LOCK_REAR)
    
    step("FRONT lock GRAB (перехватили передним)")
    lock_grab(LOCK_FRONT)
    
    step("Tray -> FRONT endstop (везём в переднюю стойку — точно по концевику!)")
    tray_to_endstop(ENDSTOP_FRONT)
    
    step("FRONT lock RELEASE (положили в ячейку)")
    lock_release(LOCK_FRONT, strong=True)
    
    step(f"Tray -> CENTER ({TRAY_CENTER} шагов к BACK)")
    tray_move(TRAY_CENTER, 1)
    
    cleanup()
    print("\n" + "="*50)
    print("DONE: Полочка перемещена из задней стойки в переднюю")
    print("="*50)


# === MAIN ===
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands:")
        print("  front_to_rear  - из передней в заднюю (8 шагов)")
        print("  rear_to_front  - из задней в переднюю (8 шагов)")
        return 1
    
    cmd = sys.argv[1]
    
    commands = {
        "front_to_rear": front_to_rear_v2,
        "rear_to_front": rear_to_front_v2,
    }
    
    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(commands.keys())}")
        return 1
    
    try:
        commands[cmd]()
    except KeyboardInterrupt:
        print("\nAborted")
        cleanup()
    finally:
        pi.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
