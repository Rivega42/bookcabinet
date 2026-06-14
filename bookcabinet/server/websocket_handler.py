"""
WebSocket Handler
"""
import json
import asyncio
from typing import Set, Dict, Any
from aiohttp import web, WSMsgType


class WebSocketHandler:
    def __init__(self):
        self.clients: Set[web.WebSocketResponse] = set()
        self._lock = asyncio.Lock()
        # Внутренние подписчики на поток broadcast-событий (SSE-диагностика и т.п.)
        self.subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """Подписка на поток broadcast-событий внутри процесса (для SSE).
        Возвращает очередь; обязательно вызвать unsubscribe() по завершении."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subscribers.discard(q)
    
    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        async with self._lock:
            self.clients.add(ws)
        
        print(f"WebSocket client connected. Total: {len(self.clients)}")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(ws, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
        finally:
            async with self._lock:
                self.clients.discard(ws)
            print(f"WebSocket client disconnected. Total: {len(self.clients)}")
        
        return ws
    
    async def _handle_message(self, ws: web.WebSocketResponse, data: str):
        try:
            message = json.loads(data)
            action = message.get('action')
            
            if action == 'ping':
                await ws.send_json({'type': 'pong'})
            
            elif action == 'authenticate':
                from ..business.auth import auth_service
                result = await auth_service.authenticate(message.get('card_rfid', ''))
                await ws.send_json({'type': 'auth_result', 'data': result})
            
            elif action == 'motor':
                from ..hardware.motors import motors
                from ..hardware.sensors import sensors
                
                cmd = message.get('command')
                value = message.get('value', 0)
                
                if cmd == 'move_xy':
                    x = message.get('x', 0)
                    y = message.get('y', 0)
                    success = await motors.move_xy(x, y)
                    pos = motors.get_position()
                    await ws.send_json({
                        'type': 'motor_result',
                        'success': success,
                        'position': pos
                    })
                
                elif cmd == 'move_relative':
                    dx = message.get('dx', 0)
                    dy = message.get('dy', 0)
                    pos = motors.get_position()
                    success = await motors.move_xy(pos['x'] + dx, pos['y'] + dy)
                    new_pos = motors.get_position()
                    await ws.send_json({
                        'type': 'motor_result',
                        'success': success,
                        'position': new_pos
                    })
                
                elif cmd == 'extend_tray':
                    steps = message.get('steps')
                    success = await motors.extend_tray(steps)
                    await ws.send_json({
                        'type': 'motor_result',
                        'success': success,
                        'tray': motors.get_position()['tray']
                    })
                
                elif cmd == 'retract_tray':
                    steps = message.get('steps')
                    success = await motors.retract_tray(steps)
                    await ws.send_json({
                        'type': 'motor_result',
                        'success': success,
                        'tray': motors.get_position()['tray']
                    })
                
                elif cmd == 'stop':
                    motors.stop()
                    await ws.send_json({
                        'type': 'motor_result',
                        'success': True,
                        'stopped': True
                    })
                
                elif cmd == 'home':
                    from ..mechanics.algorithms import algorithms
                    success = await algorithms.init_home()
                    await ws.send_json({
                        'type': 'motor_result',
                        'success': success,
                        'position': motors.get_position()
                    })
                
                elif cmd == 'get_position':
                    await ws.send_json({
                        'type': 'position',
                        **motors.get_position()
                    })
                
                elif cmd == 'get_sensors':
                    await ws.send_json({
                        'type': 'sensors',
                        'data': sensors.read_all()
                    })
                
                else:
                    await ws.send_json({
                        'type': 'error',
                        'message': f'Unknown motor command: {cmd}'
                    })
            
            elif action == 'servo':
                from ..hardware.servos import servos
                
                cmd = message.get('command')
                lock = message.get('lock', 'lock1')
                
                if cmd == 'open':
                    await servos.open_lock(lock)
                    await ws.send_json({'type': 'servo_result', 'success': True, 'lock': lock, 'state': 'open'})
                elif cmd == 'close':
                    await servos.close_lock(lock)
                    await ws.send_json({'type': 'servo_result', 'success': True, 'lock': lock, 'state': 'closed'})
                else:
                    await ws.send_json({'type': 'error', 'message': f'Unknown servo command: {cmd}'})
            
            elif action == 'shutter':
                from ..hardware.shutters import shutters
                
                cmd = message.get('command')
                shutter = message.get('shutter', 'inner')
                
                if cmd == 'open':
                    await shutters.open_shutter(shutter)
                    await ws.send_json({'type': 'shutter_result', 'success': True, 'shutter': shutter, 'state': 'open'})
                elif cmd == 'close':
                    await shutters.close_shutter(shutter)
                    await ws.send_json({'type': 'shutter_result', 'success': True, 'shutter': shutter, 'state': 'closed'})
                else:
                    await ws.send_json({'type': 'error', 'message': f'Unknown shutter command: {cmd}'})
            
            elif action == 'simulate_card':
                # Симуляция карты для тестирования
                from ..rfid.unified_card_reader import unified_reader
                uid = message.get('uid', 'TEST001')
                source = message.get('source', 'nfc')
                unified_reader.simulate_card(uid, source)
                await ws.send_json({'type': 'simulate_result', 'success': True, 'uid': uid, 'source': source})
            
        except json.JSONDecodeError:
            await ws.send_json({'type': 'error', 'message': 'Invalid JSON'})
        except Exception as e:
            await ws.send_json({'type': 'error', 'message': str(e)})
    
    async def broadcast(self, message: Dict[str, Any]):
        # Внутренние подписчики (SSE-диагностика) — best-effort, не блокируем поток
        for q in list(self.subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass

        if not self.clients:
            return

        data = json.dumps(message)
        async with self._lock:
            dead_clients = set()
            for ws in self.clients:
                try:
                    await ws.send_str(data)
                except:
                    dead_clients.add(ws)
            
            self.clients -= dead_clients
    
    async def send_progress(self, data: Dict[str, Any]):
        await self.broadcast({'type': 'progress', 'data': data})
    
    async def send_error(self, data: Dict[str, Any]):
        await self.broadcast({'type': 'error', 'data': data})
    
    async def send_sensors(self, data: Dict[str, Any]):
        await self.broadcast({'type': 'sensors', 'data': data})
    
    async def send_position(self, x: int, y: int, tray: int):
        await self.broadcast({
            'type': 'position',
            'x': x,
            'y': y,
            'tray': tray
        })
    
    async def send_card_detected(self, uid: str, source: str):
        """
        Отправка события обнаружения карты всем клиентам
        
        Args:
            uid: Нормализованный UID карты
            source: 'nfc' или 'uhf'
        """
        await self.broadcast({
            'type': 'card_detected',
            'uid': uid,
            'source': source
        })
    
    async def send_auth_result(self, result: Dict[str, Any]):
        """
        Отправка результата автоматической авторизации всем клиентам
        
        Args:
            result: Результат от auth_service.authenticate()
        """
        await self.broadcast({
            'type': 'auth_result',
            'data': result
        })


ws_handler = WebSocketHandler()
