"""
Алгоритмы управления: INIT, TAKE, GIVE с реальным path planning
"""
import asyncio
from typing import Optional, Callable, Dict, Any, List, Tuple
from datetime import datetime

from ..hardware.motors import motors
from ..hardware.servos import servos
from ..hardware.shutters import shutters
from ..hardware.sensors import sensors
from .corexy import corexy
from .calibration import calibration
from ..config import TIMEOUTS, MOCK_MODE, CABINET


class PathPlanner:
    """Планировщик траекторий для CoreXY с полным расчётом"""
    
    SAFE_ZONE_Y = 1000  # Безопасная зона Y для горизонтальных перемещений
    MAX_DIAGONAL_STEP = 500  # Максимальный шаг диагонального движения
    
    def __init__(self):
        self.reload_calibration()
        self.window = CABINET['window']
    
    def reload_calibration(self):
        """Перезагрузить калибровочные данные"""
        self.positions_x = calibration.get('positions.x', [0, 4500, 9000])
        self.positions_y = calibration.get('positions.y', [i * 450 for i in range(21)])
        self.speed = calibration.get('speeds.xy', 4000)
        # ИСТОЧНИК ИСТИНЫ по XY ячеек — полевая калибровка из корневого
        # calibration.json (racks + per-rack shelves.anchors + depth), тот же
        # резолвер, что у tools/-скриптов, которыми механику отлаживали на железе.
        # Прежняя app-схема (positions.x/y) почти всегда пустая → дефолты мимо реальных
        # стоек; держим её только как фоллбек. См. docs/FLOWS.md.
        self._field = None
        self._field_cal = None
        try:
            from tools import calibration as field_calibration
            self._field = field_calibration
            self._field_cal = field_calibration._load()
        except Exception as e:
            # КРИТИЧНО: без полевой калибровки get_cell_position уедет на ДЕФОЛТНЫЕ
            # XY ([0,4500,9000]) мимо реальных стоек. Молчать нельзя — на железе
            # это значит неверное движение каретки.
            try:
                import logging
                logging.getLogger(__name__).error(
                    'Полевая калибровка (tools/calibration + calibration.json) НЕ '
                    'загрузилась (%s) — XY ячеек будут ДЕФОЛТНЫМИ, движение неверным. '
                    'Проверьте корневой calibration.json и sys.path.', e)
            except Exception:
                pass

    def get_cell_position(self, row: str, x: int, y: int) -> Tuple[int, int]:
        """Получить координаты ячейки в шагах.

        Маппинг app-адресации (row,x,y) → полевой (depth.rack.shelf):
        depth = 1(FRONT)/2(BACK); rack = x+1 (стойки 1..3); shelf = y (0..20).
        """
        if self._field_cal is not None:
            try:
                depth = 1 if row == 'FRONT' else 2
                rack = x + 1
                steps_x = self._field.get_rack_x(rack, self._field_cal)
                steps_y = self._field.interpolate_y(y, depth, self._field_cal, rack=rack)
                return (steps_x, steps_y)
            except Exception:
                pass  # фоллбек на app-схему ниже
        steps_x = self.positions_x[x] if x < len(self.positions_x) else 0
        steps_y = self.positions_y[y] if y < len(self.positions_y) else 0
        return (steps_x, steps_y)
    
    def get_window_position(self) -> Tuple[int, int]:
        """Координаты окна выдачи"""
        return self.get_cell_position(
            self.window['row'],
            self.window['x'],
            self.window['y']
        )
    
    def plan_path(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Построить путь с промежуточными точками для избежания столкновений
        
        Стратегия:
        1. Для больших перемещений - сначала Y, потом X (L-образный путь)
        2. Для близких точек - прямое движение
        3. При пересечении опасных зон - добавляем промежуточные точки
        """
        path = []
        sx, sy = start
        ex, ey = end
        
        dx = abs(ex - sx)
        dy = abs(ey - sy)
        
        # Прямое движение для близких точек
        if dx < self.MAX_DIAGONAL_STEP and dy < self.MAX_DIAGONAL_STEP:
            path.append((ex, ey))
            return path
        
        # L-образный путь для дальних точек
        # Сначала двигаемся по Y (вертикально)
        if dy > self.MAX_DIAGONAL_STEP:
            # Если нужно пересечь большое расстояние по Y
            # добавляем промежуточные точки каждые 2000 шагов
            step_count = max(1, dy // 2000)
            y_step = (ey - sy) / step_count
            
            for i in range(1, step_count):
                intermediate_y = int(sy + y_step * i)
                path.append((sx, intermediate_y))
            
            path.append((sx, ey))
        
        # Затем двигаемся по X (горизонтально)
        if dx > self.MAX_DIAGONAL_STEP:
            step_count = max(1, dx // 2000)
            x_step = (ex - sx) / step_count
            
            current_y = ey
            for i in range(1, step_count):
                intermediate_x = int(sx + x_step * i)
                path.append((intermediate_x, current_y))
        
        # Финальная точка
        path.append((ex, ey))
        
        return path
    
    def estimate_time(self, start: Tuple[int, int], end: Tuple[int, int]) -> float:
        """Оценка времени перемещения в секундах с учётом пути"""
        path = self.plan_path(start, end)
        
        total_distance = 0
        current = start
        
        for point in path:
            dx = abs(point[0] - current[0])
            dy = abs(point[1] - current[1])
            # Для CoreXY: время = max(dx, dy) т.к. оси двигаются параллельно
            total_distance += max(dx, dy)
            current = point
        
        if self.speed <= 0:
            return 0
        
        return total_distance / self.speed
    
    def get_total_cells(self) -> int:
        """Получить общее количество ячеек"""
        return len(CABINET['rows']) * CABINET['columns'] * CABINET['positions']


class Algorithms:
    def __init__(self):
        self.state = 'idle'
        self.current_operation = None
        self.progress_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        self.path_planner = PathPlanner()
        self._stop_requested = False
    
    def set_callbacks(self, progress: Callable = None, error: Callable = None):
        self.progress_callback = progress
        self.error_callback = error
    
    @staticmethod
    async def _call_cb(cb, payload):
        """Колбэк может быть и sync (bridge), и async (websocket) —
        раньше await на результате sync-колбэка ронял операцию после
        первого же progress-события."""
        result = cb(payload)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_progress(self, step: int, total: int, message: str):
        if self.progress_callback:
            await self._call_cb(self.progress_callback, {
                'step': step,
                'total': total,
                'message': message,
                'operation': self.current_operation,
            })

    async def _emit_error(self, code: int, message: str):
        if self.error_callback:
            await self._call_cb(self.error_callback, {
                'code': code,
                'message': message,
                'operation': self.current_operation,
            })
    
    async def _check_sensors_for_home(self) -> bool:
        """Проверка концевиков при homing"""
        return sensors.is_at_home()
    
    async def _check_tray_sensors(self) -> Dict[str, bool]:
        """Проверка датчиков лотка"""
        return {
            'retracted': sensors.is_tray_retracted(),
            'extended': sensors.is_tray_extended(),
        }
    
    async def _safe_move_xy(self, target_x: int, target_y: int, timeout_ms: int = None) -> bool:
        """Безопасное перемещение с проверкой датчиков и аварийной остановкой"""
        if self._stop_requested:
            return False
        
        timeout = timeout_ms or TIMEOUTS['move']
        
        current_pos = motors.get_position()
        path = self.path_planner.plan_path(
            (current_pos['x'], current_pos['y']),
            (target_x, target_y)
        )
        
        for point in path:
            if self._stop_requested:
                motors.stop()
                await self._emit_error(11, 'Операция остановлена пользователем')
                return False
            
            # Проверка перед движением - все направления
            if not MOCK_MODE:
                all_sensors = sensors.read_all()
                
                # Движение вправо (X+) - проверяем x_end
                if point[0] > current_pos['x'] and all_sensors.get('x_end'):
                    motors.stop()
                    await self._emit_error(10, 'Сработал концевик X (конец)')
                    return False
                
                # Движение влево (X-) - проверяем x_begin
                if point[0] < current_pos['x'] and all_sensors.get('x_begin'):
                    motors.stop()
                    await self._emit_error(10, 'Сработал концевик X (начало)')
                    return False
                
                # Движение вперёд (Y+) - проверяем y_end
                if point[1] > current_pos['y'] and all_sensors.get('y_end'):
                    motors.stop()
                    await self._emit_error(10, 'Сработал концевик Y (конец)')
                    return False
                
                # Движение назад (Y-) - проверяем y_begin
                if point[1] < current_pos['y'] and all_sensors.get('y_begin'):
                    motors.stop()
                    await self._emit_error(10, 'Сработал концевик Y (начало)')
                    return False
            
            # Движение к точке
            success = await motors.move_xy(point[0], point[1])
            if not success:
                await self._emit_error(12, 'Ошибка перемещения мотора')
                return False
            
            # Проверка после движения - неожиданные срабатывания
            if not MOCK_MODE:
                all_sensors = sensors.read_all()
                
                # Неожиданный x_end при движении к цели (ещё не достигнута)
                if all_sensors.get('x_end') and point[0] < target_x:
                    motors.stop()
                    await self._emit_error(10, 'Неожиданное срабатывание концевика X (конец)')
                    return False
                
                # Неожиданный x_begin при движении от начала
                if all_sensors.get('x_begin') and point[0] > 0:
                    motors.stop()
                    await self._emit_error(10, 'Неожиданное срабатывание концевика X (начало)')
                    return False
                
                # Неожиданный y_end при движении к цели
                if all_sensors.get('y_end') and point[1] < target_y:
                    motors.stop()
                    await self._emit_error(10, 'Неожиданное срабатывание концевика Y (конец)')
                    return False
                
                # Неожиданный y_begin при движении от начала
                if all_sensors.get('y_begin') and point[1] > 0:
                    motors.stop()
                    await self._emit_error(10, 'Неожиданное срабатывание концевика Y (начало)')
                    return False
            
            current_pos = motors.get_position()
        
        return True
    
    def _chk(self, ok, what: str):
        """CRIT-2: строгая проверка результата мех-шага — БД не должна врать про
        issued/extracted при физически несостоявшемся цикле. При ok is False бросаем
        RuntimeError (ловится except → state=error → business видит False → не комми́тит).
        Фолбэк «мало ли»: MECH_STRICT=false → старое снисходительное поведение."""
        import os
        strict = os.environ.get('MECH_STRICT', 'true').lower() in ('1', 'true', 'yes', 'on')
        if strict and ok is False:
            raise RuntimeError(f"мех-шаг не удался: {what}")
        return ok

    async def _safe_tray_extend(self, steps: int = None) -> bool:
        """Безопасное выдвижение лотка с проверкой датчиков"""
        if self._stop_requested:
            return False
        
        # Проверка начального состояния
        if not MOCK_MODE:
            tray_status = await self._check_tray_sensors()
            # Если уже выдвинут на нужную позицию
            if tray_status['extended'] and steps is None:
                return True
        
        success = await motors.extend_tray(steps)
        
        if not success:
            await self._emit_error(20, 'Ошибка выдвижения лотка')
            return False
        
        # Проверка результата
        if not MOCK_MODE:
            # Ждём стабилизации датчика
            await asyncio.sleep(0.3)
            tray_status = await self._check_tray_sensors()
            
            if steps is None and not tray_status['extended']:
                # Полное выдвижение но датчик не сработал
                await self._emit_error(21, 'Лоток не достиг конечной позиции')
                return False
        
        return True
    
    async def _safe_tray_retract(self, steps: int = None) -> bool:
        """Безопасное втягивание лотка с проверкой датчиков"""
        if self._stop_requested:
            return False
        
        # Проверка начального состояния
        if not MOCK_MODE:
            tray_status = await self._check_tray_sensors()
            # Если уже втянут
            if tray_status['retracted'] and steps is None:
                return True
        
        success = await motors.retract_tray(steps)
        
        if not success:
            await self._emit_error(22, 'Ошибка втягивания лотка')
            return False
        
        # Проверка результата
        if not MOCK_MODE:
            await asyncio.sleep(0.3)
            tray_status = await self._check_tray_sensors()
            
            if steps is None and not tray_status['retracted']:
                # Полное втягивание но датчик не сработал
                await self._emit_error(23, 'Лоток не достиг начальной позиции')
                return False
        
        return True
    
    async def init_home(self) -> bool:
        """Алгоритм INIT - возврат в начальное положение"""
        self.current_operation = 'INIT'
        self.state = 'homing'
        self._stop_requested = False
        
        try:
            await self._emit_progress(1, 5, 'Проверка состояния лотка')
            
            tray_status = await self._check_tray_sensors()
            if not tray_status['retracted']:
                await self._emit_progress(2, 5, 'Втягивание лотка')
                await self._safe_tray_retract()
            
            await self._emit_progress(3, 5, 'Движение к началу по X')
            
            if MOCK_MODE:
                await asyncio.sleep(0.5)
                motors.position['x'] = 0
            else:
                while not sensors.read('x_begin'):
                    if self._stop_requested:
                        return False
                    await motors.move_xy(motors.position['x'] - 100, motors.position['y'])
                motors.position['x'] = 0
            
            await self._emit_progress(4, 5, 'Движение к началу по Y')
            
            if MOCK_MODE:
                await asyncio.sleep(0.5)
                motors.position['y'] = 0
            else:
                while not sensors.read('y_begin'):
                    if self._stop_requested:
                        return False
                    await motors.move_xy(motors.position['x'], motors.position['y'] - 100)
                motors.position['y'] = 0
            
            await self._emit_progress(5, 5, 'Инициализация завершена')
            
            if MOCK_MODE:
                sensors.set_mock('x_begin', 1)
                sensors.set_mock('y_begin', 1)
                sensors.set_mock('tray_begin', 1)
            
            self.state = 'idle'
            return True
            
        except Exception as e:
            await self._emit_error(1, f'Ошибка инициализации: {e}')
            self.state = 'error'
            return False
    
    async def take_shelf(self, row: str, x: int, y: int) -> bool:
        """Алгоритм TAKE - извлечение полки для выдачи книги"""
        self.current_operation = 'TAKE'
        self.state = 'busy'
        self._stop_requested = False
        total_steps = 13
        
        try:
            await self._emit_progress(1, total_steps, 'Проверка лотка')
            if not sensors.is_tray_retracted() or MOCK_MODE:
                await self._safe_tray_retract()
            
            target_x, target_y = self.path_planner.get_cell_position(row, x, y)
            await self._emit_progress(2, total_steps, f'Перемещение к ячейке ({row}, {x}, {y})')
            if not await self._safe_move_xy(target_x, target_y):
                return False
            
            grab_params = calibration.get(f'grab_{row.lower()}', {
                'extend1': 1500, 'retract': 1500, 'extend2': 3000
            })
            
            await self._emit_progress(3, total_steps, 'Выдвижение лотка (1-й этап)')
            self._chk(await self._safe_tray_extend(grab_params.get('extend1', 1500)), 'выдвижение лотка 1')

            lock = 'lock1' if row == 'FRONT' else 'lock2'
            await self._emit_progress(4, total_steps, 'Захват полки (закрытие замка)')
            self._chk(await servos.close_lock(lock), 'захват замком')

            await self._emit_progress(5, total_steps, 'Втягивание лотка')
            self._chk(await self._safe_tray_retract(grab_params.get('retract', 1500)), 'втягивание лотка')

            await self._emit_progress(6, total_steps, 'Освобождение защёлки (открытие замка)')
            self._chk(await servos.open_lock(lock), 'открытие замка')

            await self._emit_progress(7, total_steps, 'Выдвижение лотка (2-й этап)')
            self._chk(await self._safe_tray_extend(grab_params.get('extend2', 3000)), 'выдвижение лотка 2')

            await self._emit_progress(8, total_steps, 'Фиксация полки')
            self._chk(await servos.close_lock(lock), 'фиксация замком')

            await self._emit_progress(9, total_steps, 'Полное втягивание')
            self._chk(await self._safe_tray_retract(), 'полное втягивание')

            window_x, window_y = self.path_planner.get_window_position()
            await self._emit_progress(10, total_steps, 'Перемещение к окну выдачи')
            if not await self._safe_move_xy(window_x, window_y):
                return False

            await self._emit_progress(11, total_steps, 'Открытие внутренней шторки')
            await shutters.open_shutter('inner')

            await self._emit_progress(12, total_steps, 'Выдвижение в окно')
            self._chk(await self._safe_tray_extend(), 'выдвижение в окно')
            
            await self._emit_progress(13, total_steps, 'Открытие внешней шторки')
            await shutters.open_shutter('outer')
            
            self.state = 'waiting_user'
            return True
            
        except Exception as e:
            await self._emit_error(2, f'Ошибка TAKE: {e}')
            self.state = 'error'
            return False
    
    async def give_shelf(self, row: str, x: int, y: int) -> bool:
        """Алгоритм GIVE - возврат полки в ячейку"""
        self.current_operation = 'GIVE'
        self.state = 'busy'
        self._stop_requested = False
        total_steps = 12
        
        try:
            await self._emit_progress(1, total_steps, 'Закрытие внешней шторки')
            await shutters.close_shutter('outer')
            
            await self._emit_progress(2, total_steps, 'Втягивание лотка')
            await self._safe_tray_retract()
            
            await self._emit_progress(3, total_steps, 'Закрытие внутренней шторки')
            await shutters.close_shutter('inner')
            
            target_x, target_y = self.path_planner.get_cell_position(row, x, y)
            await self._emit_progress(4, total_steps, f'Перемещение к ячейке ({row}, {x}, {y})')
            if not await self._safe_move_xy(target_x, target_y):
                return False
            
            grab_params = calibration.get(f'grab_{row.lower()}', {
                'extend1': 1500, 'retract': 1500, 'extend2': 3000
            })
            
            await self._emit_progress(5, total_steps, 'Выдвижение лотка (вставка)')
            self._chk(await self._safe_tray_extend(grab_params.get('extend2', 3000)), 'выдвижение лотка (вставка)')

            lock = 'lock1' if row == 'FRONT' else 'lock2'
            await self._emit_progress(6, total_steps, 'Освобождение полки (открытие замка)')
            self._chk(await servos.open_lock(lock), 'освобождение замка')

            await self._emit_progress(7, total_steps, 'Частичное втягивание')
            self._chk(await self._safe_tray_retract(grab_params.get('retract', 1500)), 'частичное втягивание')

            await self._emit_progress(8, total_steps, 'Фиксация защёлки (закрытие замка)')
            self._chk(await servos.close_lock(lock), 'фиксация замком')

            await self._emit_progress(9, total_steps, 'Выдвижение для освобождения')
            self._chk(await self._safe_tray_extend(grab_params.get('extend1', 1500)), 'выдвижение для освобождения')

            await self._emit_progress(10, total_steps, 'Открытие замка')
            self._chk(await servos.open_lock(lock), 'открытие замка')

            await self._emit_progress(11, total_steps, 'Полное втягивание')
            self._chk(await self._safe_tray_retract(), 'полное втягивание')
            
            await self._emit_progress(12, total_steps, 'Операция завершена')
            
            self.state = 'idle'
            return True
            
        except Exception as e:
            await self._emit_error(3, f'Ошибка GIVE: {e}')
            self.state = 'error'
            return False
    
    async def deliver_to_window(self, row: str, x: int, y: int) -> bool:
        """Доставить полку с книгой из ячейки к ПЕРЕДНЕМУ окну выдачи.

        FRONT — обычный путь (одиночный замок) = существующий take_shelf.
        BACK  — КРОСС-РЯД: перехват полки на платформу (motors.cross_grab_onto_platform,
                задний ряд → передний замок держит) → каретка к окну → выдвинуть в окно.

        ⚠️ Кросс-рядная ветка (BACK) — композиция валидированного extract_rear
        (shelf_operations.py, 2 перехвата) + существующая доставка к окну.
        Валидировать на железе пошагово. Живой issue-флоу её пока НЕ зовёт
        (issue_service использует take_shelf) — включаем после сухого прогона.
        Обратный путь (stow задней книги: фронт-held → задняя стойка) асимметричен —
        проектируется на железе (см. docs/PEREHVAT.md).
        """
        if row == 'FRONT':
            return await self.take_shelf(row, x, y)

        self.current_operation = 'TAKE'
        self.state = 'busy'
        self._stop_requested = False
        try:
            await self._emit_progress(1, 8, 'Проверка лотка')
            if not sensors.is_tray_retracted() or MOCK_MODE:
                await self._safe_tray_retract()

            tx, ty = self.path_planner.get_cell_position(row, x, y)
            await self._emit_progress(2, 8, f'Перемещение к задней ячейке ({x}, {y})')
            if not await self._safe_move_xy(tx, ty):
                return False

            # Перехват: захват задней полки НА платформу (передний замок держит)
            if not await motors.cross_grab_onto_platform('BACK'):
                await self._emit_error(2, 'Перехват: не удалось захватить полку из заднего ряда')
                self.state = 'error'
                return False
            await self._emit_progress(5, 8, 'Полка на платформе (перехват выполнен)')

            wx, wy = self.path_planner.get_window_position()
            await self._emit_progress(6, 8, 'Перемещение к окну выдачи')
            if not await self._safe_move_xy(wx, wy):
                return False

            await self._emit_progress(7, 8, 'Открытие внутренней шторки')
            await shutters.open_shutter('inner')
            await self._safe_tray_extend()
            await self._emit_progress(8, 8, 'Открытие внешней шторки')
            await shutters.open_shutter('outer')

            self.state = 'waiting_user'
            return True
        except Exception as e:
            await self._emit_error(2, f'Ошибка доставки (кросс-ряд): {e}')
            self.state = 'error'
            return False

    async def wait_for_user(self, timeout_ms: int = None, book_rfid: str = None) -> bool:
        """Ожидание, пока пользователь/библиотекарь заберёт книгу из окна.

        Если передан book_rfid и не мок — ждём, пока RRU9816 перестанет видеть метку
        этой книги (книгу физически вынули). Логика безопасная:
          - пока метку НИ РАЗУ не увидели (ридер выключен / не добивает до окна / мок),
            ведём себя как раньше — просто досыпаем до таймаута, ничего не «детектим»;
          - таймаут всегда верхняя граница (железное правило: таймаут обязателен).
        """
        timeout = timeout_ms or TIMEOUTS['user_wait']

        if not book_rfid or MOCK_MODE:
            await asyncio.sleep(timeout / 1000)
            return True

        try:
            from ..rfid.book_reader import book_reader
        except Exception:
            await asyncio.sleep(timeout / 1000)
            return True

        POLL = 0.3              # период проверки присутствия метки, с
        STABLE_ABSENT = 3       # столько подряд «нет метки» = книгу забрали (анти-дребезг UHF)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout / 1000
        seen = False
        absent = 0

        while loop.time() < deadline:
            if self._stop_requested:
                return True
            present = book_reader.is_present(book_rfid)
            if present:
                seen = True
                absent = 0
            elif seen:
                absent += 1
                if absent >= STABLE_ABSENT:
                    return True  # метка пропала после того как была видна → книгу забрали
            await asyncio.sleep(POLL)

        # Таймаут: либо метку так и не увидели (фоллбек на старое поведение),
        # либо пользователь не забрал — в любом случае не висим, идём дальше.
        return True
    
    def stop(self):
        """Аварийная остановка"""
        self._stop_requested = True
        motors.stop()
        # Безопасность: при аварии шторки не оставляем открытыми (рука/книга в окне).
        # stop() синхронный — закрываем напрямую, без await.
        try:
            shutters.close_all_immediate()
        except Exception:
            pass
        self.state = 'stopped'
    
    def get_state(self) -> Dict[str, Any]:
        return {
            'state': self.state,
            'current_operation': self.current_operation,
            'position': motors.get_position(),
            'sensors': sensors.read_all(),
            'servos': servos.get_all_states(),
            'shutters': shutters.get_all_states(),
        }


algorithms = Algorithms()
