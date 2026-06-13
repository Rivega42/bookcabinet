"""
Калибровка системы v2.1
Полная поддержка wizard калибровки
"""
import asyncio
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from ..config import CABINET, GPIO_PINS


class CalibrationWizard:
    """Состояние wizard калибровки"""
    def __init__(self):
        self.mode: Optional[str] = None
        self.step: int = 0
        self.kinematics_results: Dict[str, int] = {}
        self.points10_data: List[Dict] = []
        self.grab_side: Optional[str] = None
    
    def reset(self):
        self.mode = None
        self.step = 0
        self.kinematics_results = {}
        self.points10_data = []
        self.grab_side = None


class Calibration:
    VERSION = "2.1"
    
    def __init__(self, filepath: str = 'bookcabinet/calibration.json'):
        self.filepath = filepath
        self.data = self._load()
        self.wizard = CalibrationWizard()
    
    def _default_data(self) -> Dict[str, Any]:
        return {
            'version': self.VERSION,
            'timestamp': datetime.now().isoformat(),
            'kinematics': {
                'x_plus_dir_a': 1,
                'x_plus_dir_b': -1,
                'y_plus_dir_a': 1,
                'y_plus_dir_b': 1,
            },
            'positions': {
                'x': [1891, 6392, 10894],
                'y': [i * 423 for i in range(21)],
            },
            'window': CABINET.get('window', {'col': 1, 'y_start': 7, 'y_end': 11}),
            'grab_front': {
                'extend1': 1900,
                'retract': 1500,
                'extend2': 3100,
            },
            'grab_back': {
                'extend1': 1900,
                'retract': 1500,
                'extend2': 3100,
            },
            'speeds': {
                'xy': 4000,
                'tray': 2000,
                'acceleration': 8000,
            },
            'servos': {
                'lock1_open': 0,
                'lock1_close': 95,
                'lock2_open': 0,
                'lock2_close': 95,
            },
            'tray': {
                'extend_steps': 5000,
                'retract_steps': 5000,
            },
            'blocked_cells': {
                'front': {
                    '1': [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
                },
                'back': {
                    '0': [19, 20],
                    '1': [19, 20],
                    '2': [20],
                },
            },
        }
    
    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    if 'version' not in data:
                        data['version'] = self.VERSION
                    if 'timestamp' not in data:
                        data['timestamp'] = datetime.now().isoformat()
                    if 'blocked_cells' not in data:
                        data['blocked_cells'] = self._default_data()['blocked_cells']
                    if 'tray' not in data:
                        data['tray'] = self._default_data()['tray']
                    return data
            except Exception:
                pass
        # Файла нет (или он битый) → едем по ДЕФОЛТНЫМ XY/grab, НЕ по полевым
        # racks/shelves из корневого calibration.json. На шкафу это надо видеть:
        # пока не прогнан встроенный мастер калибровки, механика приложения на дефолтах.
        # Подробности — docs/FLOWS.md, раздел «два файла калибровки».
        try:
            import logging
            logging.getLogger(__name__).warning(
                'Калибровка приложения %s не найдена — используются ДЕФОЛТНЫЕ '
                'positions/grab (не полевые racks/shelves). Прогоните мастер '
                'калибровки в админке. См. docs/FLOWS.md.', self.filepath)
        except Exception:
            pass
        return self._default_data()
    
    def save(self):
        self.data['timestamp'] = datetime.now().isoformat()
        self.data['version'] = self.VERSION
        os.makedirs(os.path.dirname(self.filepath) if os.path.dirname(self.filepath) else '.', exist_ok=True)
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self.data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        keys = key.split('.')
        data = self.data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value
        self.save()
    
    def set_position_x(self, column: int, steps: int):
        self.data['positions']['x'][column] = steps
        self.save()
    
    def set_position_y(self, row: int, steps: int):
        self.data['positions']['y'][row] = steps
        self.save()
    
    def reset(self):
        self.data = self._default_data()
        self.save()
    
    def export_json(self) -> str:
        return json.dumps(self.data, indent=2)
    
    def import_json(self, json_str: str) -> Dict:
        try:
            data = json.loads(json_str)
            validation = self.validate(data)
            if validation['valid']:
                self.data = data
                self.save()
                return {'success': True}
            return {'success': False, 'errors': validation['errors']}
        except json.JSONDecodeError as e:
            return {'success': False, 'errors': [f'Invalid JSON: {str(e)}']}
    
    def toggle_blocked_cell(self, side: str, col: int, row: int) -> bool:
        if 'blocked_cells' not in self.data:
            self.data['blocked_cells'] = {'front': {}, 'back': {}}
        
        if side not in self.data['blocked_cells']:
            self.data['blocked_cells'][side] = {}
        
        col_str = str(col)
        if col_str not in self.data['blocked_cells'][side]:
            self.data['blocked_cells'][side][col_str] = []
        
        cells = self.data['blocked_cells'][side][col_str]
        if row in cells:
            cells.remove(row)
            blocked = False
        else:
            cells.append(row)
            cells.sort()
            blocked = True
        
        self.save()
        return blocked
    
    def is_cell_blocked(self, side: str, col: int, row: int) -> bool:
        blocked = self.data.get('blocked_cells', {}).get(side, {}).get(str(col), [])
        return row in blocked
    
    def validate(self, data: Dict = None) -> Dict:
        """Валидация данных калибровки"""
        to_validate = data if data else self.data
        errors = []
        warnings = []
        
        positions = to_validate.get('positions', {})
        
        x_positions = positions.get('x', [])
        if len(x_positions) != 3:
            errors.append(f'positions.x должен содержать 3 элемента, найдено {len(x_positions)}')
        else:
            for i, x in enumerate(x_positions):
                if not isinstance(x, (int, float)) or x < 0:
                    errors.append(f'positions.x[{i}] должен быть >= 0')
                if x > 15000:
                    warnings.append(f'positions.x[{i}] = {x} выходит за типичный диапазон')
            
            if x_positions != sorted(x_positions):
                errors.append('positions.x должны быть отсортированы по возрастанию')
        
        y_positions = positions.get('y', [])
        if len(y_positions) != 21:
            errors.append(f'positions.y должен содержать 21 элемент, найдено {len(y_positions)}')
        else:
            for i, y in enumerate(y_positions):
                if not isinstance(y, (int, float)) or y < 0:
                    errors.append(f'positions.y[{i}] должен быть >= 0')
            
            if y_positions != sorted(y_positions):
                errors.append('positions.y должны быть отсортированы по возрастанию')
        
        kinematics = to_validate.get('kinematics', {})
        for key in ['x_plus_dir_a', 'x_plus_dir_b', 'y_plus_dir_a', 'y_plus_dir_b']:
            val = kinematics.get(key)
            if val not in [-1, 1]:
                errors.append(f'kinematics.{key} должен быть -1 или 1')
        
        speeds = to_validate.get('speeds', {})
        if speeds.get('xy', 0) <= 0 or speeds.get('xy', 0) > 10000:
            errors.append('speeds.xy должен быть в диапазоне 1-10000')
        if speeds.get('tray', 0) <= 0 or speeds.get('tray', 0) > 10000:
            errors.append('speeds.tray должен быть в диапазоне 1-10000')
        if speeds.get('acceleration', 0) <= 0 or speeds.get('acceleration', 0) > 20000:
            errors.append('speeds.acceleration должен быть в диапазоне 1-20000')
        
        servos = to_validate.get('servos', {})
        for key in ['lock1_open', 'lock1_close', 'lock2_open', 'lock2_close']:
            val = servos.get(key, -1)
            if not isinstance(val, (int, float)) or val < 0 or val > 180:
                errors.append(f'servos.{key} должен быть в диапазоне 0-180')
        
        for grab_key in ['grab_front', 'grab_back']:
            grab = to_validate.get(grab_key)
            if grab is None:
                errors.append(f'{grab_key} обязателен')
                continue
            if not isinstance(grab, dict):
                errors.append(f'{grab_key} должен быть объектом')
                continue
            for key in ['extend1', 'retract', 'extend2']:
                if key not in grab:
                    errors.append(f'{grab_key}.{key} обязателен')
                    continue
                val = grab.get(key, -1)
                if not isinstance(val, (int, float)) or val < 0 or val > 10000:
                    errors.append(f'{grab_key}.{key} должен быть в диапазоне 0-10000')
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
        }
    
    def update_with_validation(self, data: Dict) -> Dict:
        """Обновление калибровки с валидацией"""
        merged = {**self.data}
        
        for key in ['positions', 'kinematics', 'speeds', 'servos', 'grab_front', 'grab_back', 'tray', 'blocked_cells']:
            if key in data:
                if isinstance(data[key], dict) and isinstance(merged.get(key), dict):
                    merged[key] = {**merged.get(key, {}), **data[key]}
                else:
                    merged[key] = data[key]
        
        validation = self.validate(merged)
        
        if validation['valid']:
            self.data = merged
            self.save()
            return {'success': True, 'warnings': validation['warnings']}
        else:
            return {'success': False, 'errors': validation['errors'], 'warnings': validation['warnings']}


