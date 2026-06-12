#!/usr/bin/env python3
# iqrfid5102_power_bruteforce.py
# Перебор ВСЕХ возможных команд управления мощностью для IQRFID-5102
#
# Разные китайские UHF ридеры используют разные команды:
# - 0x76/0x77 - стандартные (не работают на нашем)
# - 0xB6/0xB7 - альтернативные (Electron, некоторые китайские)
# - 0x66 - временная мощность
# - 0xF0/0xF1 - параметры демодулятора (могут включать мощность)
# - 0x07/0x08 - частотный регион (иногда включает мощность)
#
# Запуск:
#   python3 tools/iqrfid5102_power_bruteforce.py /dev/ttyUSB0

import serial
import time
import sys

PORT = "/dev/ttyUSB0"
BAUDRATE = 57600
TIMEOUT = 0.3


def crc16_8408(data: bytes) -> bytes:
    """CRC-16 с полиномом 0x8408"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_cmd(cmd: int, data: bytes = b'') -> bytes:
    """Формат: [LEN][ADR][CMD][DATA...][CRC16]"""
    length = 1 + 1 + len(data) + 2
    packet = bytes([length, 0x00, cmd]) + data
    crc = crc16_8408(packet)
    return packet + crc


def send_and_receive(ser: serial.Serial, cmd: int, data: bytes = b'', name: str = "") -> bytes:
    """Отправка команды и получение ответа"""
    packet = build_cmd(cmd, data)
    
    print(f"\n{name} (cmd=0x{cmd:02X}):")
    print(f"  TX: {packet.hex(' ')}")
    
    ser.reset_input_buffer()
    ser.write(packet)
    time.sleep(0.15)
    
    response = ser.read(64)
    
    if response:
        print(f"  RX: {response.hex(' ')}")
        
        # Анализируем ответ
        if len(response) >= 4:
            resp_cmd = response[2]
            status = response[3]
            
            # Проверяем успех
            if resp_cmd == cmd:
                print(f"  ✓ Команда распознана! (echo cmd=0x{resp_cmd:02X})")
                if status == 0x10:
                    print(f"  ✓✓✓ УСПЕХ! (status=0x10)")
                    return response
                elif status <= 33:
                    print(f"  Возможно мощность: {status} dBm")
                    return response
            elif resp_cmd == 0x00:
                print(f"  ✗ Команда не поддерживается (cmd=0x00, error=0x{status:02X})")
            else:
                print(f"  ? Неожиданный ответ cmd=0x{resp_cmd:02X}")
    else:
        print(f"  RX: (нет ответа)")
    
    return response


def main():
    global PORT
    
    if len(sys.argv) > 1:
        PORT = sys.argv[1]
    
    print("=" * 60)
    print("IQRFID-5102 Power Command Bruteforce")
    print("=" * 60)
    print(f"Порт: {PORT}")
    print(f"Baudrate: {BAUDRATE}")
    print()
    print("Пробуем все известные команды управления мощностью...")
    
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
        time.sleep(0.2)
        print("✓ Порт открыт")
        
        # Сначала проверяем что ридер отвечает
        print("\n" + "=" * 40)
        print("Проверка связи (Inventory):")
        print("=" * 40)
        send_and_receive(ser, 0x01, b'', "Inventory")
        
        # Список команд для тестирования
        power_commands = [
            # (cmd, data, description)
            (0x77, b'', "Get Power (стандартная)"),
            (0xB7, b'', "Get Power (альтернативная)"),
            (0x08, b'', "Get Frequency Region"),
            (0xF1, b'', "Get Demodulator Params"),
            (0x72, b'', "Get Firmware Version"),
            (0x7B, b'', "Get Temperature"),
            (0x75, b'', "Get Work Antenna"),
            (0x6A, b'', "Get RF Link Profile"),
            (0x63, b'', "Get Antenna Detector"),
            (0x68, b'', "Get Reader Identifier"),
        ]
        
        print("\n" + "=" * 40)
        print("Тест GET команд:")
        print("=" * 40)
        
        working_get_cmd = None
        for cmd, data, name in power_commands:
            resp = send_and_receive(ser, cmd, data, name)
            if resp and len(resp) >= 4 and resp[2] == cmd:
                working_get_cmd = cmd
        
        # Теперь пробуем SET команды
        set_commands = [
            # (cmd, data, description)
            (0x76, bytes([30]), "Set Power 30dBm (стандартная 0x76)"),
            (0x66, bytes([30]), "Set Temp Power 30dBm (0x66)"),
            (0xB6, bytes([30]), "Set Power 30dBm (альтернативная 0xB6)"),
            (0xB6, bytes([0x00, 30]), "Set Power 30dBm (0xB6 с antenna ID)"),
            (0x76, bytes([0x1E]), "Set Power 30dBm (0x76, hex format)"),
            (0x76, bytes([26]), "Set Power 26dBm (пониженная)"),
            (0x76, bytes([20]), "Set Power 20dBm (минимальная)"),
            # Пробуем с разными форматами данных
            (0xB6, bytes([0x00, 0x1E]), "Set Power (0xB6 [ant, power])"),
            (0xB6, bytes([30, 30, 30, 30]), "Set Power all antennas (0xB6)"),
        ]
        
        print("\n" + "=" * 40)
        print("Тест SET команд мощности:")
        print("=" * 40)
        
        working_set_cmd = None
        for cmd, data, name in set_commands:
            resp = send_and_receive(ser, cmd, data, name)
            if resp and len(resp) >= 4:
                if resp[3] == 0x10:  # Success
                    working_set_cmd = (cmd, data)
                    print(f"\n  ✓✓✓ НАШЛИ РАБОЧУЮ КОМАНДУ! ✓✓✓")
                    break
        
        # Пробуем ещё экзотические команды
        exotic_commands = [
            (0x22, bytes([30]), "Set Power (0x22)"),
            (0x07, bytes([0x03, 0x00, 0x06]), "Set Freq Region CHN"),
            (0xF0, bytes([0x01, 30]), "Set Demod Param (0xF0)"),
            (0x09, bytes([30]), "Unknown 0x09"),
            (0x0A, bytes([30]), "Unknown 0x0A"),
            (0x0B, bytes([30]), "Unknown 0x0B"),
            (0xA0, bytes([30]), "Unknown 0xA0"),
            (0xA1, bytes([30]), "Unknown 0xA1"),
        ]
        
        if not working_set_cmd:
            print("\n" + "=" * 40)
            print("Тест экзотических команд:")
            print("=" * 40)
            
            for cmd, data, name in exotic_commands:
                resp = send_and_receive(ser, cmd, data, name)
                if resp and len(resp) >= 4:
                    if resp[3] == 0x10:
                        working_set_cmd = (cmd, data)
                        print(f"\n  ✓✓✓ НАШЛИ РАБОЧУЮ КОМАНДУ! ✓✓✓")
                        break
        
        ser.close()
        
        # Итоги
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ:")
        print("=" * 60)
        
        if working_set_cmd:
            cmd, data = working_set_cmd
            print(f"✓ Найдена рабочая команда SET POWER:")
            print(f"  CMD: 0x{cmd:02X}")
            print(f"  DATA: {data.hex(' ')}")
            print()
            print("Теперь можно обновить драйвер!")
        else:
            print("✗ Ни одна команда SET POWER не сработала")
            print()
            print("Вероятные причины:")
            print("  1. Мощность зафиксирована аппаратно в модуле Bee02")
            print("  2. Нужна специфическая последовательность команд")
            print("  3. Требуется другой формат данных")
            print()
            print("Рекомендации:")
            print("  - Искать документацию конкретно на 'UHF Reader Bee02 V1.6'")
            print("  - Использовать RRU9816 для карт (у него 20см дальность)")
            print("  - Рассмотреть замену на ридер с внешней антенной")
        
    except serial.SerialException as e:
        print(f"✗ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
