#!/usr/bin/env python3
"""
BookCabinet — переместить полочку из одной ячейки в другую.

Использование:
    python3 move_shelf.py <from> <to> [скорость]
    python3 move_shelf.py --v2 <from> <to> [скорость]

Опции:
    --home  хоминг перед стартом
    --v2    режим с концевиками + автоперехват
"""
import os
import sys
import subprocess

DEFAULT_SPEED = 2600
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
GOTO = os.path.join(TOOLS_DIR, 'goto.py')
SHELF_OPS = os.path.join(TOOLS_DIR, 'shelf_operations.py')


def parse_depth(address):
    return int(address.split('.')[0])


def run(cmd):
    print(f'\n>>> {" ".join(cmd)}')
    return subprocess.call(cmd)


def main():
    args = sys.argv[1:]
    
    home = '--home' in args
    use_v2 = '--v2' in args
    
    flags = ('--home', '--v2')
    pos_args = [a for a in args if a not in flags]
    
    if len(pos_args) < 2:
        print(__doc__)
        return 1
    
    src, dst = pos_args[0], pos_args[1]
    speed = pos_args[2] if len(pos_args) >= 3 else str(DEFAULT_SPEED)
    
    src_depth = parse_depth(src)
    dst_depth = parse_depth(dst)
    
    extract_cmd = 'extract_rear' if src_depth == 2 else 'extract_front'
    
    if use_v2:
        # v2 с параметром from_depth
        return_cmd = f'return_rear_v2:{src_depth}' if dst_depth == 2 else f'return_front_v2:{src_depth}'
    else:
        return_cmd = 'return_rear' if dst_depth == 2 else 'return_front'
    
    print('=' * 60)
    print(f'  MOVE: {src} -> {dst}')
    print(f'  extract={extract_cmd}, return={return_cmd}')
    print('=' * 60)
    
    # Шаг 1: goto src
    goto_args = ['python3', GOTO]
    if home:
        goto_args += ['--home']
    goto_args += [speed, src]
    if run(goto_args) != 0:
        return 1
    
    # Шаг 2: extract
    if run(['python3', SHELF_OPS, extract_cmd]) != 0:
        return 1
    
    # Шаг 3: goto dst
    if run(['python3', GOTO, speed, dst]) != 0:
        return 1
    
    # Шаг 4: return
    if use_v2:
        # Вызываем напрямую с параметром
        cmd_name, from_depth = return_cmd.split(':')
        if run(['python3', '-c', 
                f'import sys; sys.path.insert(0, "{TOOLS_DIR}"); '
                f'from shelf_operations import {cmd_name}; '
                f'{cmd_name}(from_depth={from_depth})']) != 0:
            return 1
    else:
        if run(['python3', SHELF_OPS, return_cmd]) != 0:
            return 1
    
    print('\n' + '=' * 60)
    print(f'  DONE: {src} -> {dst}')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
