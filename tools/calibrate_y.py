#!/usr/bin/env python3
"""
calibrate_y.py — интерактивная калибровка Y-позиций всех полок.
Обход: shelf 1..21, в каждой полке rack 1..3.
Front и Back — проверяются одновременно (каретка в одной X-позиции).
Управление: Enter=OK, +=выше, -=ниже, s=пропустить, q=выход.
"""
import json
import sys
import os
import time
import pigpio

CAL_FILE = "/home/admin42/bookcabinet/calibration.json"
STEP = 50  # шагов на каждое +/-

# GPIO CoreXY (из config)
PIN_A_STEP = 14
PIN_A_DIR  = 15
PIN_B_STEP = 19
PIN_B_DIR  = 21

RACKS_X = {1: 100, 2: 10220, 3: 20370}  # из calibration.json

def load_cal():
    with open(CAL_FILE) as f:
        return json.load(f)

def save_cal(cal):
    with open(CAL_FILE, "w") as f:
        json.dump(cal, f, indent=2, ensure_ascii=False)
    print("  💾 Сохранено.")

def get_anchor_map(cal):
    anchors = cal["shelves"]["anchors"]
    return {a["shelf"]: {"front_y": a["front_y"], "back_y": a["back_y"]} for a in anchors}

def interpolate_y(anchor_map, shelf):
    keys = sorted(anchor_map.keys())
    for i in range(len(keys)-1):
        s0, s1 = keys[i], keys[i+1]
        if s0 <= shelf <= s1:
            y0 = anchor_map[s0]["front_y"]
            y1 = anchor_map[s1]["front_y"]
            t = (shelf - s0) / (s1 - s0)
            val = int(y0 + t*(y1-y0))
            return val
    return None

def build_y_table(cal):
    """Полная таблица Y для всех полок 0-21"""
    anchor_map = get_anchor_map(cal)
    result = {}
    for s in range(22):
        if s in anchor_map:
            result[s] = anchor_map[s]["front_y"]
        else:
            result[s] = interpolate_y(anchor_map, s)
    return result

def is_disabled(cal, depth, rack, shelf):
    cell = f"{depth}.{rack}.{shelf}"
    return cell in cal["disabled_cells"] or cell == cal["special_cells"].get("window")

def move_to_y(pi, current_y, target_y):
    """Движение по Y через CoreXY: Y+ = A=1,B=1; Y- = A=0,B=0"""
    steps = abs(target_y - current_y)
    if steps == 0:
        return
    direction = 1 if target_y > current_y else 0
    # DIR для обоих моторов
    pi.write(PIN_A_DIR, direction)
    pi.write(PIN_B_DIR, direction)
    pi.set_mode(PIN_A_STEP, pigpio.OUTPUT)
    pi.set_mode(PIN_B_STEP, pigpio.OUTPUT)
    # Генерируем шаги
    freq = 2000
    period_us = int(1_000_000 / freq)
    pulse_us = period_us // 2
    pi.wave_clear()
    wf = [
        pigpio.pulse(1<<PIN_A_STEP | 1<<PIN_B_STEP, 0, pulse_us),
        pigpio.pulse(0, 1<<PIN_A_STEP | 1<<PIN_B_STEP, pulse_us),
    ]
    pi.wave_add_generic(wf)
    wid = pi.wave_create()
    pi.wave_send_repeat(wid)
    time.sleep(steps / freq)
    pi.wave_tx_stop()
    pi.wave_delete(wid)
    pi.wave_clear()

def move_to_x(pi, current_x, target_x):
    """Движение по X: X+ = A=1,B=0; X- = A=0,B=1"""
    steps = abs(target_x - current_x)
    if steps == 0:
        return
    if target_x > current_x:
        pi.write(PIN_A_DIR, 1)
        pi.write(PIN_B_DIR, 0)
    else:
        pi.write(PIN_A_DIR, 0)
        pi.write(PIN_B_DIR, 1)
    freq = 2000
    period_us = int(1_000_000 / freq)
    pulse_us = period_us // 2
    pi.wave_clear()
    wf = [
        pigpio.pulse(1<<PIN_A_STEP | 1<<PIN_B_STEP, 0, pulse_us),
        pigpio.pulse(0, 1<<PIN_A_STEP | 1<<PIN_B_STEP, pulse_us),
    ]
    pi.wave_add_generic(wf)
    wid = pi.wave_create()
    pi.wave_send_repeat(wid)
    time.sleep(steps / freq)
    pi.wave_tx_stop()
    pi.wave_delete(wid)
    pi.wave_clear()

def ask(prompt):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.readline().strip()

