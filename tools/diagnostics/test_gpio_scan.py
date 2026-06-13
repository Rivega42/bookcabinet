#!/usr/bin/env python3
"""
Перебор всех GPIO пинов для диагностики подключений.
Поочерёдно активирует каждый пин - смотри что двигается!

Использование:
  python3 tools/test_gpio_scan.py
"""

import RPi.GPIO as GPIO
import time

# Все выходные пины по документации RPI3_WIRING_FINAL
OUTPUT_PINS = {
    # Сервоприводы (PWM)
    18: "Servo Lock1 (FRONT) - клемма J",
    13: "Servo Lock2 (BACK) - клемма K",
    
    # Шторки (реле)
    14: "Шторка внешняя - клемма 7",
    15: "Шторка внутренняя - клемма 6",
    
    # Motor A
    2: "Motor A STEP - клемма 2",
    3: "Motor A DIR - клемма 3",
    
    # Motor B
    19: "Motor B STEP - клемма L",
    21: "Motor B DIR - клемма N",
    
    # Tray Motor
    24: "Tray STEP - Pin 18 (штырь)",
    25: "Tray DIR - Pin 22 (штырь)",
}

def test_pin(pin, name):
    """Тест одного пина"""
    print(f"\n{'='*60}")
    print(f"GPIO {pin}: {name}")
    print(f"{'='*60}")
    
    GPIO.setup(pin, GPIO.OUT)
    
    print(">>> Включаю (HIGH)... СМОТРИ ЧТО ДВИГАЕТСЯ!")
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(1.5)
    
    print(">>> Выключаю (LOW)...")
    GPIO.output(pin, GPIO.LOW)
    time.sleep(0.5)
    
    # Для сервоприводов попробуем PWM
    if pin in [18, 13]:
        print(">>> Пробую PWM (серво должно двигаться)...")
        pwm = GPIO.PWM(pin, 50)  # 50 Hz для серво
        pwm.start(0)
        
        # Позиция 0° (5%)
        print("    -> Угол ~0° (5%)")
        pwm.ChangeDutyCycle(5)
        time.sleep(0.8)
        
        # Позиция 90° (7.5%)
        print("    -> Угол ~90° (7.5%)")
        pwm.ChangeDutyCycle(7.5)
        time.sleep(0.8)
        
        # Позиция 180° (10%)
        print("    -> Угол ~180° (10%)")
        pwm.ChangeDutyCycle(10)
        time.sleep(0.8)
        
        pwm.stop()
    
    response = input("\nЧто произошло? (Enter - ничего, или опиши): ").strip()
    return response

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         ДИАГНОСТИКА GPIO - ПЕРЕБОР ВСЕХ ПИНОВ               ║
╠══════════════════════════════════════════════════════════════╣
║  Скрипт будет поочерёдно активировать каждый GPIO пин.      ║
║  Смотри на шкаф и записывай что реально двигается!          ║
║                                                              ║
║  После каждого пина - опиши что видел.                      ║
║  Ctrl+C - выход                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    input("Нажми Enter чтобы начать...")
    
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    results = {}
    
    try:
        for pin, name in OUTPUT_PINS.items():
            response = test_pin(pin, name)
            results[pin] = response
            
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
    
    finally:
        GPIO.cleanup()
        
        # Итоговый отчёт
        print("\n")
        print("=" * 60)
        print("ИТОГОВЫЙ ОТЧЁТ")
        print("=" * 60)
        print(f"{'GPIO':<6} {'Ожидалось':<30} {'Факт':<20}")
        print("-" * 60)
        
        for pin, name in OUTPUT_PINS.items():
            fact = results.get(pin, "не проверен")
            short_name = name.split(" - ")[0][:28]
            print(f"{pin:<6} {short_name:<30} {fact:<20}")
        
        # Ищем несоответствия
        print("\n" + "=" * 60)
        print("ПРОБЛЕМЫ (если есть):")
        print("=" * 60)
        
        problems = []
        for pin, fact in results.items():
            if fact and fact.lower() not in ["", "ничего", "нет", "норм", "ок", "ok"]:
                expected = OUTPUT_PINS[pin].split(" - ")[0]
                if expected.lower() not in fact.lower():
                    problems.append(f"GPIO {pin}: ожидался '{expected}', факт: '{fact}'")
        
        if problems:
            for p in problems:
                print(f"  ⚠️  {p}")
        else:
            print("  ✓ Всё соответствует или не указано")

if __name__ == "__main__":
    main()
