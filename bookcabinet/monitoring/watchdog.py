"""
Watchdog - мониторинг состояния системы
"""
import asyncio
import os
import shutil
import socket
import subprocess
from typing import Dict, Optional, Callable
from datetime import datetime
from ..config import MOCK_MODE
from ..database import db


class WatchdogService:
    def __init__(self):
        self._running = False
        self._last_heartbeat = datetime.now()
        self._check_interval = 30
        self._error_callback: Optional[Callable] = None
        self._health_status: Dict = {
            'motors': True,
            'sensors': True,
            'rfid_card': True,
            'rfid_book': True,
            'database': True,
            'websocket': True,
            'disk': True,
            'temperature': True,
            'pigpiod': True,
        }
        self._consecutive_failures: Dict[str, int] = {}
        self._max_failures = 3
    
    def set_error_callback(self, callback: Callable):
        self._error_callback = callback
    
    async def start(self, interval: int = 30):
        self._running = True
        self._check_interval = interval
        
        db.add_system_log('INFO', 'Watchdog запущен', 'watchdog')
        
        while self._running:
            try:
                await self._check_health()
                self._last_heartbeat = datetime.now()
                
                if not MOCK_MODE:
                    self._notify_systemd()
                
            except Exception as e:
                db.add_system_log('ERROR', f'Ошибка watchdog: {e}', 'watchdog')
            
            await asyncio.sleep(self._check_interval)
    
    def stop(self):
        self._running = False
        db.add_system_log('INFO', 'Watchdog остановлен', 'watchdog')
    
    async def _check_health(self):
        await self._check_motors()
        await self._check_sensors()
        await self._check_rfid()
        await self._check_database()
        await self._check_websocket()
        await self._run_check('disk', self._check_disk_space)
        await self._run_check('temperature', self._check_temperature)
        await self._run_check('pigpiod', self._check_pigpiod)

    async def _run_check(self, component: str, check_fn):
        """Helper: run a (healthy, message) returning coroutine and report."""
        try:
            ok, message = await check_fn()
            if ok:
                self._report_success(component)
            else:
                self._report_failure(component, message)
        except Exception as e:
            self._report_failure(component, str(e))

    async def _check_disk_space(self):
        """Disk space check — warn if free < 10%, critical if < 5%."""
        import shutil
        try:
            usage = shutil.disk_usage('/')
            free_pct = usage.free / usage.total * 100
            if free_pct < 5:
                return False, f"Disk {free_pct:.1f}% free (CRITICAL)"
            elif free_pct < 10:
                return False, f"Disk {free_pct:.1f}% free (LOW)"
            return True, f"Disk {free_pct:.1f}% free"
        except Exception as e:
            return False, f"Disk check error: {e}"

    async def _check_temperature(self):
        """RPi temperature check — warn >75°C, critical >85°C."""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp') as f:
                temp_c = int(f.read().strip()) / 1000
            if temp_c > 85:
                return False, f"CPU {temp_c:.1f}°C (CRITICAL)"
            elif temp_c > 75:
                return False, f"CPU {temp_c:.1f}°C (HIGH)"
            return True, f"CPU {temp_c:.1f}°C"
        except Exception as e:
            return False, f"Temp check error: {e}"

    async def _check_pigpiod(self):
        """pigpiod daemon running."""
        import subprocess
        try:
            subprocess.check_output(['pigs', 't'], timeout=2, stderr=subprocess.DEVNULL)
            return True, "pigpiod OK"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            return False, f"pigpiod not responding: {e}"
    
    async def _check_motors(self):
        try:
            from ..hardware.motors import motors
            
            pos = motors.get_position()
            if pos is None:
                self._report_failure('motors', 'Не удалось получить позицию')
            else:
                self._report_success('motors')
        except Exception as e:
            self._report_failure('motors', str(e))
    
    async def _check_sensors(self):
        try:
            from ..hardware.sensors import sensors
            
            data = sensors.read_all()
            if data is None:
                self._report_failure('sensors', 'Не удалось прочитать датчики')
            else:
                self._report_success('sensors')
        except Exception as e:
            self._report_failure('sensors', str(e))
    
    async def _check_rfid(self):
        try:
            from ..rfid.card_reader import card_reader
            from ..rfid.book_reader import book_reader
            
            if card_reader.mock_mode or card_reader.reader is not None:
                self._report_success('rfid_card')
            else:
                self._report_failure('rfid_card', 'Ридер карт не подключён')
            
            if book_reader.mock_mode or book_reader.serial is not None:
                self._report_success('rfid_book')
            else:
                self._report_failure('rfid_book', 'Ридер книг не подключён')
        except Exception as e:
            self._report_failure('rfid_card', str(e))
            self._report_failure('rfid_book', str(e))
    
    async def _check_database(self):
        try:
            stats = db.get_statistics()
            if stats is not None:
                self._report_success('database')
            else:
                self._report_failure('database', 'Ошибка доступа к БД')
        except Exception as e:
            self._report_failure('database', str(e))
    
    async def _check_websocket(self):
        try:
            from ..server.websocket_handler import ws_handler
            
            client_count = len(ws_handler.clients)
            if client_count >= 0:
                self._report_success('websocket')
        except Exception as e:
            self._report_failure('websocket', str(e))
    
    def _report_failure(self, component: str, message: str):
        self._consecutive_failures[component] = self._consecutive_failures.get(component, 0) + 1
        
        if self._consecutive_failures[component] >= self._max_failures:
            if self._health_status.get(component, True):
                self._health_status[component] = False
                error_msg = f'Компонент {component} недоступен: {message}'
                db.add_system_log('ERROR', error_msg, 'watchdog')
                
                if self._error_callback:
                    asyncio.create_task(self._notify_error(component, message))
    
    def _report_success(self, component: str):
        was_failed = not self._health_status.get(component, True)
        self._health_status[component] = True
        self._consecutive_failures[component] = 0
        
        if was_failed:
            db.add_system_log('INFO', f'Компонент {component} восстановлен', 'watchdog')
    
    async def _notify_error(self, component: str, message: str):
        if self._error_callback:
            try:
                await self._error_callback(component, message)
            except:
                pass
    
    def _notify_systemd(self):
        try:
            notify_socket = os.environ.get('NOTIFY_SOCKET')
            if notify_socket:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                sock.connect(notify_socket)
                sock.sendall(b'WATCHDOG=1')
                sock.close()
        except:
            pass
    
    def get_health_status(self) -> Dict:
        all_healthy = all(self._health_status.values())
        return {
            'healthy': all_healthy,
            'components': self._health_status.copy(),
            'last_check': self._last_heartbeat.isoformat(),
            'uptime_seconds': (datetime.now() - self._last_heartbeat).total_seconds() if self._running else 0,
        }
    
    def is_healthy(self) -> bool:
        return all(self._health_status.values())
    
    def heartbeat(self):
        self._last_heartbeat = datetime.now()


