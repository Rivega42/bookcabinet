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
        self.position_trusted = True   # False после таймаута движения → требуется хоминг (Волна 2)
        self.mock_mode = MOCK_MODE
        self.pi = None
        # Центр лотка в шагах: измеряется home_tray_with_sensor при калибровке.
        # Используется перехватом (cross_handoff) как парковочная позиция —
        # живое значение точнее хардкода 11300 (см. docs/PEREHVAT.md).
        self.tray_center = None

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
    
    def _wait_tx(self, timeout_s: float) -> bool:
        """Ждать конца передачи волны с ДЕДЛАЙНОМ (железное правило: таймаут на движении).
        При переборе — wave_tx_stop и False, чтобы не висеть вечно на заклинившем моторе."""
        t0 = time.time()
        while self.pi.wave_tx_busy():
            if time.time() - t0 > timeout_s:
                try:
                    self.pi.wave_tx_stop()
                except Exception:
                    pass
                return False
            time.sleep(0.005)
        return True

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
            if not self._wait_tx((repeats * chunk_size) / max(1, frequency) * 2 + 1.0):
                self.pi.wave_delete(wave_id)
                return False   # таймаут движения — не врём об успехе

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
                if not self._wait_tx(remainder / max(1, frequency) * 2 + 0.5):
                    self.pi.wave_delete(wave_id)
                    return False
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
                    
                    if not self._wave_steps(step_pins, max_steps, MOTOR_SPEEDS["xy"]):
                        self.position_trusted = False   # позиция неизвестна → нужен хоминг
                        return False   # таймаут движения — позицию НЕ обновляем, успех НЕ рапортуем

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
                if not self._wave_steps([GPIO_PINS["TRAY_STEP"]], steps, MOTOR_SPEEDS["tray"]):
                    return False   # таймаут движения лотка — успех НЕ рапортуем

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
            self.tray_center = center   # запоминаем живой центр для перехвата (cross_handoff)
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
    
    def _tray_center_steps(self) -> int:
        """Центр лотка для перехвата. Приоритет: живая калибровка
        (self.tray_center) → полевой calibration.json (tray.center_steps) →
        константа cross_operations_v2 (11300)."""
        if self.tray_center:
            return int(self.tray_center)
        try:
            from tools import calibration as field_cal
            return int(field_cal._load()['tray']['center_steps'])
        except Exception:
            return 11300

    # ===== Низкоуровневые примитивы лотка для перехвата (порт cross_operations_v2) =====
    # Константы байт-в-байт из field-validated скрипта. НЕ менять без железа.
    _HF_FREQ = 12000          # TRAY_FREQ
    _HF_LOCK_DISTANCE = 12600 # ход перехвата = 16 см между замками (сверено по geometry.md)
    _HF_GRAB_PWM = 1200       # захват (НЕ servos.close_lock=1556!)
    _HF_RELEASE_PWM = 500     # отпускание
    _HF_BACKOFF = 1500
    _HF_SLOW = 1500
    _HF_TIMEOUT = 25.0        # страховка подвода к концевику (в поле таймаута нет)
    # Первый ход extract_* — ПОЛНОЕ втягивание полки на каретку (а не один LOCK_DISTANCE!).
    # Это и было причиной «полка наполовину»: cross_operations_v2 делал 1 перехват,
    # shelf_operations.py (field-validated) делает 2 перехвата с длинным первым ходом.
    _HF_EXTRACT_FRONT_FIRST = 16900  # extract_front шаг 3 (к BACK)
    _HF_EXTRACT_REAR_FIRST = 16800   # extract_rear шаг 3 (к FRONT) = REAR_HANDOFF_REAR_FROM_BACK
    # Кросс-рядный transfer (после extract_*). Выверено на железе 2026-06-27 (tray_panel).
    _HF_FTR_STEP6 = 12500            # front_to_rear T6 (12500→FRONT)
    _HF_RTF_S2 = 13100              # rear_to_front S2 (поле 12600 НЕ доезжало на 500 → 13100)
    _HF_RTF_S4 = 12700              # rear_to_front S4 (12700→FRONT)
    _HF_RTF_S6 = 12600             # rear_to_front S6 (12600→BACK)

    def _tray_setup_pins(self):
        import pigpio
        for p in ("TRAY_STEP", "TRAY_DIR", "TRAY_ENA_1", "TRAY_ENA_2"):
            self.pi.set_mode(GPIO_PINS[p], pigpio.OUTPUT)
        self.pi.write(GPIO_PINS["TRAY_ENA_1"], 1); self.pi.write(GPIO_PINS["TRAY_ENA_2"], 1)
        for s in ("SENSOR_TRAY_END", "SENSOR_TRAY_BEGIN"):
            self.pi.set_mode(GPIO_PINS[s], pigpio.INPUT)
            self.pi.set_pull_up_down(GPIO_PINS[s], pigpio.PUD_UP)
            self.pi.set_glitch_filter(GPIO_PINS[s], 1000)
        time.sleep(0.1)

    def _tray_make_wave(self, freq):
        import pigpio
        STEP = GPIO_PINS["TRAY_STEP"]; half = int(1000000 / freq) // 2
        self.pi.wave_clear()
        self.pi.wave_add_generic([pigpio.pulse(1 << STEP, 0, half),
                                  pigpio.pulse(0, 1 << STEP, half)])
        return self.pi.wave_create()

    def _tray_stable(self, sensor, n=5):
        for _ in range(n):
            if self.pi.read(sensor) == 0:
                return False
            time.sleep(0.0005)
        return True

    def _tray_move_steps(self, d, steps, freq):
        EN1 = GPIO_PINS["TRAY_ENA_1"]; EN2 = GPIO_PINS["TRAY_ENA_2"]; DIR = GPIO_PINS["TRAY_DIR"]
        w = self._tray_make_wave(freq)
        self.pi.write(EN1, 0); self.pi.write(EN2, 0)
        self.pi.write(DIR, d); time.sleep(0.01)
        self.pi.wave_send_repeat(w)
        time.sleep(steps / freq)
        self.pi.wave_tx_stop()
        self.pi.write(EN1, 1); self.pi.write(EN2, 1)
        self.pi.wave_delete(w)

    async def _tray_to_endstop(self, d, sensor):
        """FAST → backoff → SLOW подвод (как cross_operations_v2.tray_to_endstop),
        с таймаутом. False, если концевик не пойман."""
        EN1 = GPIO_PINS["TRAY_ENA_1"]; EN2 = GPIO_PINS["TRAY_ENA_2"]; DIR = GPIO_PINS["TRAY_DIR"]
        for phase_freq in (self._HF_FREQ, self._HF_SLOW):
            if phase_freq == self._HF_SLOW:
                self._tray_move_steps(1 - d, self._HF_BACKOFF, self._HF_FREQ)
                time.sleep(0.05)
            w = self._tray_make_wave(phase_freq)
            self.pi.write(EN1, 0); self.pi.write(EN2, 0)
            self.pi.write(DIR, d); time.sleep(0.01)
            self.pi.wave_send_repeat(w)
            t0 = time.time(); hit = False
            while time.time() - t0 < self._HF_TIMEOUT:
                if self._tray_stable(sensor):
                    hit = True; break
                await asyncio.sleep(0.002)
            self.pi.wave_tx_stop()
            self.pi.write(EN1, 1); self.pi.write(EN2, 1)
            self.pi.wave_delete(w)
            if not hit:
                return False
        return True

    def _tray_lock(self, pin, pwm, strong=False):
        for _ in range(3 if strong else 1):
            self.pi.set_servo_pulsewidth(pin, pwm)
            time.sleep(0.5)
        self.pi.set_servo_pulsewidth(pin, 0)

    async def _hf_progress(self, on_progress, step, total, msg):
        if on_progress:
            ev = on_progress({'step': step, 'total': total, 'message': msg,
                              'operation': 'HANDOFF'})
            if asyncio.iscoroutine(ev):
                await ev

    async def cross_grab_onto_platform(self, from_row: str, on_progress=None,
                                       step_base: int = 0, total: int = 7) -> bool:
        """Извлечь полку из стойки `from_row` ПОЛНОСТЬЮ на каретку — точный порт
        shelf_operations.py extract_front / extract_rear (field-validated, 2026-06-13).
        7 шагов, ДВА перехвата (первый ход 16900/16800 втягивает полку целиком).
        После: from_row=FRONT → держит ЗАДНИЙ замок; from_row=BACK → ПЕРЕДНИЙ."""
        FRONT = GPIO_PINS["SENSOR_TRAY_END"]; BACK = GPIO_PINS["SENSOR_TRAY_BEGIN"]
        L_FRONT = GPIO_PINS["LOCK_FRONT"]; L_REAR = GPIO_PINS["LOCK_REAR"]
        LD = self._HF_LOCK_DISTANCE
        if from_row == 'FRONT':
            # extract_front: endstop FRONT, grab FRONT, 16900→BACK, rel FRONT,
            #                12600→FRONT, grab REAR, 12600→BACK  (держит REAR)
            seq_sensor, seq_dir = FRONT, 0
            lock1, lock2 = L_FRONT, L_REAR
            first_move = self._HF_EXTRACT_FRONT_FIRST
            m3_dir, m5_dir, m7_dir = 1, 0, 1
        elif from_row == 'BACK':
            # extract_rear: endstop BACK, grab REAR, 16800→FRONT, rel REAR,
            #               12600→BACK, grab FRONT, 12600→FRONT  (держит FRONT)
            seq_sensor, seq_dir = BACK, 1
            lock1, lock2 = L_REAR, L_FRONT
            first_move = self._HF_EXTRACT_REAR_FIRST
            m3_dir, m5_dir, m7_dir = 0, 1, 0
        else:
            return False
        steps = ["Лоток к концевику стойки", "Захват полки 1-м замком",
                 f"Перехват 1: лоток {first_move}", "Отпуск 1-го замка",
                 "Перехват 2: лоток LOCK_DISTANCE", "Захват 2-м замком",
                 "Втягивание на каретку (LOCK_DISTANCE)"]
        if self.mock_mode or not self.pi:
            for i, m in enumerate(steps, 1):
                await self._hf_progress(on_progress, step_base + i, total, m); await asyncio.sleep(0.01)
            return True
        self._tray_setup_pins()
        try:
            await self._hf_progress(on_progress, step_base + 1, total, steps[0])
            if not await self._tray_to_endstop(seq_dir, seq_sensor):
                return False
            await self._hf_progress(on_progress, step_base + 2, total, steps[1])
            self._tray_lock(lock1, self._HF_GRAB_PWM)
            await self._hf_progress(on_progress, step_base + 3, total, steps[2])
            self._tray_move_steps(m3_dir, first_move, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 4, total, steps[3])
            self._tray_lock(lock1, self._HF_RELEASE_PWM)
            await self._hf_progress(on_progress, step_base + 5, total, steps[4])
            self._tray_move_steps(m5_dir, LD, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 6, total, steps[5])
            self._tray_lock(lock2, self._HF_GRAB_PWM)
            await self._hf_progress(on_progress, step_base + 7, total, steps[6])
            self._tray_move_steps(m7_dir, LD, self._HF_FREQ)
            return True
        except Exception:
            return False
        finally:
            self.pi.write(GPIO_PINS["TRAY_ENA_1"], 1); self.pi.write(GPIO_PINS["TRAY_ENA_2"], 1)

    async def cross_place_into_rack(self, to_row: str, on_progress=None,
                                    step_base: int = 7, total: int = 14) -> bool:
        """Уложить полку с каретки В стойку `to_row` — точный порт shelf_operations.py
        return_front / return_rear (field-validated). 7 шагов, перехват + укладка strong.
        Ожидает: to_row=FRONT → полку держит ЗАДНИЙ замок (после extract_front);
                  to_row=BACK  → ПЕРЕДНИЙ (после extract_rear)."""
        FRONT = GPIO_PINS["SENSOR_TRAY_END"]; BACK = GPIO_PINS["SENSOR_TRAY_BEGIN"]
        L_FRONT = GPIO_PINS["LOCK_FRONT"]; L_REAR = GPIO_PINS["LOCK_REAR"]
        LD = self._HF_LOCK_DISTANCE
        center = self._tray_center_steps()
        if to_row == 'FRONT':
            # return_front: 12600→FRONT, rel REAR, 12600→BACK, grab FRONT,
            #               endstop FRONT, rel FRONT strong, CENTER→BACK
            m1_dir, rel_lock, m3_dir = 0, L_REAR, 1
            grab_lock, end_sensor, end_dir, center_dir = L_FRONT, FRONT, 0, 1
        elif to_row == 'BACK':
            # return_rear: 12600→BACK, rel FRONT, 12600→FRONT, grab REAR,
            #              endstop BACK, rel REAR strong, CENTER→FRONT
            m1_dir, rel_lock, m3_dir = 1, L_FRONT, 0
            grab_lock, end_sensor, end_dir, center_dir = L_REAR, BACK, 1, 0
        else:
            return False
        steps = ["Лоток к концевику ряда", "Отпуск держащего замка",
                 "Перехват: лоток LOCK_DISTANCE", "Захват замком ряда",
                 "Лоток к концевику стойки", "Укладка: отпуск замка (strong)", "Лоток в CENTER"]
        if self.mock_mode or not self.pi:
            for i, m in enumerate(steps, 1):
                await self._hf_progress(on_progress, step_base + i, total, m); await asyncio.sleep(0.01)
            self.position["tray"] = 0
            return True
        self._tray_setup_pins()
        try:
            await self._hf_progress(on_progress, step_base + 1, total, steps[0])
            if not await self._tray_to_endstop(end_dir, end_sensor):  # ФИКС: было слепое tray_move → проскок концевика
                return False
            await self._hf_progress(on_progress, step_base + 2, total, steps[1])
            self._tray_lock(rel_lock, self._HF_RELEASE_PWM)
            await self._hf_progress(on_progress, step_base + 3, total, steps[2])
            self._tray_move_steps(m3_dir, LD, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 4, total, steps[3])
            self._tray_lock(grab_lock, self._HF_GRAB_PWM)
            await self._hf_progress(on_progress, step_base + 5, total, steps[4])
            if not await self._tray_to_endstop(end_dir, end_sensor):
                return False
            await self._hf_progress(on_progress, step_base + 6, total, steps[5])
            self._tray_lock(grab_lock, self._HF_RELEASE_PWM, strong=True)
            await self._hf_progress(on_progress, step_base + 7, total, steps[6])
            self._tray_move_steps(center_dir, center, self._HF_FREQ)
            self.position["tray"] = 0
            return True
        except Exception:
            return False
        finally:
            self.pi.write(GPIO_PINS["TRAY_ENA_1"], 1); self.pi.write(GPIO_PINS["TRAY_ENA_2"], 1)
            try:
                self.pi.set_servo_pulsewidth(L_FRONT, 0); self.pi.set_servo_pulsewidth(L_REAR, 0)
                self.pi.wave_clear()
            except Exception:
                pass

    async def _transfer_to_rear(self, on_progress=None, step_base: int = 7, total: int = 17) -> bool:
        """T1–T10: переложить полку (на каретке, держит ЗАДНИЙ замок после extract_front)
        в ЗАДНИЙ ряд. Порт shelf_operations.py front_to_rear — подтверждён на железе 2026-06-27."""
        L_FRONT = GPIO_PINS["LOCK_FRONT"]; L_REAR = GPIO_PINS["LOCK_REAR"]
        BACK = GPIO_PINS["SENSOR_TRAY_BEGIN"]
        LD = self._HF_LOCK_DISTANCE; center = self._tray_center_steps()
        steps = ["Отпуск заднего", "Лоток LOCK_DISTANCE→FRONT", "Захват переднего",
                 "Лоток LOCK_DISTANCE→BACK", "Отпуск переднего", "Лоток 12500→FRONT",
                 "Захват заднего", "Лоток к BACK концевику", "Укладка в задний (strong)",
                 "Лоток в CENTER"]
        if self.mock_mode or not self.pi:
            for i, m in enumerate(steps, 1):
                await self._hf_progress(on_progress, step_base + i, total, m); await asyncio.sleep(0.01)
            self.position["tray"] = 0
            return True
        self._tray_setup_pins()
        try:
            await self._hf_progress(on_progress, step_base + 1, total, steps[0]); self._tray_lock(L_REAR, self._HF_RELEASE_PWM)
            await self._hf_progress(on_progress, step_base + 2, total, steps[1]); self._tray_move_steps(0, LD, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 3, total, steps[2]); self._tray_lock(L_FRONT, self._HF_GRAB_PWM)
            await self._hf_progress(on_progress, step_base + 4, total, steps[3]); self._tray_move_steps(1, LD, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 5, total, steps[4]); self._tray_lock(L_FRONT, self._HF_RELEASE_PWM)
            await self._hf_progress(on_progress, step_base + 6, total, steps[5]); self._tray_move_steps(0, self._HF_FTR_STEP6, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 7, total, steps[6]); self._tray_lock(L_REAR, self._HF_GRAB_PWM)
            await self._hf_progress(on_progress, step_base + 8, total, steps[7])
            if not await self._tray_to_endstop(1, BACK):
                return False
            await self._hf_progress(on_progress, step_base + 9, total, steps[8]); self._tray_lock(L_REAR, self._HF_RELEASE_PWM, strong=True)
            await self._hf_progress(on_progress, step_base + 10, total, steps[9]); self._tray_move_steps(0, center, self._HF_FREQ)
            self.position["tray"] = 0
            return True
        except Exception:
            return False
        finally:
            self.pi.write(GPIO_PINS["TRAY_ENA_1"], 1); self.pi.write(GPIO_PINS["TRAY_ENA_2"], 1)
            try:
                self.pi.set_servo_pulsewidth(L_FRONT, 0); self.pi.set_servo_pulsewidth(L_REAR, 0); self.pi.wave_clear()
            except Exception:
                pass

    async def _transfer_to_front(self, on_progress=None, step_base: int = 7, total: int = 17) -> bool:
        """S1–S10: переложить полку (на каретке, держит ПЕРЕДНИЙ замок после extract_rear)
        в ПЕРЕДНИЙ ряд. Порт shelf_operations.py rear_to_front; S2=13100 откалибровано
        на железе 2026-06-27 (поле 12600 не доезжало); хвост S9–S10 выверен на железе."""
        L_FRONT = GPIO_PINS["LOCK_FRONT"]; L_REAR = GPIO_PINS["LOCK_REAR"]
        FRONT = GPIO_PINS["SENSOR_TRAY_END"]
        LD = self._HF_LOCK_DISTANCE; center = self._tray_center_steps()
        steps = ["Отпуск переднего", f"Лоток {self._HF_RTF_S2}→BACK", "Захват заднего",
                 "Лоток 12700→FRONT", "Отпуск заднего", "Лоток 12600→BACK", "Захват переднего",
                 "Лоток к FRONT концевику", "Укладка в передний (strong)", "Лоток в CENTER"]
        if self.mock_mode or not self.pi:
            for i, m in enumerate(steps, 1):
                await self._hf_progress(on_progress, step_base + i, total, m); await asyncio.sleep(0.01)
            self.position["tray"] = 0
            return True
        self._tray_setup_pins()
        try:
            await self._hf_progress(on_progress, step_base + 1, total, steps[0]); self._tray_lock(L_FRONT, self._HF_RELEASE_PWM)
            await self._hf_progress(on_progress, step_base + 2, total, steps[1]); self._tray_move_steps(1, self._HF_RTF_S2, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 3, total, steps[2]); self._tray_lock(L_REAR, self._HF_GRAB_PWM)
            await self._hf_progress(on_progress, step_base + 4, total, steps[3]); self._tray_move_steps(0, self._HF_RTF_S4, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 5, total, steps[4]); self._tray_lock(L_REAR, self._HF_RELEASE_PWM)
            await self._hf_progress(on_progress, step_base + 6, total, steps[5]); self._tray_move_steps(1, self._HF_RTF_S6, self._HF_FREQ)
            await self._hf_progress(on_progress, step_base + 7, total, steps[6]); self._tray_lock(L_FRONT, self._HF_GRAB_PWM)
            await self._hf_progress(on_progress, step_base + 8, total, steps[7])
            if not await self._tray_to_endstop(0, FRONT):
                return False
            await self._hf_progress(on_progress, step_base + 9, total, steps[8]); self._tray_lock(L_FRONT, self._HF_RELEASE_PWM, strong=True)
            await self._hf_progress(on_progress, step_base + 10, total, steps[9]); self._tray_move_steps(1, center, self._HF_FREQ)
            self.position["tray"] = 0
            return True
        except Exception:
            return False
        finally:
            self.pi.write(GPIO_PINS["TRAY_ENA_1"], 1); self.pi.write(GPIO_PINS["TRAY_ENA_2"], 1)
            try:
                self.pi.set_servo_pulsewidth(L_FRONT, 0); self.pi.set_servo_pulsewidth(L_REAR, 0); self.pi.wave_clear()
            except Exception:
                pass

    async def cross_handoff(self, direction: str, on_progress=None) -> bool:
        """
        Кросс-рядный перенос полки между СТОЙКАМИ одной колонки.
        = extract_* (полный захват на каретку) + transfer_* (перекладка в др. ряд).
        Порт shelf_operations.py front_to_rear / rear_to_front, ВЫВЕРЕНО НА ЖЕЛЕЗЕ 2026-06-27
        (tray_panel): front_to_rear как поле; rear_to_front с откалиброванным S2=13100. 17 шагов.

        direction:
          'front_to_rear' — из передней стойки в заднюю,
          'rear_to_front' — из задней в переднюю.
        """
        if direction == 'front_to_rear':
            if not await self.cross_grab_onto_platform('FRONT', on_progress, step_base=0, total=17):
                return False
            return await self._transfer_to_rear(on_progress, step_base=7, total=17)
        elif direction == 'rear_to_front':
            if not await self.cross_grab_onto_platform('BACK', on_progress, step_base=0, total=17):
                return False
            return await self._transfer_to_front(on_progress, step_base=7, total=17)
        return False

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
