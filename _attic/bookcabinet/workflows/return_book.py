"""
Production book return workflow.
Implements the 19-step sequence from issue #80.

Mirror logic to issue.py: user PLACES a book (tag appears), RFID verify after
appearance, auto-fallback to nearest free cell if target is occupied.

Uses subprocess calls to tested standalone tools (goto.py, shelf_operations.py,
shutter.py) for hardware operations. RFID via bookcabinet.rfid.book_reader.

Steps:
  1.  Start
  2.  PARALLEL: open inner shutter + goto window
  3.  Extract empty shelf from window (prepare for receiving)
  4.  Return shelf to window (ready for book placement)
  5.  Close inner shutter
  6.  Open outer shutter
  7.  Screen: "Place book" + 60 sec countdown
  8-9. Poll RFID: wait for tag to APPEAR
  10. RFID verify: detected == expected?
  11. Screen: "Thank you! 5 sec"
  12. Wait 5 sec (UX confirmation)
  13. Close outer shutter
  14. Open inner shutter
  15. Extract shelf with book from window
  16. Goto target cell
  17. Return shelf to target
  18. Close inner shutter
  19. Log result

Error scenarios:
  A. Tag mismatch -> "Wrong book, please remove" + 60 sec retry
  B. 60 sec timeout no tag -> close outer, book not returned
  C. RFID reader error -> manual confirm mode
  D. Target cell occupied -> auto-fallback to nearest free cell
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
SHUTTER_WAIT = 15          # seconds to wait for shutter physical travel
DROP_TIMEOUT = 60          # seconds to wait for user to place book
RFID_CHECK_INTERVAL = 0.5  # RFID polling interval
RFID_READ_TIMEOUT = 3      # single RFID read timeout
CONFIRM_DISPLAY_SEC = 5    # "Thank you" screen duration
MISMATCH_RETRY_SEC = 60    # seconds for user to fix wrong book


def _parse_depth(address: str) -> int:
    """Extract depth (1=front, 2=back) from address depth.rack.shelf."""
    try:
        return int(address.split('.')[0])
    except (ValueError, IndexError):
        raise ValueError(f'Invalid address format: {address!r}, expected depth.rack.shelf')


def _extract_cmd(address: str) -> str:
    return 'extract_front' if _parse_depth(address) == 1 else 'extract_rear'


def _return_cmd(address: str) -> str:
    return 'return_front' if _parse_depth(address) == 1 else 'return_rear'


def _run_tool(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a tools/* subprocess and raise on failure."""
    log.info(f'Running: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f'Tool failed ({" ".join(cmd[-2:])}): {stderr}')
    return result


class ReturnWorkflow:
    """
    Full 19-step book return workflow per issue #80.

    Uses subprocess calls to standalone tools that are already tested on
    real hardware: goto.py, shelf_operations.py, shutter.py.
    RFID verification via bookcabinet.rfid.book_reader.BookReader.
    """

    def __init__(self, pi=None, progress_cb: Optional[Callable] = None,
                 speed: int = 2600):
        """
        Args:
            pi: pigpio.pi instance (unused; kept for API symmetry with IssueWorkflow).
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
        log.info(f'[RETURN {step}/{total}] {label}')

    # ── shutter helpers (subprocess to tools/shutter.py) ─────────

    async def _open_shutter(self, which: str):
        _run_tool(['python3', _SHUTTER, which, 'open'])

    async def _close_shutter(self, which: str):
        _run_tool(['python3', _SHUTTER, which, 'close'])

    async def _shutter_open_and_wait(self, which: str):
        await self._open_shutter(which)
        await asyncio.sleep(SHUTTER_WAIT)

    async def _shutter_close_and_wait(self, which: str):
        await self._close_shutter(which)
        await asyncio.sleep(SHUTTER_WAIT)

    # ── motion helpers ───────────────────────────────────────────

    async def _goto(self, address: str):
        _run_tool(['python3', _GOTO, str(self.speed), address])

    # ── shelf helpers ────────────────────────────────────────────

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

    # ── find fallback cell ───────────────────────────────────────

    def _find_free_cell(self) -> Optional[str]:
        """Find nearest free cell via database, return address or None."""
        try:
            from bookcabinet.database.db import db
            cell = db.find_empty_cell()
            if cell:
                # Convert DB row/x/y to address format depth.rack.shelf
                # DB cells use row=FRONT/BACK, x=column(0-2), y=position(0-20)
                depth = 1 if cell['row'] == 'FRONT' else 2
                rack = cell['x'] + 1   # x is 0-indexed in DB, rack is 1-indexed
                shelf = cell['y']
                return f'{depth}.{rack}.{shelf}'
        except Exception as e:
            log.warning(f'Could not query DB for free cell: {e}')
        return None

    # ── emergency shutdown ───────────────────────────────────────

    def _safe_shutdown(self, reason: str = 'unknown'):
        log.error(f'RETURN EMERGENCY SHUTDOWN: {reason}')
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
        target_address: str,
        window_address: str = '1.2.9',
        expected_book_rfid: Optional[str] = None,
        book_title: str = '',
        drop_timeout_sec: int = DROP_TIMEOUT,
    ) -> dict:
        """
        Execute the full 19-step return workflow.

        Returns dict with keys:
            success (bool), book_returned (bool), rfid_matched (bool|None),
            target (str), elapsed_sec (float), error (str, if failed).
        """
        TOTAL = 19
        start_time = time.time()
        book_returned = False
        rfid_matched = None
        detected_rfid = None

        try:
            # ── Step 1: Start ────────────────────────────────────
            self._emit(1, TOTAL, 'Запуск возврата',
                       target=target_address, window=window_address)

            # ── Step 2: PARALLEL — open inner shutter + goto window
            self._emit(2, TOTAL,
                       'Открытие внутренней шторки + перемещение к окну')
            await asyncio.gather(
                self._shutter_open_and_wait('inner'),
                self._goto(window_address),
            )

            # ── Step 3: Extract empty shelf from window ──────────
            self._emit(3, TOTAL, 'Извлечение пустой полочки из окна')
            await self._extract_shelf(window_address)

            # ── Step 4: Return shelf to window (ready for book) ──
            self._emit(4, TOTAL, 'Подготовка полочки для приёма книги')
            await self._return_shelf(window_address)

            # ── Step 5: Close inner shutter ──────────────────────
            self._emit(5, TOTAL, 'Закрытие внутренней шторки')
            await self._shutter_close_and_wait('inner')

            # ── Step 6: Open outer shutter ───────────────────────
            self._emit(6, TOTAL, 'Открытие внешней шторки')
            await self._shutter_open_and_wait('outer')

            # ── Step 7: Screen: "Place book" + countdown ─────────
            self._emit(7, TOTAL,
                       f'Положите книгу: {book_title}',
                       wait_seconds=drop_timeout_sec)

            # ── Steps 8-9: Poll RFID until tag APPEARS or timeout
            deadline = time.time() + drop_timeout_sec
            rfid_error_count = 0
            while time.time() < deadline and not self._cancelled:
                tag = await self._read_rfid()
                if tag is None:
                    rfid_error_count += 1
                else:
                    # Tag appeared!
                    detected_rfid = tag
                    self._emit(8, TOTAL, f'Обнаружена метка: {tag}')
                    break
                await asyncio.sleep(RFID_CHECK_INTERVAL)

            if detected_rfid is None:
                # ERROR SCENARIO B: timeout, no tag detected
                self._emit(9, TOTAL, 'Книга не сдана - таймаут')

                await self._shutter_close_and_wait('outer')

                return {
                    'success': False,
                    'error': 'drop_timeout',
                    'book_returned': False,
                    'rfid_matched': None,
                    'target': target_address,
                    'elapsed_sec': round(time.time() - start_time, 2),
                }

            # ── Step 10: RFID verify ─────────────────────────────
            self._emit(10, TOTAL, 'RFID сверка')

            if expected_book_rfid and detected_rfid:
                rfid_matched = (detected_rfid == expected_book_rfid)

                if not rfid_matched:
                    # ERROR SCENARIO A: wrong book — give user time to fix
                    log.warning(
                        f'RFID mismatch! Expected={expected_book_rfid}, '
                        f'Got={detected_rfid}')
                    self._emit(10, TOTAL,
                               'Не та книга! Заберите и положите правильную.',
                               error=True, wait_seconds=MISMATCH_RETRY_SEC)

                    # Wait for user to fix: tag should disappear then correct
                    # tag should appear within MISMATCH_RETRY_SEC
                    retry_deadline = time.time() + MISMATCH_RETRY_SEC
                    fixed = False
                    while time.time() < retry_deadline and not self._cancelled:
                        tag = await self._read_rfid()
                        if tag is None:
                            # User removed wrong book, wait for correct one
                            pass
                        elif tag == expected_book_rfid:
                            # Correct book placed!
                            detected_rfid = tag
                            rfid_matched = True
                            fixed = True
                            self._emit(10, TOTAL, 'Правильная книга обнаружена!')
                            break
                        # else: still wrong book on shelf
                        await asyncio.sleep(RFID_CHECK_INTERVAL)

                    if not fixed:
                        # Timeout on retry — close and escalate
                        self._emit(10, TOTAL,
                                   'Таймаут исправления - закрываем',
                                   error=True)
                        await self._shutter_close_and_wait('outer')

                        return {
                            'success': False,
                            'error': 'rfid_mismatch',
                            'expected': expected_book_rfid,
                            'detected': detected_rfid,
                            'book_returned': False,
                            'rfid_matched': False,
                            'target': target_address,
                            'elapsed_sec': round(time.time() - start_time, 2),
                        }
            elif expected_book_rfid and detected_rfid is None:
                # ERROR SCENARIO C: RFID reader error — proceed with
                # manual confirm mode (tag was detected earlier in the loop,
                # so this branch should not normally be reached)
                log.warning('RFID verify: reader error, proceeding in manual mode')
                rfid_matched = None

            book_returned = True

            # ── Step 11: Thank you screen ────────────────────────
            self._emit(11, TOTAL,
                       'Спасибо! Книга принята.',
                       wait_seconds=CONFIRM_DISPLAY_SEC)

            # ── Step 12: Wait for user to see confirmation ───────
            await asyncio.sleep(CONFIRM_DISPLAY_SEC)
            self._emit(12, TOTAL, 'Подтверждение показано')

            # ── Step 13: Close outer shutter ─────────────────────
            self._emit(13, TOTAL, 'Закрытие внешней шторки')
            await self._shutter_close_and_wait('outer')

            # ── Step 14: Open inner shutter ──────────────────────
            self._emit(14, TOTAL, 'Открытие внутренней шторки')
            await self._shutter_open_and_wait('inner')

            # ── Step 15: Extract shelf with book from window ─────
            self._emit(15, TOTAL, 'Извлечение полочки с книгой из окна')
            await self._extract_shelf(window_address)

            # ── Step 16: Goto target cell ────────────────────────
            # ERROR SCENARIO D: target cell occupied -> fallback
            actual_target = target_address
            try:
                await self._goto(target_address)
            except RuntimeError as e:
                log.warning(f'Target {target_address} unreachable: {e}, '
                            f'trying fallback cell')
                fallback = self._find_free_cell()
                if fallback:
                    log.info(f'Fallback cell: {fallback}')
                    actual_target = fallback
                    await self._goto(actual_target)
                else:
                    raise RuntimeError(
                        f'Target {target_address} failed and no free cells: {e}')
            self._emit(16, TOTAL, f'Перемещение к ячейке {actual_target}')

            # ── Step 17: Return shelf to target ──────────────────
            self._emit(17, TOTAL, 'Установка полочки в ячейку')
            await self._return_shelf(actual_target)

            # ── Step 18: Close inner shutter ─────────────────────
            self._emit(18, TOTAL, 'Закрытие внутренней шторки')
            await self._shutter_close_and_wait('inner')

            # ── Step 19: Log result ──────────────────────────────
            elapsed = round(time.time() - start_time, 2)
            self._emit(19, TOTAL, 'Операция завершена')

            result = {
                'success': True,
                'book_returned': book_returned,
                'rfid_matched': rfid_matched,
                'target': actual_target,
                'elapsed_sec': elapsed,
            }
            if actual_target != target_address:
                result['original_target'] = target_address
                result['fallback_used'] = True
            return result

        except Exception as e:
            # ERROR SCENARIO C: mechanical failure
            log.error(f'Return workflow error: {e}')
            self._safe_shutdown(str(e))
            return {
                'success': False,
                'error': f'mechanical_error: {e}',
                'book_returned': book_returned,
                'rfid_matched': rfid_matched,
                'target': target_address,
                'elapsed_sec': round(time.time() - start_time, 2),
            }
