#!/usr/bin/env python3
"""Статистика концевиков — частота и время в состояниях"""
import pigpio
import time

pi = pigpio.pi()

FRONT = 7
BACK = 20

pi.set_mode(FRONT, pigpio.INPUT)
pi.set_mode(BACK, pigpio.INPUT)
pi.set_pull_up_down(FRONT, pigpio.PUD_UP)
pi.set_pull_up_down(BACK, pigpio.PUD_UP)
pi.set_glitch_filter(FRONT, 1000)
pi.set_glitch_filter(BACK, 1000)
time.sleep(0.1)

print("Статистика концевиков (Ctrl+C для выхода)")
print("FRONT=GPIO7, BACK=GPIO20")
print("-" * 60)

# Счётчики
front_changes = 0
back_changes = 0
front_time_1 = 0
front_time_0 = 0
back_time_1 = 0
back_time_0 = 0

prev_front = pi.read(FRONT)
prev_back = pi.read(BACK)
prev_time = time.time()
start_time = time.time()
last_print = time.time()

try:
    while True:
        now = time.time()
        dt = now - prev_time
        
        f = pi.read(FRONT)
        b = pi.read(BACK)
        
        # Накапливаем время
        if prev_front == 1:
            front_time_1 += dt
        else:
            front_time_0 += dt
            
        if prev_back == 1:
            back_time_1 += dt
        else:
            back_time_0 += dt
        
        # Считаем переключения
        if f != prev_front:
            front_changes += 1
            prev_front = f
        if b != prev_back:
            back_changes += 1
            prev_back = b
        
        prev_time = now
        
        # Вывод каждые 0.5 сек
        if now - last_print >= 0.5:
            elapsed = now - start_time
            f_hz = front_changes / elapsed if elapsed > 0 else 0
            b_hz = back_changes / elapsed if elapsed > 0 else 0
            
            print(f"FRONT: val={f} changes={front_changes} ({f_hz:.1f}Hz) time_0={front_time_0*1000:.0f}ms time_1={front_time_1*1000:.0f}ms")
            print(f"BACK:  val={b} changes={back_changes} ({b_hz:.1f}Hz) time_0={back_time_0*1000:.0f}ms time_1={back_time_1*1000:.0f}ms")
            print()
            last_print = now
        
        time.sleep(0.001)
        
except KeyboardInterrupt:
    print("\nИтого:")
    elapsed = time.time() - start_time
    print(f"FRONT: {front_changes} переключений за {elapsed:.1f}с ({front_changes/elapsed:.1f}Hz)")
    print(f"BACK:  {back_changes} переключений за {elapsed:.1f}с ({back_changes/elapsed:.1f}Hz)")
finally:
    pi.stop()
