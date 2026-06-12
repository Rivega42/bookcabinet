#!/usr/bin/env python3
"""
Тест сервоприводов замков платформы
GPIO 18 (PWM0) — Lock1 (передний)
GPIO 13 (PWM1) — Lock2 (задний)

+ Мониторинг всех концевиков для проверки наводок
"""
import time
import sys

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("ERROR: RPi.GPIO not found. Run on Raspberry Pi!")
    sys.exit(1)

# Конфигурация замков
LOCK1_PIN = 18  # PWM0
LOCK2_PIN = 13  # PWM1

ANGLE_OPEN = 0      # Язычок опущен
ANGLE_CLOSE = 95    # Язычок поднят

PWM_FREQ = 50  # 50Hz для сервоприводов

# Конфигурация датчиков
SENSORS = {
    'X_BEGIN': 10,
    'X_END': 9,
    'Y_BEGIN': 11,
    'Y_END': 8,
    'TRAY_BEGIN': 7,
    'TRAY_END': 20,
}

# Пороги (из калибровки)
THRESHOLDS = {
    'X_BEGIN': {'high': 95, 'low': 85},
    'X_END': {'high': 95, 'low': 85},
    'Y_BEGIN': {'high': 95, 'low': 85},
    'Y_END': {'high': 95, 'low': 85},
    'TRAY_BEGIN': {'high': 95, 'low': 85},
    'TRAY_END': {'high': 95, 'low': 85},
}

SAMPLES = 50  # Для быстрого чтения


def angle_to_duty(angle):
    """Преобразование угла (0-180) в duty cycle (2-12%)"""
    return 2 + (angle / 180) * 10


def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Замки
    GPIO.setup(LOCK1_PIN, GPIO.OUT)
    GPIO.setup(LOCK2_PIN, GPIO.OUT)
    
    pwm1 = GPIO.PWM(LOCK1_PIN, PWM_FREQ)
    pwm2 = GPIO.PWM(LOCK2_PIN, PWM_FREQ)
    
    pwm1.start(0)
    pwm2.start(0)
    
    # Датчики
    for pin in SENSORS.values():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    return pwm1, pwm2


def read_sensor_percent(pin, samples=SAMPLES):
    """Читает датчик и возвращает % HIGH"""
    high_count = sum(1 for _ in range(samples) if GPIO.input(pin) == GPIO.HIGH)
    return int(high_count * 100 / samples)


def get_sensor_state(name, percent):
    """Определяет состояние датчика по порогам"""
    th = THRESHOLDS.get(name, {'high': 95, 'low': 85})
    if percent >= th['high']:
        return '🔴'  # Нажат
    elif percent <= th['low']:
        return '⚪'  # Открыт
    else:
        return '🟡'  # Переходное


def print_sensors(prefix=""):
    """Вывести состояние всех датчиков"""
    parts = []
    for name, pin in SENSORS.items():
        pct = read_sensor_percent(pin)
        state = get_sensor_state(name, pct)
        parts.append(f"{name}:{state}{pct:3d}%")
    print(f"{prefix}[{' | '.join(parts)}]")


def set_angle(pwm, angle, name=""):
    """Установить угол сервопривода"""
    duty = angle_to_duty(angle)
    print(f"  {name}: angle={angle}° duty={duty:.1f}%")
    pwm.ChangeDutyCycle(duty)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)
    print_sensors("  Sensors: ")


def test_lock(pwm, name):
    """Тест одного замка"""
    print(f"\n{'='*60}")
    print(f"  Testing {name}")
    print(f"{'='*60}")
    
    print_sensors("  Before: ")
    
    input(f"Press Enter to OPEN {name} (angle={ANGLE_OPEN})...")
    set_angle(pwm, ANGLE_OPEN, name)
    
    input(f"Press Enter to CLOSE {name} (angle={ANGLE_CLOSE})...")
    set_angle(pwm, ANGLE_CLOSE, name)
    
    print(f"  {name} test complete!")


def interactive_mode(pwm1, pwm2):
    """Интерактивный режим"""
    print("\n" + "="*60)
    print("  INTERACTIVE MODE")
    print("="*60)
    print("Commands:")
    print("  1o / 1c  — Lock1 open/close")
    print("  2o / 2c  — Lock2 open/close")
    print("  ao / ac  — All open/close")
    print("  1:45     — Lock1 to 45 degrees")
    print("  2:90     — Lock2 to 90 degrees")
    print("  s        — Show sensors")
    print("  q        — Quit")
    print()
    
    print_sensors("Initial: ")
    
    while True:
        try:
            cmd = input("Command: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
        
        if cmd == 'q':
            break
        elif cmd == 's':
            print_sensors("Sensors: ")
        elif cmd == '1o':
            set_angle(pwm1, ANGLE_OPEN, "Lock1")
        elif cmd == '1c':
            set_angle(pwm1, ANGLE_CLOSE, "Lock1")
        elif cmd == '2o':
            set_angle(pwm2, ANGLE_OPEN, "Lock2")
        elif cmd == '2c':
            set_angle(pwm2, ANGLE_CLOSE, "Lock2")
        elif cmd == 'ao':
            set_angle(pwm1, ANGLE_OPEN, "Lock1")
            set_angle(pwm2, ANGLE_OPEN, "Lock2")
        elif cmd == 'ac':
            set_angle(pwm1, ANGLE_CLOSE, "Lock1")
            set_angle(pwm2, ANGLE_CLOSE, "Lock2")
        elif ':' in cmd:
            try:
                lock, angle = cmd.split(':')
                angle = int(angle)
                if angle < 0 or angle > 180:
                    print("  Angle must be 0-180")
                    continue
                if lock == '1':
                    set_angle(pwm1, angle, "Lock1")
                elif lock == '2':
                    set_angle(pwm2, angle, "Lock2")
            except ValueError:
                print("  Invalid format. Use: 1:45 or 2:90")
        else:
            print("  Unknown command")


def main():
    print("="*60)
    print("  LOCK SERVO TEST + SENSOR MONITOR")
    print("="*60)
    print(f"Lock1: GPIO {LOCK1_PIN} (PWM0)")
    print(f"Lock2: GPIO {LOCK2_PIN} (PWM1)")
    print(f"Open angle: {ANGLE_OPEN}°, Close angle: {ANGLE_CLOSE}°")
    print(f"Sensors: {', '.join(SENSORS.keys())}")
    
    pwm1, pwm2 = setup()
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == '-i':
            interactive_mode(pwm1, pwm2)
        else:
            test_lock(pwm1, "Lock1")
            test_lock(pwm2, "Lock2")
            
            print("\n" + "="*60)
            print("  Run with -i for interactive mode")
            print("="*60)
    finally:
        pwm1.stop()
        pwm2.stop()
        GPIO.cleanup()
        print("\nGPIO cleanup done.")


if __name__ == '__main__':
    main()
