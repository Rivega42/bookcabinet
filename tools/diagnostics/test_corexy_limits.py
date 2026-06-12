#!/usr/bin/env python3
"""
Тест CoreXY моторов с концевиками.

Управление:
  W/S - движение по Y (вверх/вниз)
  A/D - движение по X (влево/вправо)
  +/- - изменить скорость
  Q   - выход

При срабатывании концевика - остановка.

Запуск:
  python3 tools/test_corexy_limits.py
"""

import RPi.GPIO as GPIO
import time
import sys
import tty
import termios
import select

# === GPIO пины (из config.py) ===
# Моторы
MOTOR_A_STEP = 2
MOTOR_A_DIR = 3
MOTOR_B_STEP = 19
MOTOR_B_DIR = 21

# Концевики (HIGH = сработал!)
SENSOR_LEFT = 9
SENSOR_RIGHT = 10
SENSOR_BOTTOM = 8
SENSOR_TOP = 11

# === Параметры движения ===
# Скорость: шагов/сек (из config.py: xy=4000)
# Но Python GPIO медленнее, начнём с 1000 и можно менять
SPEED = 1000  # шагов/сек
STEPS_PER_MOVE = 100  # шагов за одно нажатие


def calc_delay(speed):
    """Рассчитать задержку между импульсами"""
    return 1.0 / (2 * speed)


def setup_gpio():
    """Инициализация GPIO"""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Моторы - выходы
    for pin in [MOTOR_A_STEP, MOTOR_A_DIR, MOTOR_B_STEP, MOTOR_B_DIR]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    
    # Датчики - входы с подтяжкой
    for pin in [SENSOR_LEFT, SENSOR_RIGHT, SENSOR_BOTTOM, SENSOR_TOP]:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def read_sensors():
    """Чтение датчиков (True = сработал)"""
    return {
        'left': GPIO.input(SENSOR_LEFT) == GPIO.HIGH,
        'right': GPIO.input(SENSOR_RIGHT) == GPIO.HIGH,
        'bottom': GPIO.input(SENSOR_BOTTOM) == GPIO.HIGH,
        'top': GPIO.input(SENSOR_TOP) == GPIO.HIGH,
    }


def step_motors(a_dir, b_dir, steps, block_sensor=None):
    """
    Шаги моторов CoreXY.
    
    CoreXY логика:
      X+ (вправо): A+, B+
      X- (влево):  A-, B-
      Y+ (вверх):  A+, B-
      Y- (вниз):   A-, B+
    """
    global SPEED
    delay = calc_delay(SPEED)
    
    GPIO.output(MOTOR_A_DIR, a_dir)
    GPIO.output(MOTOR_B_DIR, b_dir)
    time.sleep(0.001)
    
    for i in range(steps):
        # Проверяем только датчик в направлении движения
        if block_sensor:
            sensors = read_sensors()
            if sensors.get(block_sensor):
                return block_sensor, i
        
        # Шаг обоих моторов
        GPIO.output(MOTOR_A_STEP, GPIO.HIGH)
        GPIO.output(MOTOR_B_STEP, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(MOTOR_A_STEP, GPIO.LOW)
        GPIO.output(MOTOR_B_STEP, GPIO.LOW)
        time.sleep(delay)
    
    return None, steps


def move_up(steps=STEPS_PER_MOVE):
    """Вверх - блокируем только TOP"""
    return step_motors(1, 0, steps, 'top')


def move_down(steps=STEPS_PER_MOVE):
    """Вниз - блокируем только BOTTOM"""
    return step_motors(0, 1, steps, 'bottom')


def move_left(steps=STEPS_PER_MOVE):
    """Влево - блокируем только LEFT"""
    return step_motors(0, 0, steps, 'left')


def move_right(steps=STEPS_PER_MOVE):
    """Вправо - блокируем только RIGHT"""
    return step_motors(1, 1, steps, 'right')


def print_status():
    """Вывод состояния датчиков"""
    s = read_sensors()
    active = [k.upper() for k, v in s.items() if v]
    sensors_str = ' '.join(active) if active else '---'
    print(f"  [{sensors_str}] Speed: {SPEED} steps/sec")


def get_key():
    """Неблокирующее чтение клавиши"""
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1)
    return None


def main():
    global SPEED
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║            ТЕСТ CoreXY С КОНЦЕВИКАМИ                         ║
╠══════════════════════════════════════════════════════════════╣
║  Управление:                                                 ║
║    W - вверх      S - вниз                                   ║
║    A - влево      D - вправо                                 ║
║    + - быстрее    - - медленнее                              ║
║    Q - выход                                                 ║
║                                                              ║
║  Движение блокируется только если едем В датчик!             ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    setup_gpio()
    
    # Сохраняем настройки терминала
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setcbreak(sys.stdin.fileno())
        
        print("Ready. WASD=move, +/-=speed, Q=quit\n")
        print_status()
        
        while True:
            key = get_key()
            
            if key == 'q' or key == 'Q':
                print("\nExit...")
                break
            
            # Изменение скорости
            if key == '+' or key == '=':
                SPEED = min(SPEED + 500, 5000)
                print(f"Speed: {SPEED}")
                continue
            if key == '-' or key == '_':
                SPEED = max(SPEED - 500, 500)
                print(f"Speed: {SPEED}")
                continue
            
            triggered = None
            done_steps = 0
            
            if key == 'w' or key == 'W':
                print("UP...", end=' ', flush=True)
                triggered, done_steps = move_up()
                print(f"STOP @{done_steps}" if triggered else f"ok ({done_steps})")
                
            elif key == 's' or key == 'S':
                print("DOWN...", end=' ', flush=True)
                triggered, done_steps = move_down()
                print(f"STOP @{done_steps}" if triggered else f"ok ({done_steps})")
                
            elif key == 'a' or key == 'A':
                print("LEFT...", end=' ', flush=True)
                triggered, done_steps = move_left()
                print(f"STOP @{done_steps}" if triggered else f"ok ({done_steps})")
                
            elif key == 'd' or key == 'D':
                print("RIGHT...", end=' ', flush=True)
                triggered, done_steps = move_right()
                print(f"STOP @{done_steps}" if triggered else f"ok ({done_steps})")
            
            if key and key.lower() in ['w', 'a', 's', 'd']:
                print_status()
            
            time.sleep(0.05)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        GPIO.cleanup()
        print("GPIO cleanup done")


if __name__ == "__main__":
    main()
