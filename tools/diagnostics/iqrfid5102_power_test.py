#!/usr/bin/env python3
# iqrfid5102_power_test.py
# Тест настройки мощности IQRFID-5102 с ПРАВИЛЬНЫМ протоколом 0xA0
#
# ВАЖНО! Протокол IQRFID-5102 (и подобных китайских UHF ридеров):
# - Формат: [0xA0][LEN][ADR][CMD][DATA...][CHECKSUM]
# - Checksum: (~SUM + 1) & 0xFF (простая сумма, НЕ CRC-16!)
# - Baudrate: 115200 (НЕ 57600!)
#
# Запуск:
#   Windows: py tools/iqrfid5102_power_test.py COM2
#   RPi:     python3 tools/iqrfid5102_power_test.py /dev/ttyUSB0

import serial
import time
import sys

# Конфигурация
BAUDRATE = 115200  # ВАЖНО: 115200, не 57600!
TIMEOUT = 1.0
ADDRESS = 0x00

# Команды (из документации UHF RFID Serial Interface Protocol V2.37)
CMD_GET_FIRMWARE = 0x72
CMD_SET_WORK_ANTENNA = 0x74
CMD_GET_WORK_ANTENNA = 0x75
CMD_SET_OUTPUT_POWER = 0x76      # Установить мощность (сохранить во flash)
CMD_GET_OUTPUT_POWER = 0x77      # Получить текущую мощность
CMD_SET_TEMP_POWER = 0x66        # Установить мощность (без сохранения)
CMD_REAL_TIME_INVENTORY = 0x89  # Inventory в реальном времени
CMD_GET_TEMPERATURE = 0x7B


def checksum(data: bytes) -> int:
    """
    Checksum по документации: (~SUM + 1) & 0xFF
    Суммируем все байты кроме Head (0xA0) и самого checksum
    """
    s = sum(data) & 0xFF
    return ((~s) + 1) & 0xFF


def build_packet(cmd: int, data: bytes = b'') -> bytes:
    """
    Формат пакета: [0xA0][LEN][ADR][CMD][DATA...][CHECKSUM]
    LEN = количество байт после LEN (addr + cmd + data + checksum)
    """
    length = 1 + 1 + len(data) + 1  # addr + cmd + data + checksum
    packet_body = bytes([length, ADDRESS, cmd]) + data
    chk = checksum(packet_body)
    return bytes([0xA0]) + packet_body + bytes([chk])


def parse_response(data: bytes) -> dict:
    """Разбор ответа ридера"""
    if not data or len(data) < 5:
        return {'error': 'No response or too short'}
    
    if data[0] != 0xA0:
        return {'error': f'Invalid header: {hex(data[0])}'}
    
    length = data[1]
    addr = data[2]
    cmd = data[3]
    
    # Проверяем что есть данные
    if len(data) < length + 2:  # +2 для Head и Len
        return {'error': 'Incomplete response'}
    
    # Данные между cmd и checksum
    payload = data[4:4 + length - 3] if length > 3 else b''
    
    return {
        'cmd': cmd,
        'addr': addr,
        'payload': payload,
        'raw': data.hex(' ')
    }


def send_command(ser: serial.Serial, cmd: int, data: bytes = b'', debug: bool = True) -> dict:
    """Отправка команды и получение ответа"""
    packet = build_packet(cmd, data)
    
    if debug:
        print(f"  TX: {packet.hex(' ')}")
    
    ser.reset_input_buffer()
    ser.write(packet)
    time.sleep(0.15)
    
    response = ser.read(64)
    
    if debug:
        if response:
            print(f"  RX: {response.hex(' ')}")
        else:
            print(f"  RX: (нет ответа)")
    
    return parse_response(response)


def get_firmware_version(ser: serial.Serial) -> str:
    """Получить версию прошивки"""
    result = send_command(ser, CMD_GET_FIRMWARE)
    if 'payload' in result and len(result['payload']) >= 2:
        major = result['payload'][0]
        minor = result['payload'][1]
        return f"{major}.{minor}"
    return "unknown"


def get_power(ser: serial.Serial) -> int:
    """Получить текущую мощность"""
    print("\n--- Получение текущей мощности ---")
    result = send_command(ser, CMD_GET_OUTPUT_POWER)
    
    if 'payload' in result and len(result['payload']) >= 1:
        power = result['payload'][0]
        print(f"  ✓ Текущая мощность: {power} dBm")
        return power
    
    # Проверяем на ошибку
    if 'payload' in result and len(result['payload']) >= 1:
        error_code = result['payload'][0]
        print(f"  ✗ Ошибка: 0x{error_code:02X}")
    
    return -1


