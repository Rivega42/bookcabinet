#!/usr/bin/env python3
"""Test hardware waves motor control"""
import sys
sys.path.insert(0, "/home/admin42/bookcabinet")

import asyncio
from bookcabinet.hardware.motors import Motors

async def main():
    m = Motors()
    print(f"Mock mode: {m.mock_mode}")
    print(f"Pi connected: {m.pi and m.pi.connected if m.pi else False}")
    
    if m.mock_mode:
        print("ERROR: Running in mock mode!")
        return
    
    print("\nTest Motor A (500 steps CW)...")
    await m.test_motor("A", 1, 500)
    await asyncio.sleep(0.5)
    
    print("Test Motor A (500 steps CCW)...")
    await m.test_motor("A", -1, 500)
    await asyncio.sleep(0.5)
    
    print("Test Motor B (500 steps CW)...")
    await m.test_motor("B", 1, 500)
    await asyncio.sleep(0.5)
    
    print("Test Motor B (500 steps CCW)...")
    await m.test_motor("B", -1, 500)
    
    print("\nDone!")

asyncio.run(main())
