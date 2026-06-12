#!/usr/bin/env python3
# iqrfid5102_protocol_detector.py
# Определение протокола IQRFID-5102 и настройка мощности
#
# Китайские UHF ридеры используют разные протоколы:
# 1. Протокол 0xA0: [0xA0][LEN][ADR][CMD][DATA][CHECKSUM] - 115200 baud
# 2. Простой протокол: [LEN][ADR][CMD][DATA][CRC16] - 57600 baud  
# 3. Сверх-простой: [LEN][ADR][CMD][DATA][CHECKSUM] - 57600/115200 baud
#
# Этот скрипт попробует все варианты!
#
# Запуск:
#   Windows: py tools/iqrfid5102_protocol_detector.py COM2
#   RPi:     python3 tools/iqrfid5102_protocol_detector.py /dev/ttyUSB0

import serial
import time
import sys


def crc16_8408(data: bytes) -> bytes:
    """CRC-16 с полиномом 0x8408 (CCITT reversed, LSB first)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def simple_checksum(data: bytes) -> int:
    """Простой checksum: (~SUM + 1) & 0xFF"""
    s = sum(data) & 0xFF
    return ((~s) + 1) & 0xFF


def xor_checksum(data: bytes) -> int:
    """XOR checksum"""
    result = 0
    for b in data:
        result ^= b
    return result


class Protocol:
    """Базовый класс протокола"""
    name = "Unknown"
    baudrate = 57600
    
    def build_inventory(self) -> bytes:
        raise NotImplementedError
    
    def build_get_power(self) -> bytes:
        raise NotImplementedError
    
    def build_set_power(self, power: int) -> bytes:
        raise NotImplementedError
    
    def parse_response(self, data: bytes) -> dict:
        return {'raw': data.hex(' ') if data else 'empty'}


class Protocol_0xA0(Protocol):
    """Протокол с заголовком 0xA0 и простым checksum"""
    name = "0xA0 Protocol (115200)"
    baudrate = 115200
    
    def _build(self, cmd: int, data: bytes = b'') -> bytes:
        length = 1 + 1 + len(data) + 1  # addr + cmd + data + checksum
        body = bytes([length, 0x00, cmd]) + data
        chk = simple_checksum(body)
        return bytes([0xA0]) + body + bytes([chk])
    
    def build_inventory(self) -> bytes:
        return self._build(0x89, b'\x01')  # Real-time inventory
    
    def build_get_power(self) -> bytes:
        return self._build(0x77)
    
    def build_set_power(self, power: int) -> bytes:
        return self._build(0x66, bytes([power]))  # Temporary power
    
    def parse_response(self, data: bytes) -> dict:
        if not data or data[0] != 0xA0:
            return {'valid': False, 'raw': data.hex(' ') if data else 'empty'}
        return {'valid': True, 'raw': data.hex(' ')}


class Protocol_Simple_CRC16(Protocol):
    """Простой протокол с CRC-16 (текущий драйвер)"""
    name = "Simple + CRC16 (57600)"
    baudrate = 57600
    
    def _build(self, cmd: int, data: bytes = b'') -> bytes:
        length = 1 + 1 + len(data) + 2  # addr + cmd + data + crc
        packet = bytes([length, 0x00, cmd]) + data
        crc = crc16_8408(packet)
        return packet + crc
    
    def build_inventory(self) -> bytes:
        return self._build(0x01)
    
    def build_get_power(self) -> bytes:
        return self._build(0x77)
    
    def build_set_power(self, power: int) -> bytes:
        return self._build(0x76, bytes([power]))
    
    def parse_response(self, data: bytes) -> dict:
        if not data or len(data) < 5:
            return {'valid': False, 'raw': data.hex(' ') if data else 'empty'}
        # Проверяем что длина совпадает
        if data[0] == len(data) - 2:  # len не включает себя и первый байт
            return {'valid': True, 'raw': data.hex(' '), 'cmd': data[2], 'status': data[3]}
        return {'valid': False, 'raw': data.hex(' ')}


class Protocol_Simple_Checksum(Protocol):
    """Простой протокол с простым checksum"""
    name = "Simple + Checksum (57600)"
    baudrate = 57600
    
    def _build(self, cmd: int, data: bytes = b'') -> bytes:
        length = 1 + 1 + len(data) + 1  # addr + cmd + data + checksum
        packet = bytes([length, 0x00, cmd]) + data
        chk = simple_checksum(packet)
        return packet + bytes([chk])
    
    def build_inventory(self) -> bytes:
        return self._build(0x01)
    
    def build_get_power(self) -> bytes:
        return self._build(0x77)
    
    def build_set_power(self, power: int) -> bytes:
        return self._build(0x76, bytes([power]))


class Protocol_0xA0_115200_v2(Protocol):
    """Протокол 0xA0 с другими командами"""
    name = "0xA0 Protocol v2 (115200)"
    baudrate = 115200
    
    def _build(self, cmd: int, data: bytes = b'') -> bytes:
        length = 1 + 1 + len(data) + 1
        body = bytes([length, 0x00, cmd]) + data
        chk = simple_checksum(body)
        return bytes([0xA0]) + body + bytes([chk])
    
    def build_inventory(self) -> bytes:
        return self._build(0x80, b'\x01')  # Buffer inventory
    
    def build_get_power(self) -> bytes:
        return self._build(0x77)
    
    def build_set_power(self, power: int) -> bytes:
        return self._build(0x76, bytes([power]))


class Protocol_Both_Baudrates(Protocol):
    """Пробуем 115200 с простым протоколом"""
    name = "Simple + CRC16 (115200)"
    baudrate = 115200
    
    def _build(self, cmd: int, data: bytes = b'') -> bytes:
        length = 1 + 1 + len(data) + 2
        packet = bytes([length, 0x00, cmd]) + data
        crc = crc16_8408(packet)
        return packet + crc
    
    def build_inventory(self) -> bytes:
        return self._build(0x01)
    
    def build_get_power(self) -> bytes:
        return self._build(0x77)
    
    def build_set_power(self, power: int) -> bytes:
        return self._build(0x76, bytes([power]))


def test_protocol(port: str, protocol: Protocol) -> bool:
    """Тестируем протокол"""
    print(f"\n{'='*50}")
    print(f"Тест: {protocol.name}")
    print(f"Baudrate: {protocol.baudrate}")
    print(f"{'='*50}")
    
    try:
        ser = serial.Serial(port, protocol.baudrate, timeout=0.5)
        time.sleep(0.1)
        
        # Тест 1: Inventory
        cmd = protocol.build_inventory()
        print(f"\n1. Inventory:")
        print(f"   TX: {cmd.hex(' ')}")
        
        ser.reset_input_buffer()
        ser.write(cmd)
        time.sleep(0.15)
        response = ser.read(64)
        
        print(f"   RX: {response.hex(' ') if response else '(нет ответа)'}")
        
        # Анализируем ответ
        if response:
            # Проверяем признаки валидного ответа
            valid = False
            
            # Для протокола 0xA0
            if response[0] == 0xA0 and len(response) >= 5:
                print(f"   ✓ Ответ начинается с 0xA0 - похоже на протокол 0xA0!")
                valid = True
            
            # Для простого протокола - длина должна совпадать
            elif len(response) >= 5:
                expected_len = response[0]
                # Для CRC16: len включает addr+cmd+data+2(crc), т.е. len+2 = total
                if expected_len + 2 == len(response) or expected_len == len(response) - 1:
                    print(f"   ✓ Длина пакета корректна!")
                    valid = True
                    
                    # Проверяем статус (обычно байт 3)
                    if len(response) > 3:
                        status = response[3]
                        if status == 0xFB:
                            print(f"   ✓ Status 0xFB = No tags (это нормально)")
                        elif status == 0x01:
                            print(f"   ✓ Status 0x01 = Tag found!")
                        elif status == 0x10:
                            print(f"   ✓ Status 0x10 = Command success")
            
            if valid:
                # Пробуем получить мощность
                print(f"\n2. Get Power:")
                cmd = protocol.build_get_power()
                print(f"   TX: {cmd.hex(' ')}")
                
                ser.reset_input_buffer()
                ser.write(cmd)
                time.sleep(0.15)
                response = ser.read(64)
                
                print(f"   RX: {response.hex(' ') if response else '(нет ответа)'}")
                
                if response and len(response) >= 5:
                    # Пробуем извлечь мощность
                    # Для протокола 0xA0: [A0][len][addr][cmd][power][chk]
                    # Для простого: [len][addr][cmd][power][crc16]
                    if response[0] == 0xA0 and len(response) >= 5:
                        power = response[4] if len(response) > 4 else -1
                        print(f"   Возможная мощность: {power} dBm")
                    elif len(response) >= 5:
                        # Простой протокол: data начинается с байта 3
                        power = response[3] if response[3] <= 33 else response[4] if len(response) > 4 else -1
                        print(f"   Возможная мощность: {power} dBm")
                
                # Пробуем установить мощность
                print(f"\n3. Set Power (30 dBm):")
                cmd = protocol.build_set_power(30)
                print(f"   TX: {cmd.hex(' ')}")
                
                ser.reset_input_buffer()
                ser.write(cmd)
                time.sleep(0.15)
                response = ser.read(64)
                
                print(f"   RX: {response.hex(' ') if response else '(нет ответа)'}")
                
                if response:
                    # Проверяем успех
                    if 0x10 in response:  # CommandSuccess
                        print(f"   ✓✓✓ УСПЕХ! Мощность установлена!")
                        ser.close()
                        return True
                    elif 0xFF in response or 0x11 in response:
                        print(f"   ✗ Команда не поддерживается или ошибка")
        
        ser.close()
        
    except serial.SerialException as e:
        print(f"   ✗ Ошибка: {e}")
    
    return False


def main():
    if sys.platform == 'win32':
        port = "COM2"
    else:
        port = "/dev/ttyUSB0"
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    print("=" * 60)
    print("IQRFID-5102 Protocol Detector & Power Configuration")
    print("=" * 60)
    print(f"Порт: {port}")
    print()
    print("Этот скрипт попробует разные протоколы и найдёт рабочий")
    print("для настройки мощности вашего ридера.")
    
    # Список протоколов для тестирования
    protocols = [
        Protocol_Simple_CRC16(),       # Текущий драйвер (57600)
        Protocol_Both_Baudrates(),     # CRC16 но 115200
        Protocol_0xA0(),               # Стандартный 0xA0 (115200)
        Protocol_0xA0_115200_v2(),     # 0xA0 с другими командами
        Protocol_Simple_Checksum(),    # Простой checksum (57600)
    ]
    
    working_protocol = None
    
    for proto in protocols:
        if test_protocol(port, proto):
            working_protocol = proto
            break
    
    print("\n" + "=" * 60)
    if working_protocol:
        print(f"✓✓✓ НАЙДЕН РАБОЧИЙ ПРОТОКОЛ: {working_protocol.name}")
        print(f"    Baudrate: {working_protocol.baudrate}")
        print()
        print("Теперь можно обновить драйвер с правильными настройками!")
    else:
        print("✗ Ни один протокол не сработал для установки мощности")
        print()
        print("Возможные причины:")
        print("  1. IQRFID-5102 имеет фиксированную мощность (аппаратно)")
        print("  2. Нужен другой протокол или команды")
        print("  3. Проблема с подключением")
        print()
        print("Рекомендация: посмотреть логи выше - какой протокол")
        print("даёт валидные ответы на Inventory, и искать документацию")
        print("на конкретную модель ридера.")


if __name__ == "__main__":
    main()
