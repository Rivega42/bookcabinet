#!/usr/bin/env python3
"""Калибровка платформы: FRONT -> BACK -> CENTER с backoff"""
import pigpio
import time

pi = pigpio.pi()

STEP = 18
DIR = 27
EN1 = 25
EN2 = 26
FRONT = 7
BACK = 20

SPEED_FAST = 10000    # Быстрый подход
SPEED_BACKOFF = 2000  # Скорость отхода
SPEED_SLOW = 1500     # Медленный подход
BACKOFF_STEPS = 1500  # Шагов отхода

# Setup motors
for p in [STEP, DIR, EN1, EN2]:
    pi.set_mode(p, pigpio.OUTPUT)
pi.write(EN1, 1)
pi.write(EN2, 1)

# Setup endstops with filters
pi.set_mode(FRONT, pigpio.INPUT)
pi.set_mode(BACK, pigpio.INPUT)
pi.set_pull_up_down(FRONT, pigpio.PUD_UP)
pi.set_pull_up_down(BACK, pigpio.PUD_UP)
pi.set_glitch_filter(FRONT, 1000)
pi.set_glitch_filter(BACK, 1000)
time.sleep(0.1)

def create_wave(speed):
    period_us = int(1000000 / speed)
    pulse_us = period_us // 2
    pi.wave_clear()
    pi.wave_add_generic([
        pigpio.pulse(1 << STEP, 0, pulse_us),
        pigpio.pulse(0, 1 << STEP, pulse_us)
    ])
    return pi.wave_create()

def sensor_stable(sensor, count=10):
    for _ in range(count):
        if pi.read(sensor) == 0:
            return False
        time.sleep(0.0005)
    return True

def move_steps(direction, steps, speed):
    wave = create_wave(speed)
    
    pi.write(EN1, 0)
    pi.write(EN2, 0)
    pi.write(DIR, direction)
    time.sleep(0.05)
    
    pi.wave_send_repeat(wave)
    time.sleep(steps / speed)
    pi.wave_tx_stop()
    
    pi.write(EN1, 1)
    pi.write(EN2, 1)
    pi.wave_delete(wave)

def move_until(direction, sensor, speed):
    wave = create_wave(speed)
    
    pi.write(EN1, 0)
    pi.write(EN2, 0)
    pi.write(DIR, direction)
    time.sleep(0.05)
    
    pi.wave_send_repeat(wave)
    
    start = time.time()
    while not sensor_stable(sensor, 10):
        pass
    
    pi.wave_tx_stop()
    pi.write(EN1, 1)
    pi.write(EN2, 1)
    
    elapsed = time.time() - start
    steps = int(elapsed * speed)
    pi.wave_delete(wave)
    return steps

def home_to(direction, sensor, name):
    # Быстрый подход
    print(f"Moving to {name} (fast)...", end=" ", flush=True)
    move_until(direction, sensor, SPEED_FAST)
    print("hit!", end=" ", flush=True)
    
    # Отход
    backoff_dir = 1 if direction == 0 else 0
    move_steps(backoff_dir, BACKOFF_STEPS, SPEED_BACKOFF)
    print("backoff...", end=" ", flush=True)
    time.sleep(0.1)
    
    # Медленный подход
    steps = move_until(direction, sensor, SPEED_SLOW)
    print(f"OK (slow: {steps} steps)")
    return steps

try:
    print(f"Initial: FRONT={pi.read(FRONT)} BACK={pi.read(BACK)}")
    print()
    
    # 1. К FRONT с backoff
    home_to(0, FRONT, "FRONT")
    time.sleep(0.3)
    
    # 2. К BACK с backoff (измеряем total)
    print("Measuring total travel...")
    
    print("Moving to BACK (fast)...", end=" ", flush=True)
    fast_steps = move_until(1, BACK, SPEED_FAST)
    print("hit!", end=" ", flush=True)
    
    move_steps(0, BACKOFF_STEPS, SPEED_BACKOFF)
    print("backoff...", end=" ", flush=True)
    time.sleep(0.1)
    
    slow_steps = move_until(1, BACK, SPEED_SLOW)
    print(f"OK (slow: {slow_steps} steps)")
    
    total = fast_steps + slow_steps
    
    time.sleep(0.3)
    
    # 3. В CENTER
    center = total // 2
    print(f"Moving to CENTER ({center} steps)...", end=" ", flush=True)
    move_steps(0, center, SPEED_FAST)
    print("OK")
    
    print(f"\n=== Total: {total} steps, Center: {center} ===")
    
except KeyboardInterrupt:
    print("\nПрервано")
    pi.wave_tx_stop()
finally:
    pi.write(EN1, 1)
    pi.write(EN2, 1)
    try:
        pi.wave_clear()
    except:
        pass
    pi.stop()
