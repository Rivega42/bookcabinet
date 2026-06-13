#!/usr/bin/env python3
"""Тест всех датчиков и концевиков BookCabinet"""
import RPi.GPIO as GPIO
import time
from config import GPIO_PINS

# Настройка GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Список всех датчиков из конфигурации
SENSORS = {
    'platform_top': GPIO_PINS['SENSORS']['PLATFORM_TOP'],
    'platform_bottom': GPIO_PINS['SENSORS']['PLATFORM_BOTTOM'],
    'corexy_left': GPIO_PINS['SENSORS']['COREXY_LEFT'],
    'corexy_right': GPIO_PINS['SENSORS']['COREXY_RIGHT'],
    'corexy_front': GPIO_PINS['SENSORS']['COREXY_FRONT'],
    'corexy_back': GPIO_PINS['SENSORS']['COREXY_BACK'],
    'door_main': GPIO_PINS['SENSORS']['DOOR_MAIN'],
    'door_service': GPIO_PINS['SENSORS']['DOOR_SERVICE'],
    'shutter_left': GPIO_PINS['SENSORS']['SHUTTER_LEFT'],
    'shutter_right': GPIO_PINS['SENSORS']['SHUTTER_RIGHT']
}

# Инициализация всех пинов как входов с подтяжкой
for name, pin in SENSORS.items():
    if pin and pin > 0:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        print(f"✓ {name:20} GPIO{pin:2} настроен")

print("\n" + "="*60)
print("ТЕСТ ДАТЧИКОВ - нажимайте концевики для проверки")
print("="*60)
print("\nФормат: [Название] GPIO[пин] = [состояние] (НАЖАТ/отпущен)")
print("Помните: логика инвертирована - LOW = НАЖАТ!\n")
print("Нажмите Ctrl+C для выхода\n")

# Словарь для отслеживания предыдущих состояний
prev_states = {}

try:
    while True:
        output = []
        changed = False
        
        for name, pin in SENSORS.items():
            if pin and pin > 0:
                # Читаем состояние (инверсия: LOW = нажат)
                raw_state = GPIO.input(pin)
                pressed = (raw_state == GPIO.LOW)
                
                # Проверяем изменение
                if name not in prev_states:
                    prev_states[name] = pressed
                
                if prev_states[name] != pressed:
                    changed = True
                    prev_states[name] = pressed
                
                # Форматируем вывод
                status = "НАЖАТ" if pressed else "отпущен"
                color = "\033[92m" if pressed else "\033[90m"  # Зелёный/серый
                reset = "\033[0m"
                
                output.append(f"{color}{name:20} GPIO{pin:2} = {status:8}{reset}")
        
        # Обновляем экран только при изменениях
        if changed:
            print("\033[H\033[J")  # Очистка экрана
            print("="*60)
            print("МОНИТОРИНГ ДАТЧИКОВ (Ctrl+C для выхода)")
            print("="*60)
            print()
            
            for line in output:
                print(line)
            
            print("\n" + "="*60)
            print("Подсказки:")
            print("- Платформа: проверьте верхний и нижний концевики")
            print("- CoreXY: проверьте все 4 концевика (лево/право/перед/зад)")
            print("- Двери: откройте/закройте основную и сервисную")
            print("- Шторки: проверьте левую и правую")
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n\nТест завершён")
finally:
    GPIO.cleanup()
