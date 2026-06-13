#!/usr/bin/env python3
"""
calib_x.py — калибровка X позиций стоек.
Едем к каждой стойке, ждём команду.
Enter=OK, +=правее, -=левее, число=шагов, q=выход
"""
import sys, json, time
sys.path.insert(0, '/home/admin42/bookcabinet/tools')
from book_sequences import BookSequenceRunner, XY_CONFIG

CAL_FILE = '/home/admin42/bookcabinet/calibration.json'
STEP = 100

def ask(prompt):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == '': raise KeyboardInterrupt
    return line.strip()

def main():
    with open(CAL_FILE) as f:
        cal = json.load(f)

    racks_x = {1: int(cal['racks']['1']), 2: int(cal['racks']['2']), 3: int(cal['racks']['3'])}

    print('\n' + '='*50)
    print('  КАЛИБРОВКА X СТОЕК')
    print('  Enter=OK  +=правее  -=левее  число=шагов  q=выход')
    print(f'  Шаг +/-: {STEP} шагов')
    print('='*50)

    r = ask('\nНачинаем? (y/n): ')
    if r.lower() != 'y':
        return

    runner = BookSequenceRunner()
    cur_x = 0
    new_x = dict(racks_x)

    # Едем на среднюю полку Y чтобы было удобно смотреть
    MID_Y = 10320  # полка 10

    try:
        for rack in [1, 2, 3]:
            x_target = new_x[rack]
            print(f'\n{"="*50}')
            print(f'  СТОЙКА {rack} | X={x_target}')
            print(f'  Еду X={x_target}, Y={MID_Y}...')

            runner._home_xy()
            cur_x = 0
            time.sleep(0.3)
            runner._move_to(x_target, MID_Y)
            cur_x = x_target
            time.sleep(0.3)

            current_x = x_target
            while True:
                ans = ask(f'  [Rack {rack}] X={current_x} → ')
                if ans == 'q':
                    raise KeyboardInterrupt
                elif ans == '':
                    print(f'  ✅ OK, X={current_x}')
                    new_x[rack] = current_x
                    break
                elif ans == '+':
                    runner.motion.move(1, 1, STEP, XY_CONFIG.fast)
                    current_x += STEP
                    print(f'  → X={current_x}')
                elif ans == '-':
                    runner.motion.move(0, 0, STEP, XY_CONFIG.fast)
                    current_x -= STEP
                    print(f'  → X={current_x}')
                elif ans.lstrip('-+').isdigit():
                    delta = int(ans)
                    if delta > 0:
                        runner.motion.move(1, 1, delta, XY_CONFIG.fast)
                    else:
                        runner.motion.move(0, 0, abs(delta), XY_CONFIG.fast)
                    current_x += delta
                    print(f'  → X={current_x}')
                else:
                    print('  ? Enter=OK  +=правее  -=левее  число=шагов  q=выход')

    except KeyboardInterrupt:
        print('\n  Прерывание...')
    finally:
        try: runner.close()
        except: pass

    print(f'\n{"="*50}')
    print('  Результат:')
    changed = False
    for rack in [1, 2, 3]:
        old, new = racks_x[rack], new_x[rack]
        diff = new - old
        mark = f'  ({diff:+d})' if diff != 0 else '  (без изменений)'
        print(f'    Rack {rack}: {old} → {new}{mark}')
        if diff != 0: changed = True

    if not changed:
        print('  Коррекций нет!')
        return

    ans = ask('\n  Сохранить в calibration.json? (y/n): ')
    if ans.lower() != 'y':
        print('  Не сохранено.')
        return

    cal['racks']['1'] = new_x[1]
    cal['racks']['2'] = new_x[2]
    cal['racks']['3'] = new_x[3]
    with open(CAL_FILE, 'w') as f:
        json.dump(cal, f, indent=2, ensure_ascii=False)
    print('  ✅ Сохранено!')

if __name__ == '__main__':
    main()
