#!/usr/bin/env python3
"""
homing_pigpio.py v5 — canonical BookCabinet homing wrapper.
HOME = LEFT + BOTTOM.
Implementation delegates to corexy_motion_v2.
"""
from __future__ import annotations

import os
from corexy_motion_v2 import CoreXYMotionV2, MotionConfig

CONFIG = MotionConfig(
    fast=800,
    slow=300,
    backoff_x=300,
    backoff_y=500,
)

LOCK_FRONT = 12
LOCK_REAR = 13


def locks_to_zero():
    """Сбросить замки в 0 перед хомингом"""
    print('[INIT] Замки -> 0')
    os.system(f'pigs s {LOCK_FRONT} 0')
    os.system(f'pigs s {LOCK_REAR} 0')


def main() -> int:
    print('=' * 50)
    print('  HOMING BookCabinet v5 (corexy_motion_v2)')
    print(
        f'  FAST={CONFIG.fast} SLOW={CONFIG.slow} '
        f'BACKOFF_X={CONFIG.backoff_x} BACKOFF_Y={CONFIG.backoff_y}'
    )
    print('  HOME = LEFT(pin9) + BOTTOM(pin8)')
    print('=' * 50)

    # Сбросить замки перед хомингом
    locks_to_zero()

    try:
        with CoreXYMotionV2(config=CONFIG) as motion:
            print('\n[INIT] Состояние концевиков:')
            for name, value in motion.state().items():
                print(f'  {name}: {"НАЖАТ" if value == 1 else "свободен"}')

            ok = motion.home_xy()
            if ok:
                print('\n==> HOME OK: LEFT + BOTTOM')
                return 0

            print('\n==> Хоминг завершён с ошибками')
            return 1
    except KeyboardInterrupt:
        print('\nПрервано')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