watchdog = WatchdogService()


class StartupRecovery:
    """Checks hardware state on startup and recovers if needed.

    Called once during service startup to ensure the cabinet is in a
    known-safe state: shutters closed, carriage homed, tray sensor-homed.

    Порядок важен (механика, Роман 2026-06-13): лоток хомится по датчику
    ТОЛЬКО когда каретка в home (x=0,y=0). Поэтому:
      1. шторки закрыть;
      2. грубо втянуть лоток (слепо) — лишь чтобы освободить путь каретке;
      3. хоминг XY → каретка в 0,0;
      4. ТОЧНЫЙ sensor-хоминг лотка к концевику BACK (истинный ноль лотка).
    """

    async def check_and_recover(self) -> dict:
        """Run startup recovery sequence.

        Returns dict summarizing what was done.
        """
        results = {'shutters': None, 'tray': None, 'homing': None, 'tray_homing': None}

        try:
            from ..hardware.shutters import shutters

            # Close shutters for safety
            await shutters.close_shutter('outer')
            await shutters.close_shutter('inner')
            results['shutters'] = 'closed'
        except Exception as e:
            results['shutters'] = f'error: {e}'
            db.add_system_log('ERROR', f'Startup recovery shutters: {e}', 'watchdog')

        try:
            from ..hardware.sensors import sensors
            from ..hardware.motors import motors

            # Грубое (слепое) втягивание лотка — только чтобы освободить путь
            # каретке. Истинный ноль лотка устанавливается ниже sensor-хомингом.
            if not sensors.is_tray_retracted():
                await motors.retract_tray()
                results['tray'] = 'retracted (coarse)'
            else:
                results['tray'] = 'already_retracted'
        except Exception as e:
            results['tray'] = f'error: {e}'
            db.add_system_log('ERROR', f'Startup recovery tray: {e}', 'watchdog')

        try:
            from ..hardware.sensors import sensors
            from ..hardware.motors import motors

            # Хоминг каретки XY → x=0, y=0 (необходимо ДО хоминга лотка)
            result = await motors.home_with_sensors(sensors)
            results['homing'] = 'ok' if result else 'failed'
        except Exception as e:
            results['homing'] = f'error: {e}'
            db.add_system_log('ERROR', f'Startup recovery homing: {e}', 'watchdog')

        try:
            from ..hardware.sensors import sensors
            from ..hardware.motors import motors

            # Точный sensor-хоминг лотка к концевику BACK. Лоток можно хомить
            # ТОЛЬКО при каретке в home (Роман 2026-06-13), поэтому строго после
            # успешного хоминга XY. Раньше старт делал лишь слепой retract.
            if results['homing'] == 'ok':
                tray_ok = await motors.home_tray_with_sensor(sensors)
                results['tray_homing'] = 'ok' if tray_ok else 'failed'
            else:
                results['tray_homing'] = 'skipped (XY homing not ok)'
        except Exception as e:
            results['tray_homing'] = f'error: {e}'
            db.add_system_log('ERROR', f'Startup recovery tray homing: {e}', 'watchdog')

        db.add_system_log(
            'INFO',
            f'Startup recovery complete: {results}',
            'watchdog',
        )
        return results


startup_recovery = StartupRecovery()
