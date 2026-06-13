#!/usr/bin/env python3
"""
calib_y_interactive.py — интерактивная калибровка Y.
Обход: rack 1 → полки 1..21, rack 2 → полки 1..21, rack 3 → полки 1..21
В каждой позиции проверяем FRONT и BACK одновременно.
Команды: Enter=OK, +=выше, -=ниже, число=шагов, s=пропустить, q=выход
"""
import sys
import json
import time

sys.path.insert(0, '/home/admin42/bookcabinet/tools')
from book_sequences import BookSequenceRunner, XY_CONFIG

CAL_FILE = '/home/admin42/bookcabinet/calibration.json'
STEP = 100

def load_cal():
    with open(CAL_FILE) as f:
        return json.load(f)

def save_cal(cal):
    with open(CAL_FILE, 'w') as f:
        json.dump(cal, f, indent=2, ensure_ascii=False)

def build_y_table(cal):
    anchors = cal['shelves']['anchors']
    anchor_map = {a['shelf']: a['front_y'] for a in anchors}
    keys = sorted(anchor_map.keys())
    result = {}
    for s in range(22):
        if s in anchor_map:
            result[s] = anchor_map[s]
        else:
            for i in range(len(keys)-1):
                s0, s1 = keys[i], keys[i+1]
                if s0 <= s <= s1:
                    t = (s - s0) / (s1 - s0)
                    result[s] = int(anchor_map[s0] + t*(anchor_map[s1]-anchor_map[s0]))
                    break
    return result

def is_disabled(cal, depth, rack, shelf):
    cell = f'{depth}.{rack}.{shelf}'
    return cell in cal['disabled_cells'] or cell == cal['special_cells'].get('window')

def ask(prompt):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == '':
        raise KeyboardInterrupt
    return line.strip()

def main():
    cal = load_cal()
    y_table = build_y_table(cal)
    racks_x = {1: int(cal['racks']['1']), 2: int(cal['racks']['2']), 3: int(cal['racks']['3'])}

    print('\n' + '='*55)
    print('  КАЛИБРОВКА Y — обход по стойкам')
    print('  Порядок: Rack1 полки 1-21, Rack2 полки 1-21, Rack3 полки 1-21')
    print('  Enter=OK  +=выше  -=ниже  число=шагов  s=пропуск  q=выход')
    print(f'  Шаг +/-: {STEP} шагов')
    print('='*55)
    r = ask('\nКаретка отхомингована? Начинаем? (y/n): ')
    if r.lower() != 'y':
        print('Отмена.')
        return

    runner = BookSequenceRunner()
    cur_x, cur_y = 0, 0
    corrections = {}  # shelf -> новый Y

    try:
        for rack in [1, 2, 3]:
            x_target = racks_x[rack]
            print(f'\n{"="*55}')
            print(f'  СТОЙКА {rack} | X={x_target}')
            print(f'  Еду к X={x_target}...')

            # Сначала хомингуемся по Y (едем вниз), потом к нужному X
            # _move_to считает от нуля, поэтому после каждой стойки нужен хоминг
            runner._home_xy()
            cur_x, cur_y = 0, 0
            time.sleep(0.5)

            # Едем к X стойки
            runner._move_to(x_target, 0)
            cur_x = x_target

            for shelf in range(1, 22):
                has_f = not is_disabled(cal, 1, rack, shelf)
                has_b = not is_disabled(cal, 2, rack, shelf)
                if not has_f and not has_b:
                    print(f'  [Полка {shelf:2d}] заблокирована — пропускаю')
                    continue

                rows = []
                if has_f: rows.append('FRONT')
                if has_b: rows.append('BACK')

                y_target = corrections.get(shelf, y_table[shelf])

                print(f'\n  Полка {shelf:2d} [{"+".join(rows)}]')
                print(f'  Еду Y={y_target}...')

                # Движение только по Y от текущей позиции
                dy = y_target - cur_y
                if dy > 0:
                    runner.motion.move(1, 0, dy, XY_CONFIG.fast)
                elif dy < 0:
                    runner.motion.move(0, 1, abs(dy), XY_CONFIG.fast)
                cur_y = y_target
                time.sleep(0.3)

                current_y = y_target
                while True:
                    ans = ask(f'  [{rack}.{shelf}] Y={current_y} → ')
                    if ans == 'q':
                        raise KeyboardInterrupt
                    elif ans == 's':
                        print('  ⏭ Пропущено')
                        break
                    elif ans == '':
                        print('  ✅ OK')
                        corrections[shelf] = current_y
                        break
                    elif ans == '+':
                        delta = STEP
                        runner.motion.move(1, 0, delta, XY_CONFIG.fast)
                        current_y += delta
                        cur_y = current_y
                        print(f'  ↑ Y={current_y}')
                    elif ans == '-':
                        delta = STEP
                        runner.motion.move(0, 1, delta, XY_CONFIG.fast)
                        current_y -= delta
                        cur_y = current_y
                        print(f'  ↓ Y={current_y}')
                    elif ans.lstrip('-+').isdigit():
                        delta = int(ans)
                        if delta > 0:
                            runner.motion.move(1, 0, delta, XY_CONFIG.fast)
                        else:
                            runner.motion.move(0, 1, abs(delta), XY_CONFIG.fast)
                        current_y += delta
                        cur_y = current_y
                        print(f'  → Y={current_y}')
                    else:
                        print('  ? Enter=OK  +=выше  -=ниже  число=шагов  s=пропуск  q=выход')

    except KeyboardInterrupt:
        print('\n\n  Прерывание...')
    finally:
        try:
            runner.close()
        except:
            pass

    changed = {s: y for s, y in corrections.items() if y != y_table.get(s)}
    print(f'\n{"="*55}')
    if not changed:
        print('  Коррекций нет!')
        return

    print(f'  Скорректировано полок: {len(changed)}')
    for s in sorted(changed):
        old = y_table.get(s, '?')
        new = changed[s]
        diff = new - old if isinstance(old, int) else '?'
        print(f'    Полка {s:2d}: {old} → {new} ({diff:+d})')

    ans = ask('\n  Сохранить в calibration.json? (y/n): ')
    if ans.lower() != 'y':
        print('  Не сохранено.')
        return

    anchors = cal['shelves']['anchors']
    existing = {a['shelf']: a for a in anchors}
    for s, new_y in changed.items():
        if s in existing:
            existing[s]['front_y'] = new_y
            existing[s]['back_y'] = new_y
        else:
            anchors.append({'shelf': s, 'front_y': new_y, 'back_y': new_y})
    anchors.sort(key=lambda a: a['shelf'])
    cal['shelves']['anchors'] = anchors
    save_cal(cal)
    print('  ✅ Сохранено!')

if __name__ == '__main__':
    main()
