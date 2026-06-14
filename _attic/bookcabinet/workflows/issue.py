"""
Production book issue workflow.
Implements the 18-step sequence from issue #79.

Uses subprocess calls to tested standalone tools (goto.py, shelf_operations.py,
shutter.py) for hardware operations. RFID via bookcabinet.rfid.book_reader.

Steps:
  1.  Start
  2.  PARALLEL: open inner shutter + goto source cell
  3.  Extract shelf from source
  4.  Goto window (inner already open)
  5.  Return shelf to window
  6.  Close inner shutter
  7.  RFID verify (mismatch -> return shelf, abort)
  8.  Open outer shutter
  9.  Screen: "pick up book" + countdown
  10. Poll RFID: wait for tag to disappear
  11. Tag gone -> 5 sec grace; or timeout -> book not picked up
  12. Close outer shutter
  13. Open inner shutter
  14. Extract (empty) shelf from window
  15. Goto source
  16. Return shelf to source
  17. Close inner shutter
  18. Log result
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

# Paths to standalone tools
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'tools')
_GOTO = os.path.join(_TOOLS_DIR, 'goto.py')
_SHELF_OPS = os.path.join(_TOOLS_DIR, 'shelf_operations.py')
_SHUTTER = os.path.join(_TOOLS_DIR, 'shutter.py')

# Timing constants
SHUTTER_WAIT = 15        # seconds to wait for shutter physical travel (10 real + 5 margin)
PICKUP_TIMEOUT = 30      # seconds to wait for user to pick up book
RFID_CHECK_INTERVAL = 0.5  # RFID polling interval
RFID_READ_TIMEOUT = 3    # single RFID read timeout
GRACE_AFTER_PICKUP = 5   # seconds after tag disappears before closing


def _parse_depth(address: str) -> int:
    """Extract depth (1=front, 2=back) from address depth.rack.shelf."""
    try:
        return int(address.split('.')[0])
    except (ValueError, IndexError):
        raise ValueError(f'Invalid address format: {address!r}, expected depth.rack.shelf')


def _extract_cmd(address: str) -> str:
    """Return the shelf_operations.py command name for extraction."""
    return 'extract_front' if _parse_depth(address) == 1 else 'extract_rear'


def _return_cmd(address: str) -> str:
    """Return the shelf_operations.py command name for shelf return."""
    return 'return_front' if _parse_depth(address) == 1 else 'return_rear'


def _run_tool(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a tools/* subprocess and raise on failure."""
    log.info(f'Running: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f'Tool failed ({" ".join(cmd[-2:])}): {stderr}')
    return result


class IssueWorkflow:
    """
    Full 18-step book issue workflow per issue #79.

    Uses subprocess calls to standalone tools that are already tested on
    real hardware: goto.py, shelf_operations.py, shutter.py.
    RFID verification via bookcabinet.rfid.book_reader.BookReader.
    """

    def __init__(self, pi=None, progress_cb: Optional[Callable] = None,
                 speed: int = 2600):
        """
        Args:
            pi: pigpio.pi instance (only needed if you want to share one;
                otherwise shutter.py creates its own).
            progress_cb: callback(step, total, label, **extra) for progress events.
            speed: carriage speed for goto.py (default 2600).
        """
        self.speed = speed
        self.progress_cb = progress_cb
        self._cancelled = False

    # ── progress ─────────────────────────────────────────────────

    def _emit(self, step: int, total: int, label: str, **extra):
        if self.progress_cb:
            self.progress_cb(step=step, total=total, label=label, **extra)
        log.info(f'[ISSUE {step}/{total}] {label}')

    # ── shutter helpers (subprocess to tools/shutter.py) ─────────

    async def _open_shutter(self, which: str):
        """Open shutter via tools/shutter.py. which = 'inner' | 'outer'."""
        _run_tool(['python3', _SHUTTER, which, 'open'])

    async def _close_shutter(self, which: str):
        _run_tool(['python3', _SHUTTER, which, 'close'])

    async def _shutter_open_and_wait(self, which: str):
        """Open shutter and wait for physical completion."""
        await self._open_shutter(which)
        await asyncio.sleep(SHUTTER_WAIT)

    async def _shutter_close_and_wait(self, which: str):
        await self._close_shutter(which)
        await asyncio.sleep(SHUTTER_WAIT)

    # ── motion helpers (subprocess to tools/goto.py) ─────────────

    async def _goto(self, address: str):
        """Move carriage to cell address via goto.py (subprocess)."""
        _run_tool(['python3', _GOTO, str(self.speed), address])

    # ── shelf helpers (subprocess to tools/shelf_operations.py) ──

    async def _extract_shelf(self, address: str):
        cmd_name = _extract_cmd(address)
        _run_tool(['python3', _SHELF_OPS, cmd_name])

    async def _return_shelf(self, address: str):
        cmd_name = _return_cmd(address)
        _run_tool(['python3', _SHELF_OPS, cmd_name])

    # ── RFID ─────────────────────────────────────────────────────

    async def _read_rfid(self) -> Optional[str]:
        """Read a single RFID tag. Returns EPC string or None."""
        try:
            # Import the singleton book_reader from rfid module
            rfid_path = os.path.join(os.path.dirname(__file__), '..')
            if rfid_path not in sys.path:
                sys.path.insert(0, rfid_path)
            from bookcabinet.rfid.book_reader import book_reader

            if not book_reader.serial and not book_reader.mock_mode:
                await book_reader.connect()

            tags = await asyncio.wait_for(
                book_reader.inventory(),
                timeout=RFID_READ_TIMEOUT,
            )
            return tags[0] if tags else None
        except asyncio.TimeoutError:
            log.warning('RFID read timeout')
            return None
        except Exception as e:
            log.warning(f'RFID read error: {e}')
            return None

    # ── emergency shutdown ───────────────────────────────────────

    def _safe_shutdown(self, reason: str = 'unknown'):
        """Emergency: close both shutters via subprocess."""
        log.error(f'ISSUE EMERGENCY SHUTDOWN: {reason}')
        for which in ('outer', 'inner'):
            try:
                _run_tool(['python3', _SHUTTER, which, 'close'], timeout=10)
            except Exception:
                pass

    # ── cancel ───────────────────────────────────────────────────

    def cancel(self):
        self._cancelled = True

    # ── main workflow ────────────────────────────────────────────

    async def run(
        self,
        source_address: str,
        window_address: str = '1.2.9',
        expected_book_rfid: Optional[str] = None,
        book_title: str = '',
        pickup_timeout_sec: int = PICKUP_TIMEOUT,
    ) -> dict:
        """
        Execute the full 18-step issue workflow.

        Returns dict with keys:
            success (bool), book_picked_up (bool), rfid_matched (bool|None),
            source (str), elapsed_sec (float), error (str, if failed).
        """
        TOTAL = 18
        start_time = time.time()
        book_picked_up = False
        rfid_matched = None

        try:
            # ── Step 1: Start ────────────────────────────────────
            self._emit(1, TOTAL, 'Запуск выдачи',
                       source=source_address, window=window_address)

            # ── Step 2: PARALLEL — open inner shutter + goto source
            self._emit(2, TOTAL,
                       'Открытие внутренней шторки + перемещение к ячейке')
            await asyncio.gather(
                self._shutter_open_and_wait('inner'),
                self._goto(source_address),
            )

            # ── Step 3: Extract shelf from source ────────────────
            self._emit(3, TOTAL, 'Извлечение полочки')
            await self._extract_shelf(source_address)

            # ── Step 4: Goto window (inner already open) ─────────
            self._emit(4, TOTAL, 'Перемещение к окну выдачи')
            await self._goto(window_address)

            # ── Step 5: Return shelf to window ───────────────────
            self._emit(5, TOTAL, 'Размещение полочки в окне')
            await self._return_shelf(window_address)

            # ── Step 6: Close inner shutter ──────────────────────
            self._emit(6, TOTAL, 'Закрытие внутренней шторки')
            await self._shutter_close_and_wait('inner')

            # ── Step 7: RFID verify ──────────────────────────────
            self._emit(7, TOTAL, 'RFID проверка книги')
            detected_rfid = await self._read_rfid()

            if expected_book_rfid and detected_rfid:
                rfid_matched = (detected_rfid == expected_book_rfid)
                if not rfid_matched:
                    # ERROR SCENARIO A: wrong book — return shelf without
                    # opening outer shutter
                    log.error(
                        f'RFID mismatch! Expected={expected_book_rfid}, '
                        f'Got={detected_rfid}')
                    self._emit(7, TOTAL, 'ОШИБКА: не та книга!', error=True)

                    # Return shelf to source (steps 13-17 without outer)
                    await self._shutter_open_and_wait('inner')
                    await self._extract_shelf(window_address)
                    await self._goto(source_address)
                    await self._return_shelf(source_address)
                    await self._shutter_close_and_wait('inner')

                    return {
                        'success': False,
                        'error': 'rfid_mismatch',
                        'expected': expected_book_rfid,
                        'detected': detected_rfid,
                        'source': source_address,
                        'book_picked_up': False,
                        'rfid_matched': False,
                        'elapsed_sec': round(time.time() - start_time, 2),
                    }
            elif expected_book_rfid and detected_rfid is None:
                # Could not read tag — log warning but proceed
                log.warning('RFID: no tag detected at verify step, proceeding')
                rfid_matched = None

            # ── Step 8: Open outer shutter ───────────────────────
            self._emit(8, TOTAL, 'Открытие внешней шторки')
            await self._shutter_open_and_wait('outer')

            # ── Step 9: Show pickup screen ───────────────────────
            self._emit(9, TOTAL,
                       f'Заберите книгу: {book_title}',
                       wait_seconds=pickup_timeout_sec)

            # ── Steps 10-11: Poll RFID until book gone or timeout
            deadline = time.time() + pickup_timeout_sec
            while time.time() < deadline and not self._cancelled:
                tag = await self._read_rfid()
                if tag is None or (expected_book_rfid and tag != expected_book_rfid):
                    # Book removed!
                    book_picked_up = True
                    self._emit(10, TOTAL, 'Книга забрана!')
                    await asyncio.sleep(GRACE_AFTER_PICKUP)
                    break
                await asyncio.sleep(RFID_CHECK_INTERVAL)

            if not book_picked_up:
                # ERROR SCENARIO B: not picked up within timeout
                self._emit(11, TOTAL, 'Книга не забрана - возвращаем')

            # ── Step 12: Close outer shutter ─────────────────────
            self._emit(12, TOTAL, 'Закрытие внешней шторки')
            await self._shutter_close_and_wait('outer')

            # ── Step 13: Open inner shutter ──────────────────────
            self._emit(13, TOTAL, 'Открытие внутренней шторки')
            await self._shutter_open_and_wait('inner')

            # ── Step 14: Extract (empty) shelf from window ───────
            self._emit(14, TOTAL, 'Извлечение полочки из окна')
            await self._extract_shelf(window_address)

            # ── Step 15: Goto source ─────────────────────────────
            self._emit(15, TOTAL, 'Возврат полочки в ячейку')
            await self._goto(source_address)

            # ── Step 16: Return shelf to source ──────────────────
            self._emit(16, TOTAL, 'Установка полочки')
            await self._return_shelf(source_address)

            # ── Step 17: Close inner shutter ─────────────────────
            self._emit(17, TOTAL, 'Закрытие внутренней шторки')
            await self._shutter_close_and_wait('inner')

            # ── Step 18: Log result ──────────────────────────────
            elapsed = round(time.time() - start_time, 2)
            self._emit(18, TOTAL, 'Операция завершена')

            return {
                'success': True,
                'book_picked_up': book_picked_up,
                'rfid_matched': rfid_matched,
                'source': source_address,
                'elapsed_sec': elapsed,
            }

        except Exception as e:
            # ERROR SCENARIO C: mechanical failure
            log.error(f'Issue workflow error: {e}')
            self._safe_shutdown(str(e))
            return {
                'success': False,
                'error': f'mechanical_error: {e}',
                'source': source_address,
                'book_picked_up': False,
                'rfid_matched': rfid_matched,
                'elapsed_sec': round(time.time() - start_time, 2),
            }
