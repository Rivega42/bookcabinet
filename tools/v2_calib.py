# v2_calib.py - интерактивная калибровка
import datetime

CALIB_LOG = "/home/admin42/bookcabinet/logs/calibration.log"

def log_calib(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CALIB_LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"  [LOG] {msg}")

def interactive_calibrate(current_steps, direction, lock_pin, lock_name, tray_move_fn, lock_grab_fn, lock_release_fn):
    total_offset = 0
    dir_name = "BACK" if direction == 1 else "FRONT"
    opposite_dir = 1 - direction
    opp_name = "FRONT" if direction == 1 else "BACK"
    
    print(f"\n  === КАЛИБРОВКА шага 4.3 ===")
    print(f"  Позиция: {current_steps} шагов к {dir_name}")
    print(f"  Замок: {lock_name} (GPIO {lock_pin})")
    print(f"  Команды:")
    print(f"    +N  — двинуть N шагов к {dir_name}")
    print(f"    -N  — двинуть N шагов к {opp_name}")
    print(f"    g   — замок GRAB")
    print(f"    r   — замок RELEASE")
    print(f"    ok  — готово, продолжить\n")
    
    log_calib(f"START: base={current_steps}, dir={dir_name}, lock={lock_name}")
    
    while True:
        try:
            cmd = input(f"  [{current_steps}{total_offset:+d}] > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return None
        
        if cmd == "ok":
            final = current_steps + total_offset
            log_calib(f"DONE: final={final} (offset={total_offset:+d})")
            return final
        elif cmd == "q":
            log_calib("CANCELLED")
            return None
        elif cmd == "g":
            lock_grab_fn(lock_pin)
            log_calib(f"GRAB {lock_name}")
        elif cmd == "r":
            lock_release_fn(lock_pin)
            log_calib(f"RELEASE {lock_name}")
        elif cmd.lstrip("-+").isdigit():
            try:
                delta = int(cmd)
                if delta > 0:
                    tray_move_fn(abs(delta), direction)
                    total_offset += delta
                    log_calib(f"MOVE +{abs(delta)} to {dir_name}, offset={total_offset:+d}")
                elif delta < 0:
                    tray_move_fn(abs(delta), opposite_dir)
                    total_offset += delta
                    log_calib(f"MOVE {delta} to {opp_name}, offset={total_offset:+d}")
            except ValueError:
                print("  Неверный формат")
        else:
            print("  ? (+N/-N/g/r/ok/q)")
