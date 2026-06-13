#!/usr/bin/env python3
"""Тест всех интерфейсов ACR1281"""
from smartcard.System import readers
from smartcard.util import toHexString
import time

print("=== ТЕСТ ВСЕХ ИНТЕРФЕЙСОВ ACR1281 ===\n")

available = readers()
print(f"Найдено интерфейсов: {len(available)}")
for r in available:
    print(f"  - {r}")

print("\n⚡ Поднесите карту к считывателю...\n")

# Тестируем каждый интерфейс
while True:
    for reader_idx, reader in enumerate(available):
        try:
            connection = reader.createConnection()
            connection.connect()
            
            # Пробуем получить UID
            GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
            data, sw1, sw2 = connection.transmit(GET_UID)
            
            if sw1 == 0x90 and sw2 == 0x00 and data:
                uid = ''.join(format(x, '02X') for x in data)
                print(f"\n✅ КАРТА НАЙДЕНА на интерфейсе {reader_idx} ({reader})!")
                print(f"   UID: {uid}")
                print(f"   Форматированный: {' '.join([uid[i:i+2] for i in range(0, len(uid), 2)])}")
                print()
                
                connection.disconnect()
                time.sleep(2)  # Пауза чтобы не спамить
                
            connection.disconnect()
            
        except Exception:
            pass  # Нет карты на этом интерфейсе
    
    time.sleep(0.2)
