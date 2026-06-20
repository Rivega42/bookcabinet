"""
Управление моторами CoreXY и платформой
Использует pigpio hardware waves для плавной работы (DMA)
"""
import asyncio
import time
from typing import Tuple
from ..config import GPIO_PINS, MOTOR_SPEEDS, MOCK_MODE, TIMEOUTS


class Motors:
    def __init__(self):
        self.position = {"x": 0, "y": 0, "tray": 0}
        self.is_moving = False
        self.mock_mode = MOCK_MODE
        self.pi = None

        # Real step counters via pigpio callbacks on STEP pins
        self._step_count_a = 0
        self._step_count_b = 0
        self._step_callback_a = None
        self._step_callback_b = None

        if not self.mock_mode:
            try:
                import pigpio
                self.pi = pigpio.pi()
                if not self.pi.connected:
                    print("WARNING: pigpio not connected, switching to mock mode")
                    self.mock_mode = True
                else:
                    # Setup output pins
                    for pin_name in ["MOTOR_A_STEP", "MOTOR_A_DIR", "MOTOR_B_STEP", "MOTOR_B_DIR", "TRAY_STEP", "TRAY_DIR"]:
                        self.pi.set_mode(GPIO_PINS[pin_name], pigpio.OUTPUT)
                        self.pi.write(GPIO_PINS[pin_name], 0)
                    self._setup_step_counter()
            except ImportError:
                print("WARNING: pigpio not installed, switching to mock mode")
                self.mock_mode = True

    def _setup_step_counter(self):
        """Setup pigpio callbacks on STEP pins for real step counting."""
        if self.pi and not self.mock_mode:
            import pigpio
            self._step_callback_a = self.pi.callback(
                GPIO_PINS["MOTOR_A_STEP"], pigpio.RISING_EDGE, self._on_step_a
            )
            self._step_callback_b = self.pi.callback(
                GPIO_PINS["MOTOR_B_STEP"], pigpio.RISING_EDGE, self._on_step_b
            )
            print("[motors] Step counters active on pins "
                  f"A={GPIO_PINS['MOTOR_A_STEP']}, B={GPIO_PINS['MOTOR_B_STEP']}")

    def _on_step_a(self, gpio, level, tick):
        self._step_count_a += 1

    def _on_step_b(self, gpio, level, tick):
        self._step_count_b += 1

    def get_real_step_counts(self) -> dict:
        """Return the number of steps counted on each motor since last reset."""
        return {'a': self._step_count_a, 'b': self._step_count_b}

    def reset_step_counts(self):
        """Reset both step counters to zero."""
        self._step_count_a = 0
        self._step_count_b = 0
    
    def _wave_steps(self, step_pins: list, steps: int, frequency: int = 4000) -> bool:
        """Execute steps using hardware waves (DMA) for smooth operation"""
        if self.mock_mode or not self.pi:
            return True
        
        import pigpio
        pulse_us = int(500000 / frequency)
        
        # Create wave mask for step pins
        step_mask = 0
        for pin in step_pins:
            step_mask |= (1 << pin)
        
        self.pi.wave_clear()
        
        # Build wave with 200 steps per chunk
        chunk_size = min(200, steps)
        wf = []
        for _ in range(chunk_size):
            wf.append(pigpio.pulse(step_mask, 0, pulse_us))
            wf.append(pigpio.pulse(0, step_mask, pulse_us))
        
        self.pi.wave_add_generic(wf)
        wave_id = self.pi.wave_create()
        
        if wave_id < 0:
            return False
        
        # Calculate repeats
        repeats = steps // chunk_size
        remainder = steps % chunk_size
        
        if repeats > 0:
            chain = [255, 0, wave_id, 255, 1, repeats & 0xFF, (repeats >> 8) & 0xFF]
            self.pi.wave_chain(chain)
            
            while self.pi.wave_tx_busy():
                time.sleep(0.01)
        
        self.pi.wave_delete(wave_id)
        
        # Handle remainder
        if remainder > 0:
            self.pi.wave_clear()
            wf = []
            for _ in range(remainder):
                wf.append(pigpio.pulse(step_mask, 0, pulse_us))
                wf.append(pigpio.pulse(0, step_mask, pulse_us))
            self.pi.wave_add_generic(wf)
            wave_id = self.pi.wave_create()
            
            if wave_id >= 0:
                self.pi.wave_send_once(wave_id)
                while self.pi.wave_tx_busy():
                    time.sleep(0.01)
                self.pi.wave_delete(wave_id)
        
        return True
    
    async def move_xy(self, target_x: int, target_y: int) -> bool:
        """Move to target position using CoreXY kinematics"""
        if self.is_moving:
            return False
        
        self.is_moving = True
        try:
            dx = target_x - self.position["x"]
            dy = target_y - self.position["y"]
            
            # CoreXY kinematics
            steps_a = dx + dy
            steps_b = -dx + dy
            
            dir_a = 1 if steps_a > 0 else 0
            dir_b = 1 if steps_b > 0 else 0
            
            if self.mock_mode:
                await asyncio.sleep(TIMEOUTS["move"] / 1000)
            else:
                # Set directions
                self.pi.write(GPIO_PINS["MOTOR_A_DIR"], dir_a)
                self.pi.write(GPIO_PINS["MOTOR_B_DIR"], dir_b)
                time.sleep(0.01)
                
                # Move both motors simultaneously
                max_steps = max(abs(steps_a), abs(steps_b))
                if max_steps > 0:
                    step_pins = []
                    if abs(steps_a) > 0:
                        step_pins.append(GPIO_PINS["MOTOR_A_STEP"])
                    if abs(steps_b) > 0:
                        step_pins.append(GPIO_PINS["MOTOR_B_STEP"])
                    
                    self._wave_steps(step_pins, max_steps, MOTOR_SPEEDS["xy"])
            
            self.position["x"] = target_x
            self.position["y"] = target_y
            return True
            
        finally:
            self.is_moving = False
    
    async def move_tray(self, direction: str, steps: int = 3000) -> bool:
        """Move tray in/out"""
        if self.is_moving:
            return False
        
        self.is_moving = True
        try:
            is_extend = direction in ("extend", "out", "+")
            
            if self.mock_mode:
                timeout = TIMEOUTS["tray_extend"] if is_extend else TIMEOUTS["tray_retract"]
                await asyncio.sleep(timeout / 1000)
            else:
                self.pi.write(GPIO_PINS["TRAY_DIR"], 1 if is_extend else 0)
                time.sleep(0.01)
                self._wave_steps([GPIO_PINS["TRAY_STEP"]], steps, MOTOR_SPEEDS["tray"])
            
            self.position["tray"] = 1 if is_extend else 0
            return True
            
        finally:
            self.is_moving = False
    
    async def extend_tray(self, steps: int = 3000) -> bool:
        return await self.move_tray("extend", steps)
    
    async def retract_tray(self, steps: int = 3000) -> bool:
        return await self.move_tray("retract", steps)
    
    def get_position(self) -> dict:
        return self.position.copy()
    
    def stop(self):
        """Emergency stop"""
        self.is_moving = False
        if self.pi and not self.mock_mode:
            self.pi.wave_tx_stop()
            self.pi.write(GPIO_PINS["MOTOR_A_STEP"], 0)
            self.pi.write(GPIO_PINS["MOTOR_B_STEP"], 0)
            self.pi.write(GPIO_PINS["TRAY_STEP"], 0)
    
    async def home(self) -> bool:
        """Move to home position (0, 0)"""
        result = await self.move_xy(0, 0)
        if result:
            await self.retract_tray()
        return result

    def _read_pin_direct(self, pin: int) -> bool:
        """Прямое чтение пина без debounce — для хоминга"""
        if self.mock_mode:
            return False
        readings = [self.pi.read(pin) for _ in range(5)]
        return sum(readings) >= 3

    async def home_with_sensors(self, sensors) -> bool:
        """
        Хоминг XY по концевикам.
        Делегирует в corexy_motion_v2.py (canonical baseline).
        HOME = LEFT + BOTTOM (подтверждено 2026-04-10).
        Скорости: FAST=800, SLOW=300.
        """
        if self.mock_mode:
            await asyncio.sleep(2.0)
            self.position["x"] = 0
            self.position["y"] = 0
            return True

        print("[homing] Делегирование в corexy_motion_v2 (HOME=LEFT+BOTTOM)...")
        try:
            import sys, os
            v2_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'tools')
            v2_dir = os.path.abspath(v2_dir)
            if v2_dir not in sys.path:
                sys.path.insert(0, v2_dir)
            from corexy_motion_v2 import CoreXYMotionV2, MotionConfig

            # Переиспользуем текущее pigpio-соединение
            motion = CoreXYMotionV2(pi=self.pi, config=MotionConfig())
            ok = motion.home_xy()

            self.position["x"] = 0
            self.position["y"] = 0
            if ok:
                self.reset_step_counts()
            print(f"[homing] v2 результат: {'OK' if ok else 'FAIL'}")
            return ok
        except ImportError as e:
            print(f"[homing] WARN: corexy_motion_v2 недоступен ({e})")
            return False
        except Exception as e:
            print(f"[homing] Ошибка v2 homing: {e}")
            return False

    async def home_tray_with_sensor(self, sensors) -> bool:
        """
        Калибровка лотка по образцу полевого tools/tray_calib_final.py:
        FRONT → BACK (измерение полного хода) → CENTER.

        Двухэтапный подход на каждый концевик (FAST 10000 → backoff 1500 @2000
        → SLOW 1500). КЛЮЧЕВОЕ: sensor_stable требует 10 ПОДРЯД чтений «нажато»
        (любой 0 сбрасывает) — устойчиво к шуму GPIO20. Прежний одноэтапный
        хоминг только до BACK ловил ЛОЖНОЕ срабатывание → ложный ноль (баг,
        вскрытый на железе 2026-06-13).

        DIR: 0=FRONT, 1=BACK. Вызывать ТОЛЬКО при каретке в home (x=0, y=0).
        Возвращает False, если любой концевик не достигнут за MOVE_TIMEOUT.
        """
        if self.position["x"] != 0 or self.position["y"] != 0:
            print("[tray] ERROR: калибровка лотка только при каретке в 0,0")
            return False

        if self.mock_mode:
            await asyncio.sleep(1.0)
            self.position["tray"] = 0
            return True

        import pigpio
        STEP = GPIO_PINS["TRAY_STEP"]; DIR = GPIO_PINS["TRAY_DIR"]
        EN1 = GPIO_PINS["TRAY_ENA_1"]; EN2 = GPIO_PINS["TRAY_ENA_2"]
        FRONT = GPIO_PINS["SENSOR_TRAY_END"]; BACK = GPIO_PINS["SENSOR_TRAY_BEGIN"]
        FAST, BACKOFF_SPD, SLOW = 10000, 2000, 1500
        BACKOFF_STEPS = 1500
        MOVE_TIMEOUT = 20.0   # страховка на подход к концевику (в полевом скрипте таймаута нет)

        for p in (STEP, DIR, EN1, EN2):
            self.pi.set_mode(p, pigpio.OUTPUT)
        self.pi.write(EN1, 1); self.pi.write(EN2, 1)
        for s in (FRONT, BACK):
            self.pi.set_mode(s, pigpio.INPUT)
            self.pi.set_pull_up_down(s, pigpio.PUD_UP)
            self.pi.set_glitch_filter(s, 1000)
        time.sleep(0.1)

        def make_wave(speed):
            period = int(1000000 / speed); half = period // 2
            self.pi.wave_clear()
            self.pi.wave_add_generic([pigpio.pulse(1 << STEP, 0, half),
                                      pigpio.pulse(0, 1 << STEP, half)])
            return self.pi.wave_create()

        def stable(sensor, n=10):
            for _ in range(n):
                if self.pi.read(sensor) == 0:
                    return False
                time.sleep(0.0005)
            return True

        def move_steps(direction, steps, speed):
            w = make_wave(speed)
            self.pi.write(EN1, 0); self.pi.write(EN2, 0)
            self.pi.write(DIR, direction); time.sleep(0.05)
            self.pi.wave_send_repeat(w)
            time.sleep(steps / speed)
            self.pi.wave_tx_stop()
            self.pi.write(EN1, 1); self.pi.write(EN2, 1)
            self.pi.wave_delete(w)

        def move_until(direction, sensor, speed):
            w = make_wave(speed)
            self.pi.write(EN1, 0); self.pi.write(EN2, 0)
            self.pi.write(DIR, direction); time.sleep(0.05)
            self.pi.wave_send_repeat(w)
            t0 = time.time(); reached = False
            while time.time() - t0 < MOVE_TIMEOUT:
                if stable(sensor, 10):
                    reached = True; break
            self.pi.wave_tx_stop()
            self.pi.write(EN1, 1); self.pi.write(EN2, 1)
            steps = int((time.time() - t0) * speed)
            self.pi.wave_delete(w)
            return steps, reached

        def home_to(direction, sensor):
            _, hit = move_until(direction, sensor, FAST)
            if not hit:
                return None
            move_steps(1 if direction == 0 else 0, BACKOFF_STEPS, BACKOFF_SPD)
            time.sleep(0.1)
            steps, hit = move_until(direction, sensor, SLOW)
            return steps if hit else None

        try:
            # 1. К FRONT (DIR=0) двухэтапно
            if home_to(0, FRONT) is None:
                print("[tray] FRONT не достигнут (таймаут)")
                return False
            time.sleep(0.3)
            # 2. К BACK (DIR=1), меряем полный ход
            fast_steps, hit = move_until(1, BACK, FAST)
            if not hit:
                print("[tray] BACK fast не достигнут (таймаут)")
                return False
            move_steps(0, BACKOFF_STEPS, BACKOFF_SPD)
            time.sleep(0.1)
            slow_steps, hit = move_until(1, BACK, SLOW)
            if not hit:
                print("[tray] BACK slow не достигнут (таймаут)")
                return False
            total = fast_steps + slow_steps
            center = total // 2
            # 3. В CENTER (DIR=0 от BACK)
            move_steps(0, center, FAST)
            self.position["tray"] = 0   # лоток в центре = рабочее положение покоя
            print(f"[tray] калибровка OK: total={total}, center={center}")
            return True
        finally:
            self.pi.write(EN1, 1); self.pi.write(EN2, 1)
            try:
                self.pi.wave_clear()
            except Exception:
                pass
    
    async def cross_handoff(self, direction: str, on_progress=None) -> bool:
        """
        Кросс-рядный ПЕРЕХВАТ полки — порт tools/cross_operations_v2.py
        (field-validated). 8 шагов с перехватом замков. Логика и константы
        байт-в-байт из полевого скрипта; убраны input()-паузы, добавлен таймаут
        на подвод к концевику (железное правило).

        direction:
          'rear_to_front' — взять из ЗАДНЕГО ряда, вынести в ПЕРЕДНИЙ
                            (для выдачи задней книги в переднее окно),
          'front_to_rear' — из переднего в задний (для возврата в задний ряд).

        ⚠️ ВАЛИДИРОВАТЬ НА ЖЕЛЕЗЕ рядом с tools/cross_operations_v2.py как эталоном.
        Мок только проверяет порядок 8 шагов.
        """
        # --- константы cross_operations_v2.py (НЕ менять без железа) ---
        STEP = GPIO_PINS["TRAY_STEP"]; DIR = GPIO_PINS["TRAY_DIR"]
        EN1 = GPIO_PINS["TRAY_ENA_1"]; EN2 = GPIO_PINS["TRAY_ENA_2"]
        FRONT = GPIO_PINS["SENSOR_TRAY_END"]; BACK = GPIO_PINS["SENSOR_TRAY_BEGIN"]
        L_FRONT = GPIO_PINS["LOCK_FRONT"]; L_REAR = GPIO_PINS["LOCK_REAR"]
        TRAY_FREQ = 12000
        LOCK_DISTANCE = 12600
        TRAY_CENTER = 11300
        LOCK_GRAB_PWM = 1200
        LOCK_RELEASE_PWM = 500
        BACKOFF_STEPS = 1500
        SLOW_FREQ = 1500
        MOVE_TIMEOUT = 25.0   # с, страховка подвода к концевику (в поле таймаута нет)

        # DIR: 0=FRONT, 1=BACK
        if direction == 'rear_to_front':
            first_lock, second_lock = L_REAR, L_FRONT
            first_sensor, second_sensor = BACK, FRONT
            first_dir, second_dir = 1, 0     # подвод: к BACK / к FRONT
            handoff_dir, center_dir = 0, 1   # перехват к FRONT, центр к BACK
        elif direction == 'front_to_rear':
            first_lock, second_lock = L_FRONT, L_REAR
            first_sensor, second_sensor = FRONT, BACK
            first_dir, second_dir = 0, 1
            handoff_dir, center_dir = 1, 0
        else:
            return False

        async def progress(step, msg):
            if on_progress:
                ev = on_progress({'step': step, 'total': 8, 'message': msg,
                                  'operation': 'HANDOFF'})
                if asyncio.iscoroutine(ev):
                    await ev

        # --- MOCK: только последовательность шагов ---
        if self.mock_mode or not self.pi:
            for i, msg in enumerate([
                "Лоток к 1-му концевику", "Захват 1-м замком",
                "Перехват: лоток на LOCK_DISTANCE", "Отпуск 1-го замка",
                "Перехват 2-м замком", "Лоток ко 2-му концевику",
                "Укладка: отпуск 2-го (strong)", "Лоток в CENTER"], 1):
                await progress(i, msg)
                await asyncio.sleep(0.01)
            self.position["tray"] = 0
            return True

        import pigpio
        for p in (STEP, DIR, EN1, EN2):
            self.pi.set_mode(p, pigpio.OUTPUT)
        self.pi.write(EN1, 1); self.pi.write(EN2, 1)
        for s in (FRONT, BACK):
            self.pi.set_mode(s, pigpio.INPUT)
            self.pi.set_pull_up_down(s, pigpio.PUD_UP)
            self.pi.set_glitch_filter(s, 1000)
        time.sleep(0.1)

        def make_wave(freq):
            half = int(1000000 / freq) // 2
            self.pi.wave_clear()
            self.pi.wave_add_generic([pigpio.pulse(1 << STEP, 0, half),
                                      pigpio.pulse(0, 1 << STEP, half)])
            return self.pi.wave_create()

        def stable(sensor, n=5):
            for _ in range(n):
                if self.pi.read(sensor) == 0:
                    return False
                time.sleep(0.0005)
            return True

        def move_steps(d, steps, freq):
            w = make_wave(freq)
            self.pi.write(EN1, 0); self.pi.write(EN2, 0)
            self.pi.write(DIR, d); time.sleep(0.01)
            self.pi.wave_send_repeat(w)
            time.sleep(steps / freq)
            self.pi.wave_tx_stop()
            self.pi.write(EN1, 1); self.pi.write(EN2, 1)
            self.pi.wave_delete(w)

        async def to_endstop(d, sensor):
            """FAST → backoff → SLOW подвод (как cross_operations_v2.tray_to_endstop),
            с таймаутом. Возвращает False, если концевик не пойман."""
            for phase_freq in (TRAY_FREQ, SLOW_FREQ):
                if phase_freq == SLOW_FREQ:
                    move_steps(1 - d, BACKOFF_STEPS, TRAY_FREQ)  # отъезд от концевика
                    time.sleep(0.05)
                w = make_wave(phase_freq)
                self.pi.write(EN1, 0); self.pi.write(EN2, 0)
                self.pi.write(DIR, d); time.sleep(0.01)
                self.pi.wave_send_repeat(w)
                t0 = time.time(); hit = False
                while time.time() - t0 < MOVE_TIMEOUT:
                    if stable(sensor):
                        hit = True; break
                    await asyncio.sleep(0.002)
                self.pi.wave_tx_stop()
                self.pi.write(EN1, 1); self.pi.write(EN2, 1)
                self.pi.wave_delete(w)
                if not hit:
                    return False
            return True

        def lock(pin, pwm, strong=False):
            for _ in range(3 if strong else 1):
                self.pi.set_servo_pulsewidth(pin, pwm)
                time.sleep(0.5)
            self.pi.set_servo_pulsewidth(pin, 0)

        try:
            await progress(1, "Лоток к концевику (захват из стойки)")
            if not await to_endstop(first_dir, first_sensor):
                return False
            await progress(2, "Захват полки 1-м замком")
            lock(first_lock, LOCK_GRAB_PWM)
            await progress(3, "Перехват: лоток на LOCK_DISTANCE")
            move_steps(handoff_dir, LOCK_DISTANCE, TRAY_FREQ)
            await progress(4, "Отпуск 1-го замка")
            lock(first_lock, LOCK_RELEASE_PWM)
            await progress(5, "Перехват 2-м замком")
            lock(second_lock, LOCK_GRAB_PWM)
            await progress(6, "Лоток ко 2-му концевику")
            if not await to_endstop(second_dir, second_sensor):
                return False
            await progress(7, "Укладка: отпуск 2-го замка (strong)")
            lock(second_lock, LOCK_RELEASE_PWM, strong=True)
            await progress(8, "Лоток в CENTER")
            move_steps(center_dir, TRAY_CENTER, TRAY_FREQ)
            self.position["tray"] = 0
            return True
        finally:
            self.pi.write(EN1, 1); self.pi.write(EN2, 1)
            try:
                self.pi.set_servo_pulsewidth(first_lock, 0)
                self.pi.set_servo_pulsewidth(second_lock, 0)
                self.pi.wave_clear()
            except Exception:
                pass

    async def test_motor(self, motor: str, direction: int, steps: int = 500) -> bool:
        """Test individual motor"""
        if self.is_moving:
            return False
        
        self.is_moving = True
        try:
            motor = motor.upper()
            if motor == "A":
                step_pin = GPIO_PINS["MOTOR_A_STEP"]
                dir_pin = GPIO_PINS["MOTOR_A_DIR"]
            elif motor == "B":
                step_pin = GPIO_PINS["MOTOR_B_STEP"]
                dir_pin = GPIO_PINS["MOTOR_B_DIR"]
            else:
                return False
            
            if self.mock_mode:
                await asyncio.sleep(0.5)
            else:
                self.pi.write(dir_pin, 1 if direction > 0 else 0)
                time.sleep(0.01)
                self._wave_steps([step_pin], abs(steps), MOTOR_SPEEDS["xy"])
            
            return True
        finally:
            self.is_moving = False
    
    async def move_corexy(self, axis: str, steps: int) -> bool:
        """Move along CoreXY axis with endstop protection.
        Автоматически ставит callback на концевик в сторону движения.
        При срабатывании — мгновенный стоп DMA."""
        if self.is_moving:
            return False
        
        self.is_moving = True
        try:
            axis = axis.upper()
            
            if self.mock_mode:
                await asyncio.sleep(0.5)
                return True
            
            import pigpio
            
            # Определяем направление и концевик
            endstop_pin = None
            if axis == "X":
                dir_val = 1 if steps > 0 else 0
                self.pi.write(GPIO_PINS["MOTOR_A_DIR"], dir_val)
                self.pi.write(GPIO_PINS["MOTOR_B_DIR"], dir_val)
                # X+ (вправо) → SENSOR_X_END, X- (влево) → SENSOR_X_BEGIN
                endstop_pin = GPIO_PINS["SENSOR_X_END"] if steps > 0 else GPIO_PINS["SENSOR_X_BEGIN"]
            elif axis == "Y":
                if steps > 0:
                    self.pi.write(GPIO_PINS["MOTOR_A_DIR"], 1)
                    self.pi.write(GPIO_PINS["MOTOR_B_DIR"], 0)
                else:
                    self.pi.write(GPIO_PINS["MOTOR_A_DIR"], 0)
                    self.pi.write(GPIO_PINS["MOTOR_B_DIR"], 1)
                # Y+ (вверх) → SENSOR_Y_END, Y- (вниз) → SENSOR_Y_BEGIN
                endstop_pin = GPIO_PINS["SENSOR_Y_END"] if steps > 0 else GPIO_PINS["SENSOR_Y_BEGIN"]
            else:
                return False
            
            time.sleep(0.001)
            
            # Если уже на концевике — не ехать
            if self.pi.read(endstop_pin):
                print(f"[move] {axis} pin {endstop_pin} уже HIGH, движение отменено")
                return False
            
            # Glitch filter 500us: фильтрует спайки от DIR/STEP, пропускает реальное нажатие
            GLITCH_US = 500
            self.pi.set_glitch_filter(endstop_pin, GLITCH_US)
            time.sleep(0.005)
            
            # Callback: мгновенный стоп при концевике
            hit_flag = [False]
            def _on_endstop(gpio, level, tick):
                if level == 1:
                    self.pi.wave_tx_stop()
                    hit_flag[0] = True
            
            cb = self.pi.callback(endstop_pin, pigpio.RISING_EDGE, _on_endstop)
            
            # Движение wave чанками
            step_pins = [GPIO_PINS["MOTOR_A_STEP"], GPIO_PINS["MOTOR_B_STEP"]]
            step_mask = (1 << step_pins[0]) | (1 << step_pins[1])
            pulse_us = int(500000 / MOTOR_SPEEDS["xy"])
            total = abs(steps)
            chunk = 2000
            done = 0
            
            while done < total and not hit_flag[0]:
                remaining = min(chunk, total - done)
                wf = []
                for _ in range(remaining):
                    wf.append(pigpio.pulse(step_mask, 0, pulse_us))
                    wf.append(pigpio.pulse(0, step_mask, pulse_us))
                self.pi.wave_clear()
                self.pi.wave_add_generic(wf)
                wid = self.pi.wave_create()
                if wid < 0:
                    break
                self.pi.wave_send_once(wid)
                while self.pi.wave_tx_busy():
                    time.sleep(0.0005)
                self.pi.wave_delete(wid)
                done += remaining
            
            # Cleanup
            cb.cancel()
            self.pi.set_glitch_filter(endstop_pin, 0)
            
            if hit_flag[0]:
                print(f"[move] {axis} ENDSTOP HIT at ~{done} steps (pin {endstop_pin})")
            
            return True
        finally:
            self.is_moving = False


motors = Motors()
