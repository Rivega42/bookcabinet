#!/usr/bin/env python3
"""
tray_calib_v2.py — калибровка платформы с backoff как в homing
"""
import pigpio
import time

STEP = 18
DIR = 27
EN1 = 25
EN2 = 26
FRONT = 7
BACK = 20

FAST = 3000  # Hz
SLOW = 1000   # Hz
BACKOFF = 500 # steps

pi = pigpio.pi()

def setup():
    pi.set_mode(FRONT, pigpio.INPUT)
    pi.set_mode(BACK, pigpio.INPUT)
    pi.set_pull_up_down(FRONT, pigpio.PUD_UP)
    pi.set_pull_up_down(BACK, pigpio.PUD_UP)
    pi.set_glitch_filter(FRONT, 1000)
    pi.set_glitch_filter(BACK, 1000)
    time.sleep(0.1)
    
    for p in [STEP, DIR, EN1, EN2]:
        pi.set_mode(p, pigpio.OUTPUT)
    pi.write(EN1, 1)
    pi.write(EN2, 1)

def move_steps(direction, steps, freq):
    """Двигать на steps шагов с частотой freq."""
    pi.write(EN1, 0)
    pi.write(EN2, 0)
    pi.write(DIR, direction)
    time.sleep(0.001)
    
    delay = 1.0 / freq / 2
    for _ in range(steps):
        pi.write(STEP, 1)
        time.sleep(delay)
        pi.write(STEP, 0)
        time.sleep(delay)
    
    pi.write(EN1, 1)
    pi.write(EN2, 1)

def move_until(direction, sensor, freq, max_steps=50000):
    """Двигать до срабатывания концевика."""
    pi.write(EN1, 0)
    pi.write(EN2, 0)
    pi.write(DIR, direction)
    time.sleep(0.001)
    
    delay = 1.0 / freq / 2
    steps = 0
    while pi.read(sensor) == 0 and steps < max_steps:
        pi.write(STEP, 1)
        time.sleep(delay)
        pi.write(STEP, 0)
        time.sleep(delay)
        steps += 1
    
    pi.write(EN1, 1)
    pi.write(EN2, 1)
    return steps, pi.read(sensor) == 1

def seek_endstop(name, direction, sensor, back_dir):
    """FAST -> BACKOFF -> SLOW"""
    print(f"[{name}] FAST...", end=" ", flush=True)
    steps, hit = move_until(direction, sensor, FAST)
    print(f"{"OK" if hit else "FAIL"} ({steps} steps)")
    if not hit:
        return 0, False
    
    print(f"[{name}] BACKOFF {BACKOFF}...", end=" ", flush=True)
    move_steps(back_dir, BACKOFF, SLOW)
    print("OK")
    time.sleep(0.05)
    
    print(f"[{name}] SLOW...", end=" ", flush=True)
    steps2, hit2 = move_until(direction, sensor, SLOW, BACKOFF + 200)
    print(f"{OK if hit2 else FAIL} ({steps2} steps)")
    
    return steps, hit2

def calibrate():
    setup()
    print(f"Initial: FRONT={pi.read(FRONT)} BACK={pi.read(BACK)}")
    print()
    
    seek_endstop("FRONT", 0, FRONT, 1)
    total, ok = seek_endstop("BACK", 1, BACK, 0)
    
    if not ok:
        print("\nCALIBRATION FAILED")
        return
    
    center = total // 2
    print(f"\nMoving to CENTER ({center} steps)...")
    move_steps(0, center, FAST)
    
    print(f"\n=== Total: {total} steps, Center: {center} ===")

if __name__ == "__main__":
    try:
        calibrate()
    finally:
        pi.write(EN1, 1)
        pi.write(EN2, 1)
        pi.stop()
