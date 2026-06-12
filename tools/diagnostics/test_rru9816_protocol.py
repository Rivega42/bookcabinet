# test_rru9816_protocol.py
# Тест: пробуем разные варианты общения с RRU9816
#
# Запуск: py test_rru9816_protocol.py
# Требуется: py -m pip install pyserial

import serial
import time

PORT = "COM16"
BAUDRATES = [57600, 115200, 9600, 38400]

def checksum(data):
    """Китайский UHF checksum: (~SUM + 1) & 0xFF"""
    return (~sum(data) + 1) & 0xFF

def build_cmd_a0(addr, cmd, data=b''):
    """Протокол 0xA0"""
    length = len(data) + 3
    packet = bytes([0xA0, length, addr, cmd]) + data
    packet += bytes([checksum(packet[1:])])
    return packet

def build_cmd_bb(cmd, data=b''):
    """Альтернативный протокол 0xBB (некоторые ридеры)"""
    length = len(data) + 1
    packet = bytes([0xBB, 0x00, cmd, length]) + data
    crc = sum(packet[1:]) & 0xFF
    packet += bytes([crc, 0x7E])
    return packet

# Разные команды для тестирования
COMMANDS = [
    ("0xA0 Inventory", build_cmd_a0(0x00, 0x01)),
    ("0xA0 GetVersion", build_cmd_a0(0x00, 0x03)),
    ("0xA0 Reset", build_cmd_a0(0x00, 0x70)),
    ("0xBB Inventory", build_cmd_bb(0x22)),
    ("0xBB GetVersion", build_cmd_bb(0x03)),
    ("Raw: просто слушаем", None),
]

print(f"=== Тестирование RRU9816 на {PORT} ===\n")

for baud in BAUDRATES:
    print(f"\n--- Baudrate: {baud} ---")
    try:
        ser = serial.Serial(PORT, baud, timeout=1)
        time.sleep(0.3)  # Дать время на инициализацию
        
        # Сначала просто послушаем - может ридер сам что-то шлёт
        ser.reset_input_buffer()
        time.sleep(0.5)
        initial = ser.read(64)
        if initial:
            print(f"  [!] Ридер сам прислал: {initial.hex(' ')}")
        
        for name, cmd in COMMANDS:
            if cmd is None:
                continue
            ser.reset_input_buffer()
            ser.write(cmd)
            time.sleep(0.2)
            response = ser.read(64)
            status = response.hex(' ') if response else "нет ответа"
            print(f"  {name}: {cmd.hex(' ')} -> {status}")
            
            if response:
                print(f"  [+] ЕСТЬ ОТВЕТ! Baudrate={baud}")
                
        ser.close()
    except serial.SerialException as e:
        print(f"  Ошибка: {e}")

print("\n=== Тест завершён ===")
