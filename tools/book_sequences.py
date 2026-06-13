#!/usr/bin/env python3
"""
BookCabinet — Book Issue/Return Mechanical Sequences

Standalone Python script implementing full issue and return cycles
using the existing hardware tools (corexy_motion_v2, tray_platform, calibration).

Importable by bridge.py for integration with the TS server.

GPIO pin assignments:
  Shutters: SHUTTER_OUTER=2 (HIGH=open, LOW=close), SHUTTER_INNER=3
  Locks:    LOCK_FRONT=12, LOCK_REAR=13 (PWM servos: 500us=open, 1500us=close)
  Tray:     STEP=18, DIR=27, EN1=25, EN2=26

Usage:
  python3 tools/book_sequences.py issue 1.1.5
  python3 tools/book_sequences.py return 1.3.7
  python3 tools/book_sequences.py test-shutters
"""
# IMPORTANT: These GPIO pin constants MUST match bookcabinet/config.py GPIO_PINS.
# TODO: Import from config.py to eliminate duplication (see issue #59).
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Callable, Optional

# Allow imports from the tools directory when run standalone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from corexy_motion_v2 import CoreXYMotionV2, MotionConfig
from tray_platform import TrayPlatform
from calibration import resolve_cell, get_window

import pigpio

# === GPIO pins ===
SHUTTER_OUTER = 2
SHUTTER_INNER = 3
LOCK_FRONT = 12
LOCK_REAR = 13

# === XY homing config (confirmed safe baseline) ===
XY_CONFIG = MotionConfig(fast=800, homing_fast=1800, slow=300, backoff_x=300, backoff_y=500)

# === Timing constants ===
ISSUE_USER_WAIT_SEC = 30
RETURN_USER_WAIT_SEC = 60
SHUTTER_SETTLE_SEC = 0.3
LOCK_SETTLE_SEC = 0.3
MOVE_SETTLE_SEC = 0.2


POS_FILE = '/tmp/carriage_pos.json'

def _save_pos(x, y, address=''):
    import json
    try:
        with open(POS_FILE, 'w') as f:
            json.dump({'x': x, 'y': y, 'address': address}, f)
    except Exception:
        pass

class SequenceError(Exception):
    """Raised when a sequence step fails."""
    pass


