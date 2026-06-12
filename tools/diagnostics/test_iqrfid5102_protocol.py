# test_iqrfid5102_protocol.py
# Тест IQRFID-5102 с правильным протоколом
#
# Протокол: [LEN][ADR][CMD][DATA...][CRC_LOW][CRC_HIGH]
# CRC-16: polynomial 0x8408, init 0xFFFF
# Baudrate: 57600
#
# Запуск: py tools/test_iqrfid5102_protocol.py COM2

import serial
import time
import sys

PORT = "COM2"
BAUDRATE = 57600

def crc16_8408(data):
    """CRC-16 с полиномом 0x8408 (CRC-CCITT reversed)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    # LSB first
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

def build_cmd(addr, cmd, data=b''):
    """
    Формат: [LEN][ADR][CMD][DATA...][CRC_LOW][CRC_HIGH]
    LEN = длина после LEN (addr + cmd + data + 2 байта CRC)
    """
    length = 1 + 1 + len(data) + 2  # addr + cmd + data + crc
    packet = bytes([length, addr, cmd]) + data
    crc = crc16_8408(packet)
    packet += crc
    return packet

def parse_response(data):
    """Разбор ответа"""
    if len(data) < 5:
        return None
    
    length = data[0]
    addr = data[1]
    cmd = data[2]
    
    if cmd == 0x01:  # Inventory response
        if len(data) >= 4:
            status = data[3]
            if status == 0xFB:
                return {'cmd': 'inventory', 'status': 'no_tags'}
            elif status == 0x01 and len(data) > 6:
                count = data[4] if len(data) > 4 else 0
                epc_len = data[5] if len(data) > 5 else 0
                if len(data) >= 6 + epc_len:
                    epc = data[6:6+epc_len].hex().upper()
                    return {'cmd': 'inventory', 'status': 'tag_found', 'count': count, 'epc': epc}
    
    return {'cmd': hex(cmd), 'raw': data.hex(' ')}

def main():
    global PORT
    
    if len(sys.argv) > 1:
        PORT = sys.argv[1]
    
    print(f"=== Тест IQRFID-5102 на {PORT} ===")
    print(f"Baudrate: {BAUDRATE}")
    print(f"Протокол: [LEN][ADR][CMD][DATA][CRC16]")
    print(f"CRC-16: poly=0x8408, init=0xFFFF")
    print()
    
    # Команда Inventory: 04 00 01 DB 4B
    inventory_cmd = build_cmd(0x00, 0x01)
    print(f"Inventory команда: {inventory_cmd.hex(' ')}")
    print(f"Ожидаемая:         04 00 01 db 4b")
    print()
    
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        time.sleep(0.2)
        
        print("Подключено! Сканирование меток (5 сек)...")
        print("Поднеси метку к ридеру!")
        print()
        
        start = time.time()
        tags_found = set()
        
        while time.time() - start < 5:
            ser.reset_input_buffer()
            ser.write(inventory_cmd)
            time.sleep(0.1)
            
            response = ser.read(64)
            if response:
                print(f"  TX: {inventory_cmd.hex(' ')}")
                print(f"  RX: {response.hex(' ')}")
                
                parsed = parse_response(response)
                if parsed:
                    if parsed.get('status') == 'tag_found':
                        epc = parsed.get('epc', '')
                        if epc and epc not in tags_found:
                            tags_found.add(epc)
                            print(f"  [+] МЕТКА: {epc}")
                    elif parsed.get('status') == 'no_tags':
                        print(f"  [.] нет меток")
                print()
            
            time.sleep(0.2)
        
        ser.close()
        
        print("=" * 40)
        if tags_found:
            print(f"✓ Найдено меток: {len(tags_found)}")
            for tag in tags_found:
                print(f"  EPC: {tag}")
        else:
            print("Меток не найдено")
            
    except serial.SerialException as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
