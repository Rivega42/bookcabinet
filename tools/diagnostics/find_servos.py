#!/usr/bin/env python3
"""
Поиск сервоприводов на всех GPIO пинах.
Перебирает все доступные пины и подаёт PWM сигнал.

Использование:
  python3 tools/find_servos.py
"""

import RPi.GPIO as GPIO
import time

# Все GPIO пины которые можно использовать на RPi3
# Исключаем: 0,1 (I2C EEPROM), и те что уже заняты известными функциями
ALL_GPIO = [
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
    14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27
]

def test_servo(pin):
    """Подать PWM сигнал на пин как для серво"""
    try:
        GPIO.setup(pin, GPIO.OUT)
        pwm = GPIO.PWM(pin, 50)  # 50 Hz
        pwm.start(0)
        
        # Позиция 1
        pwm.ChangeDutyCycle(5)
        time.sleep(0.4)
        
        # Позиция 2
        pwm.ChangeDutyCycle(10)
        time.sleep(0.4)
        
        # Позиция 3
        pwm.ChangeDutyCycle(7.5)
        time.sleep(0.3)
        
        pwm.stop()
        GPIO.setup(pin, GPIO.IN)  # Освободить пин
        return True
    except Exception as e:
        return False

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║              ПОИСК СЕРВОПРИВОДОВ НА GPIO                     ║
╠══════════════════════════════════════════════════════════════╣
║  Скрипт будет подавать PWM сигнал на каждый GPIO.           ║
║  Смотри какие сервоприводы дёргаются!                        ║
║                                                              ║
║  Введи:                                                      ║
║    1 = двигалась серва Lock1 (передний замок)               ║
║    2 = двигалась серва Lock2 (задний замок)                 ║
║    Enter = ничего не двигалось                               ║
║    q = выход                                                 ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    input("Нажми Enter чтобы начать...")
    
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    found_servo1 = None
    found_servo2 = None
    
    try:
        for pin in ALL_GPIO:
            print(f"\n>>> GPIO {pin:2d} - подаю PWM...", end=" ", flush=True)
            
            if test_servo(pin):
                response = input("Что двигалось? (1/2/Enter/q): ").strip().lower()
                
                if response == 'q':
                    break
                elif response == '1':
                    found_servo1 = pin
                    print(f"    ✓ Servo Lock1 найдена на GPIO {pin}!")
                elif response == '2':
                    found_servo2 = pin
                    print(f"    ✓ Servo Lock2 найдена на GPIO {pin}!")
                else:
                    print("    - ничего")
            else:
                print("skip")
                
    except KeyboardInterrupt:
        print("\n\nПрервано")
    
    finally:
        GPIO.cleanup()
        
        # Итог
        print("\n")
        print("=" * 60)
        print("РЕЗУЛЬТАТ ПОИСКА")
        print("=" * 60)
        
        if found_servo1:
            print(f"✓ Servo Lock1 (FRONT): GPIO {found_servo1}")
            if found_servo1 != 18:
                print(f"  ⚠️  В документации GPIO 18, факт GPIO {found_servo1}")
                print(f"  → Нужно исправить config.py или переткнуть провод!")
        else:
            print("✗ Servo Lock1: НЕ НАЙДЕНА")
            
        if found_servo2:
            print(f"✓ Servo Lock2 (BACK): GPIO {found_servo2}")
            if found_servo2 != 13:
                print(f"  ⚠️  В документации GPIO 13, факт GPIO {found_servo2}")
                print(f"  → Нужно исправить config.py или переткнуть провод!")
        else:
            print("✗ Servo Lock2: НЕ НАЙДЕНА")
        
        print()
        
        if found_servo1 or found_servo2:
            print("=" * 60)
            print("ИСПРАВЛЕНИЕ В config.py:")
            print("=" * 60)
            print()
            print("LOCKS = {")
            print(f"    'lock1': {found_servo1 if found_servo1 else '???'},  # Servo Lock1 FRONT")
            print(f"    'lock2': {found_servo2 if found_servo2 else '???'},  # Servo Lock2 BACK")
            print("}")

if __name__ == "__main__":
    main()
