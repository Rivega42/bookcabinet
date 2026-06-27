#!/usr/bin/env python3
"""
Веб-ПУЛЬТ лотка и замков (кнопки) для отладки перехвата на ЖЕЛЕЗЕ (pigpiod).
Те же валидированные примитивы, что в shelf_operations.py / tray_jog.py.
Каждое действие пишется в ~/bookcabinet/logs/tray_panel_*.log + видно в логе на странице.

ВАЖНО: сервис bookcabinet ДОЛЖЕН быть остановлен (sudo systemctl stop bookcabinet),
иначе два контроллера GPIO. На ноуте железа нет — запускать ТОЛЬКО на RPi.

Запуск:   python3 tools/tray_panel.py
Открыть:  http://<IP RPi>:8080   (с ноута)  или  http://localhost:8080  (на экране шкафа)

DIR: 0=FRONT, 1=BACK. Концевик 1=нажат. Все движения сериализованы (одно за раз).
"""
import asyncio
import time
import os
import sys
import datetime
import subprocess

import pigpio
from aiohttp import web

PROJECT = os.path.expanduser("~/bookcabinet")

# === КОНСТАНТЫ (из shelf_operations.py) ===
TRAY_STEP = 18
TRAY_DIR = 27
TRAY_EN1 = 25
TRAY_EN2 = 26
TRAY_FREQ = 12000

ENDSTOP_FRONT = 7
ENDSTOP_BACK = 20
ENDSTOP_FAST_CAP = 12000   # подвод к концевику НЕ быстрее валидированного 12000 (не зависит от модификатора скорости)

LOCK_FRONT = 12
LOCK_REAR = 13

TRAY_CENTER = 11300
LOCK_DISTANCE = 12600
EXTRACT_FRONT_FIRST = 16900
EXTRACT_REAR_FIRST = 16800
# Кросс-рядные шаги transfer (из shelf_operations.py front_to_rear/rear_to_front V1)
CROSS_FRONT_TO_REAR_STEP6 = 12500
CROSS_REAR_TO_FRONT_STEP4 = 12700
CROSS_REAR_TO_FRONT_STEP6 = 12600
REAR_TO_FRONT_S2 = 13100   # откалибровано на железе 2026-06-27 (поле 12600 не доезжало на 500)

LOCK_GRAB_PWM = 1200
LOCK_RELEASE_PWM = 500

MOVE_TIMEOUT = 25.0
PORT = 8080

pi = pigpio.pi()
if not pi.connected:
    print("ОШИБКА: pigpio не подключён. pigpiod запущен? сервис остановлен?")
    sys.exit(1)

