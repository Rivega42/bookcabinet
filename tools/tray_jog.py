#!/usr/bin/env python3
"""
Ручной jog-пульт ЛОТКА и ЗАМКОВ для отладки перехвата на ЖЕЛЕЗЕ (pigpiod).
Каждое действие пишется в лог (~/bookcabinet/logs/tray_jog_*.log) и в консоль,
с состоянием концевиков ДО/ПОСЛЕ. Лог = воспроизводимый транскрипт сессии —
по нему потом переносим найденную последовательность в код.

ВАЖНО: сервис bookcabinet ДОЛЖЕН быть остановлен (sudo systemctl stop bookcabinet),
иначе два контроллера GPIO. На ноуте железа нет — запускать ТОЛЬКО на RPi.

Запуск:  python3 tools/tray_jog.py

КОМАНДЫ (после каждой — лог + концевики):
  Движение лотка:
    f              лоток → FRONT концевик (двухэтапно FAST→backoff→SLOW)
    b              лоток → BACK концевик
    mf N           двинуть лоток N шагов к FRONT (DIR=0)
    mb N           двинуть лоток N шагов к BACK  (DIR=1)
    +N  /  -N      то же: +N к BACK, -N к FRONT  (напр.  +16900 ,  -12600 )
  Замки:
    gf / gr        GRAB front / rear  (захват, PWM 1200)
    rf / rr        RELEASE front / rear (PWM 500 → 0)
    rfs / rrs      RELEASE strong (3×500 → 0, надёжная укладка)
    L pin us       сырой servo PWM (напр.  L 12 1200 ;  L 12 0  — снять)
  Макросы (действие 1 — ПОЛНЫЙ захват полки на каретку):
    ef             extract_front  (из переднего; после — держит ЗАДНИЙ замок)
    er             extract_rear   (из заднего;  после — держит ПЕРЕДНИЙ замок)
  Прочее:
    s              прочитать концевики FRONT/BACK
    note текст     записать заметку в лог
    ? / h          эта помощь
    q              выход (EN high, замки сняты, лог закрыт)

Константы — байт-в-байт из shelf_operations.py (field-validated). НЕ менять без железа.
DIR: 0=FRONT, 1=BACK.  Концевик 1=нажат. GPIO20 (BACK) шумит → sensor_stable=5.
"""
import pigpio
import time
import sys
import os
import datetime

# === КОНСТАНТЫ (из shelf_operations.py) ===
TRAY_STEP = 18
TRAY_DIR = 27
TRAY_EN1 = 25
TRAY_EN2 = 26
TRAY_FREQ = 12000

ENDSTOP_FRONT = 7
ENDSTOP_BACK = 20

LOCK_FRONT = 12
LOCK_REAR = 13

TRAY_CENTER = 11300
LOCK_DISTANCE = 12600
EXTRACT_FRONT_FIRST = 16900   # extract_front шаг 3 (к BACK) — полное втягивание
EXTRACT_REAR_FIRST = 16800    # extract_rear шаг 3 (к FRONT) = REAR_HANDOFF_REAR_FROM_BACK

LOCK_GRAB_PWM = 1200
LOCK_RELEASE_PWM = 500

MOVE_TIMEOUT = 25.0           # страховка подвода к концевику (железное правило)

pi = pigpio.pi()
if not pi.connected:
    print("ОШИБКА: pigpio не подключён. pigpiod запущен? сервис остановлен?")
    sys.exit(1)