class BookSequenceRunner:
    """
    Controls the full mechanical sequence for issuing/returning books.
    Manages XY motion, tray, shutters, and locks via pigpio.
    """

    # Class-level lock prevents concurrent issue/return sequences
    # across all BookSequenceRunner instances (issue #44).
    _global_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, pi: Optional[pigpio.pi] = None, progress_cb: Optional[Callable] = None):
        self._owns_pi = pi is None
        self.pi = pi or pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("Cannot connect to pigpiod")

        self.progress_cb = progress_cb or (lambda **kw: None)
        self.motion: Optional[CoreXYMotionV2] = None
        self.tray: Optional[TrayPlatform] = None
        self._shutters_setup = False

    def _emit(self, step: int, label: str, status: str = "running", **extra):
        """Emit a progress event."""
        event = {"step": step, "label": label, "status": status, **extra}
        self.progress_cb(**event)

    def _setup_shutters(self):
        """Configure shutter and lock pins as outputs."""
        if self._shutters_setup:
            return
        for pin in [SHUTTER_OUTER, SHUTTER_INNER, LOCK_FRONT, LOCK_REAR]:
            self.pi.set_mode(pin, pigpio.OUTPUT)
        # Ensure shutters are closed at startup
        self.pi.write(SHUTTER_OUTER, 0)
        self.pi.write(SHUTTER_INNER, 0)
        self._shutters_setup = True

    def _open_shutter(self, pin: int):
        self.pi.write(pin, 1)
        time.sleep(SHUTTER_SETTLE_SEC)

    def _close_shutter(self, pin: int):
        self.pi.write(pin, 0)
        time.sleep(SHUTTER_SETTLE_SEC)

    def _open_lock(self, pin: int):
        self.pi.set_servo_pulsewidth(pin, 500)   # 0° = открыт
        time.sleep(0.5)
        self.pi.set_servo_pulsewidth(pin, 0)     # снять нагрузку с сервы

    def _close_lock(self, pin: int):
        self.pi.set_servo_pulsewidth(pin, 1500)  # 90° = закрыт
        time.sleep(0.5)
        self.pi.set_servo_pulsewidth(pin, 0)     # снять нагрузку с сервы

    def _safe_shutdown(self, reason: str = "unknown"):
        """Emergency safe state: close shutters, unlock locks, retract tray, stop motion."""
        log = logging.getLogger(__name__)
        log.error(f"EMERGENCY SHUTDOWN: {reason}")

        # 1. Close shutters
        try:
            self.pi.write(SHUTTER_OUTER, 0)
            self.pi.write(SHUTTER_INNER, 0)
        except Exception as e:
            log.error(f"  Failed to close shutters: {e}")

        # 2. Unlock BOTH locks (PWM!) — КРИТИЧНО чтобы книга не застряла
        try:
            self.pi.set_servo_pulsewidth(LOCK_FRONT, 500)
            self.pi.set_servo_pulsewidth(LOCK_REAR, 500)
            time.sleep(0.5)
            self.pi.set_servo_pulsewidth(LOCK_FRONT, 0)
            self.pi.set_servo_pulsewidth(LOCK_REAR, 0)
            log.info("  Locks unlocked for safety")
        except Exception as e:
            log.error(f"  Failed to unlock: {e}")

        # 3. Retract tray
        try:
            if self.tray:
                self.tray.go_front()
        except Exception as e:
            log.error(f"  Failed to retract tray: {e}")

        # 4. Stop motion
        try:
            if self.motion:
                self.motion.stop()
        except Exception as e:
            log.error(f"  Failed to stop motion: {e}")

    def _init_motion(self) -> CoreXYMotionV2:
        """Initialize XY motion controller (reuse if already created)."""
        if self.motion is None:
            self.motion = CoreXYMotionV2(pi=self.pi, config=XY_CONFIG)
        return self.motion

    def _init_tray(self) -> TrayPlatform:
        """Initialize tray platform controller (reuse if already created)."""
        if self.tray is None:
            self.tray = TrayPlatform()
        return self.tray

    def _move_to(self, x: int, y: int):
        """Move carriage to absolute position using CoreXY motion.

        Since home is LEFT+BOTTOM (0,0), moving to (x,y) means:
          X right: A=1, B=1
          Y up:    A=1, B=0
        We use the motion.move() with a large step count and speed,
        relying on the step count for positioning.
        """
        motion = self._init_motion()
        # Move X: right is A=1, B=1
        if x > 0:
            motion.move(1, 1, x, XY_CONFIG.fast)  # X right
            time.sleep(MOVE_SETTLE_SEC)
        # Move Y: up is A=1, B=0
        if y > 0:
            motion.move(1, 0, y, XY_CONFIG.fast)  # Y up
            time.sleep(MOVE_SETTLE_SEC)
        _save_pos(x, y)

    def _home_xy(self) -> bool:
        """Home XY to LEFT+BOTTOM."""
        motion = self._init_motion()
        ok = motion.home_xy()
        if ok:
            _save_pos(0, 0, 'home')
        return ok

    async def issue_book_sequence(self, cell_address: str) -> dict:
        """
        Full issue sequence (книговыдача):
        1. Home XY (if not already homed)
        2. Move carriage to cell
        3. Open inner shutter
        4. Extend tray BACK (grab shelf)
        5. Close inner shutter
        6. Move carriage to window
        7. Open inner shutter
        8. Close front lock, extend tray FRONT
        9. Open outer shutter
        10. Wait for user (30 sec)
        11. Close outer shutter
        12. Retract tray
        13. Close inner shutter
        14. Home

        Returns: dict with success, steps executed, timing info
        """
        # Early validation of cell address — fail fast before touching hardware (issue #61)
        try:
            x, y = resolve_cell(cell_address)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Ячейка {cell_address} недоступна: {e}",
                "cell": cell_address,
                "steps": [],
                "elapsed_sec": 0.0,
            }

        # Prevent concurrent sequences (issue #44)
        if self._global_lock.locked():
            return {
                "success": False,
                "error": "Другая операция уже выполняется",
                "cell": cell_address,
                "steps": [],
                "elapsed_sec": 0.0,
            }

        async with self._global_lock:
            return await self._issue_book_sequence_impl(cell_address, x, y)

    async def _issue_book_sequence_impl(self, cell_address: str, x: int, y: int) -> dict:
        t_start = time.time()
        steps_done = []

        try:
            self._setup_shutters()

            # Step 1: Home XY
            self._emit(1, "Homing XY", "running")
            ok = self._home_xy()
            if not ok:
                raise SequenceError("XY homing failed")
            self._emit(1, "Homing XY", "done")
            steps_done.append("home_xy")

            # Step 2: Move carriage to cell
            self._emit(2, "Moving to cell", "running", cell=cell_address)
            self._move_to(x, y)
            self._emit(2, "Moving to cell", "done", cell=cell_address, x=x, y=y)
            steps_done.append("move_to_cell")

            # Step 3: Open inner shutter
            self._emit(3, "Opening inner shutter", "running")
            self._open_shutter(SHUTTER_INNER)
            self._emit(3, "Opening inner shutter", "done")
            steps_done.append("open_inner")

            # Step 4: Extend tray BACK (grab the shelf)
            self._emit(4, "Extending tray back", "running")
            tray = self._init_tray()
            tray_ok = tray.go_back()
            if not tray_ok:
                raise SequenceError("Tray extend back failed")
            self._emit(4, "Extending tray back", "done")
            steps_done.append("tray_back")

            # Step 5: Close inner shutter
            self._emit(5, "Closing inner shutter", "running")
            self._close_shutter(SHUTTER_INNER)
            self._emit(5, "Closing inner shutter", "done")
            steps_done.append("close_inner")

            # Step 6: Move carriage to window
            self._emit(6, "Moving to window", "running")
            # Must home first to reset position, then move to window
            ok = self._home_xy()
            if not ok:
                raise SequenceError("XY homing before window move failed")
            window_addr = get_window()
            wx, wy = resolve_cell(window_addr)
            self._move_to(wx, wy)
            self._emit(6, "Moving to window", "done", window=window_addr, x=wx, y=wy)
            steps_done.append("move_to_window")

            # Step 7: Open inner shutter
            self._emit(7, "Opening inner shutter at window", "running")
            self._open_shutter(SHUTTER_INNER)
            self._emit(7, "Opening inner shutter at window", "done")
            steps_done.append("open_inner_window")

            # Step 8: Close front lock + extend tray FRONT
            self._emit(8, "Locking front, extending tray", "running")
            self._close_lock(LOCK_FRONT)
            tray_ok = tray.go_front()
            if not tray_ok:
                raise SequenceError("Tray extend front failed")
            self._emit(8, "Locking front, extending tray", "done")
            steps_done.append("lock_tray_front")

            # Step 9: Open outer shutter
            self._emit(9, "Opening outer shutter", "running")
            self._open_shutter(SHUTTER_OUTER)
            self._emit(9, "Opening outer shutter", "done", wait_seconds=ISSUE_USER_WAIT_SEC)
            steps_done.append("open_outer")

            # Step 10: Wait for user (30 sec)
            self._emit(10, "Waiting for user", "running", wait_seconds=ISSUE_USER_WAIT_SEC)
            await asyncio.sleep(ISSUE_USER_WAIT_SEC)
            self._emit(10, "Waiting for user", "done")
            steps_done.append("user_wait")

            # Step 11: Close outer shutter
            self._emit(11, "Closing outer shutter", "running")
            self._close_shutter(SHUTTER_OUTER)
            self._emit(11, "Closing outer shutter", "done")
            steps_done.append("close_outer")

            # Step 12: Retract tray
            self._emit(12, "Retracting tray", "running")
            tray_ok = tray.go_back()
            if not tray_ok:
                raise SequenceError("Tray retract failed")
            self._emit(12, "Retracting tray", "done")
            steps_done.append("retract_tray")

            # Step 13: Close inner shutter
            self._emit(13, "Closing inner shutter", "running")
            self._close_shutter(SHUTTER_INNER)
            self._emit(13, "Closing inner shutter", "done")
            steps_done.append("close_inner_final")

            # Step 14: Home
            self._emit(14, "Homing", "running")
            ok = self._home_xy()
            if not ok:
                raise SequenceError("Final homing failed")
            self._emit(14, "Homing", "done")
            steps_done.append("final_home")

            elapsed = round(time.time() - t_start, 2)
            return {
                "success": True,
                "cell": cell_address,
                "steps": steps_done,
                "elapsed_sec": elapsed,
            }

        except Exception as e:
            self._safe_shutdown(reason=f"issue_book_sequence failed: {e}")
            elapsed = round(time.time() - t_start, 2)
            return {
                "success": False,
                "error": str(e),
                "cell": cell_address,
                "steps": steps_done,
                "elapsed_sec": elapsed,
            }

    async def return_book_sequence(self, free_cell_address: str) -> dict:
        """
        Full return sequence (книгоприём):
        1. Home XY
        2. Move to window
        3. Open outer shutter
        4. Wait for book placement (60 sec)
        5. Close outer shutter
        6. Open inner shutter
        7. Retract tray (pull shelf in)
        8. Close inner shutter
        9. Move carriage to free cell
        10. Open inner shutter
        11. Extend tray BACK (place shelf)
        12. Close inner shutter
        13. Home

        Returns: dict with success, steps executed, timing info
        """
        # Early validation of cell address — fail fast before touching hardware (issue #61)
        try:
            x, y = resolve_cell(free_cell_address)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Ячейка {free_cell_address} недоступна: {e}",
                "cell": free_cell_address,
                "steps": [],
                "elapsed_sec": 0.0,
            }

        # Prevent concurrent sequences (issue #44)
        if self._global_lock.locked():
            return {
                "success": False,
                "error": "Другая операция уже выполняется",
                "cell": free_cell_address,
                "steps": [],
                "elapsed_sec": 0.0,
            }

        async with self._global_lock:
            return await self._return_book_sequence_impl(free_cell_address, x, y)

    async def _return_book_sequence_impl(self, free_cell_address: str, x: int, y: int) -> dict:
        t_start = time.time()
        steps_done = []

        try:
            self._setup_shutters()

            # Step 1: Home XY
            self._emit(1, "Homing XY", "running")
            ok = self._home_xy()
            if not ok:
                raise SequenceError("XY homing failed")
            self._emit(1, "Homing XY", "done")
            steps_done.append("home_xy")

            # Step 2: Move to window
            self._emit(2, "Moving to window", "running")
            window_addr = get_window()
            wx, wy = resolve_cell(window_addr)
            self._move_to(wx, wy)
            self._emit(2, "Moving to window", "done", window=window_addr, x=wx, y=wy)
            steps_done.append("move_to_window")

            # Step 3: Open outer shutter
            self._emit(3, "Opening outer shutter", "running")
            self._open_shutter(SHUTTER_OUTER)
            self._emit(3, "Opening outer shutter", "done", wait_seconds=RETURN_USER_WAIT_SEC)
            steps_done.append("open_outer")

            # Step 4: Wait for book placement (60 sec)
            self._emit(4, "Waiting for book placement", "running", wait_seconds=RETURN_USER_WAIT_SEC)
            await asyncio.sleep(RETURN_USER_WAIT_SEC)
            self._emit(4, "Waiting for book placement", "done")
            steps_done.append("user_wait")

            # Step 5: Close outer shutter
            self._emit(5, "Closing outer shutter", "running")
            self._close_shutter(SHUTTER_OUTER)
            self._emit(5, "Closing outer shutter", "done")
            steps_done.append("close_outer")

            # Step 6: Open inner shutter
            self._emit(6, "Opening inner shutter", "running")
            self._open_shutter(SHUTTER_INNER)
            self._emit(6, "Opening inner shutter", "done")
            steps_done.append("open_inner")

            # Step 7: Retract tray (pull shelf in)
            self._emit(7, "Retracting tray", "running")
            tray = self._init_tray()
            tray_ok = tray.go_back()
            if not tray_ok:
                raise SequenceError("Tray retract failed")
            self._emit(7, "Retracting tray", "done")
            steps_done.append("retract_tray")

            # Step 8: Close inner shutter
            self._emit(8, "Closing inner shutter", "running")
            self._close_shutter(SHUTTER_INNER)
            self._emit(8, "Closing inner shutter", "done")
            steps_done.append("close_inner")

            # Step 9: Move carriage to free cell
            self._emit(9, "Moving to cell", "running", cell=free_cell_address)
            # Home first to reset position
            ok = self._home_xy()
            if not ok:
                raise SequenceError("XY homing before cell move failed")
            self._move_to(x, y)
            self._emit(9, "Moving to cell", "done", cell=free_cell_address, x=x, y=y)
            steps_done.append("move_to_cell")

            # Step 10: Open inner shutter
            self._emit(10, "Opening inner shutter", "running")
            self._open_shutter(SHUTTER_INNER)
            self._emit(10, "Opening inner shutter", "done")
            steps_done.append("open_inner_cell")

            # Step 11: Extend tray BACK (place shelf into cell)
            self._emit(11, "Extending tray back", "running")
            tray_ok = tray.go_back()
            if not tray_ok:
                raise SequenceError("Tray extend back failed")
            self._emit(11, "Extending tray back", "done")
            steps_done.append("tray_back")

            # Step 12: Close inner shutter
            self._emit(12, "Closing inner shutter", "running")
            self._close_shutter(SHUTTER_INNER)
            self._emit(12, "Closing inner shutter", "done")
            steps_done.append("close_inner_final")

            # Step 13: Home
            self._emit(13, "Homing", "running")
            ok = self._home_xy()
            if not ok:
                raise SequenceError("Final homing failed")
            self._emit(13, "Homing", "done")
            steps_done.append("final_home")

            elapsed = round(time.time() - t_start, 2)
            return {
                "success": True,
                "cell": free_cell_address,
                "steps": steps_done,
                "elapsed_sec": elapsed,
            }

        except Exception as e:
            self._safe_shutdown(reason=f"return_book_sequence failed: {e}")
            elapsed = round(time.time() - t_start, 2)
            return {
                "success": False,
                "error": str(e),
                "cell": free_cell_address,
                "steps": steps_done,
                "elapsed_sec": elapsed,
            }

    def close(self):
        """Clean up hardware resources."""
        try:
            if self.motion:
                self.motion.close()
                self.motion = None
        except Exception:
            pass
        try:
            if self.tray:
                self.tray.close()
                self.tray = None
        except Exception:
            pass
        if self._owns_pi:
            try:
                self.pi.stop()
            except Exception:
                pass