LOGDIR = os.path.expanduser("~/bookcabinet/logs")
os.makedirs(LOGDIR, exist_ok=True)
LOGFILE = os.path.join(
    LOGDIR, "tray_panel_%s.log" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
_logfh = open(LOGFILE, "a", buffering=1)
RECENT = []   # последние строки лога для UI

ACTION_LOCK = asyncio.Lock()


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = "[%s] %s" % (ts, msg)
    print(line, flush=True)
    _logfh.write(line + "\n")
    RECENT.append(line)
    del RECENT[:-300]


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
    fast = min(TRAY_FREQ, ENDSTOP_FAST_CAP)   # подвод к концевику не быстрее 12000 (надёжный захват датчика)
    period = int(1000000 / fast)
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

    pi.write(TRAY_DIR, 1 - direction)
    time.sleep(0.01)
    pi.wave_send_repeat(wid)
    time.sleep(1500 / fast)
    pi.wave_tx_stop()
    pi.wave_delete(wid)

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


def extract_front():
    log("=== МАКРО extract_front (полный захват из ПЕРЕДНЕГО) ===")
    if not tray_to_endstop(ENDSTOP_FRONT):
        return
    lock_grab(LOCK_FRONT)
    tray_move(EXTRACT_FRONT_FIRST, 1)
    lock_release(LOCK_FRONT)
    tray_move(LOCK_DISTANCE, 0)
    lock_grab(LOCK_REAR)
    tray_move(LOCK_DISTANCE, 1)
    log("=== extract_front DONE — полка на каретке, держит ЗАДНИЙ замок ===")


def extract_rear():
    log("=== МАКРО extract_rear (полный захват из ЗАДНЕГО) ===")
    if not tray_to_endstop(ENDSTOP_BACK):
        return
    lock_grab(LOCK_REAR)
    tray_move(EXTRACT_REAR_FIRST, 0)
    lock_release(LOCK_REAR)
    tray_move(LOCK_DISTANCE, 1)
    lock_grab(LOCK_FRONT)
    tray_move(LOCK_DISTANCE, 0)
    log("=== extract_rear DONE — полка на каретке, держит ПЕРЕДНИЙ замок ===")


def return_front():
    """Уложить полку (держит ЗАДНИЙ замок) в ПЕРЕДНИЙ ряд. Порт shelf_operations return_front.
    Родная функция пульта → читает глобальные TRAY_FREQ и PWM (модификаторы действуют)."""
    log("=== return_front (уложить в ПЕРЕДНИЙ ряд) ===")
    tray_move(LOCK_DISTANCE, 0)
    lock_release(LOCK_REAR)
    tray_move(LOCK_DISTANCE, 1)
    lock_grab(LOCK_FRONT)
    if not tray_to_endstop(ENDSTOP_FRONT):
        return
    lock_release(LOCK_FRONT, strong=True)
    tray_move(TRAY_CENTER, 1)
    log("=== return_front DONE — полка в переднем ряду, лоток в центре ===")


def return_rear():
    """Уложить полку (держит ПЕРЕДНИЙ замок) в ЗАДНИЙ ряд. Порт shelf_operations return_rear.
    Родная функция пульта → читает глобальные TRAY_FREQ и PWM (модификаторы действуют)."""
    log("=== return_rear (уложить в ЗАДНИЙ ряд) ===")
    tray_move(LOCK_DISTANCE, 1)
    lock_release(LOCK_FRONT)
    tray_move(LOCK_DISTANCE, 0)
    lock_grab(LOCK_REAR)
    if not tray_to_endstop(ENDSTOP_BACK):
        return
    lock_release(LOCK_REAR, strong=True)
    tray_move(TRAY_CENTER, 0)
    log("=== return_rear DONE — полка в заднем ряду, лоток в центре ===")


def front_to_rear():
    """ПЕРЕД→ЗАД: порт shelf_operations.py front_to_rear V1 (полный, 10 шагов transfer)."""
    log("=== МАКРО front_to_rear (переложить ПЕРЕД→ЗАД) ===")
    extract_front()                            # → держит ЗАДНИЙ замок (13), pos ~16900
    lock_release(LOCK_REAR)                    # T1
    tray_move(LOCK_DISTANCE, 0)                # T2  12600 → FRONT
    lock_grab(LOCK_FRONT)                       # T3
    tray_move(LOCK_DISTANCE, 1)                # T4  12600 → BACK
    lock_release(LOCK_FRONT)                   # T5
    tray_move(CROSS_FRONT_TO_REAR_STEP6, 0)    # T6  12500 → FRONT
    lock_grab(LOCK_REAR)                        # T7
    if not tray_to_endstop(ENDSTOP_BACK):      # T8
        return
    lock_release(LOCK_REAR, strong=True)       # T9  укладка в ЗАДНИЙ ряд
    tray_move(TRAY_CENTER, 0)                  # T10 CENTER → FRONT
    log("=== front_to_rear DONE — полка в ЗАДНЕМ ряду ===")


def rear_to_front():
    """ЗАД→ПЕРЕД: shelf_operations.py rear_to_front V1 (поле обрывалось на шаге 8;
    шаги 9–10 дописаны по симметрии — ПРОВЕРИТЬ НА ЖЕЛЕЗЕ)."""
    log("=== МАКРО rear_to_front (переложить ЗАД→ПЕРЕД) ===")
    extract_rear()                             # → держит ПЕРЕДНИЙ замок (12)
    lock_release(LOCK_FRONT)                   # S1
    tray_move(REAR_TO_FRONT_S2, 1)             # S2  13100 → BACK (откалибровано)
    lock_grab(LOCK_REAR)                        # S3
    tray_move(CROSS_REAR_TO_FRONT_STEP4, 0)    # S4  12700 → FRONT
    lock_release(LOCK_REAR)                    # S5
    tray_move(CROSS_REAR_TO_FRONT_STEP6, 1)    # S6  12600 → BACK
    lock_grab(LOCK_FRONT)                       # S7
    if not tray_to_endstop(ENDSTOP_FRONT):     # S8
        return
    lock_release(LOCK_FRONT, strong=True)      # S9  укладка в ПЕРЕДНИЙ ряд (дописано)
    tray_move(TRAY_CENTER, 1)                  # S10 CENTER → BACK (дописано)
    log("=== rear_to_front DONE — полка в ПЕРЕДНЕМ ряду ===")


def rtf_grab():
    """rear→front ЭТАП 1: extract_rear + отпуск переднего → точка ручной подгонки S2.
    Дальше Роман джогом подводит ЗАДНИЙ замок под прорезь и жмёт 'Захват ЗАДНИЙ'."""
    log("=== rtf ЭТАП 1: extract_rear + release FRONT (к ручной подгонке S2) ===")
    extract_rear()                 # → держит ПЕРЕДНИЙ замок (12)
    lock_release(LOCK_FRONT)       # S1
    log(">>> ПОДГОНКА: джогом +N (к BACK) подведи ЗАДНИЙ замок (13) под прорезь,")
    log(">>> затем 'Захват ЗАДНИЙ' (gr), затем '2. довезти в перёд'")


def rtf_finish():
    """rear→front ЭТАП 2: довоз в передний ряд (S4..S10).
    Ожидает: ЗАДНИЙ замок держит полку (после ручной подгонки + захвата)."""
    log("=== rtf ЭТАП 2: довоз в ПЕРЕДНИЙ ряд (S4..S10) ===")
    tray_move(CROSS_REAR_TO_FRONT_STEP4, 0)    # S4  12700 → FRONT
    lock_release(LOCK_REAR)                    # S5
    tray_move(CROSS_REAR_TO_FRONT_STEP6, 1)    # S6  12600 → BACK
    lock_grab(LOCK_FRONT)                       # S7
    if not tray_to_endstop(ENDSTOP_FRONT):     # S8
        return
    lock_release(LOCK_FRONT, strong=True)      # S9
    tray_move(TRAY_CENTER, 1)                  # S10
    log("=== rtf ЭТАП 2 DONE — полка в ПЕРЕДНЕМ ряду ===")


def ftr_grab():
    """front→rear ЭТАП 1: extract_front + отпуск заднего → точка ручной подгонки T2.
    Дальше Роман джогом −N (к FRONT) подводит ПЕРЕДНИЙ замок под прорезь и жмёт 'Захват ПЕРЕДНИЙ'."""
    log("=== ftr ЭТАП 1: extract_front + release REAR (к ручной подгонке T2) ===")
    extract_front()                # → держит ЗАДНИЙ замок (13)
    lock_release(LOCK_REAR)        # T1
    log(">>> ПОДГОНКА: джогом −N (к FRONT) подведи ПЕРЕДНИЙ замок (12) под прорезь,")
    log(">>> затем 'Захват ПЕРЕДНИЙ' (gf), затем '2. довезти в зад'")


def ftr_finish():
    """front→rear ЭТАП 2: довоз в задний ряд (T4..T10).
    Ожидает: ПЕРЕДНИЙ замок держит полку (после ручной подгонки + захвата)."""
    log("=== ftr ЭТАП 2: довоз в ЗАДНИЙ ряд (T4..T10) ===")
    tray_move(LOCK_DISTANCE, 1)                # T4  12600 → BACK
    lock_release(LOCK_FRONT)                   # T5
    tray_move(CROSS_FRONT_TO_REAR_STEP6, 0)    # T6  12500 → FRONT
    lock_grab(LOCK_REAR)                        # T7
    if not tray_to_endstop(ENDSTOP_BACK):      # T8
        return
    lock_release(LOCK_REAR, strong=True)       # T9
    tray_move(TRAY_CENTER, 0)                  # T10
    log("=== ftr ЭТАП 2 DONE — полка в ЗАДНЕМ ряду ===")


# ============ ГИД ПО ШАГАМ (вкладка 1): каждый шаг по кнопке, между — джог +/− ============
GUIDE = {"name": None, "idx": 0, "steps": []}


def _guide_ftr():
    LF, LR = LOCK_FRONT, LOCK_REAR
    LD, C = LOCK_DISTANCE, TRAY_CENTER
    return [
        ("extract 1: → FRONT концевик", lambda: tray_to_endstop(ENDSTOP_FRONT)),
        ("extract 2: GRAB передний", lambda: lock_grab(LF)),
        ("extract 3: 16900 → BACK", lambda: tray_move(EXTRACT_FRONT_FIRST, 1)),
        ("extract 4: RELEASE передний", lambda: lock_release(LF)),
        ("extract 5: 12600 → FRONT", lambda: tray_move(LD, 0)),
        ("extract 6: GRAB задний", lambda: lock_grab(LR)),
        ("extract 7: 12600 → BACK", lambda: tray_move(LD, 1)),
        ("transfer 1: RELEASE задний", lambda: lock_release(LR)),
        ("transfer 2: 12600 → FRONT", lambda: tray_move(LD, 0)),
        ("transfer 3: GRAB передний", lambda: lock_grab(LF)),
        ("transfer 4: 12600 → BACK", lambda: tray_move(LD, 1)),
        ("transfer 5: RELEASE передний", lambda: lock_release(LF)),
        ("transfer 6: 12500 → FRONT", lambda: tray_move(CROSS_FRONT_TO_REAR_STEP6, 0)),
        ("transfer 7: GRAB задний", lambda: lock_grab(LR)),
        ("transfer 8: → BACK концевик", lambda: tray_to_endstop(ENDSTOP_BACK)),
        ("transfer 9: RELEASE задний strong", lambda: lock_release(LR, True)),
        ("transfer 10: CENTER → FRONT", lambda: tray_move(C, 0)),
    ]


def _guide_rtf():
    LF, LR = LOCK_FRONT, LOCK_REAR
    LD, C = LOCK_DISTANCE, TRAY_CENTER
    return [
        ("extract 1: → BACK концевик", lambda: tray_to_endstop(ENDSTOP_BACK)),
        ("extract 2: GRAB задний", lambda: lock_grab(LR)),
        ("extract 3: 16800 → FRONT", lambda: tray_move(EXTRACT_REAR_FIRST, 0)),
        ("extract 4: RELEASE задний", lambda: lock_release(LR)),
        ("extract 5: 12600 → BACK", lambda: tray_move(LD, 1)),
        ("extract 6: GRAB передний", lambda: lock_grab(LF)),
        ("extract 7: 12600 → FRONT", lambda: tray_move(LD, 0)),
        ("transfer 1: RELEASE передний", lambda: lock_release(LF)),
        ("transfer 2: %d → BACK (S2)" % REAR_TO_FRONT_S2, lambda: tray_move(REAR_TO_FRONT_S2, 1)),
        ("transfer 3: GRAB задний", lambda: lock_grab(LR)),
        ("transfer 4: 12700 → FRONT", lambda: tray_move(CROSS_REAR_TO_FRONT_STEP4, 0)),
        ("transfer 5: RELEASE задний", lambda: lock_release(LR)),
        ("transfer 6: 12600 → BACK", lambda: tray_move(CROSS_REAR_TO_FRONT_STEP6, 1)),
        ("transfer 7: GRAB передний", lambda: lock_grab(LF)),
        ("transfer 8: → FRONT концевик", lambda: tray_to_endstop(ENDSTOP_FRONT)),
        ("transfer 9: RELEASE передний strong", lambda: lock_release(LF, True)),
        ("transfer 10: CENTER → BACK", lambda: tray_move(C, 1)),
    ]


def guide_start(name):
    GUIDE["steps"] = _guide_ftr() if name == "front_to_rear" else _guide_rtf()
    GUIDE["name"] = name
    GUIDE["idx"] = 0
    log("=== ГИД %s: старт, %d шагов. 'СЛЕД. ШАГ' выполняет; между шагами джог +/− для подгонки ===" % (name, len(GUIDE["steps"])))


def guide_next():
    if not GUIDE["steps"] or GUIDE["idx"] >= len(GUIDE["steps"]):
        log("ГИД: все шаги выполнены")
        return
    i = GUIDE["idx"]
    label, fn = GUIDE["steps"][i]
    log("--- ГИД шаг %d/%d: %s ---" % (i + 1, len(GUIDE["steps"]), label))
    fn()
    GUIDE["idx"] += 1


def guide_state():
    if not GUIDE["name"]:
        return {"name": None}
    total = len(GUIDE["steps"])
    idx = GUIDE["idx"]
    nxt = GUIDE["steps"][idx][0] if idx < total else "— конец —"
    return {"name": GUIDE["name"], "idx": idx, "total": total, "next": nxt}


# ============ ВКЛАДКА 2: книгоприём/выдача через полевые скрипты ============
def run_field(args, timeout=150):
    """Запустить tools/<script> подпроцессом и записать вывод в лог."""
    log(">>> RUN: python3 %s" % " ".join(args))
    try:
        p = subprocess.run(["python3"] + args, cwd=PROJECT,
                           capture_output=True, text=True, timeout=timeout)
        for line in (p.stdout or "").splitlines()[-30:]:
            log("    " + line)
        for line in (p.stderr or "").splitlines()[-10:]:
            log("    [err] " + line)
        log("<<< RC=%d" % p.returncode)
        return p.returncode == 0
    except subprocess.TimeoutExpired:
        log("<<< ТАЙМАУТ %ss — СТОП" % timeout)
        return False


def cell_depth(addr):
    try:
        return int(str(addr).split(".")[0])
    except Exception:
        return 1


def op_home():
    run_field(["tools/homing_pigpio.py"], timeout=180)


def op_goto(addr):
    run_field(["tools/goto.py", "800", str(addr)], timeout=120)


def op_take(addr):
    """Доехать до ячейки (goto, XY) и затянуть книгу на каретку РОДНЫМ extract
    (читает глобальные TRAY_FREQ и PWM — модификаторы действуют)."""
    if not run_field(["tools/goto.py", "800", str(addr)], timeout=120):
        return
    if cell_depth(addr) == 2:
        extract_rear()
    else:
        extract_front()


def op_put(addr):
    """Доехать до ячейки (goto, XY) и выложить книгу РОДНЫМ return
    (читает глобальные TRAY_FREQ и PWM — модификаторы действуют)."""
    if not run_field(["tools/goto.py", "800", str(addr)], timeout=120):
        return
    if cell_depth(addr) == 2:
        return_rear()
    else:
        return_front()


def op_shutter(which, action):
    run_field(["tools/shutter.py", str(which), str(action)], timeout=40)


# ============ Глобальный модификатор PWM замков ============
def set_pwm(grab=None, release=None):
    """Глобально переключить PWM захвата/отпуска. Действует на ВСЕ замочные операции
    пульта (джог, макросы, гид). На подпроцессы вкладки 2 (полевые скрипты) НЕ влияет."""
    global LOCK_GRAB_PWM, LOCK_RELEASE_PWM
    if grab not in (None, ""):
        LOCK_GRAB_PWM = int(grab)
        log("PWM ЗАХВАТА (GRAB) замков → %d (для всех операций пульта)" % LOCK_GRAB_PWM)
    if release not in (None, ""):
        LOCK_RELEASE_PWM = int(release)
        log("PWM ОТПУСКА (RELEASE) замков → %d" % LOCK_RELEASE_PWM)


def pwm_state():
    return {"grab": LOCK_GRAB_PWM, "release": LOCK_RELEASE_PWM}


# ============ Глобальный модификатор СКОРОСТИ лотка ============
def set_speed(freq):
    """Глобально переключить частоту шагов лотка (TRAY_FREQ, Гц). Действует на ВСЕ
    движения лотка пульта (jog, endstop FAST-фаза, макросы, гид). Медленный подвод
    к концевику (1500 Гц) остаётся фиксированным для точности. Защита от 0/абсурда."""
    global TRAY_FREQ
    f = int(freq)
    f = max(200, min(30000, f))   # не делить на 0, не рвать ремень
    TRAY_FREQ = f
    log("СКОРОСТЬ лотка (TRAY_FREQ) → %d Гц (для всех движений пульта)" % TRAY_FREQ)


def speed_state():
    return {"freq": TRAY_FREQ}


def cleanup():
    pi.write(TRAY_EN1, 1)
    pi.write(TRAY_EN2, 1)
    os.system("pigs s %d 0" % LOCK_FRONT)
    os.system("pigs s %d 0" % LOCK_REAR)
    try:
        pi.wave_clear()
    except Exception:
        pass


# ===================== WEB =====================
HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Пульт лотка — отладка перехвата</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body { margin:0; background:#0d1117; color:#e6edf3; font:16px/1.4 system-ui,Segoe UI,Roboto,sans-serif; padding:12px; }
  h2 { margin:14px 0 8px; font-size:15px; color:#9aa7b4; text-transform:uppercase; letter-spacing:.05em; }
  .sensors { display:flex; gap:10px; margin-bottom:8px; }
  .chip { flex:1; padding:14px; border-radius:12px; background:#161b22; border:1px solid #30363d; text-align:center; font-weight:700; font-size:18px; }
  .chip .dot { display:inline-block; width:14px; height:14px; border-radius:50%; background:#444; margin-left:8px; vertical-align:middle; }
  .chip.on .dot { background:#3fb950; box-shadow:0 0 10px #3fb950; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .grid.three { grid-template-columns:1fr 1fr 1fr; }
  button { font:600 16px system-ui; padding:18px 10px; border-radius:12px; border:1px solid #30363d;
           background:#21262d; color:#e6edf3; cursor:pointer; touch-action:manipulation; }
  button:active { transform:scale(.97); }
  button.grab { background:#1f6feb; border-color:#1f6feb; }
  button.rel  { background:#30363d; }
  button.rels { background:#9e6a03; border-color:#9e6a03; }
  button.macro{ background:#238636; border-color:#238636; font-size:17px; padding:22px 10px; }
  button.endst{ background:#30363d; }
  button.stop { background:#da3633; border-color:#da3633; font-size:18px; width:100%; padding:20px; }
  .jogrow { display:flex; gap:8px; align-items:center; margin-bottom:8px; }
  .jogrow input { flex:1; min-width:0; padding:16px; font-size:18px; text-align:center; border-radius:10px;
                  border:1px solid #30363d; background:#0d1117; color:#e6edf3; }
  .presets { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
  .presets button { padding:12px 4px; font-size:14px; }
  .note { display:flex; gap:8px; }
  .note input { flex:1; padding:14px; border-radius:10px; border:1px solid #30363d; background:#0d1117; color:#e6edf3; }
  #busy { position:fixed; top:0; left:0; right:0; background:#9e6a03; color:#fff; text-align:center;
          padding:8px; font-weight:700; display:none; z-index:9; }
  pre#log { background:#010409; border:1px solid #30363d; border-radius:10px; padding:10px; height:200px;
            overflow:auto; font:12px/1.5 ui-monospace,Consolas,monospace; white-space:pre-wrap; }
  .hint { color:#8b949e; font-size:13px; margin:2px 0 8px; }
  .tabs { display:flex; gap:6px; margin:0 0 10px; position:sticky; top:0; background:#0d1117; padding:6px 0; z-index:6; }
  .tabbtn { flex:1; padding:14px; background:#161b22; font-size:15px; }
  .tabbtn.active { background:#1f6feb; border-color:#1f6feb; }
  #guideinfo { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px; margin:6px 0; font-size:14px; }
</style></head><body>
<div id="busy">⏳ выполняется движение…</div>

<div class="tabs">
  <button id="tabbtn1" class="tabbtn active" onclick="showTab(1)">Лоток / перехват</button>
  <button id="tabbtn2" class="tabbtn" onclick="showTab(2)">Книгоприём / выдача</button>
</div>

<div id="tab1">
<h2>Концевики лотка</h2>
<div class="sensors">
  <div class="chip" id="sf">FRONT <span class="dot"></span></div>
  <div class="chip" id="sb">BACK <span class="dot"></span></div>
</div>

<h2>Замки</h2>
<div class="jogrow">
  <span style="font-size:13px;color:#8b949e;white-space:nowrap">PWM захв/отп</span>
  <input id="grabpwm" type="number" value="1200" inputmode="numeric" title="PWM захвата (GRAB)">
  <input id="relpwm" type="number" value="500" inputmode="numeric" title="PWM отпуска (RELEASE)">
  <button onclick="applyPwm()">применить</button>
</div>
<div id="pwminfo" class="hint">текущий: grab 1200 / release 500 (действует на джог, макросы, гид)</div>
<div class="grid three">
  <button class="grab" onclick="act('grab_front')">Захват<br>ПЕРЕДНИЙ</button>
  <button class="rel"  onclick="act('rel_front')">Отпуск<br>передний</button>
  <button class="rels" onclick="act('rels_front')">Отпуск ×3<br>передний</button>
  <button class="grab" onclick="act('grab_rear')">Захват<br>ЗАДНИЙ</button>
  <button class="rel"  onclick="act('rel_rear')">Отпуск<br>задний</button>
  <button class="rels" onclick="act('rels_rear')">Отпуск ×3<br>задний</button>
</div>

<h2>Лоток → концевик</h2>
<div class="grid">
  <button class="endst" onclick="act('to_front')">→ FRONT концевик</button>
  <button class="endst" onclick="act('to_back')">→ BACK концевик</button>
</div>

<h2>Лоток — шаги (− к FRONT / + к BACK)</h2>
<div class="jogrow">
  <button onclick="jogCustom(-1)">← FRONT</button>
  <input id="njog" type="number" value="1000" inputmode="numeric">
  <button onclick="jogCustom(1)">BACK →</button>
</div>
<div class="presets">
  <button onclick="jog(-500)">−500</button>
  <button onclick="jog(-5000)">−5000</button>
  <button onclick="jog(-12600)">−12600</button>
  <button onclick="jog(500)">+500</button>
  <button onclick="jog(5000)">+5000</button>
  <button onclick="jog(12600)">+12600</button>
  <button onclick="jog(-16900)">−16900</button>
  <button onclick="jog(16800)">+16800</button>
  <button onclick="jog(16900)">+16900</button>
</div>
<div class="hint">12600 = LOCK_DISTANCE · 16900/16800 = первый ход extract · 11300 = CENTER</div>
<div class="jogrow">
  <span style="font-size:13px;color:#8b949e;white-space:nowrap">Скорость Гц</span>
  <input id="speed" type="number" value="12000" inputmode="numeric" title="TRAY_FREQ — частота шагов лотка">
  <button onclick="applySpeed()">применить</button>
</div>
<div id="speedinfo" class="hint">текущая: 12000 Гц (FAST-фаза и jog; медленный подвод к концевику фикс. 1500)</div>

<h2>Макрос — полный захват (действие 1)</h2>
<div class="grid">
  <button class="macro" onclick="act('extract_front')">extract_front<br>из ПЕРЕДНЕГО</button>
  <button class="macro" onclick="act('extract_rear')">extract_rear<br>из ЗАДНЕГО</button>
</div>

<h2>Макрос — кросс-ряд (полная перекладка)</h2>
<div class="grid">
  <button class="macro" onclick="confirmAct('front_to_rear','ПЕРЕД→ЗАД: полка переедет из переднего ряда в задний. Полка в переднем? Продолжить?')">front → rear<br>ПЕРЕД→ЗАД</button>
  <button class="macro" onclick="confirmAct('rear_to_front','ЗАД→ПЕРЕД: полка переедет из заднего ряда в передний. Полка в заднем? Продолжить?')">rear → front<br>ЗАД→ПЕРЕД</button>
</div>

<h2>rear→front — ручная подгонка S2</h2>
<div class="grid">
  <button class="macro" onclick="confirmAct('rtf_grab','ЭТАП 1: захват из заднего + отпуск переднего. Полка в заднем ряду? Продолжить?')">1. захват<br>(к подгонке)</button>
  <button class="macro" onclick="confirmAct('rtf_finish','ЭТАП 2: довезти в передний ряд. Задний замок уже держит полку? Продолжить?')">2. довезти<br>в перёд</button>
</div>
<div class="hint">между этапами: джогом <b>+N (к BACK)</b> подведи ЗАДНИЙ замок под прорезь → «Захват ЗАДНИЙ» → этап 2. Подбери число вместо 12600.</div>

<h2>front→rear — ручная подгонка T2</h2>
<div class="grid">
  <button class="macro" onclick="confirmAct('ftr_grab','ЭТАП 1: захват из переднего + отпуск заднего. Полка в переднем ряду? Продолжить?')">1. захват<br>(к подгонке)</button>
  <button class="macro" onclick="confirmAct('ftr_finish','ЭТАП 2: довезти в задний ряд. Передний замок уже держит полку? Продолжить?')">2. довезти<br>в зад</button>
</div>
<div class="hint">между этапами: джогом <b>−N (к FRONT)</b> подведи ПЕРЕДНИЙ замок под прорезь → «Захват ПЕРЕДНИЙ» → этап 2. Подбери число вместо 12600.</div>

<h2>Гид по шагам (подгонка каждого движения +/−)</h2>
<div class="grid">
  <button onclick="confirmAct('guide_front','Гид ПЕРЕД→ЗАД по шагам. Полка в переду? Старт?')">⏯ front→rear</button>
  <button onclick="confirmAct('guide_rear','Гид ЗАД→ПЕРЕД по шагам. Полка в заду? Старт?')">⏯ rear→front</button>
</div>
<div id="guideinfo">гид не запущен</div>
<button class="macro" style="width:100%;background:#1f6feb" onclick="act('guide_next')">СЛЕД. ШАГ ▶</button>
<button class="rel" style="width:100%;margin-top:6px" onclick="act('guide_stop')">сброс гида</button>
<div class="hint">после каждого шага можно джогом <b>+/−</b> (секция «Лоток — шаги» выше) довести платформу, потом «СЛЕД. ШАГ».</div>

<h2>Заметка в лог</h2>
<div class="note">
  <input id="note" placeholder="напр. полка села ровно">
  <button onclick="sendNote()">Записать</button>
</div>
</div><!-- /tab1 -->

<div id="tab2" style="display:none">
<h2>Адрес ячейки <span style="color:#8b949e;font-weight:400">(depth.rack.shelf)</span></h2>
<div class="jogrow">
  <input id="cell" type="text" value="1.1.6">
  <button onclick="actArg('goto', cellv())">goto (доехать)</button>
</div>
<div class="hint"><b>1</b>.x.x — передний ряд, <b>2</b>.x.x — задний (depth определяет extract_front/rear)</div>

<h2>Хоминг</h2>
<button class="macro" style="width:100%" onclick="confirmAct('home','ХОМИНГ XY (каретка в LEFT+BOTTOM). Продолжить?')">ХОМИНГ XY</button>

<h2>Книга: забрать / положить</h2>
<div class="grid">
  <button class="macro" onclick="confirmActArg('take',cellv(),'Доехать до '+cellv()+' и ЗАБРАТЬ книгу (goto+extract). Продолжить?')">забрать из ячейки<br>(goto + extract)</button>
  <button class="macro" onclick="confirmActArg('put',cellv(),'Доехать до '+cellv()+' и ПОЛОЖИТЬ книгу (goto+return). Продолжить?')">положить в ячейку<br>(goto + return)</button>
</div>

<h2>Шторки окна</h2>
<div class="grid three">
  <button class="endst" onclick="shut('outer','open')">передняя<br>(outer) OPEN</button>
  <button class="endst" onclick="shut('outer','close')">передняя<br>(outer) CLOSE</button>
  <button class="endst" onclick="shut('outer','state')">outer<br>state</button>
  <button class="endst" onclick="shut('inner','open')">задняя<br>(inner) OPEN</button>
  <button class="endst" onclick="shut('inner','close')">задняя<br>(inner) CLOSE</button>
  <button class="endst" onclick="shut('inner','state')">inner<br>state</button>
</div>
<div class="hint">передняя = outer (к человеку), задняя = inner (внутрь). Если перепутано — скажи, поменяю.</div>
</div><!-- /tab2 -->

<h2 style="margin-top:16px">Аварийно</h2>
<button class="stop" onclick="act('stop')">СТОП — снять моторы и замки</button>

<h2>Лог</h2>
<pre id="log"></pre>

<script>
let busy = false;
function setBusy(b){ busy=b; document.getElementById('busy').style.display=b?'block':'none'; }
function renderLog(lines){ const el=document.getElementById('log'); el.textContent=(lines||[]).join('\\n'); el.scrollTop=el.scrollHeight; }
function renderSensors(s){
  document.getElementById('sf').classList.toggle('on', s && s.front===1);
  document.getElementById('sb').classList.toggle('on', s && s.back===1);
}
function renderGuide(g){
  const el=document.getElementById('guideinfo'); if(!el) return;
  if(!g || !g.name){ el.textContent='гид не запущен'; return; }
  if(g.idx>=g.total){ el.textContent=g.name+': все '+g.total+' шагов выполнены'; }
  else { el.textContent=g.name+' — выполнено '+g.idx+'/'+g.total+'.  СЛЕД: '+g.next; }
}
function showTab(n){
  document.getElementById('tab1').style.display = n===1?'block':'none';
  document.getElementById('tab2').style.display = n===2?'block':'none';
  document.getElementById('tabbtn1').classList.toggle('active', n===1);
  document.getElementById('tabbtn2').classList.toggle('active', n===2);
}
function cellv(){ return (document.getElementById('cell').value||'').trim(); }
function actArg(cmd,arg){ act(cmd,arg); }
function confirmActArg(cmd,arg,msg){ if(confirm(msg)) act(cmd,arg); }
function shut(which,action){ act('shutter', {which:which, action:action}); }
function applyPwm(){
  const g=parseInt(document.getElementById('grabpwm').value||'0',10);
  const r=parseInt(document.getElementById('relpwm').value||'0',10);
  act('set_pwm', {grab:g, release:r});
}
let pwmTouched=false;
function renderPwm(p){
  const el=document.getElementById('pwminfo'); if(!el||!p) return;
  el.textContent='текущий: grab '+p.grab+' / release '+p.release+' (джог, макросы, гид, забрать/положить)';
  if(!pwmTouched){ document.getElementById('grabpwm').value=p.grab; document.getElementById('relpwm').value=p.release; }
}
['grabpwm','relpwm'].forEach(function(id){ const e=document.getElementById(id); if(e) e.addEventListener('input',function(){pwmTouched=true;}); });
function applySpeed(){ const f=parseInt(document.getElementById('speed').value||'0',10); act('set_speed', {freq:f}); }
let speedTouched=false;
function renderSpeed(s){
  const el=document.getElementById('speedinfo'); if(!el||!s) return;
  el.textContent='текущая: '+s.freq+' Гц (jog/макросы/гид/забрать/положить; медл. подвод к концевику фикс. 1500)';
  if(!speedTouched){ const e=document.getElementById('speed'); if(e) e.value=s.freq; }
}
(function(){ const e=document.getElementById('speed'); if(e) e.addEventListener('input',function(){speedTouched=true;}); })();
async function act(cmd, arg){
  if(busy){ return; }
  setBusy(true);
  try{
    const r = await fetch('/act',{method:'POST',headers:{'Content-Type':'application/json'},
                                  body:JSON.stringify({cmd:cmd, arg:arg})});
    const d = await r.json();
    if(d.busy){ /* занято */ }
    renderLog(d.log); renderSensors(d.sensors); renderGuide(d.guide); renderPwm(d.pwm); renderSpeed(d.speed);
  }catch(e){ console.error(e); }
  setBusy(false);
}
function jog(n){ act('jog', n); }
function confirmAct(cmd,msg){ if(confirm(msg)) act(cmd); }
function jogCustom(sign){ const v=parseInt(document.getElementById('njog').value||'0',10); if(v>0) act('jog', sign*v); }
function sendNote(){ const el=document.getElementById('note'); if(el.value.trim()){ act('note', el.value.trim()); el.value=''; } }
async function poll(){
  try{ const r=await fetch('/sensors'); const d=await r.json(); renderSensors(d.sensors); renderGuide(d.guide); renderPwm(d.pwm); renderSpeed(d.speed); if(!busy) renderLog(d.log); }
  catch(e){}
}
setInterval(poll, 800); poll();
</script>
</body></html>"""


async def run_blocking(fn, *a):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*a))


def sensors_dict():
    f, b = sensors()
    return {"front": f, "back": b}


async def dispatch(cmd, arg):
    if cmd == "to_front":
        await run_blocking(tray_to_endstop, ENDSTOP_FRONT)
    elif cmd == "to_back":
        await run_blocking(tray_to_endstop, ENDSTOP_BACK)
    elif cmd == "jog":
        n = int(arg)
        await run_blocking(tray_move, abs(n), 1 if n >= 0 else 0)
    elif cmd == "grab_front":
        await run_blocking(lock_grab, LOCK_FRONT)
    elif cmd == "grab_rear":
        await run_blocking(lock_grab, LOCK_REAR)
    elif cmd == "rel_front":
        await run_blocking(lock_release, LOCK_FRONT, False)
    elif cmd == "rel_rear":
        await run_blocking(lock_release, LOCK_REAR, False)
    elif cmd == "rels_front":
        await run_blocking(lock_release, LOCK_FRONT, True)
    elif cmd == "rels_rear":
        await run_blocking(lock_release, LOCK_REAR, True)
    elif cmd == "extract_front":
        await run_blocking(extract_front)
    elif cmd == "extract_rear":
        await run_blocking(extract_rear)
    elif cmd == "front_to_rear":
        await run_blocking(front_to_rear)
    elif cmd == "rear_to_front":
        await run_blocking(rear_to_front)
    elif cmd == "rtf_grab":
        await run_blocking(rtf_grab)
    elif cmd == "rtf_finish":
        await run_blocking(rtf_finish)
    elif cmd == "ftr_grab":
        await run_blocking(ftr_grab)
    elif cmd == "ftr_finish":
        await run_blocking(ftr_finish)
    elif cmd == "guide_front":
        guide_start("front_to_rear")
    elif cmd == "guide_rear":
        guide_start("rear_to_front")
    elif cmd == "guide_next":
        await run_blocking(guide_next)
    elif cmd == "guide_stop":
        GUIDE["name"] = None; GUIDE["idx"] = 0; GUIDE["steps"] = []
        log("ГИД остановлен")
    elif cmd == "home":
        await run_blocking(op_home)
    elif cmd == "goto":
        await run_blocking(op_goto, arg)
    elif cmd == "take":
        await run_blocking(op_take, arg)
    elif cmd == "put":
        await run_blocking(op_put, arg)
    elif cmd == "shutter":
        await run_blocking(op_shutter, (arg or {}).get("which"), (arg or {}).get("action"))
    elif cmd == "set_pwm":
        set_pwm((arg or {}).get("grab"), (arg or {}).get("release"))
    elif cmd == "set_speed":
        set_speed((arg or {}).get("freq"))
    elif cmd == "note":
        log("ЗАМЕТКА: %s" % (arg or ""))
    elif cmd == "stop":
        await run_blocking(cleanup)
        log("СТОП — EN high, замки сняты")
    else:
        raise ValueError("неизвестная команда %s" % cmd)


async def handle_index(request):
    return web.Response(text=HTML, content_type="text/html")


async def handle_act(request):
    data = await request.json()
    cmd = data.get("cmd")
    arg = data.get("arg")
    if ACTION_LOCK.locked():
        return web.json_response({"ok": False, "busy": True, "log": RECENT[-40:],
                                  "sensors": sensors_dict(), "guide": guide_state()})
    async with ACTION_LOCK:
        ok = True
        try:
            await dispatch(cmd, arg)
        except Exception as e:
            log("ОШИБКА %s: %s" % (cmd, e))
            ok = False
    return web.json_response({"ok": ok, "log": RECENT[-40:], "sensors": sensors_dict(),
                              "guide": guide_state(), "pwm": pwm_state(), "speed": speed_state()})


async def handle_sensors(request):
    return web.json_response({"sensors": sensors_dict(), "busy": ACTION_LOCK.locked(),
                              "log": RECENT[-40:], "guide": guide_state(), "pwm": pwm_state()})


async def on_cleanup(app):
    cleanup()
    log("tray_panel ВЫХОД (EN high, замки сняты). Лог: %s" % LOGFILE)
    _logfh.close()


def main():
    setup()
    log("tray_panel СТАРТ на :%d  log=%s" % (PORT, LOGFILE))
    f, b = sensors()
    log("концевики при старте: FRONT=%d BACK=%d" % (f, b))
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_post("/act", handle_act)
    app.router.add_get("/sensors", handle_sensors)
    app.on_cleanup.append(on_cleanup)
    print("\n  Открой в браузере:  http://<IP-RPi>:%d   (или http://localhost:%d на экране шкафа)\n" % (PORT, PORT))
    web.run_app(app, host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