def set_power(ser: serial.Serial, power_dbm: int, save_to_flash: bool = False) -> bool:
    """
    Установить мощность передатчика
    
    Args:
        power_dbm: Мощность 0-33 dBm
        save_to_flash: True = сохранить во flash (0x76), False = временно (0x66)
    """
    # Ограничиваем диапазон
    power_dbm = max(0, min(33, power_dbm))
    
    cmd = CMD_SET_OUTPUT_POWER if save_to_flash else CMD_SET_TEMP_POWER
    cmd_name = "SET_OUTPUT_POWER (flash)" if save_to_flash else "SET_TEMP_POWER"
    
    print(f"\n--- Установка мощности: {power_dbm} dBm ({cmd_name}) ---")
    result = send_command(ser, cmd, bytes([power_dbm]))
    
    # Проверяем успех (0x10 = CommandSuccess)
    if 'payload' in result and len(result['payload']) >= 1:
        status = result['payload'][0]
        if status == 0x10:
            print(f"  ✓ Мощность установлена: {power_dbm} dBm")
            return True
        else:
            print(f"  ✗ Ошибка: 0x{status:02X}")
            # Расшифровка ошибок
            errors = {
                0x11: "command_fail",
                0x25: "set_output_power_error",
                0x48: "output_power_out_of_range",
            }
            if status in errors:
                print(f"     ({errors[status]})")
    
    return False


def inventory_test(ser: serial.Serial, repeat: int = 3) -> list:
    """Тест инвентаризации"""
    print(f"\n--- Inventory (repeat={repeat}) ---")
    
    tags = []
    result = send_command(ser, CMD_REAL_TIME_INVENTORY, bytes([repeat]))
    
    # Real-time inventory может вернуть несколько пакетов
    # Первые пакеты - данные меток, последний - статистика
    
    if 'payload' in result:
        payload = result['payload']
        # Если это пакет с меткой (cmd=0x89, есть FreqAnt + PC + EPC)
        if len(payload) >= 4:
            # Проверяем - это метка или статистика?
            # Статистика: AntID (1) + ReadRate (2) + TotalRead (4) = 7 байт
            # Метка: FreqAnt (1) + PC (2) + EPC (N) + RSSI (1)
            if result['cmd'] == 0x89:
                print(f"  Payload: {payload.hex(' ')}")
    
    return tags


def main():
    # Определяем порт
    if sys.platform == 'win32':
        port = "COM2"
    else:
        port = "/dev/ttyUSB0"
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    print("=" * 60)
    print("IQRFID-5102 Power Configuration Test")
    print("=" * 60)
    print(f"Порт: {port}")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Протокол: 0xA0 (UHF RFID Serial Interface V2.37)")
    print()
    
    try:
        ser = serial.Serial(port, BAUDRATE, timeout=TIMEOUT)
        time.sleep(0.2)
        print("✓ Порт открыт")
        
        # 1. Получаем версию прошивки
        print("\n--- Версия прошивки ---")
        fw = get_firmware_version(ser)
        print(f"  Firmware: {fw}")
        
        # 2. Получаем текущую мощность
        current_power = get_power(ser)
        
        # 3. Пробуем установить максимальную мощность (30 dBm)
        # Используем временную команду (0x66) чтобы не изнашивать flash
        if set_power(ser, 30, save_to_flash=False):
            print("  ✓ Мощность 30 dBm установлена!")
        else:
            print("  Пробуем альтернативное значение 26 dBm...")
            set_power(ser, 26, save_to_flash=False)
        
        # 4. Проверяем что установилось
        get_power(ser)
        
        # 5. Тест inventory
        print("\n--- Тест считывания метки (5 сек) ---")
        print("Поднеси метку к ридеру!")
        
        start = time.time()
        tags_found = set()
        
        while time.time() - start < 5:
            packet = build_packet(CMD_REAL_TIME_INVENTORY, bytes([0xFF]))  # 0xFF = fast mode
            ser.reset_input_buffer()
            ser.write(packet)
            time.sleep(0.1)
            
            # Читаем все доступные данные
            response = ser.read(256)
            
            if response and len(response) > 10:
                # Ищем пакеты с метками в ответе
                # Формат метки: A0 [len] [addr] 89 [FreqAnt] [PC 2bytes] [EPC Nbytes] [RSSI]
                i = 0
                while i < len(response):
                    if response[i] == 0xA0 and i + 1 < len(response):
                        pkt_len = response[i + 1]
                        if i + pkt_len + 2 <= len(response):
                            pkt = response[i:i + pkt_len + 2]
                            if len(pkt) > 4 and pkt[3] == 0x89:
                                # Это может быть метка
                                if pkt_len > 7:  # Минимальный размер для метки
                                    # PC (2 bytes) начинается с позиции 5
                                    # EPC идёт после PC
                                    epc_start = 7  # FreqAnt(1) + PC(2) = 3, + header(4)
                                    epc_end = pkt_len + 1  # Без RSSI
                                    if epc_end > epc_start:
                                        epc = pkt[epc_start:epc_end].hex().upper()
                                        if epc and epc not in tags_found:
                                            tags_found.add(epc)
                                            print(f"  [+] МЕТКА: {epc}")
                            i += pkt_len + 2
                        else:
                            i += 1
                    else:
                        i += 1
        
        print()
        print("=" * 60)
        if tags_found:
            print(f"✓ Найдено меток: {len(tags_found)}")
            for tag in tags_found:
                print(f"  EPC: {tag}")
        else:
            print("Меток не найдено")
        
        # Закрываем порт
        ser.close()
        
    except serial.SerialException as e:
        print(f"✗ Ошибка: {e}")
        print("\nПроверьте:")
        print("  1. Правильный порт (ls /dev/ttyUSB* или Device Manager)")
        print("  2. Порт не занят другой программой")
        print("  3. Права доступа (sudo или группа dialout)")
        sys.exit(1)


if __name__ == "__main__":
    main()
