#!/usr/bin/env python3
"""
Операции с полочками BookCabinet.
Извлечение и возврат полочек из заднего и переднего рядов.
Кросс-рядные операции (front_to_rear, rear_to_front).

Использование:
    python3 shelf_operations.py extract_rear   # Извлечь из заднего ряда
    python3 shelf_operations.py return_rear    # Вернуть в задний ряд
    python3 shelf_operations.py extract_front  # Извлечь из переднего ряда
    python3 shelf_operations.py return_front   # Вернуть в передний ряд
    python3 shelf_operations.py front_to_rear  # Переложить из переднего в задний
    python3 shelf_operations.py rear_to_front  # Переложить из заднего в передний
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

# Откалиброванные значения (21.04.2026)
TRAY_CENTER = 11300

# Задний ряд (depth=2)
REAR_HANDOFF_REAR_FROM_BACK = 16800   # Задний замок на середине каретки
REAR_HANDOFF_FRONT_FROM_BACK = 4200   # Передний замок на середине каретки

# Передний ряд (depth=1)
FRONT_HANDOFF_FRONT_FROM_BACK = 5700  # Передний замок на середине каретки
FRONT_HANDOFF_REAR_FROM_BACK = 18300  # Задний замок на середине каретки

LOCK_DISTANCE = 12600  # Расстояние между точками перехвата

# Кросс-рядные константы (откалибровано 21.04.2026)
CROSS_FRONT_TO_REAR_STEP6 = 12500  # front_to_rear: шаг 6 к FRONT
CROSS_REAR_TO_FRONT_STEP4 = 12700  # rear_to_front: шаг 4 к FRONT
CROSS_REAR_TO_FRONT_STEP6 = 12600  # rear_to_front: шаг 6 к BACK

LOCK_GRAB_PWM = 1200
LOCK_RELEASE_PWM = 500

# === ИНИЦИАЛИЗАЦИЯ ===
pi = pigpio.pi()

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

# === ЗАМКИ ===
def lock_grab(pin):
    os.system(f"pigs s {pin} {LOCK_GRAB_PWM}")
    time.sleep(0.5)
    os.system(f"pigs s {pin} 0")
    print(f"  Lock {pin}: GRAB")

def lock_release(pin, strong=False):
    """Отпустить замок. strong=True для критичных позиций (несколько команд)"""
    if strong:
        for _ in range(3):
            os.system(f"pigs s {pin} {LOCK_RELEASE_PWM}")
            time.sleep(0.5)
        os.system(f"pigs s {pin} 0")
    else:
        os.system(f"pigs s {pin} {LOCK_RELEASE_PWM}")
        time.sleep(0.5)
        os.system(f"pigs s {pin} 0")
    print(f"  Lock {pin}: RELEASE")

# === ДВИЖЕНИЕ ПЛАТФОРМЫ ===
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
    print(f"  Moving {steps} steps to {dir_name}...")
    
    pi.wave_send_repeat(wave_id)
    time.sleep(steps / TRAY_FREQ)
    pi.wave_tx_stop()
    
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)
    pi.wave_delete(wave_id)

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
    print(f"  Moving to {dir_name} (fast)...", end=" ", flush=True)
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

# === ЗАДНИЙ РЯД (depth=2) ===

def extract_rear():
    """Извлечь полочку из заднего ряда"""
    print("=== EXTRACT REAR SHELF ===")
    setup()
    
    print("Step 1: Tray -> BACK endstop")
    tray_to_endstop(ENDSTOP_BACK)
    
    print("Step 2: Rear lock -> GRAB")
    lock_grab(LOCK_REAR)
    
    print("Step 3: Tray -> 16800 steps to FRONT (rear handoff)")
    tray_move(REAR_HANDOFF_REAR_FROM_BACK, 0)
    
    print("Step 4: Rear lock -> RELEASE")
    lock_release(LOCK_REAR)
    
    print("Step 5: Tray -> 12600 steps to BACK (front handoff)")
    tray_move(LOCK_DISTANCE, 1)
    
    print("Step 6: Front lock -> GRAB")
    lock_grab(LOCK_FRONT)
    
    print("Step 7: Tray -> 12600 steps to FRONT (rear handoff)")
    tray_move(LOCK_DISTANCE, 0)
    
    cleanup()
    print("=== DONE: Shelf on carriage, front lock holding ===")

def return_rear():
    """Вернуть полочку в задний ряд"""
    print("=== RETURN REAR SHELF ===")
    setup()
    
    print("Step 1: Tray -> 12600 steps to BACK (front handoff)")
    tray_move(LOCK_DISTANCE, 1)
    
    print("Step 2: Front lock -> RELEASE")
    lock_release(LOCK_FRONT)
    
    print("Step 3: Tray -> 12600 steps to FRONT (rear handoff)")
    tray_move(LOCK_DISTANCE, 0)
    
    print("Step 4: Rear lock -> GRAB")
    lock_grab(LOCK_REAR)
    
    print("Step 5: Tray -> BACK endstop")
    tray_to_endstop(ENDSTOP_BACK)
    
    print("Step 6: Rear lock -> RELEASE")
    lock_release(LOCK_REAR, strong=True)
    
    print("Step 7: Tray -> CENTER")
    tray_move(TRAY_CENTER, 0)
    
    cleanup()
    print("=== DONE: Shelf in cell, tray at center ===")

# === ПЕРЕДНИЙ РЯД (depth=1) ===

def extract_front():
    """Извлечь полочку из переднего ряда"""
    print("=== EXTRACT FRONT SHELF ===")
    setup()
    
    print("Step 1: Tray -> FRONT endstop")
    tray_to_endstop(ENDSTOP_FRONT)
    
    print("Step 2: Front lock -> GRAB")
    lock_grab(LOCK_FRONT)
    
    print("Step 3: Tray -> 16900 steps to BACK (front handoff at 5700)")
    tray_move(16900, 1)
    
    print("Step 4: Front lock -> RELEASE")
    lock_release(LOCK_FRONT)
    
    print("Step 5: Tray -> 12600 steps to FRONT (rear handoff at 18300)")
    tray_move(LOCK_DISTANCE, 0)
    
    print("Step 6: Rear lock -> GRAB")
    lock_grab(LOCK_REAR)
    
    print("Step 7: Tray -> 12600 steps to BACK (front handoff at 5700)")
    tray_move(LOCK_DISTANCE, 1)
    
    cleanup()
    print("=== DONE: Shelf on carriage, rear lock holding ===")

def return_front():
    """Вернуть полочку в передний ряд"""
    print("=== RETURN FRONT SHELF ===")
    setup()
    
    print("Step 1: Tray -> 12600 steps to FRONT (rear handoff at 18300)")
    tray_move(LOCK_DISTANCE, 0)
    
    print("Step 2: Rear lock -> RELEASE")
    lock_release(LOCK_REAR)
    
    print("Step 3: Tray -> 12600 steps to BACK (front handoff at 5700)")
    tray_move(LOCK_DISTANCE, 1)
    
    print("Step 4: Front lock -> GRAB")
    lock_grab(LOCK_FRONT)
    
    print("Step 5: Tray -> FRONT endstop")
    tray_to_endstop(ENDSTOP_FRONT)
    
    print("Step 6: Front lock -> RELEASE")
    lock_release(LOCK_FRONT, strong=True)
    
    print("Step 7: Tray -> CENTER")
    tray_move(TRAY_CENTER, 1)
    
    cleanup()
    print("=== DONE: Shelf in cell, tray at center ===")

# === КРОСС-РЯДНЫЕ ОПЕРАЦИИ ===

def front_to_rear():
    """Переложить полочку из переднего ряда в задний"""
    print("=== FRONT TO REAR ===")
    
    # Извлекаем из переднего
    extract_front()
    
    # Перекладываем в задний
    # После extract_front: задний замок держит, ~5700 от BACK
    print("\n=== TRANSFER TO REAR ===")
    setup()
    
    print("Step 1: Rear lock -> RELEASE")
    lock_release(LOCK_REAR)
    
    print("Step 2: Tray -> 12600 to FRONT")
    tray_move(LOCK_DISTANCE, 0)
    
    print("Step 3: Front lock -> GRAB")
    lock_grab(LOCK_FRONT)
    
    print("Step 4: Tray -> 12600 to BACK")
    tray_move(LOCK_DISTANCE, 1)
    
    print("Step 5: Front lock -> RELEASE")
    lock_release(LOCK_FRONT)
    
    print("Step 6: Tray -> 12500 to FRONT")
    tray_move(CROSS_FRONT_TO_REAR_STEP6, 0)
    
    print("Step 7: Rear lock -> GRAB")
    lock_grab(LOCK_REAR)
    
    print("Step 8: Tray -> BACK endstop")
    tray_to_endstop(ENDSTOP_BACK)
    
    print("Step 9: Rear lock -> RELEASE")
    lock_release(LOCK_REAR, strong=True)
    
    print("Step 10: Tray -> CENTER")
    tray_move(TRAY_CENTER, 0)
    
    cleanup()
    print("=== DONE: Shelf moved from front to rear ===")

def rear_to_front():
    """Переложить полочку из заднего ряда в передний"""
    print("=== REAR TO FRONT ===")
    
    # Извлекаем из заднего
    extract_rear()
    
    # Перекладываем в передний
    # После extract_rear: передний замок держит, ~16800 от BACK
    print("\n=== TRANSFER TO FRONT ===")
    setup()
    
    print("Step 1: Front lock -> RELEASE")
    lock_release(LOCK_FRONT)
    
    print("Step 2: Tray -> 12600 to BACK")
    tray_move(LOCK_DISTANCE, 1)
    
    print("Step 3: Rear lock -> GRAB")
    lock_grab(LOCK_REAR)
    
    print("Step 4: Tray -> 12700 to FRONT")
    tray_move(CROSS_REAR_TO_FRONT_STEP4, 0)
    
    print("Step 5: Rear lock -> RELEASE")
    lock_release(LOCK_REAR)
    
    print("Step 6: Tray -> 12600 to BACK")
    tray_move(CROSS_REAR_TO_FRONT_STEP6, 1)
    
    print("Step 7: Front lock -> GRAB")
    lock_grab(LOCK_FRONT)
    
    print("Step 8: Tray -> FRONT endstop")
    tray_to_endstop(ENDSTOP_FRONT)
    
    print("Step 9: Front lock -> RELEASE")
    lock_release(LOCK_FRONT, strong=True)
    
    print("Step 10: Tray -> CENTER")
    tray_move(TRAY_CENTER, 1)
    
    cleanup()
    print("=== DONE: Shelf moved from rear to front ===")

# === MAIN ===
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    cmd = sys.argv[1]
    
    commands = {
        "extract_rear": extract_rear,
        "return_rear": return_rear,
        "extract_front": extract_front,
        "return_front": return_front,
        "front_to_rear": front_to_rear,
        "rear_to_front": rear_to_front,
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