def main():
    cal = load_cal()
    disabled = set(cal["disabled_cells"])
    y_table = build_y_table(cal)
    anchor_map = get_anchor_map(cal)
    corrections = {}  # shelf -> delta

    print("\n" + "="*60)
    print("  КАЛИБРОВКА Y — интерактивный обход ячеек")
    print("  Enter=OK  +=выше  -=ниже  s=пропустить  q=выход")
    print("  Шаг коррекции: 50 шагов (~0.3мм)")
    print("="*60)
    print("\n⚠️  Убедись что каретка отхоумингована!")
    r = ask("Готов? (y/n): ")
    if r.lower() != 'y':
        print("Отмена.")
        return

    pi = pigpio.pi()
    if not pi.connected:
        print("❌ pigpio не подключён!")
        return

    cur_x, cur_y = 0, 0
    total = 0
    corrected = 0

    try:
        for shelf in range(1, 22):  # 1..21 (0 — нижний упор, пропускаем)
            # Проверяем есть ли хоть одна активная ячейка на этой полке
            active_racks = []
            for rack in [1, 2, 3]:
                # Проверяем depth 1 и 2
                d1 = not is_disabled(cal, 1, rack, shelf)
                d2 = not is_disabled(cal, 2, rack, shelf)
                if d1 or d2:
                    active_racks.append((rack, d1, d2))

            if not active_racks:
                print(f"\n  [Полка {shelf}] — все ячейки заблокированы, пропускаю")
                continue

            y_target = y_table[shelf] + corrections.get(shelf, 0)
            print(f"\n{'='*60}")
            print(f"  ПОЛКА {shelf:2d} | Y={y_target} шагов")
            print(f"  Активные стойки: {[r[0] for r in active_racks]}")

            for rack, has_front, has_back in active_racks:
                x_target = RACKS_X[rack]
                rows_info = []
                if has_front: rows_info.append("FRONT(1)")
                if has_back:  rows_info.append("BACK(2)")

                print(f"\n  → Rack {rack} | X={x_target} | {' + '.join(rows_info)}")

                # Двигаемся
                if cur_y != y_target:
                    print(f"    Еду к Y={y_target}...")
                    move_to_y(pi, cur_y, y_target)
                    cur_y = y_target
                if cur_x != x_target:
                    print(f"    Еду к X={x_target}...")
                    move_to_x(pi, cur_x, x_target)
                    cur_x = x_target

                # Запрашиваем оценку
                current_y_pos = y_target
                while True:
                    total += 1
                    ans = ask(f"    [{shelf}.{rack}] Y={current_y_pos} → [Enter=OK / + / - / s / q]: ")
                    if ans == 'q':
                        raise KeyboardInterrupt
                    elif ans == 's':
                        print("    ⏭ Пропущено")
                        break
                    elif ans == '':
                        print("    ✅ OK")
                        break
                    elif ans == '+':
                        current_y_pos += STEP
                        print(f"    ↑ Y={current_y_pos}")
                        move_to_y(pi, cur_y, current_y_pos)
                        cur_y = current_y_pos
                    elif ans == '-':
                        current_y_pos -= STEP
                        print(f"    ↓ Y={current_y_pos}")
                        move_to_y(pi, cur_y, current_y_pos)
                        cur_y = current_y_pos
                    elif ans.lstrip('-').isdigit():
                        # Прямой ввод числа шагов
                        current_y_pos += int(ans)
                        print(f"    → Y={current_y_pos}")
                        move_to_y(pi, cur_y, current_y_pos)
                        cur_y = current_y_pos
                    else:
                        print("    ? Не понял. Enter=OK, +=выше, -=ниже, s=пропуск, q=выход")
                        continue

                # Если была коррекция — сохраняем дельту для этой полки
                delta = current_y_pos - y_table[shelf]
                if delta != 0:
                    corrections[shelf] = delta
                    corrected += 1

            y_table[shelf] = y_table[shelf] + corrections.get(shelf, 0)

    except KeyboardInterrupt:
        pass

    print(f"\n{'='*60}")
    print(f"  Проверено позиций: {total}")
    print(f"  Скорректировано полок: {len(corrections)}")

    if corrections:
        print("\n  Коррекции:")
        for s in sorted(corrections):
            print(f"    Полка {s:2d}: {'+' if corrections[s]>0 else ''}{corrections[s]} шагов → Y={y_table[s]}")

        ans = ask("\n  Сохранить изменения в calibration.json? (y/n): ")
        if ans.lower() == 'y':
            # Обновляем анкоры — добавляем/обновляем для скорректированных полок
            new_anchors = list(cal["shelves"]["anchors"])
            existing_shelves = {a["shelf"] for a in new_anchors}
            for s, delta in corrections.items():
                new_y = y_table[s]
                if s in existing_shelves:
                    for a in new_anchors:
                        if a["shelf"] == s:
                            a["front_y"] = new_y
                            a["back_y"] = new_y
                else:
                    new_anchors.append({"shelf": s, "front_y": new_y, "back_y": new_y})
            new_anchors.sort(key=lambda a: a["shelf"])
            cal["shelves"]["anchors"] = new_anchors
            save_cal(cal)
            print("  ✅ calibration.json обновлён!")
        else:
            print("  ℹ️  Изменения не сохранены.")
    else:
        print("  ✅ Коррекций нет, всё точно!")

    pi.stop()

if __name__ == "__main__":
    main()