LOGDIR = os.path.expanduser("~/bookcabinet/logs")
os.makedirs(LOGDIR, exist_ok=True)
LOGFILE = os.path.join(
    LOGDIR, "tray_jog_%s.log" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
_logfh = open(LOGFILE, "a", buffering=1)


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    _logfh.write(line + "\n")


def sensors():
    return pi.read(ENDSTOP_FRONT), pi.read(ENDSTOP_BACK)


def setup():
    for pin in (TRAY_STEP, TRAY_DIR, TRAY_EN1, TRAY_EN2):
        pi.set_mode(pin, pigpio.OUTPUT)
    pi.set_mode(ENDSTOP_FRONT, pigpio.INPUT)
    pi.set_mode(ENDSTOP_BACK, pigpio.INPUT)
    pi.set_pull_up_down(ENDSTOP_FRONT, pigpio.PUD_UP)
    pi.set_pull_up_down(ENDSTOP_BACK, pigpio.PUD_UP)


def sensor_stable(pin, required=5, interval=0.001):
    count = 0
    for _ in range(required * 2):
        if pi.read(pin) == 1:
            count += 1
            if count >= required:
                return True
        else:
            count = 0
        time.sleep(interval)
    return False


# === ЗАМКИ (через pigs, как в поле) ===
def lock_grab(pin):
    os.system("pigs s %d %d" % (pin, LOCK_GRAB_PWM))
    time.sleep(0.5)
    os.system("pigs s %d 0" % pin)
    log("LOCK %d GRAB (pwm %d)" % (pin, LOCK_GRAB_PWM))


def lock_release(pin, strong=False):
    if strong:
        for _ in range(3):
            os.system("pigs s %d %d" % (pin, LOCK_RELEASE_PWM))
            time.sleep(0.5)
        os.system("pigs s %d 0" % pin)
        log("LOCK %d RELEASE strong (3×%d)" % (pin, LOCK_RELEASE_PWM))
    else:
        os.system("pigs s %d %d" % (pin, LOCK_RELEASE_PWM))
        time.sleep(0.5)
        os.system("pigs s %d 0" % pin)
        log("LOCK %d RELEASE (pwm %d)" % (pin, LOCK_RELEASE_PWM))


# === ДВИЖЕНИЕ ЛОТКА ===
def tray_move(steps, direction):
    dn = "BACK" if direction == 1 else "FRONT"
    f0, b0 = sensors()
    period = int(1000000 / TRAY_FREQ)
    pulse = period // 2
    pi.wave_clear()
    pi.wave_add_generic([
        pigpio.pulse(1 << TRAY_STEP, 0, pulse),
        pigpio.pulse(0, 1 << TRAY_STEP, pulse),
    ])
    wid = pi.wave_create()
    pi.write(TRAY_EN1, 0)
    pi.write(TRAY_EN2, 0)
    pi.write(TRAY_DIR, direction)
    time.sleep(0.01)
    pi.wave_send_repeat(wid)
    time.sleep(steps / TRAY_FREQ)
    pi.wave_tx_stop()
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)
    pi.wave_delete(wid)
    f1, b1 = sensors()
    log("MOVE %d → %s | концевики (F,B) %s→%s" % (steps, dn, (f0, b0), (f1, b1)))


def tray_to_endstop(endstop_pin):
    direction = 1 if endstop_pin == ENDSTOP_BACK else 0
    dn = "BACK" if direction == 1 else "FRONT"
    f0, b0 = sensors()
    period = int(1000000 / TRAY_FREQ)
    pulse = period // 2
    pi.wave_clear()
    pi.wave_add_generic([
        pigpio.pulse(1 << TRAY_STEP, 0, pulse),
        pigpio.pulse(0, 1 << TRAY_STEP, pulse),
    ])
    wid = pi.wave_create()
    pi.write(TRAY_EN1, 0)
    pi.write(TRAY_EN2, 0)
    pi.write(TRAY_DIR, direction)
    time.sleep(0.01)

    # FAST
    t0 = time.time()
    pi.wave_send_repeat(wid)
    while not sensor_stable(endstop_pin):
        if time.time() - t0 > MOVE_TIMEOUT:
            pi.wave_tx_stop()
            pi.write(TRAY_EN1, 1); pi.write(TRAY_EN2, 1)
            pi.wave_delete(wid)
            log("ENDSTOP %s — ТАЙМАУТ (FAST), СТОП" % dn)
            return False
        time.sleep(0.001)
    pi.wave_tx_stop()

    # backoff
    pi.write(TRAY_DIR, 1 - direction)
    time.sleep(0.01)
    pi.wave_send_repeat(wid)
    time.sleep(1500 / TRAY_FREQ)
    pi.wave_tx_stop()
    pi.wave_delete(wid)

    # SLOW
    slow_freq = 1500
    sp = int(1000000 / slow_freq)
    spp = sp // 2
    pi.wave_clear()
    pi.wave_add_generic([
        pigpio.pulse(1 << TRAY_STEP, 0, spp),
        pigpio.pulse(0, 1 << TRAY_STEP, spp),
    ])
    sw = pi.wave_create()
    pi.write(TRAY_DIR, direction)
    time.sleep(0.01)
    pi.wave_send_repeat(sw)
    sc = 0
    t1 = time.time()
    while not sensor_stable(endstop_pin):
        if time.time() - t1 > MOVE_TIMEOUT:
            pi.wave_tx_stop()
            pi.write(TRAY_EN1, 1); pi.write(TRAY_EN2, 1)
            pi.wave_delete(sw)
            log("ENDSTOP %s — ТАЙМАУТ (SLOW), СТОП" % dn)
            return False
        time.sleep(1 / slow_freq)
        sc += 1
    pi.wave_tx_stop()
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)
    pi.wave_delete(sw)
    f1, b1 = sensors()
    log("ENDSTOP %s достигнут (slow %d) | концевики (F,B) %s→%s" % (dn, sc, (f0, b0), (f1, b1)))
    return True


