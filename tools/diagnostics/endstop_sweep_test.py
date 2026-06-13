#!/usr/bin/env python3
import pigpio
import time
import sys

MOTOR_A_STEP = 14
MOTOR_A_DIR  = 15
MOTOR_B_STEP = 19
MOTOR_B_DIR  = 21

SENSOR_LEFT   = 9
SENSOR_RIGHT  = 10
SENSOR_BOTTOM = 8
SENSOR_TOP    = 11

FAST = 800
BACKOFF = 300
WAVE_SEG = 200
STEP_MASK = (1 << MOTOR_A_STEP) | (1 << MOTOR_B_STEP)

pi = pigpio.pi()
if not pi.connected:
    sys.exit('ОШИБКА: pigpiod не запущен')

for p in [MOTOR_A_STEP, MOTOR_A_DIR, MOTOR_B_STEP, MOTOR_B_DIR]:
    pi.set_mode(p, pigpio.OUTPUT)
    pi.write(p, 0)

for p in [SENSOR_LEFT, SENSOR_RIGHT, SENSOR_BOTTOM, SENSOR_TOP]:
    pi.set_mode(p, pigpio.INPUT)
    pi.set_pull_up_down(p, pigpio.PUD_OFF)
    pi.set_glitch_filter(p, 300)


def sensor_state():
    return {
        'LEFT': pi.read(SENSOR_LEFT),
        'RIGHT': pi.read(SENSOR_RIGHT),
        'BOTTOM': pi.read(SENSOR_BOTTOM),
        'TOP': pi.read(SENSOR_TOP),
    }


def move(a_dir, b_dir, n, speed, stop_sensor=None):
    hit = False

    pi.write(MOTOR_A_DIR, a_dir)
    pi.write(MOTOR_B_DIR, b_dir)
    time.sleep(0.001)

    if stop_sensor is not None and pi.read(stop_sensor) == 1:
        return True

    def _cb(gpio, level, tick):
        nonlocal hit
        hit = True
        pi.wave_tx_stop()

    cb = None
    if stop_sensor is not None:
        cb = pi.callback(stop_sensor, pigpio.RISING_EDGE, _cb)

    half_us = int(1_000_000 / (2 * speed))
    pulses = []
    for _ in range(WAVE_SEG):
        pulses.append(pigpio.pulse(STEP_MASK, 0, half_us))
        pulses.append(pigpio.pulse(0, STEP_MASK, half_us))
    pi.wave_clear()
    pi.wave_add_generic(pulses)
    wid = pi.wave_create()
    if wid < 0:
        if cb:
            cb.cancel()
        raise RuntimeError(f'wave_create error: {wid}')

    reps = max(1, n // WAVE_SEG)
    chain = bytes([255, 0, wid, 255, 1, reps & 0xFF, (reps >> 8) & 0xFF])
    pi.wave_chain(chain)

    t0 = time.time()
    while pi.wave_tx_busy():
        time.sleep(0.002)
        if stop_sensor is not None and pi.read(stop_sensor) == 1:
            hit = True
            pi.wave_tx_stop()
            break
        if time.time() - t0 > 60:
            pi.wave_tx_stop()
            print('  TIMEOUT')
            break

    if cb:
        cb.cancel()
    pi.wave_delete(wid)
    pi.wave_clear()
    return hit


def backoff_if_pressed(name, sensor, a_dir, b_dir, steps=BACKOFF):
    if pi.read(sensor) == 1:
        print(f'[INIT] {name} нажат -> отъезд {steps} шагов')
        move(a_dir, b_dir, steps, FAST)
        time.sleep(0.05)


def seek(name, a_dir, b_dir, sensor):
    print(f'[{name}] Поиск концевика...', end=' ', flush=True)
    hit = move(a_dir, b_dir, 100000, FAST, sensor)
    print('OK' if hit else 'FAIL')
    print('   sensors:', sensor_state())
    return hit


try:
    print('=' * 56)
    print('  ENDSTOP SWEEP TEST')
    print(f'  FAST={FAST} BACKOFF={BACKOFF}')
    print('=' * 56)
    print('[INIT] sensors:', sensor_state())

    # X: LEFT -> RIGHT -> LEFT
    backoff_if_pressed('LEFT', SENSOR_LEFT, 1, 1)
    if not seek('X->RIGHT', 1, 1, SENSOR_RIGHT):
        raise SystemExit('X->RIGHT failed')
    move(0, 0, BACKOFF, FAST)
    time.sleep(0.05)
    if not seek('X->LEFT', 0, 0, SENSOR_LEFT):
        raise SystemExit('X->LEFT failed')

    # Y: BOTTOM -> TOP -> BOTTOM
    backoff_if_pressed('BOTTOM', SENSOR_BOTTOM, 1, 0)
    if not seek('Y->TOP', 1, 0, SENSOR_TOP):
        raise SystemExit('Y->TOP failed')
    move(0, 1, BACKOFF, FAST)
    time.sleep(0.05)
    if not seek('Y->BOTTOM', 0, 1, SENSOR_BOTTOM):
        raise SystemExit('Y->BOTTOM failed')

    print('\nDONE: full sweep OK')
finally:
    pi.wave_tx_stop()
    for p in [MOTOR_A_STEP, MOTOR_B_STEP]:
        pi.write(p, 0)
    pi.stop()
