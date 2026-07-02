"""
IQRFID-5102 UHF Book Reader (Serial)

Протокол:
- Frame: [Len][Addr][Cmd][Data...][CRC16-L][CRC16-H]
- Inventory CMD: 0x01
- Response: [Len][Addr][ReCode][AntID][NumTag][TagData...][CRC16]
- TagData: [Count][EPC_Len][PC(2)][EPC(12)][RSSI]
"""
import asyncio
import time
from typing import Optional, List, Callable, Dict
from ..config import MOCK_MODE, RFID


CMD_INVENTORY = 0x01
CMD_READ_DATA = 0x02
CMD_WRITE_DATA = 0x03
CMD_SET_POWER = 0xB6

RESPONSE_OK = 0x01
RESPONSE_NO_TAG = 0xFB
RESPONSE_ERROR = 0xFC


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE для IQRFID протокола"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc


def verify_crc(data: bytes) -> bool:
    """Проверка CRC ответа"""
    if len(data) < 3:
        return False
    payload = data[:-2]
    received_crc = data[-2] | (data[-1] << 8)
    return crc16(payload) == received_crc


class BookReader:
    def __init__(self):
        self.mock_mode = MOCK_MODE
        self.serial = None
        self.port = RFID['book_reader']
        self.baudrate = RFID['book_baudrate']
        self.address = 0x00
        self.on_tag_read: Optional[Callable] = None
        self._running = False
        self._last_tags: List[str] = []
        # Метки, видимые ПРЯМО СЕЙЧАС (обновляет цикл start_polling каждую итерацию).
        # Читается из wait_for_user для детекта «книгу забрали» — без доступа к
        # serial-порту, поэтому гонок с циклом опроса нет.
        self.current_tags: set = set()
    
    async def connect(self) -> bool:
        if self.mock_mode:
            return True
        
        try:
            import serial
            self.serial = serial.Serial(
                self.port,
                self.baudrate,
                timeout=0.5
            )
            await asyncio.sleep(0.1)
            self.serial.reset_input_buffer()
            return True
        except ImportError:
            print("pyserial not installed, switching to mock mode")
            self.mock_mode = True
            return True
        except Exception as e:
            print(f"Book reader error: {e}")
            return False
    
    def disconnect(self):
        if self.serial:
            self.serial.close()
            self.serial = None
    
    def _build_command(self, cmd: int, data: bytes = b'') -> bytes:
        """Построение команды с CRC"""
        frame = bytes([len(data) + 4, self.address, cmd]) + data
        crc = crc16(frame)
        return frame + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    
    async def inventory(self) -> List[str]:
        """Сканирование меток в поле антенны"""
        if self.mock_mode:
            return self._last_tags.copy()
        
        if not self.serial:
            return []
        
        try:
            cmd = self._build_command(CMD_INVENTORY)

            def _io():
                # блокирующий serial (HIGH-8): write + пауза + read целиком в отдельном
                # потоке, чтобы не морозить event-loop aiohttp на одноядерном RPi3
                self.serial.reset_input_buffer()
                self.serial.write(cmd)
                time.sleep(0.15)
                return self.serial.read(512)

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, _io)
            tags = self._parse_inventory(response)
            self._last_tags = tags
            return tags
        except OSError:
            # аппаратный отвал USB-порта (SerialException ⊂ OSError) — пробросить
            # наверх, чтобы start_polling переоткрыл порт с backoff, а не спамил на SD
            raise
        except Exception as e:
            print(f"Inventory parse error: {e}")
            return []
    
    def _parse_inventory(self, data: bytes) -> List[str]:
        """Парсинг ответа инвентаризации"""
        tags = []
        self._last_inventory_meta = {
            'antenna_id': 0,
            'num_tags': 0,
            'response_code': 0,
            'tags_detail': [],
        }
        
        if len(data) < 7:
            return tags
        
        if not verify_crc(data):
            print("CRC error in inventory response")
            return tags
        
        frame_len = data[0]
        addr = data[1]
        recode = data[2]
        self._last_inventory_meta['response_code'] = recode
        
        if recode == RESPONSE_NO_TAG:
            return tags
        
        if recode != RESPONSE_OK:
            print(f"Inventory error code: 0x{recode:02X}")
            return tags
        
        if len(data) < 6:
            return tags
        
        ant_id = data[3]
        num_tags = data[4]
        self._last_inventory_meta['antenna_id'] = ant_id
        self._last_inventory_meta['num_tags'] = num_tags
        
        payload_end = len(data) - 2
        offset = 5
        
        for tag_idx in range(num_tags):
            if offset >= payload_end:
                break
            
            read_count = data[offset]
            offset += 1
            
            if offset >= payload_end:
                break
            
            epc_len = data[offset]
            offset += 1
            
            total_tag_data = epc_len + 1
            if offset + total_tag_data > payload_end:
                break
            
            pc = data[offset:offset + 2]
            offset += 2
            
            epc_data_len = epc_len - 2
            epc_bytes = data[offset:offset + epc_data_len]
            offset += epc_data_len
            
            rssi = data[offset]
            offset += 1
            
            epc = ''.join(f'{b:02X}' for b in epc_bytes)
            
            tag_detail = {
                'epc': epc,
                'pc': ''.join(f'{b:02X}' for b in pc),
                'rssi': rssi,
                'rssi_dbm': rssi - 129 if rssi > 0 else None,
                'read_count': read_count,
            }
            self._last_inventory_meta['tags_detail'].append(tag_detail)
            
            if epc and epc not in tags:
                tags.append(epc)
        
        return tags
    
    def get_last_inventory_meta(self) -> Dict:
        """Получение метаданных последней инвентаризации"""
        return getattr(self, '_last_inventory_meta', {})
    
    async def read_epc(self) -> Optional[str]:
        """Чтение одной метки (первой найденной)"""
        tags = await self.inventory()
        return tags[0] if tags else None
    
    async def set_power(self, dbm: int) -> bool:
        """Установка мощности антенны (5-30 dBm)"""
        if self.mock_mode:
            return True
        
        if not self.serial:
            return False
        
        dbm = max(5, min(30, dbm))
        
        try:
            cmd = self._build_command(CMD_SET_POWER, bytes([dbm]))
            self.serial.write(cmd)
            await asyncio.sleep(0.05)
            response = self.serial.read(16)
            return len(response) > 2 and response[2] == RESPONSE_OK
        except Exception as e:
            print(f"Set power error: {e}")
            return False
    
    async def start_polling(self, interval: float = 1.0):
        """Циклическое сканирование меток. Устойчиво к отвалу USB-порта: при аппаратной
        ошибке порт закрывается, логируется ОДИН раз, и переоткрывается с экспоненциальным
        backoff (не спамим ошибку на SD каждый цикл — RPi3 не тянет питание UHF-ридеров)."""
        self._running = True
        seen_tags = set()
        err_state = False
        backoff = max(interval, 1.0)

        while self._running:
            try:
                tags = await self.inventory()
                if err_state:
                    print("[book_reader] USB-порт восстановлен")
                    err_state = False
                    backoff = max(interval, 1.0)

                for tag in tags:
                    if tag not in seen_tags:
                        seen_tags.add(tag)
                        if self.on_tag_read:
                            self.on_tag_read({'epc': tag})

                current_set = set(tags)
                self.current_tags = current_set
                seen_tags = seen_tags & current_set

                await asyncio.sleep(interval)
            except OSError as e:
                # аппаратный отвал порта: лог РАЗ, закрыть, backoff, переоткрыть
                if not err_state:
                    print(f"[book_reader] USB-порт отвалился ({e}) — reconnect с backoff, логи заглушены")
                    err_state = True
                try:
                    self.disconnect()
                except Exception:
                    pass
                self.current_tags = set()
                await asyncio.sleep(min(backoff, 30.0))
                backoff = min(backoff * 2, 30.0)
                try:
                    await self.connect()
                except Exception:
                    pass
            except Exception as e:
                # прочее (парсинг и т.п.) — не роняем цикл, короткая пауза
                if not err_state:
                    print(f"[book_reader] ошибка опроса: {e}")
                await asyncio.sleep(interval)

    def stop_polling(self):
        self._running = False
        self.current_tags = set()

    def is_present(self, epc: str) -> bool:
        """Видна ли метка прямо сейчас (по последнему циклу опроса)."""
        return epc in self.current_tags
    
    def simulate_tag(self, epc: str):
        """Симуляция чтения метки (для тестов)"""
        self._last_tags = [epc]
        if self.on_tag_read:
            self.on_tag_read({'epc': epc})
    
    def simulate_tags(self, epcs: List[str]):
        """Симуляция нескольких меток"""
        self._last_tags = epcs.copy()
        for epc in epcs:
            if self.on_tag_read:
                self.on_tag_read({'epc': epc})
    
    def get_status(self) -> Dict:
        """Статус ридера"""
        return {
            'connected': self.serial is not None or self.mock_mode,
            'mock_mode': self.mock_mode,
            'port': self.port,
            'last_tags_count': len(self._last_tags),
        }


book_reader = BookReader()
