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

import pigpio
from aiohttp import web

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
EXTRACT_FRONT_FIRST = 16900
EXTRACT_REAR_FIRST = 16800
# Кросс-рядные шаги transfer (из shelf_operations.py front_to_rear/rear_to_front V1)
CROSS_FRONT_TO_REAR_STEP6 = 12500
CROSS_REAR_TO_FRONT_STEP4 = 12700
CROSS_REAR_TO_FRONT_STEP6 = 12600

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
    time.sleep(1500 / TRAY_FREQ)
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
    tray_move(LOCK_DISTANCE, 1)                # S2  12600 → BACK
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
</style></head><body>
<div id="busy">⏳ выполняется движение…</div>

<h2>Концевики лотка</h2>
<div class="sensors">
  <div class="chip" id="sf">FRONT <span class="dot"></span></div>
  <div class="chip" id="sb">BACK <span class="dot"></span></div>
</div>

<h2>Замки</h2>
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

<h2>Заметка в лог</h2>
<div class="note">
  <input id="note" placeholder="напр. полка села ровно">
  <button onclick="sendNote()">Записать</button>
</div>

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
async function act(cmd, arg){
  if(busy){ return; }
  setBusy(true);
  try{
    const r = await fetch('/act',{method:'POST',headers:{'Content-Type':'application/json'},
                                  body:JSON.stringify({cmd:cmd, arg:arg})});
    const d = await r.json();
    if(d.busy){ /* занято */ }
    renderLog(d.log); renderSensors(d.sensors);
  }catch(e){ console.error(e); }
  setBusy(false);
}
function jog(n){ act('jog', n); }
function confirmAct(cmd,msg){ if(confirm(msg)) act(cmd); }
function jogCustom(sign){ const v=parseInt(document.getElementById('njog').value||'0',10); if(v>0) act('jog', sign*v); }
function sendNote(){ const el=document.getElementById('note'); if(el.value.trim()){ act('note', el.value.trim()); el.value=''; } }
async function poll(){
  try{ const r=await fetch('/sensors'); const d=await r.json(); renderSensors(d.sensors); if(!busy) renderLog(d.log); }
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
        return web.json_response({"ok": False, "busy": True,
                                  "log": RECENT[-40:], "sensors": sensors_dict()})
    async with ACTION_LOCK:
        ok = True
        try:
            await dispatch(cmd, arg)
        except Exception as e:
            log("ОШИБКА %s: %s" % (cmd, e))
            ok = False
    return web.json_response({"ok": ok, "log": RECENT[-40:], "sensors": sensors_dict()})


async def handle_sensors(request):
    return web.json_response({"sensors": sensors_dict(),
                              "busy": ACTION_LOCK.locked(), "log": RECENT[-40:]})


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
