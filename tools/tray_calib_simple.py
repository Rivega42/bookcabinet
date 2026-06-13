#!/usr/bin/env python3
"""Простая калибровка платформы — с debounce проверкой"""
import pigpio
import time

pi = pigpio.pi()

STEP = 18
DIR = 27
EN1 = 25
EN2 = 26
FRONT = 7
BACK = 20
FREQ = 12000

# Setup
for p in [STEP, DIR, EN1, EN2]:
    pi.set_mode(p, pigpio.OUTPUT)
pi.write(EN1, 1)
pi.write(EN2, 1)

pi.set_mode(FRONT, pigpio.INPUT)
pi.set_mode(BACK, pigpio.INPUT)
pi.set_pull_up_down(FRONT, pigpio.PUD_UP)
pi.set_pull_up_down(BACK, pigpio.PUD_UP)
pi.set_glitch_filter(FRONT, 1000)
pi.set_glitch_filter(BACK, 1000)
time.sleep(0.1)

# Create wave
period_us = int(1000000 / FREQ)
pulse_us = period_us // 2
pi.wave_clear()
pi.wave_add_generic([
    pigpio.pulse(1 << STEP, 0, pulse_us),
    pigpio.pulse(0, 1 << STEP, pulse_us)
])
wave_id = pi.wave_create()

def sensor_stable(sensor, count=5):
    """Проверить что концевик стабильно нажат count раз подряд"""
    for _ in range(count):
        if pi.read(sensor) == 0:
            return False
        time.sleep(0.001)
    return True

def move_until_endstop(direction, sensor, name):
    """Движение до стабильного срабатывания концевика"""
    pi.write(EN1, 0)
    pi.write(EN2, 0)
    pi.write(DIR, direction)
    time.sleep(0.01)
    
    print(f"Moving to {name}... (Ctrl+C to stop)")
    pi.wave_send_repeat(wave_id)
    
    start = time.time()
    steps = 0
    while not sensor_stable(sensor, 5):
        time.sleep(0.001)
        steps += int(FREQ * 0.001)
    
    pi.wave_tx_stop()
    pi.write(EN1, 1)
    pi.write(EN2, 1)
    
    elapsed = time.time() - start
    print(f"{name} done after {steps} steps ({elapsed:.2f}s)")
    return steps

try:
    print(f"Initial: FRONT={pi.read(FRONT)} BACK={pi.read(BACK)}")
    print()
    
    move_until_endstop(0, FRONT, "FRONT")
    time.sleep(0.5)
    
    total = move_until_endstop(1, BACK, "BACK")
    time.sleep(0.5)
    
    center = total // 2
    print(f"\nMoving to CENTER ({center} steps)...")
    
    pi.write(EN1, 0)
    pi.write(EN2, 0)
    pi.write(DIR, 0)  # к FRONT
    time.sleep(0.01)
    pi.wave_send_repeat(wave_id)
    time.sleep(center / FREQ)
    pi.wave_tx_stop()
    pi.write(EN1, 1)
    pi.write(EN2, 1)
    
    print(f"\n=== Total: {total} steps, Center: {center} ===")
    
except KeyboardInterrupt:
    print("\nПрервано")
    pi.wave_tx_stop()
    
finally:
    pi.write(EN1, 1)
    pi.write(EN2, 1)
    pi.wave_delete(wave_id)
    pi.stop()
