#!/usr/bin/env python3
"""
CoreXY движение через pigpio — wave_chain + callback.
Мгновенная остановка на концевике через wave_tx_stop().
"""
import pigpio
import time
import sys

# === Пины ===
MOTOR_A_STEP = 14
MOTOR_A_DIR  = 15
MOTOR_B_STEP = 19
MOTOR_B_DIR  = 21

SENSOR_LEFT   = 9
SENSOR_RIGHT  = 10
SENSOR_BOTTOM = 8
SENSOR_TOP    = 11

# === Параметры ===
FAST = 1500    # шагов/сек
SLOW = 400     # шагов/сек (хоминг медленная фаза)
BACK = 200     # шагов отъезда
WAVE_SEG = 200 # шагов в одном сегменте wave_chain

# === Защита: какой концевик блокирует какое направление ===
# (a_dir, b_dir) → sensor_pin
DIR_TO_SENSOR = {
    (0, 1): SENSOR_BOTTOM,  # Y→BOTTOM
    (1, 0): SENSOR_TOP,     # Y→TOP
    (1, 1): SENSOR_RIGHT,   # X→RIGHT
    (0, 0): SENSOR_LEFT,    # X→LEFT
}

pi = pigpio.pi()
if not pi.connected:
    print("ОШИБКА: pigpiod не запущен! sudo pigpiod")
    sys.exit(1)

# Настройка пинов
for p in [MOTOR_A_STEP, MOTOR_A_DIR, MOTOR_B_STEP, MOTOR_B_DIR]:
    pi.set_mode(p, pigpio.OUTPUT)
    pi.write(p, 0)
for p in [SENSOR_LEFT, SENSOR_RIGHT, SENSOR_BOTTOM, SENSOR_TOP]:
    pi.set_mode(p, pigpio.INPUT)
    pi.set_pull_up_down(p, pigpio.PUD_UP)
# Glitch filter на X концевики (шум при движении)
pi.set_glitch_filter(SENSOR_LEFT, 300)
pi.set_glitch_filter(SENSOR_RIGHT, 300)
pi.set_glitch_filter(SENSOR_BOTTOM, 300)
pi.set_glitch_filter(SENSOR_TOP, 300)

STEP_MASK = (1 << MOTOR_A_STEP) | (1 << MOTOR_B_STEP)

# Глобальный флаг для callback
_hit = False


def _on_endstop(gpio, level, tick):
    global _hit
    if not _hit:
        _hit = True
        pi.wave_tx_stop()


def step_pigpio(a_dir, b_dir, n, speed, stop_sensor=None):
    """
    Выполнить до n шагов через DMA wave_chain.
    stop_sensor: пин концевика — при срабатывании мгновенная остановка.
    Возвращает True если концевик сработал, False если нет.
    """
    global _hit
    _hit = False

    # Защита: не двигаемся в сторону нажатого концевика
    block_sensor = DIR_TO_SENSOR.get((a_dir, b_dir))
    if block_sensor is not None and pi.read(block_sensor) == 1:
        print(f"  ⛔ Концевик pin {block_sensor} нажат — движение заблокировано!")
        return False

    pi.write(MOTOR_A_DIR, a_dir)
    pi.write(MOTOR_B_DIR, b_dir)
    time.sleep(0.001)

    # Callback на концевик
    cb = None
    if stop_sensor is not None:
        cb = pi.callback(stop_sensor, pigpio.RISING_EDGE, _on_endstop)

    # Создаём сегмент волны
    half_us = int(1_000_000 / (2 * speed))
    pulses = []
    seg_actual = min(n, WAVE_SEG)
    for _ in range(seg_actual):
        pulses.append(pigpio.pulse(STEP_MASK, 0, half_us))
        pulses.append(pigpio.pulse(0, STEP_MASK, half_us))
    pi.wave_clear()
    pi.wave_add_generic(pulses)
    wid = pi.wave_create()
    if wid < 0:
        if cb:
            cb.cancel()
        raise RuntimeError(f"wave_create error: {wid}")

    # wave_chain: полные сегменты
    seg_actual = min(n, WAVE_SEG)
    full_reps = max(1, n // seg_actual)
    remainder = n % seg_actual if n > seg_actual else 0
    chain = bytes([255, 0, wid, 255, 1, full_reps & 0xFF, (full_reps >> 8) & 0xFF])
    pi.wave_chain(chain)

    # Ждём основные шаги
    t0 = time.time()
    while pi.wave_tx_busy():
        time.sleep(0.002)
        if _hit or time.time() - t0 > 60:
            pi.wave_tx_stop()
            break

    # Остаточные шаги (n % WAVE_SEG)
    if remainder > 0 and not _hit:
        rem_pulses = []
        for _ in range(remainder):
            rem_pulses.append(pigpio.pulse(STEP_MASK, 0, half_us))
            rem_pulses.append(pigpio.pulse(0, STEP_MASK, half_us))
        pi.wave_clear()
        pi.wave_add_generic(rem_pulses)
        wid2 = pi.wave_create()
        if wid2 >= 0:
            pi.wave_chain(bytes([255, 0, wid2, 255, 1, 1, 0]))
            while pi.wave_tx_busy():
                time.sleep(0.002)
                if _hit: break
            pi.wave_delete(wid2)

    # (ожидание выполнено выше)

    if cb:
        cb.cancel()
    try:
        pi.wave_delete(wid)
    except Exception:
        pass
    pi.wave_clear()
    return _hit


def go(name, ad, bd, sensor, back_ad, back_bd):
    print(f"  {name}...", end=" ", flush=True)
    hit = step_pigpio(ad, bd, 100000, FAST, sensor)
    if hit:
        print("концевик!")
    else:
        print("не найден")
    step_pigpio(back_ad, back_bd, BACK, FAST)
    time.sleep(0.1)


def home_axis(name, ad, bd, sensor, back_ad, back_bd):
    print(f"  {name}...", end=" ", flush=True)
    step_pigpio(ad, bd, 100000, FAST, sensor)
    step_pigpio(back_ad, back_bd, BACK, FAST)
    time.sleep(0.1)
    hit = step_pigpio(ad, bd, BACK + 50, SLOW, sensor)
    if hit:
        print("HOME ✓")
    else:
        print("HOME ✗ (не найден)")


def main():
    print("=" * 50)
    print(f"  ОБХОД КОНЦЕВИКОВ (pigpio DMA, {FAST} шагов/сек)")
    print("=" * 50)

    go("X→LEFT",   0, 0, SENSOR_LEFT,   1, 1)
    go("Y→TOP",    1, 0, SENSOR_TOP,    0, 1)
    go("X→RIGHT",  1, 1, SENSOR_RIGHT,  0, 0)
    go("Y→BOTTOM", 0, 1, SENSOR_BOTTOM, 1, 0)

    time.sleep(0.3)
    print("\nХоминг:")
    home_axis("X→RIGHT",  1, 1, SENSOR_RIGHT,  0, 0)
    time.sleep(0.3)
    home_axis("Y→BOTTOM", 0, 1, SENSOR_BOTTOM, 1, 0)

    pi.stop()
    print("\n✓ HOME (RIGHT+BOTTOM)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pi.wave_tx_stop()
        pi.stop()
        print("\nПрервано")
