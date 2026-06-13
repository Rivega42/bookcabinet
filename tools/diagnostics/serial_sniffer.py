# serial_sniffer.py
# Перехват трафика между приложением и COM портом
# 
# Требуется: py -m pip install pyserial

import serial
import threading
import time
import sys

# Реальный ридер
REAL_PORT = "COM2"
REAL_BAUD = 57600

# Виртуальный порт (от com0com) - сюда подключается приложение
# Пара: COM1 <-> COM18, приложение на COM1, скрипт слушает COM18
VIRTUAL_PORT = "COM18"

def hex_dump(data, direction):
    """Красивый вывод hex"""
    if not data:
        return
    hex_str = data.hex(' ')
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {direction}: {hex_str}")
    print(f"           ASCII: {ascii_str}")
    print()

def forward(src, dst, direction):
    """Пересылка данных с логированием"""
    while True:
        try:
            data = src.read(src.in_waiting or 1)
            if data:
                hex_dump(data, direction)
                dst.write(data)
        except Exception as e:
            print(f"Ошибка {direction}: {e}")
            break

def main():
    print(f"=== Serial Sniffer ===")
    print(f"Реальный ридер: {REAL_PORT} @ {REAL_BAUD}")
    print(f"Виртуальный порт: {VIRTUAL_PORT}")
    print(f"")
    print(f"В демо приложении RRU9816 выбери COM1")
    print(f"")
    print(f"Ctrl+C для выхода")
    print(f"=" * 40)
    print()

    try:
        real = serial.Serial(REAL_PORT, REAL_BAUD, timeout=0.1)
        virtual = serial.Serial(VIRTUAL_PORT, REAL_BAUD, timeout=0.1)
    except serial.SerialException as e:
        print(f"Ошибка открытия порта: {e}")
        sys.exit(1)

    # Два потока: APP -> READER и READER -> APP
    t1 = threading.Thread(target=forward, args=(virtual, real, "APP->READER"), daemon=True)
    t2 = threading.Thread(target=forward, args=(real, virtual, "READER->APP"), daemon=True)
    
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nСтоп")

if __name__ == "__main__":
    main()
