#!/usr/bin/env python3
"""Детальная отладка NFC считывателя"""
from smartcard.System import readers
from smartcard.util import toHexString
import time

print("=== ТЕСТ NFC ACR1281 ===\n")

# Получаем список считывателей
available = readers()
print(f"Найдено считывателей: {len(available)}")
for i, r in enumerate(available):
    print(f"  {i}: {r}")

if not available:
    print("Нет считывателей!")
    exit(1)

# Берём первый ACR
reader = available[0]
print(f"\nИспользуем: {reader}")

print("\n⚡ Поднесите карту к считывателю...\n")

last_atr = None
while True:
    try:
        connection = reader.createConnection()
        connection.connect()
        
        # ATR карты
        atr = connection.getATR()
        atr_hex = toHexString(atr)
        
        if atr_hex != last_atr:
            print(f"✓ Карта обнаружена!")
            print(f"  ATR: {atr_hex}")
            last_atr = atr_hex
            
            # Пробуем разные команды для получения UID
            commands = [
                ([0xFF, 0xCA, 0x00, 0x00, 0x00], "GET UID (стандарт)"),
                ([0xFF, 0xCA, 0x00, 0x00, 0x04], "GET UID (4 байта)"),
                ([0xFF, 0xCA, 0x00, 0x00, 0x07], "GET UID (7 байт)"),
                ([0xFF, 0xB0, 0x00, 0x00, 0x10], "READ BINARY"),
                ([0x90, 0x60, 0x00, 0x00, 0x00], "GET VERSION"),
            ]
            
            for cmd, name in commands:
                try:
                    data, sw1, sw2 = connection.transmit(cmd)
                    if sw1 == 0x90 and sw2 == 0x00:
                        uid = ''.join(format(x, '02X') for x in data)
                        print(f"  ✓ {name}: {uid}")
                    else:
                        print(f"  ✗ {name}: SW={sw1:02X} {sw2:02X}")
                except Exception as e:
                    print(f"  ✗ {name}: {e}")
        
        connection.disconnect()
        
    except Exception as e:
        if last_atr:
            print("Карта убрана")
            last_atr = None
    
    time.sleep(0.5)
