"""
Единый лок механики: один портал — одна операция за раз.

Раньше `_mech_lock` жил только в api_routes и покрывал HTTP-операции, а WS-путь
управления механикой (motor/servo/shutter/home) и /api/init, /api/move шли мимо →
два драйвера одного портала (гонка). Теперь и HTTP, и WS берут ЭТОТ лок.
"""
import asyncio

mech_lock = asyncio.Lock()