def _json_progress(**event):
    """Print progress as JSON line to stdout (for bridge.py integration)."""
    print(json.dumps({"type": "progress", **event}, ensure_ascii=False), flush=True)


async def main_async(argv: list[str]) -> int:
    if len(argv) < 1:
        print(__doc__)
        return 1

    cmd = argv[0]
    runner = BookSequenceRunner(progress_cb=_json_progress)

    try:
        if cmd == "issue":
            if len(argv) < 2:
                print("Usage: book_sequences.py issue <cell_address>")
                return 1
            cell = argv[1]
            result = await runner.issue_book_sequence(cell)
            print(json.dumps({"type": "result", **result}, ensure_ascii=False), flush=True)
            return 0 if result["success"] else 1

        elif cmd == "return":
            if len(argv) < 2:
                print("Usage: book_sequences.py return <cell_address>")
                return 1
            cell = argv[1]
            result = await runner.return_book_sequence(cell)
            print(json.dumps({"type": "result", **result}, ensure_ascii=False), flush=True)
            return 0 if result["success"] else 1

        elif cmd == "test-shutters":
            runner._setup_shutters()
            print("Opening inner shutter (pin 3)...")
            runner._open_shutter(SHUTTER_INNER)
            time.sleep(1)
            print("Closing inner shutter...")
            runner._close_shutter(SHUTTER_INNER)
            time.sleep(0.5)
            print("Opening outer shutter (pin 2)...")
            runner._open_shutter(SHUTTER_OUTER)
            time.sleep(1)
            print("Closing outer shutter...")
            runner._close_shutter(SHUTTER_OUTER)
            print("Shutter test complete.")
            return 0

        else:
            print(f"Unknown command: {cmd}")
            print(__doc__)
            return 1

    finally:
        runner.close()


def main():
    return asyncio.run(main_async(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
