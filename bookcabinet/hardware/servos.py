"""
Управление сервоприводами (замки)
"""
import asyncio
from .gpio_manager import gpio
from ..config import GPIO_PINS, SERVO_ANGLES, MOCK_MODE


class Servos:
    def __init__(self):
        self.mock_mode = MOCK_MODE
        self.states = {
            'lock1': 'closed',
            'lock2': 'closed',
        }
    
    def _angle_to_pulsewidth(self, angle: int) -> int:
        return int(500 + (angle / 180) * 2000)
    
    async def set_angle(self, servo: str, angle: int) -> bool:
        """Выставить угол. Возвращает bool: успех = команда серве не упала.
        Сенсора положения замка нет — это лучший доступный сигнал отказа (CRIT-2)."""
        try:
            pin = GPIO_PINS['SERVO_LOCK_1'] if servo == 'lock1' else GPIO_PINS['SERVO_LOCK_2']
            pulsewidth = self._angle_to_pulsewidth(angle)
            gpio.set_servo_pulsewidth(pin, pulsewidth)
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            print(f"[servos] set_angle FAILED {servo}={angle}: {e}")
            return False

    async def open_lock(self, lock: str = 'lock1') -> bool:
        angle_key = f'{lock}_open'
        angle = SERVO_ANGLES.get(angle_key, 0)
        ok = await self.set_angle(lock, angle)
        if ok:
            self.states[lock] = 'open'
        return ok

    async def close_lock(self, lock: str = 'lock1') -> bool:
        angle_key = f'{lock}_close'
        angle = SERVO_ANGLES.get(angle_key, 95)
        ok = await self.set_angle(lock, angle)
        if ok:
            self.states[lock] = 'closed'
        return ok
    
    def get_state(self, lock: str = 'lock1') -> str:
        return self.states.get(lock, 'unknown')
    
    def get_all_states(self) -> dict:
        return self.states.copy()


servos = Servos()