# === МАКРОСЫ: полный захват (действие 1) ===
def extract_front():
    log("=== МАКРО extract_front (полный захват из ПЕРЕДНЕГО) ===")
    if not tray_to_endstop(ENDSTOP_FRONT):
        return
    lock_grab(LOCK_FRONT)
    tray_move(EXTRACT_FRONT_FIRST, 1)   # к BACK
    lock_release(LOCK_FRONT)
    tray_move(LOCK_DISTANCE, 0)         # к FRONT
    lock_grab(LOCK_REAR)
    tray_move(LOCK_DISTANCE, 1)         # к BACK
    log("=== extract_front DONE — полка на каретке, держит ЗАДНИЙ замок ===")


def extract_rear():
    log("=== МАКРО extract_rear (полный захват из ЗАДНЕГО) ===")
    if not tray_to_endstop(ENDSTOP_BACK):
        return
    lock_grab(LOCK_REAR)
    tray_move(EXTRACT_REAR_FIRST, 0)    # к FRONT
    lock_release(LOCK_REAR)
    tray_move(LOCK_DISTANCE, 1)         # к BACK
    lock_grab(LOCK_FRONT)
    tray_move(LOCK_DISTANCE, 0)         # к FRONT
    log("=== extract_rear DONE — полка на каретке, держит ПЕРЕДНИЙ замок ===")


def cleanup():
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)
    os.system("pigs s %d 0" % LOCK_FRONT)
    os.system("pigs s %d 0" % LOCK_REAR)
    try:
        pi.wave_clear()
    except Exception:
        pass


def main():
    setup()
    log("tray_jog СТАРТ. log=%s" % LOGFILE)
    f, b = sensors()
    log("концевики при старте: FRONT=%d BACK=%d" % (f, b))
    print(__doc__)
    while True:
        try:
            raw = input("tray> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        log("> %s" % raw)               # транскрипт: что набрали
        parts = raw.split()
        op = parts[0].lower()
        try:
            if op in ("q", "quit", "exit"):
                break
            elif op in ("?", "h", "help"):
                print(__doc__)
            elif op == "s":
                f, b = sensors()
                log("концевики: FRONT=%d BACK=%d" % (f, b))
            elif op == "f":
                tray_to_endstop(ENDSTOP_FRONT)
            elif op == "b":
                tray_to_endstop(ENDSTOP_BACK)
            elif op == "mf" and len(parts) >= 2:
                tray_move(abs(int(parts[1])), 0)
            elif op == "mb" and len(parts) >= 2:
                tray_move(abs(int(parts[1])), 1)
            elif op == "gf":
                lock_grab(LOCK_FRONT)
            elif op == "gr":
                lock_grab(LOCK_REAR)
            elif op == "rf":
                lock_release(LOCK_FRONT)
            elif op == "rr":
                lock_release(LOCK_REAR)
            elif op == "rfs":
                lock_release(LOCK_FRONT, strong=True)
            elif op == "rrs":
                lock_release(LOCK_REAR, strong=True)
            elif op == "l" and len(parts) >= 3:
                pin = int(parts[1]); us = int(parts[2])
                os.system("pigs s %d %d" % (pin, us))
                log("RAW servo %d = %d" % (pin, us))
            elif op == "ef":
                extract_front()
            elif op == "er":
                extract_rear()
            elif op == "note":
                log("ЗАМЕТКА: %s" % raw[4:].strip())
            elif raw[0] in "+-" and raw[1:].strip().isdigit():
                n = int(raw)
                tray_move(abs(n), 1 if n >= 0 else 0)   # + к BACK, - к FRONT
            else:
                print("неизвестно: '%s'  (? — помощь)" % raw)
        except Exception as e:
            log("ОШИБКА команды '%s': %s" % (raw, e))
    cleanup()
    log("tray_jog ВЫХОД (EN high, замки сняты). Лог: %s" % LOGFILE)
    _logfh.close()
    pi.stop()


if __name__ == "__main__":
    main()
