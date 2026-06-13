#!/usr/bin/env python3
"""Мониторинг концевиков платформы в реальном времени"""
import pigpio
import time
from datetime import datetime

pi = pigpio.pi()

# Setup с фильтрами
pi.set_mode(7, pigpio.INPUT)
pi.set_mode(20, pigpio.INPUT)
pi.set_pull_up_down(7, pigpio.PUD_UP)
pi.set_pull_up_down(20, pigpio.PUD_UP)
pi.set_glitch_filter(7, 1000)
pi.set_glitch_filter(20, 1000)
time.sleep(0.1)

log_file = open("/tmp/endstops.log", "w")

print("Мониторинг концевиков (Ctrl+C для выхода)")
print("FRONT=GPIO7, BACK=GPIO20")
print("-" * 50)

prev_front = prev_back = -1
start_time = time.time()
FREQ = 12000

try:
    while True:
        front = pi.read(7)
        back = pi.read(20)
        
        elapsed = time.time() - start_time
        steps = int(elapsed * FREQ)
        
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"{now} FRONT={front} BACK={back} steps={steps}"
        
        if front != prev_front or back != prev_back:
            print(f">>> {line} <<<")
            log_file.write(line + " CHANGED\n")
            log_file.flush()
            prev_front, prev_back = front, back
        else:
            print(line)
            log_file.write(line + "\n")
            log_file.flush()
        
        time.sleep(0.05)  # 20 Hz
except KeyboardInterrupt:
    print("\nСтоп")
finally:
    log_file.close()
    pi.stop()