calibration = Calibration()


class AutoCalibrator:
    """
    Автоматическое определение рабочего поля по концевикам.
    Алгоритм:
    1. Home XY (x=0, y=0 по концевикам)
    2. Едем +X до SENSOR_X_END → записываем max_x
    3. Возврат x=0
    4. Едем +Y до SENSOR_Y_END → записываем max_y
    5. Возврат y=0
    6. Рассчитываем позиции ячеек по формуле с отступами
    7. Сохраняем в calibration.json
    """

    # Отступы от концевиков до первой/последней ячейки (шаги)
    MARGIN_X = 500   # отступ от левого концевика до колонки 0
    MARGIN_Y = 300   # отступ от нижнего концевика до ряда 0

    def __init__(self, calibration: 'Calibration'):
        self.calibration = calibration

    async def run(self, motors, sensors, progress_callback=None) -> dict:
        """Запустить полную авто-калибровку"""
        results = {}

        def progress(msg):
            print(f"[calibration] {msg}")
            if progress_callback:
                progress_callback(msg)

        # Шаг 1: Хоминг
        progress("Хоминг XY...")
        await motors.home_with_sensors(sensors)

        # Шаг 2: Найти max_x
        progress("Поиск правой границы (max_x)...")
        max_x = await self._find_axis_limit(motors, sensors, "x", progress)
        results["max_x"] = max_x
        progress(f"max_x = {max_x} шагов")

        # Возврат в 0
        await motors.move_xy(0, motors.position["y"])

        # Шаг 3: Найти max_y
        progress("Поиск верхней границы (max_y)...")
        max_y = await self._find_axis_limit(motors, sensors, "y", progress)
        results["max_y"] = max_y
        progress(f"max_y = {max_y} шагов")

        # Возврат в 0,0
        await motors.move_xy(0, 0)

        # Шаг 4: Рассчитать позиции ячеек
        num_cols = 3
        num_rows = 21

        usable_x = max_x - 2 * self.MARGIN_X
        usable_y = max_y - 2 * self.MARGIN_Y

        step_x = usable_x // (num_cols - 1) if num_cols > 1 else 0
        step_y = usable_y // (num_rows - 1) if num_rows > 1 else 0

        positions_x = [self.MARGIN_X + i * step_x for i in range(num_cols)]
        positions_y = [self.MARGIN_Y + i * step_y for i in range(num_rows)]

        results["positions_x"] = positions_x
        results["positions_y"] = positions_y

        # Шаг 5: Сохранить
        self.calibration.data["positions"]["x"] = positions_x
        self.calibration.data["positions"]["y"] = positions_y
        self.calibration.save()

        progress(f"Калибровка завершена. X: {positions_x}, Y шаг: {step_y}")
        return results

    async def _find_axis_limit(self, motors, sensors, axis: str, progress) -> int:
        """Двигаться по оси до концевика, вернуть количество шагов"""
        HOMING_SPEED = 1500
        HOMING_CHUNK = 300
        MAX_STEPS = 70000

        sensor_name = "x_end" if axis == "x" else "y_end"
        total_steps = 0

        if motors.mock_mode:
            await asyncio.sleep(2.0)
            return 20000 if axis == "x" else 45000

        # +X: dir_a=1 dir_b=0 in CoreXY; +Y: dir_a=1 dir_b=1
        if axis == "x":
            motors.pi.write(GPIO_PINS["MOTOR_A_DIR"], 1)
            motors.pi.write(GPIO_PINS["MOTOR_B_DIR"], 0)
        else:
            motors.pi.write(GPIO_PINS["MOTOR_A_DIR"], 1)
            motors.pi.write(GPIO_PINS["MOTOR_B_DIR"], 1)
        time.sleep(0.01)

        while not sensors.is_triggered(sensor_name) and total_steps < MAX_STEPS:
            motors._wave_steps(
                [GPIO_PINS["MOTOR_A_STEP"], GPIO_PINS["MOTOR_B_STEP"]],
                HOMING_CHUNK,
                HOMING_SPEED
            )
            total_steps += HOMING_CHUNK
            await asyncio.sleep(0)

        return total_steps
