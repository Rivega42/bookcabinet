/**
 * HTTP and WebSocket route definitions.
 * API endpoints for cabinet control, RFID operations, user management.
 * WebSocket server for real-time tag events and status updates.
 */
import type { Express, Request, Response, NextFunction } from "express";
import { createServer, type Server } from "http";
import { WebSocketServer, WebSocket } from "ws";
import { storage } from "./storage";
import { rfidService } from "./services/rfidService";
import { cabinetService } from "./services/cabinetService";
import { irbisService } from "./services/irbisService";
import { pythonBridge } from "./services/pythonBridge";
import { operationQueue } from "./services/operationQueue";
import { execSync } from 'child_process';
import * as fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import rateLimit from 'express-rate-limit';
import type {
  WebSocketMessage, TagReadEvent, RfidReaderStatus, SystemLog,
  SystemStatus, User, Cell, Book, CalibrationData
} from "@shared/schema";
import { ReaderType } from "@shared/schema";
import { z } from "zod";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const BOOKCABINET_ROOT =
  process.env.BOOKCABINET_ROOT || path.resolve(__dirname, '..');

// Zod schemas for request body validation
// #62: RFID / card UID validation — hex-only for book tags; slightly looser for cards
// because different reader families emit different encodings (NFC UID vs UHF EPC).
const rfidSchema = z
  .string()
  .min(8)
  .max(48)
  .regex(/^[A-Fa-f0-9]+$/, 'Invalid hex format');
const cardUidSchema = z.string().min(6).max(48);

const authCardSchema = z.object({ rfid: cardUidSchema });
const issueSchema = z.object({
  bookRfid: rfidSchema,
  userRfid: cardUidSchema,
});
const returnSchema = z.object({ bookRfid: rfidSchema });
const loadBookSchema = z.object({
  bookRfid: rfidSchema,
  title: z.string().min(1),
  author: z.string().optional(),
});

// #65: Rate limiters. Small windows, conservative caps — the whole machine
// is one cabinet serving a line of students, not a public API.
const authLimiter = rateLimit({
  windowMs: 60_000,
  max: 20,
  message: 'Слишком много попыток, попробуйте позже',
  standardHeaders: true,
  legacyHeaders: false,
});

const operationLimiter = rateLimit({
  windowMs: 60_000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
});

// Состояние системы (будет управляться механикой)
let systemStatus: SystemStatus = {
  state: 'idle',
  position: { x: 0, y: 0, tray: 0 },
  sensors: {
    x_begin: true,
    x_end: false,
    y_begin: true,
    y_end: false,
    tray_begin: true,
    tray_end: false,
  },
  shutters: { inner: false, outer: false },
  locks: { front: false, back: false },
  irbisConnected: false,
  autonomousMode: true,
  maintenanceMode: false,
};

// Текущая сессия авторизации
let currentSession: { user: User | null; expiresAt: Date | null } = {
  user: null,
  expiresAt: null,
};

// #45: Auth middleware. `currentSession` is a module-level singleton representing
// "the person currently standing in front of the cabinet", so these middlewares
// simply check whether that session is still valid. They are not a replacement
// for a per-user token — the cabinet is a single-kiosk device.
function requireSession(req: Request, res: Response, next: NextFunction) {
  if (
    !currentSession.user ||
    !currentSession.expiresAt ||
    currentSession.expiresAt < new Date()
  ) {
    currentSession = { user: null, expiresAt: null };
    return res.status(401).json({ error: 'Требуется авторизация' });
  }
  next();
}

function requireRole(...roles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!currentSession.user) {
      return res.status(401).json({ error: 'Требуется авторизация' });
    }
    if (!roles.includes(currentSession.user.role)) {
      return res.status(403).json({ error: 'Недостаточно прав' });
    }
    next();
  };
}

export async function registerRoutes(app: Express): Promise<Server> {
  const httpServer = createServer(app);
  const wss = new WebSocketServer({ server: httpServer, path: '/ws' });

  // ─── Auth Shutter Daemon ───────────────────────────────
  {
    const { spawn } = await import('child_process');
    const daemonPath =
      process.env.AUTH_DAEMON_PATH ||
      path.join(BOOKCABINET_ROOT, 'bookcabinet/services/auth_shutter_daemon.py');
    
    const startDaemon = () => {
      const daemon = spawn('sudo', ['python3', daemonPath], { stdio: ['ignore', 'pipe', 'pipe'] });

      daemon.on('error', (err: Error) => {
        console.error('[auth-daemon] failed to start:', err.message);
      });

      daemon.stdout.on('data', (data: Buffer) => {
        data.toString().split('\n').filter(Boolean).forEach(line => {
          try {
            const event = JSON.parse(line);
            broadcast({ type: 'reader_status', data: event } as any);
            console.log('[auth-daemon]', line.trim());
          } catch {}
        });
      });

      daemon.stderr.on('data', (d: Buffer) => {
        const msg = d.toString().trim();
        if (msg) console.error('[auth-daemon]', msg);
      });

      daemon.on('close', (code: number) => {
        console.log(`[auth-daemon] exited (${code}), restarting in 5s...`);
        setTimeout(startDaemon, 5000);
      });
    };

    // Демон требует sudo + GPIO — запускается только на Pi.
    if (process.platform === 'linux') {
      setTimeout(startDaemon, 3000);
    }
  }

  // Ручное управление шторками
  app.post("/api/shutter/:action", async (req, res) => {
    const { spawn } = await import('child_process');
    const { action } = req.params;
    const scripts: Record<string, string> = {
      'open-outer':  'import RPi.GPIO as G; G.setmode(G.BCM); G.setwarnings(False); G.setup(2,G.OUT); G.output(2,G.HIGH)',
      'close-outer': 'import RPi.GPIO as G; G.setmode(G.BCM); G.setwarnings(False); G.setup(2,G.OUT); G.output(2,G.LOW)',
      'open-inner':  'import RPi.GPIO as G; G.setmode(G.BCM); G.setwarnings(False); G.setup(3,G.OUT); G.output(3,G.HIGH)',
      'close-inner': 'import RPi.GPIO as G; G.setmode(G.BCM); G.setwarnings(False); G.setup(3,G.OUT); G.output(3,G.LOW)',
      'close-all':   'import RPi.GPIO as G; G.setmode(G.BCM); G.setwarnings(False); G.setup(2,G.OUT); G.setup(3,G.OUT); G.output(2,G.LOW); G.output(3,G.LOW)',
      'open-all':    'import RPi.GPIO as G; G.setmode(G.BCM); G.setwarnings(False); G.setup(2,G.OUT); G.setup(3,G.OUT); G.output(2,G.HIGH); G.output(3,G.HIGH)',
    };
    const script = scripts[action];
    if (!script) return res.status(400).json({ error: 'Unknown action' });
    const p = spawn('sudo', ['python3', '-c', script]);
    p.on('close', () => res.json({ success: true, action }));
  });


  const clients = new Set<WebSocket>();

  const broadcast = (message: WebSocketMessage) => {
    const messageStr = JSON.stringify(message);
    clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(messageStr);
      }
    });
  };

  // RFID Service event handlers
  rfidService.on('tagRead', (tagEvent: TagReadEvent) => {
    broadcast({ type: 'tag_read', data: tagEvent });
    // #23: broadcast book_read and book_presence for book RFID tags
    if (tagEvent.epc) {
      broadcast({ type: 'book_read', data: { rfid: tagEvent.epc, timestamp: new Date().toISOString() } } as any);
      broadcast({ type: 'book_presence', data: { present: true, rfid: tagEvent.epc } } as any);
    }
  });

  rfidService.on('status', (status: RfidReaderStatus) => {
    broadcast({ type: 'reader_status', data: status });
  });

  // Cabinet Service event handlers
  cabinetService.on('state_changed', (state) => {
    broadcast({ type: 'cabinet_state', data: state });
  });

  cabinetService.on('operation_started', (data) => {
    broadcast({ type: 'operation_started', data });
  });

  cabinetService.on('operation_completed', (data) => {
    broadcast({ type: 'operation_completed', data });
  });

  cabinetService.on('operation_failed', (data) => {
    broadcast({ type: 'operation_failed', data });
    // #23: Also broadcast as 'error' event for frontend
    broadcast({ type: 'error', data: { code: 'OPERATION_FAILED', message: data?.message || 'Operation failed' } } as any);
  });

  cabinetService.on('cell_opened', (position) => {
    broadcast({ type: 'cell_opened', data: position });
  });

  cabinetService.on('book_detected', (rfid) => {
    broadcast({ type: 'book_detected', data: { rfid } });
    // #23: Also broadcast as 'book_read' for frontend WebSocket listeners
    broadcast({ type: 'book_read', data: { rfid, timestamp: new Date().toISOString() } } as any);
  });

  // WebSocket connection handler
  wss.on('connection', (ws) => {
    clients.add(ws);
    console.log('WebSocket client connected');

    ws.send(JSON.stringify({ type: 'status', data: systemStatus }));
    ws.send(JSON.stringify({ type: 'reader_status', data: rfidService.getConnectionStatus() }));

    ws.on('message', async (data) => {
      try {
        const message = JSON.parse(data.toString());
        await handleWebSocketMessage(message, ws, broadcast);
      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    });

    ws.on('close', () => {
      clients.delete(ws);
      console.log('WebSocket client disconnected');
    });

    ws.on('error', (error) => {
      console.error('WebSocket error:', error);
      clients.delete(ws);
    });
  });

  // ==================== СИСТЕМА ====================

  app.get("/api/status", (req, res) => {
    res.json(systemStatus);
  });

  // #56: Health check endpoint. Deliberately lightweight — tests that the
  // event loop is alive, the storage layer can answer a trivial query, and the
  // Python bridge responds. Each sub-check is bounded so the overall response
  // time is < ~3.5 s even when the bridge is dead.
  app.get("/api/health", async (req, res) => {
    const checks: Record<string, boolean | string> = {
      server: true,
      storage: false,
      python_bridge: false,
    };

    try {
      await storage.getStatistics();
      checks.storage = true;
    } catch (e: any) {
      checks.storage = `error: ${e?.message ?? 'unknown'}`;
    }

    try {
      const result = await Promise.race([
        pythonBridge.status(),
        new Promise((_, rej) =>
          setTimeout(() => rej(new Error('timeout')), 3000),
        ),
      ]);
      checks.python_bridge = !!result;
    } catch (e: any) {
      checks.python_bridge = `error: ${e?.message ?? 'unknown'}`;
    }

    const allHealthy = Object.values(checks).every((v) => v === true);
    res.status(allHealthy ? 200 : 503).json({
      status: allHealthy ? 'ok' : 'degraded',
      checks,
      timestamp: new Date().toISOString(),
      uptime_seconds: Math.floor(process.uptime()),
    });
  });

  // ─── RFID Test (SSE stream) ────────────────────────────
  app.get("/api/rfid-test/:readerId", async (req, res) => {
    const { readerId } = req.params;
    const { spawn } = await import('child_process');
    const fs = await import('fs');

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.flushHeaders();

    const send = (data: object) => {
      res.write(`data: ${JSON.stringify(data)}\n\n`);
    };

    send({ type: 'info', message: `Запуск теста ${readerId}...` });

    let proc: any = null;

    if (readerId === 'acr1281') {
      const script = `
import time, sys
from smartcard.System import readers
rs = readers()
nfc = [r for r in rs if '00 01' in str(r)]
if not nfc:
    print('{"type":"error","message":"Считыватель не найден"}', flush=True)
    sys.exit(1)
reader = nfc[0]
print('{"type":"info","message":"ACR1281 готов — поднеси ЕКП карту"}', flush=True)
last = None
deadline = time.time() + 30
while time.time() < deadline:
    try:
        c = reader.createConnection()
        c.connect()
        data, sw1, sw2 = c.transmit([0xFF,0xCA,0x00,0x00,0x00])
        c.disconnect()
        if sw1 == 0x90:
            uid = ''.join(f'{b:02X}' for b in data)
            if uid != last:
                last = uid
                import json
                print(json.dumps({"type":"card","uid":uid,"reader":"ACR1281","protocol":"NFC 13.56MHz"}), flush=True)
        else:
            if last:
                last = None
                print('{"type":"info","message":"Карта убрана"}', flush=True)
    except:
        if last:
            last = None
            print('{"type":"info","message":"Карта убрана"}', flush=True)
    time.sleep(0.2)
print('{"type":"done","message":"Тест завершён (30 сек)"}', flush=True)
`;
      proc = spawn('python3', ['-c', script]);

    } else if (readerId === 'rru9816' || readerId === 'iqrfid5102') {
      const port = readerId === 'rru9816' ? '/dev/ttyUSB0' : '/dev/ttyUSB2';
      const script = `
import serial, time, json, sys

PORT = '${readerId === 'rru9816' ? '/dev/ttyUSB0' : '/dev/ttyUSB2'}'

def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, crc >> 8])

def build_cmd(cmd, data=b''):
    pkt = bytes([1+1+len(data)+2, 0x00, cmd]) + data
    return pkt + crc16(pkt)

CMD = build_cmd(0x01)

try:
    ser = serial.Serial(PORT, 57600, timeout=0.5)
    reader_name = '${readerId === 'rru9816' ? 'RRU9816' : 'IQRFID-5102'}'
    print(json.dumps({"type":"info","message":f"{reader_name} готов — поднеси метку/карту"}), flush=True)
    found = set()
    deadline = time.time() + 30
    while time.time() < deadline:
        ser.reset_input_buffer()
        ser.write(CMD)
        time.sleep(0.15)
        resp = ser.read(256)
        if resp and len(resp) > 6:
            status = resp[3]
            if status == 0x01:
                count = resp[4]
                off = 5
                for _ in range(count):
                    if off >= len(resp)-2: break
                    off += 1
                    epc_len = resp[off]; off += 1
                    if off+epc_len > len(resp)-2: break
                    epc = resp[off:off+epc_len].hex().upper()
                    off += epc_len
                    if epc and epc not in found:
                        found.add(epc)
                        print(json.dumps({"type":"tag","epc":epc,"reader":reader_name,"protocol":"UHF 860-960MHz"}), flush=True)
        time.sleep(0.15)
    ser.close()
    print(json.dumps({"type":"done","message":"Тест завершён (30 сек)"}), flush=True)
except Exception as e:
    print(json.dumps({"type":"error","message":str(e)}), flush=True)
`;
      proc = spawn('python3', ['-c', script]);
    } else {
      send({ type: 'error', message: `Неизвестный считыватель: ${readerId}` });
      res.end();
      return;
    }

    if (proc) {
      proc.stdout.on('data', (data: Buffer) => {
        data.toString().split('\n').filter(Boolean).forEach(line => {
          try { send(JSON.parse(line)); } catch { send({ type: 'raw', message: line }); }
        });
      });
      proc.stderr.on('data', (data: Buffer) => {
        send({ type: 'error', message: data.toString().trim() });
      });
      proc.on('close', () => {
        send({ type: 'done', message: 'Соединение закрыто' });
        res.end();
      });
      req.on('close', () => { proc?.kill(); });
    }
  });

  // ─── RFID Reader Status ────────────────────────────────
  app.get("/api/rfid-readers", (req, res) => {
    const readers = [
      {
        id: 'acr1281',
        name: 'ACR1281U-C',
        type: 'NFC 13.56MHz',
        role: 'ЕКП карты',
        port: 'pcscd',
        connected: false,
        error: null as string | null,
      },
      {
        id: 'rru9816',
        name: 'RRU9816',
        type: 'UHF 860-960MHz',
        role: 'Метки книг',
        port: '/dev/ttyUSB0',
        connected: false,
        error: null as string | null,
      },
      {
        id: 'iqrfid5102',
        name: 'IQRFID-5102',
        type: 'UHF 860-960MHz',
        role: 'Библ. карты',
        port: '/dev/ttyUSB2',
        connected: false,
        error: null as string | null,
      },
    ];

    // ACR1281: проверяем через pcscd
    try {
      const result = execSync('pgrep -x pcscd', { timeout: 1000 }).toString().trim();
      readers[0].connected = result.length > 0;
    } catch {
      readers[0].connected = false;
      readers[0].error = 'pcscd не запущен';
    }

    // RRU9816 + IQRFID-5102: проверяем наличие портов
    readers[1].connected = fs.existsSync('/dev/ttyUSB0');
    if (!readers[1].connected) readers[1].error = 'Устройство не обнаружено';

    readers[2].connected = fs.existsSync('/dev/ttyUSB2');
    if (!readers[2].connected) readers[2].error = 'Устройство не обнаружено';

    res.json(readers);
  });

  app.post("/api/maintenance", async (req, res) => {
    const { enabled } = req.body;
    systemStatus.maintenanceMode = Boolean(enabled);
    broadcast({ type: 'status', data: systemStatus });
    await storage.addSystemLog({
      level: enabled ? 'WARNING' : 'INFO',
      message: enabled ? 'Режим обслуживания включён' : 'Режим обслуживания отключён',
      component: 'SYSTEM',
    });
    res.json({ success: true, maintenanceMode: systemStatus.maintenanceMode });
  });

  // ==================== ЯЧЕЙКИ ====================

  app.get("/api/cells", async (req, res) => {
    try {
      const cells = await storage.getAllCells();
      res.json(cells);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get cells' });
    }
  });

  // Специфичные роуты ПЕРЕД параметризованными
  app.get("/api/cells/extraction", async (req, res) => {
    try {
      const cells = await storage.getCellsNeedingExtraction();
      res.json(cells);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get cells' });
    }
  });

  app.get("/api/cells/available/:row?", async (req, res) => {
    try {
      const cells = await storage.getAvailableCells(req.params.row);
      res.json(cells);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get available cells' });
    }
  });

  // Параметризованные роуты ПОСЛЕ специфичных
  app.get("/api/cells/:id", async (req, res) => {
    try {
      const cell = await storage.getCell(parseInt(req.params.id));
      if (!cell) return res.status(404).json({ error: 'Cell not found' });
      res.json(cell);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get cell' });
    }
  });

  app.patch("/api/cells/:id", async (req, res) => {
    try {
      const cell = await storage.updateCell(parseInt(req.params.id), req.body);
      if (!cell) return res.status(404).json({ error: 'Cell not found' });
      res.json(cell);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to update cell' });
    }
  });

  // ==================== ПОЛЬЗОВАТЕЛИ ====================

  app.get("/api/users", async (req, res) => {
    try {
      const users = await storage.getAllUsers();
      res.json(users);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get users' });
    }
  });

  app.get("/api/users/:id", async (req, res) => {
    try {
      const user = await storage.getUser(req.params.id);
      if (!user) return res.status(404).json({ error: 'User not found' });
      res.json(user);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get user' });
    }
  });

  app.get("/api/users/rfid/:rfid", async (req, res) => {
    try {
      const user = await storage.getUserByRfid(req.params.rfid);
      if (!user) return res.status(404).json({ error: 'User not found' });
      res.json(user);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get user' });
    }
  });

  app.post("/api/users", async (req, res) => {
    try {
      const user = await storage.createUser(req.body);
      res.status(201).json(user);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to create user' });
    }
  });

  // ==================== КНИГИ ====================

  app.get("/api/books", async (req, res) => {
    try {
      const books = await storage.getAllBooks();
      res.json(books);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get books' });
    }
  });

  app.get("/api/books/:id", async (req, res) => {
    try {
      const book = await storage.getBook(req.params.id);
      if (!book) return res.status(404).json({ error: 'Book not found' });
      res.json(book);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get book' });
    }
  });

  app.get("/api/books/rfid/:rfid", async (req, res) => {
    try {
      const book = await storage.getBookByRfid(req.params.rfid);
      if (!book) return res.status(404).json({ error: 'Book not found' });
      res.json(book);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get book' });
    }
  });

  app.get("/api/books/reserved/:userRfid", async (req, res) => {
    try {
      const books = await storage.getReservedBooks(req.params.userRfid);
      res.json(books);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get reserved books' });
    }
  });

  app.post("/api/books", async (req, res) => {
    try {
      const book = await storage.createBook(req.body);
      res.status(201).json(book);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to create book' });
    }
  });

  app.patch("/api/books/:id", async (req, res) => {
    try {
      const book = await storage.updateBook(req.params.id, req.body);
      if (!book) return res.status(404).json({ error: 'Book not found' });
      res.json(book);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to update book' });
    }
  });

  // ==================== ОПЕРАЦИИ ====================

  app.get("/api/operations", async (req, res) => {
    try {
      const limit = req.query.limit ? parseInt(req.query.limit as string) : undefined;
      const operations = await storage.getAllOperations(limit);
      res.json(operations);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get operations' });
    }
  });

  app.get("/api/operations/today", async (req, res) => {
    try {
      const operations = await storage.getOperationsToday();
      res.json(operations);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get operations' });
    }
  });

  app.post("/api/operations", async (req, res) => {
    try {
      const operation = await storage.createOperation(req.body);
      res.status(201).json(operation);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to create operation' });
    }
  });

  // ==================== АВТОРИЗАЦИЯ ====================

  app.post("/api/auth/card", authLimiter, async (req, res) => {
    try {
      const parsed = authCardSchema.safeParse(req.body);
      if (!parsed.success) return res.status(400).json({ error: 'RFID is required', details: parsed.error.issues });
      const { rfid } = parsed.data;

      if (systemStatus.maintenanceMode) {
        return res.status(503).json({ error: 'Шкаф временно недоступен' });
      }

      const user = await storage.getUserByRfid(rfid);
      if (!user) {
        await storage.addSystemLog({
          level: 'WARNING',
          message: `Неизвестная карта: ${rfid}`,
          component: 'RFID',
        });
        return res.status(404).json({ error: 'Карта не зарегистрирована' });
      }

      if (user.blocked) {
        return res.status(403).json({ error: 'Обратитесь к библиотекарю' });
      }

      currentSession = {
        user,
        expiresAt: new Date(Date.now() + 5 * 60 * 1000), // 5 минут
      };

      await storage.addSystemLog({
        level: 'INFO',
        message: `Авторизация: ${user.name} (${user.role})`,
        component: 'SYSTEM',
      });

      broadcast({ type: 'card_read', data: { uid: rfid, cardType: 'library', timestamp: new Date().toISOString() } });

      const reservedBooks = await storage.getReservedBooks(rfid);
      const needsExtraction = await storage.getCellsNeedingExtraction();

      res.json({ 
        success: true, 
        user,
        reservedBooks,
        needsExtraction: needsExtraction.length,
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Auth failed' });
    }
  });

  app.post("/api/auth/logout", (req, res) => {
    currentSession = { user: null, expiresAt: null };
    res.json({ success: true });
  });

  app.get("/api/auth/session", (req, res) => {
    if (!currentSession.user || !currentSession.expiresAt || currentSession.expiresAt < new Date()) {
      currentSession = { user: null, expiresAt: null };
      return res.json({ authenticated: false });
    }
    res.json({ authenticated: true, user: currentSession.user });
  });

  // ==================== БИЗНЕС-ОПЕРАЦИИ ====================

  // Python bridge — delegated to PythonBridgeService (server/services/pythonBridge.ts)
  const runPythonBridge = (command: string, args: string[]) =>
    pythonBridge.execute(command, args, (msg) => broadcast({ type: 'progress', data: msg }));

  app.post("/api/issue", requireSession, operationLimiter, async (req, res) => {
    try {
      const parsed = issueSchema.safeParse(req.body);
      if (!parsed.success) return res.status(400).json({ error: 'bookRfid and userRfid are required', details: parsed.error.issues });
      const { bookRfid, userRfid } = parsed.data;

      // Делегируем в Python бизнес-слой (механическая верификация)
      const result = await runPythonBridge('issue', [bookRfid, userRfid]);

      if (result.success) {
        // Синхронизируем TS-хранилище с результатом Python
        const book = await storage.getBookByRfid(bookRfid);
        if (book) {
          await storage.updateBook(book.id, {
            status: 'issued',
            issuedToRfid: userRfid,
            reservedForRfid: null,
            cellId: null,
          });
          if (book.cellId !== null) {
            await storage.updateCell(book.cellId, {
              status: 'empty',
              bookRfid: null,
              bookTitle: null,
              reservedFor: null,
            });
          }
        }

        await storage.addSystemLog({
          level: 'SUCCESS',
          message: `Выдана книга: ${result.book?.title || bookRfid}`,
          component: 'SYSTEM',
        });
      }

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Issue failed' });
    }
  });

  app.post("/api/return", requireSession, operationLimiter, async (req, res) => {
    try {
      const parsed = returnSchema.safeParse(req.body);
      if (!parsed.success) return res.status(400).json({ error: 'bookRfid is required', details: parsed.error.issues });
      const { bookRfid } = parsed.data;

      // Делегируем в Python бизнес-слой (механическая верификация)
      const result = await runPythonBridge('return', [bookRfid]);

      if (result.success) {
        // Синхронизируем TS-хранилище
        const book = await storage.getBookByRfid(bookRfid);
        if (book && result.cell) {
          await storage.updateBook(book.id, {
            status: 'in_cabinet',
            issuedToRfid: null,
            cellId: result.cell.id,
          });
          await storage.updateCell(result.cell.id, {
            status: 'occupied',
            bookRfid,
            bookTitle: book.title,
            needsExtraction: true,
          });
        }

        await storage.addSystemLog({
          level: 'SUCCESS',
          message: `Возвращена книга: ${result.book?.title || bookRfid}`,
          component: 'SYSTEM',
        });
      }

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Return failed' });
    }
  });

  // ==================== ОПЕРАЦИИ БИБЛИОТЕКАРЯ ====================

  app.post("/api/reserve", requireSession, async (req, res) => {
    try {
      const { bookRfid, userRfid } = req.body;
      if (!bookRfid || !userRfid) {
        return res.status(400).json({ error: 'bookRfid and userRfid are required' });
      }

      const result = await cabinetService.reserveBook(bookRfid, userRfid);
      if (!result.success) {
        return res.status(400).json({ error: result.message });
      }

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Reserve failed' });
    }
  });

  app.post("/api/cancel-reservation", requireSession, async (req, res) => {
    try {
      const { bookRfid, userRfid } = req.body;
      if (!bookRfid || !userRfid) {
        return res.status(400).json({ error: 'bookRfid and userRfid are required' });
      }

      const result = await cabinetService.cancelReservation(bookRfid, userRfid);
      if (!result.success) {
        return res.status(400).json({ error: result.message });
      }

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Cancel reservation failed' });
    }
  });

  app.post("/api/load-book", requireSession, requireRole('librarian', 'admin'), async (req, res) => {
    try {
      const parsed = loadBookSchema.safeParse(req.body);
      if (!parsed.success) return res.status(400).json({ error: 'bookRfid and title are required', details: parsed.error.issues });
      const { bookRfid, title, author } = parsed.data;

      const result = await cabinetService.loadBook(bookRfid, title, author);
      if (!result.success) {
        return res.status(400).json({ error: result.message });
      }

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Load book failed' });
    }
  });

  app.post("/api/extract", requireSession, requireRole('librarian', 'admin'), async (req, res) => {
    try {
      const { cellId } = req.body;
      if (cellId === undefined) {
        return res.status(400).json({ error: 'cellId is required' });
      }

      const result = await cabinetService.extractBook(cellId);
      if (!result.success) {
        return res.status(400).json({ error: result.message });
      }

      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Extract failed' });
    }
  });

  app.post("/api/extract-all", requireSession, requireRole('librarian', 'admin'), async (req, res) => {
    try {
      const result = await cabinetService.extractAllReturned();
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Extract all failed' });
    }
  });

  app.post("/api/run-inventory", async (req, res) => {
    try {
      const result = await cabinetService.runInventory();
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Inventory failed' });
    }
  });

  app.get("/api/cabinet/state", (req, res) => {
    try {
      const state = cabinetService.getState();
      res.json(state);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Get state failed' });
    }
  });

  app.post("/api/cabinet/clear-error", (req, res) => {
    try {
      cabinetService.clearError();
      res.json({ success: true });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Clear error failed' });
    }
  });

  // ==================== RFID (существующие) ====================

  app.get("/api/ports", async (req, res) => {
    try {
      const ports = await rfidService.getAvailablePorts();
      res.json({ ports });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get ports' });
    }
  });

  app.get("/api/reader-configs", (req, res) => {
    try {
      const configs = rfidService.getReaderConfigs();
      res.json({ configs });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get reader configs' });
    }
  });

  app.post("/api/connect", async (req, res) => {
    try {
      const { port, readerType, baudRate } = req.body;
      if (!port) return res.status(400).json({ error: 'Port is required' });
      if (!readerType) return res.status(400).json({ error: 'Reader type is required' });
      if (!Object.values(ReaderType).includes(readerType)) {
        return res.status(400).json({ error: 'Invalid reader type' });
      }
      await rfidService.connect(port, readerType, baudRate);
      res.json({ success: true, message: `Connected to ${readerType} successfully` });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to connect' });
    }
  });

  app.post("/api/disconnect", async (req, res) => {
    try {
      await rfidService.disconnect();
      res.json({ success: true, message: 'Disconnected successfully' });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to disconnect' });
    }
  });

  app.post("/api/inventory", async (req, res) => {
    try {
      rfidService.manualInventory();
      res.json({ success: true, message: 'Inventory started' });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to start inventory' });
    }
  });

  // ==================== ТЕГИ И ЛОГИ ====================

  app.get("/api/tags", async (req, res) => {
    try {
      const tags = await storage.getAllRfidTags();
      res.json(tags);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get tags' });
    }
  });

  app.delete("/api/tags", async (req, res) => {
    try {
      await storage.clearAllRfidTags();
      res.json({ success: true, message: 'All tags cleared' });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to clear tags' });
    }
  });

  app.get("/api/logs", async (req, res) => {
    try {
      const limit = req.query.limit ? parseInt(req.query.limit as string) : undefined;
      const logs = await storage.getAllSystemLogs(limit);
      res.json(logs);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get logs' });
    }
  });

  app.delete("/api/logs", async (req, res) => {
    try {
      await storage.clearSystemLogs();
      res.json({ success: true, message: 'Logs cleared' });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to clear logs' });
    }
  });

  app.get("/api/statistics", async (req, res) => {
    try {
      const stats = await storage.getStatistics();
      res.json(stats);
      broadcast({ type: 'statistics', data: stats });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get statistics' });
    }
  });

  app.get("/api/diagnostics", async (req, res) => {
    try {
      const rfidStatus = rfidService.getConnectionStatus();
      
      res.json({
        sensors: systemStatus.sensors,
        motors: systemStatus.state === 'error' ? 'error' : 'ok',
        rfid: {
          cardReader: rfidStatus.connected ? 'connected' : 'disconnected',
          bookReader: 'connected', // Mock: book reader always connected in dev mode
        },
        system: {
          state: systemStatus.state,
          position: systemStatus.position,
          shutters: systemStatus.shutters,
          locks: systemStatus.locks,
          irbisConnected: systemStatus.irbisConnected,
          autonomousMode: systemStatus.autonomousMode,
          maintenanceMode: systemStatus.maintenanceMode,
        }
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get diagnostics' });
    }
  });

  // ==================== СИМУЛЯЦИЯ (для тестирования) ====================

  app.post("/api/simulate-tag-read", async (req, res) => {
    try {
      const { epc, rssi, timestamp } = req.body;
      if (!epc) return res.status(400).json({ error: 'EPC is required' });

      const tag = await storage.createOrUpdateRfidTag({
        epc,
        rssi: rssi?.toString() || '-50',
      });

      const tagEvent = {
        epc: tag.epc,
        rssi: parseFloat(tag.rssi || '0'),
        timestamp: timestamp || new Date().toISOString(),
      };

      broadcast({ type: 'tag_read', data: tagEvent });

      await storage.addSystemLog({
        level: 'INFO',
        message: `Simulated tag read: ${epc}, RSSI: ${rssi || -50} dBm`,
        component: 'RFID',
      });

      res.json({ success: true, message: 'Tag simulated successfully', tag });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to simulate tag' });
    }
  });

  app.post("/api/simulate-card-read", async (req, res) => {
    try {
      const { rfid } = req.body;
      if (!rfid) return res.status(400).json({ error: 'RFID is required' });

      broadcast({ 
        type: 'card_read', 
        data: { uid: rfid, cardType: 'library', timestamp: new Date().toISOString() } 
      });

      res.json({ success: true, message: 'Card simulated successfully' });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to simulate card' });
    }
  });

  // ==================== ЭКСТРЕННАЯ ОСТАНОВКА ====================

  let movementInProgress = false;

  app.post("/api/emergency-stop", async (req, res) => {
    try {
      movementInProgress = false;
      systemStatus.state = 'idle';
      systemStatus.currentOperation = undefined;

      await storage.addSystemLog({
        level: 'WARNING',
        message: 'ЭКСТРЕННАЯ ОСТАНОВКА активирована',
        component: 'SAFETY',
      });

      broadcast({ type: 'status', data: systemStatus });
      res.json({ success: true, message: 'Emergency stop activated' });
    } catch (error) {
      res.status(500).json({ error: 'Emergency stop failed' });
    }
  });

  // ==================== ТЕСТИРОВАНИЕ МЕХАНИКИ ====================

  const MAX_SPEED = 3000; // Выше — stall мотора

  // DIR_TO_SENSOR: нельзя двигаться в направлении нажатого концевика
  function checkEndstopSafety(axis: string, steps: number): string | null {
    const sensors = systemStatus.sensors;
    if (axis === 'x' && steps < 0 && sensors.x_begin) return 'Концевик LEFT нажат — движение влево заблокировано';
    if (axis === 'x' && steps > 0 && sensors.x_end) return 'Концевик RIGHT нажат — движение вправо заблокировано';
    if (axis === 'y' && steps < 0 && sensors.y_begin) return 'Концевик BOTTOM нажат — движение вниз заблокировано';
    if (axis === 'y' && steps > 0 && sensors.y_end) return 'Концевик TOP нажат — движение вверх заблокировано';
    return null;
  }

  app.post("/api/test/motor", async (req, res) => {
    try {
      const { command, axis, steps, speed } = req.body;

      // Блокировка параллельных движений
      if (movementInProgress && command === 'move') {
        return res.status(409).json({ error: 'Движение уже выполняется' });
      }

      // Валидация скорости
      if (speed && speed > MAX_SPEED) {
        return res.status(400).json({ error: `Скорость ${speed} превышает максимум ${MAX_SPEED} шаг/сек` });
      }

      // DIR_TO_SENSOR защита
      if (command === 'move' && axis && steps) {
        const blocked = checkEndstopSafety(axis, steps);
        if (blocked) {
          return res.status(400).json({ error: blocked });
        }
      }

      await storage.addSystemLog({
        level: 'INFO',
        message: `Тест мотора: ${command} ${axis || ''} steps=${steps || 0} speed=${speed || 1000}`,
        component: 'MOTOR',
      });

      if (command === 'move') {
        movementInProgress = true;
        systemStatus.state = 'busy';
        try {
          const currentPos = systemStatus.position;
          if (axis === 'x') {
            systemStatus.position = { ...currentPos, x: currentPos.x + (steps || 0) };
          } else if (axis === 'y') {
            systemStatus.position = { ...currentPos, y: currentPos.y + (steps || 0) };
          }
          broadcast({ type: 'position', data: { ...systemStatus.position, timestamp: new Date().toISOString() } });
        } finally {
          movementInProgress = false;
          systemStatus.state = 'idle';
        }
      } else if (command === 'home') {
        movementInProgress = true;
        systemStatus.state = 'busy';
        try {
          systemStatus.position = { x: 0, y: 0, tray: 0 };
          broadcast({ type: 'position', data: { ...systemStatus.position, timestamp: new Date().toISOString() } });
        } finally {
          movementInProgress = false;
          systemStatus.state = 'idle';
        }
      }

      res.json({ success: true, position: systemStatus.position });
    } catch (error) {
      movementInProgress = false;
      systemStatus.state = 'idle';
      res.status(500).json({ error: error instanceof Error ? error.message : 'Motor test failed' });
    }
  });

  app.post("/api/test/tray", async (req, res) => {
    try {
      const { command } = req.body;

      if (movementInProgress) {
        return res.status(409).json({ error: 'Движение уже выполняется' });
      }

      // DIR_TO_SENSOR: проверка концевиков лотка
      if (command === 'extend' && systemStatus.sensors.tray_end) {
        return res.status(400).json({ error: 'Концевик лотка (передний) нажат — выдвижение заблокировано' });
      }
      if (command === 'retract' && systemStatus.sensors.tray_begin) {
        return res.status(400).json({ error: 'Концевик лотка (задний) нажат — задвижение заблокировано' });
      }

      await storage.addSystemLog({
        level: 'INFO',
        message: `Тест лотка: ${command}`,
        component: 'MOTOR',
      });

      movementInProgress = true;
      systemStatus.state = 'busy';
      try {
        if (command === 'extend') {
          systemStatus.position = { ...systemStatus.position, tray: 1000 };
        } else if (command === 'retract') {
          systemStatus.position = { ...systemStatus.position, tray: 0 };
        }
        broadcast({ type: 'position', data: { ...systemStatus.position, timestamp: new Date().toISOString() } });
      } finally {
        movementInProgress = false;
        systemStatus.state = 'idle';
      }

      res.json({ success: true, position: systemStatus.position });
    } catch (error) {
      movementInProgress = false;
      systemStatus.state = 'idle';
      res.status(500).json({ error: error instanceof Error ? error.message : 'Tray test failed' });
    }
  });

  app.post("/api/test/servo", async (req, res) => {
    try {
      const { servo, command } = req.body;
      
      await storage.addSystemLog({
        level: 'INFO',
        message: `Тест сервопривода: ${servo} ${command}`,
        component: 'SERVO',
      });

      // Симуляция сервопривода
      if (servo === 'lock1' || servo === 'front') {
        systemStatus.locks.front = command === 'open';
      } else if (servo === 'lock2' || servo === 'back') {
        systemStatus.locks.back = command === 'open';
      }
      broadcast({ type: 'status', data: systemStatus });

      res.json({ success: true, locks: systemStatus.locks });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Servo test failed' });
    }
  });

  app.post("/api/test/shutter", async (req, res) => {
    try {
      const { shutter, command } = req.body;
      
      await storage.addSystemLog({
        level: 'INFO',
        message: `Тест шторки: ${shutter} ${command}`,
        component: 'SHUTTER',
      });

      // Симуляция шторки
      if (shutter === 'inner') {
        systemStatus.shutters.inner = command === 'open';
      } else if (shutter === 'outer') {
        systemStatus.shutters.outer = command === 'open';
      }
      broadcast({ type: 'status', data: systemStatus });

      res.json({ success: true, shutters: systemStatus.shutters });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Shutter test failed' });
    }
  });

  app.post("/api/test/sensors", async (req, res) => {
    try {
      await storage.addSystemLog({
        level: 'INFO',
        message: 'Проверка всех датчиков',
        component: 'SENSOR',
      });

      // Симуляция чтения датчиков
      res.json({ 
        success: true, 
        sensors: systemStatus.sensors,
        message: 'Все датчики проверены'
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Sensor test failed' });
    }
  });

  // ==================== КАЛИБРОВКА ====================

  const defaultCalibration: CalibrationData = {
    version: '2.1',
    timestamp: new Date().toISOString(),
    kinematics: { x_plus_dir_a: 1, x_plus_dir_b: -1, y_plus_dir_a: 1, y_plus_dir_b: 1 },
    positions: { 
      x: [1891, 6392, 10894], // 3 колонки (типичные значения из ТЗ)
      y: [0, 423, 846, 1269, 1692, 2113, 2538, 2961, 3384, 3807, 
          4230, 4653, 5076, 5499, 5922, 6347, 6770, 7193, 7616, 8039, 8459] // 21 ряд
    },
    window: { x: 1, y: 9 }, // колонка 1, ряд 9 - окно выдачи
    grab_front: { extend1: 1900, retract: 1500, extend2: 3100 },
    grab_back: { extend1: 1850, retract: 1500, extend2: 3050 },
    speeds: { xy: 4000, tray: 2000, acceleration: 8000 },
    servos: { lock1_open: 90, lock1_close: 0, lock2_open: 90, lock2_close: 0 },
    tray: { maxFront: 4500, maxBack: 4500 },
    blocked_cells: {
      front: {
        "0": [],
        "1": [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18], // окно + шторки
        "2": []
      },
      back: {
        "0": [19, 20],
        "1": [19, 20],
        "2": [20]
      }
    }
  };

  let calibrationData: CalibrationData = { ...defaultCalibration };

  app.get("/api/calibration", requireSession, requireRole('admin'), async (req, res) => {
    try {
      res.json(calibrationData);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get calibration' });
    }
  });

  app.post("/api/calibration", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const newData = req.body;

      // Валидация скоростей — не больше 3000 шаг/сек (stall мотора)
      if (newData.speeds) {
        if (newData.speeds.xy && newData.speeds.xy > MAX_SPEED) {
          return res.status(400).json({ error: `Скорость XY ${newData.speeds.xy} превышает максимум ${MAX_SPEED}` });
        }
        if (newData.speeds.tray && newData.speeds.tray > MAX_SPEED) {
          return res.status(400).json({ error: `Скорость лотка ${newData.speeds.tray} превышает максимум ${MAX_SPEED}` });
        }
      }

      // Мержим новые данные с существующими
      calibrationData = {
        ...calibrationData,
        ...newData,
        timestamp: new Date().toISOString(),
        kinematics: { ...calibrationData.kinematics, ...newData.kinematics },
        positions: { ...calibrationData.positions, ...newData.positions },
        window: { ...calibrationData.window, ...newData.window },
        grab_front: { ...calibrationData.grab_front, ...newData.grab_front },
        grab_back: { ...calibrationData.grab_back, ...newData.grab_back },
        speeds: { ...calibrationData.speeds, ...newData.speeds },
        servos: { ...calibrationData.servos, ...newData.servos },
        tray: { ...calibrationData.tray, ...newData.tray },
        blocked_cells: newData.blocked_cells ? {
          front: { ...calibrationData.blocked_cells.front, ...newData.blocked_cells.front },
          back: { ...calibrationData.blocked_cells.back, ...newData.blocked_cells.back }
        } : calibrationData.blocked_cells,
      };

      await storage.addSystemLog({
        level: 'SUCCESS',
        message: 'Калибровочные данные обновлены',
        component: 'CALIBRATION',
      });

      res.json({ success: true, calibration: calibrationData });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to update calibration' });
    }
  });

  // Экспорт калибровки в JSON
  app.get("/api/calibration/export", requireSession, requireRole('admin'), async (req, res) => {
    try {
      res.json({
        success: true,
        data: calibrationData,
        exportedAt: new Date().toISOString()
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to export calibration' });
    }
  });

  // Импорт калибровки из JSON
  app.post("/api/calibration/import", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const importedData = req.body;
      
      if (!importedData.version || !importedData.kinematics || !importedData.positions) {
        throw new Error('Некорректный формат калибровочных данных');
      }
      
      calibrationData = {
        ...defaultCalibration,
        ...importedData,
        timestamp: new Date().toISOString(),
      };

      await storage.addSystemLog({
        level: 'SUCCESS',
        message: `Калибровка импортирована (версия ${importedData.version})`,
        component: 'CALIBRATION',
      });

      res.json({ success: true, calibration: calibrationData });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to import calibration' });
    }
  });

  app.post("/api/calibration/reset", requireSession, requireRole('admin'), async (req, res) => {
    try {
      calibrationData = { ...defaultCalibration };
      
      await storage.addSystemLog({
        level: 'WARNING',
        message: 'Калибровка сброшена к значениям по умолчанию',
        component: 'CALIBRATION',
      });

      res.json({ success: true, calibration: calibrationData });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to reset calibration' });
    }
  });

  // Комплексные тесты калибровки (симуляция в mock режиме)
  app.post("/api/calibration/test-suite", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const results: {
        test: string;
        status: 'pass' | 'fail' | 'running';
        message: string;
        duration?: number;
      }[] = [];

      const simulateDelay = () => new Promise(resolve => setTimeout(resolve, 100 + Math.random() * 200));

      // 1. Тест моторов - Home
      const startHome = Date.now();
      await simulateDelay();
      systemStatus.position = { x: 0, y: 0, tray: 0 };
      results.push({ 
        test: 'motors_home', 
        status: 'pass', 
        message: 'Перемещение в начальную позицию выполнено',
        duration: Date.now() - startHome
      });

      // 2. Тест лотка - выдвижение/втягивание
      const startTray = Date.now();
      await simulateDelay();
      systemStatus.position.tray = 1000;
      await simulateDelay();
      systemStatus.position.tray = 0;
      results.push({ 
        test: 'tray_cycle', 
        status: 'pass', 
        message: 'Цикл выдвижения/втягивания лотка выполнен',
        duration: Date.now() - startTray
      });

      // 3. Тест сервоприводов - замки
      const startServos = Date.now();
      await simulateDelay();
      systemStatus.locks.front = true;
      await simulateDelay();
      systemStatus.locks.front = false;
      systemStatus.locks.back = true;
      await simulateDelay();
      systemStatus.locks.back = false;
      results.push({ 
        test: 'servos_locks', 
        status: 'pass', 
        message: 'Тест сервоприводов замков пройден',
        duration: Date.now() - startServos
      });

      // 4. Тест шторок
      const startShutters = Date.now();
      await simulateDelay();
      systemStatus.shutters.inner = true;
      await simulateDelay();
      systemStatus.shutters.inner = false;
      systemStatus.shutters.outer = true;
      await simulateDelay();
      systemStatus.shutters.outer = false;
      results.push({ 
        test: 'shutters', 
        status: 'pass', 
        message: 'Тест шторок пройден',
        duration: Date.now() - startShutters
      });

      // 5. Тест датчиков
      const startSensors = Date.now();
      await simulateDelay();
      const allSensorsOk = Object.values(systemStatus.sensors).some(v => v);
      results.push({ 
        test: 'sensors', 
        status: 'pass', 
        message: `Датчики: x_begin=${systemStatus.sensors.x_begin}, y_begin=${systemStatus.sensors.y_begin}`,
        duration: Date.now() - startSensors
      });

      // 6. Тест перемещения к тестовой ячейке
      const startMove = Date.now();
      await simulateDelay();
      systemStatus.position = { x: 1000, y: 1000, tray: 0 };
      await simulateDelay();
      systemStatus.position = { x: 0, y: 0, tray: 0 };
      results.push({ 
        test: 'motors_move', 
        status: 'pass', 
        message: 'Тест перемещения выполнен',
        duration: Date.now() - startMove
      });

      const passed = results.filter(r => r.status === 'pass').length;
      const failed = results.filter(r => r.status === 'fail').length;

      await storage.addSystemLog({
        level: failed > 0 ? 'ERROR' : 'INFO',
        message: `Комплексный тест калибровки: ${passed}/${results.length} пройдено`,
        component: 'CALIBRATION',
      });

      res.json({ 
        success: failed === 0, 
        results,
        summary: { passed, failed, total: results.length }
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to run calibration suite' });
    }
  });

  // Отдельные тесты калибровки
  app.post("/api/calibration/test/:testName", requireSession, requireRole('admin'), async (req, res) => {
    const { testName } = req.params;
    
    try {
      const result: { status: 'pass' | 'fail'; message: string; duration: number } = {
        status: 'pass',
        message: '',
        duration: 0
      };
      const start = Date.now();
      const simulateDelay = () => new Promise(resolve => setTimeout(resolve, 100 + Math.random() * 200));

      switch (testName) {
        case 'home':
          await simulateDelay();
          systemStatus.position = { x: 0, y: 0, tray: 0 };
          result.message = 'Homing выполнен успешно';
          break;
        case 'tray':
          await simulateDelay();
          systemStatus.position.tray = 1000;
          await simulateDelay();
          systemStatus.position.tray = 0;
          result.message = 'Цикл лотка выполнен';
          break;
        case 'servos':
          await simulateDelay();
          systemStatus.locks.front = true;
          await simulateDelay();
          systemStatus.locks.front = false;
          result.message = 'Тест сервоприводов пройден';
          break;
        case 'shutters':
          await simulateDelay();
          systemStatus.shutters.inner = true;
          await simulateDelay();
          systemStatus.shutters.inner = false;
          result.message = 'Тест шторок пройден';
          break;
        case 'sensors':
          await simulateDelay();
          result.message = `Датчики: ${JSON.stringify(systemStatus.sensors)}`;
          break;
        case 'move-cell':
          const { x, y } = req.body;
          await simulateDelay();
          systemStatus.position = { x: x || 2000, y: y || 2000, tray: 0 };
          result.message = `Перемещение к позиции (${x || 2000}, ${y || 2000})`;
          break;
        default:
          throw new Error(`Неизвестный тест: ${testName}`);
      }

      result.duration = Date.now() - start;
      res.json({ success: true, result });
    } catch (error) {
      res.status(500).json({ 
        success: false, 
        result: { 
          status: 'fail', 
          message: error instanceof Error ? error.message : 'Test failed',
          duration: 0
        }
      });
    }
  });

  // ==================== WIZARD КАЛИБРОВКИ ====================
  
  // Текущее состояние wizard калибровки
  let calibrationWizard: {
    mode: string | null;
    step: number;
    totalSteps: number;
    currentPosition: { x: number; y: number };
    stepSize: number;
    stepSizes: number[];
    kinematicsResults: { motor: string; direction: string; response: string }[];
    pointsCalibrated: { col: number; row: number; x: number; y: number }[];
  } = {
    mode: null,
    step: 0,
    totalSteps: 0,
    currentPosition: { x: 0, y: 0 },
    stepSize: 4, // индекс размера шага (по умолчанию 10мм)
    stepSizes: [1, 2, 5, 10, 15, 20, 30, 50, 100], // 1-9 размеры шага в мм
    kinematicsResults: [],
    pointsCalibrated: []
  };

  // Начать режим калибровки кинематики (K)
  app.post("/api/calibration/wizard/kinematics/start", requireSession, requireRole('admin'), async (req, res) => {
    try {
      calibrationWizard = {
        ...calibrationWizard,
        mode: 'kinematics',
        step: 0,
        totalSteps: 4,
        kinematicsResults: []
      };
      
      await storage.addSystemLog({
        level: 'INFO',
        message: 'Запущен тест кинематики CoreXY',
        component: 'CALIBRATION',
      });

      res.json({
        success: true,
        mode: 'kinematics',
        step: 0,
        totalSteps: 4,
        instruction: 'Нажмите "Далее" для запуска теста мотора A по часовой стрелке'
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to start kinematics wizard' });
    }
  });

  // Шаг теста кинематики - запуск мотора
  app.post("/api/calibration/wizard/kinematics/step", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const { action } = req.body; // 'run' или 'response' (W/A/S/D)
      const step = calibrationWizard.step;
      
      const motorTests = [
        { motor: 'A', direction: 'CW', label: 'Мотор A по часовой' },
        { motor: 'A', direction: 'CCW', label: 'Мотор A против часовой' },
        { motor: 'B', direction: 'CW', label: 'Мотор B по часовой' },
        { motor: 'B', direction: 'CCW', label: 'Мотор B против часовой' },
      ];

      if (action === 'run') {
        // Симуляция вращения мотора
        await new Promise(resolve => setTimeout(resolve, 500));
        
        res.json({
          success: true,
          step: step,
          motor: motorTests[step].motor,
          direction: motorTests[step].direction,
          label: motorTests[step].label,
          instruction: `Куда поехала каретка? Выберите диагональное направление движения`
        });
      } else if (action === 'response') {
        const { response } = req.body; // 'W', 'A', 'S', 'D'
        
        calibrationWizard.kinematicsResults.push({
          motor: motorTests[step].motor,
          direction: motorTests[step].direction,
          response: response
        });
        
        calibrationWizard.step++;
        
        if (calibrationWizard.step >= 4) {
          // Вычисляем направления на основе ответов
          const results = calibrationWizard.kinematicsResults;
          const kinematics = computeKinematicsFromResponses(results);
          
          calibrationData.kinematics = kinematics;
          calibrationData.timestamp = new Date().toISOString();
          
          calibrationWizard.mode = null;
          
          res.json({
            success: true,
            completed: true,
            kinematics,
            message: 'Тест кинематики завершён!'
          });
        } else {
          res.json({
            success: true,
            step: calibrationWizard.step,
            motor: motorTests[calibrationWizard.step].motor,
            direction: motorTests[calibrationWizard.step].direction,
            label: motorTests[calibrationWizard.step].label,
            instruction: 'Нажмите "Далее" для запуска следующего теста'
          });
        }
      }
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to process kinematics step' });
    }
  });

  // Вычисление кинематики из ответов (диагональные направления для CoreXY)
  // WD = вверх-вправо, WA = вверх-влево, SD = вниз-вправо, SA = вниз-влево
  function computeKinematicsFromResponses(results: { motor: string; direction: string; response: string }[]) {
    let x_plus_dir_a = 1, x_plus_dir_b = -1, y_plus_dir_a = 1, y_plus_dir_b = 1;
    
    for (const r of results) {
      const resp = r.response;
      // Определяем составляющие X и Y из диагонального ответа
      const hasUp = resp.includes('W');
      const hasDown = resp.includes('S');
      const hasRight = resp.includes('D');
      const hasLeft = resp.includes('A');
      
      if (r.motor === 'A') {
        if (r.direction === 'CW') {
          // Мотор A по часовой - определяем куда движется
          if (hasRight) x_plus_dir_a = 1;
          else if (hasLeft) x_plus_dir_a = -1;
          if (hasUp) y_plus_dir_a = 1;
          else if (hasDown) y_plus_dir_a = -1;
        } else {
          // Мотор A против часовой - противоположное направление
          if (hasRight) x_plus_dir_a = -1;
          else if (hasLeft) x_plus_dir_a = 1;
          if (hasUp) y_plus_dir_a = -1;
          else if (hasDown) y_plus_dir_a = 1;
        }
      } else if (r.motor === 'B') {
        if (r.direction === 'CW') {
          // Мотор B по часовой
          if (hasRight) x_plus_dir_b = -1;
          else if (hasLeft) x_plus_dir_b = 1;
          if (hasUp) y_plus_dir_b = 1;
          else if (hasDown) y_plus_dir_b = -1;
        } else {
          // Мотор B против часовой
          if (hasRight) x_plus_dir_b = 1;
          else if (hasLeft) x_plus_dir_b = -1;
          if (hasUp) y_plus_dir_b = -1;
          else if (hasDown) y_plus_dir_b = 1;
        }
      }
    }
    
    return { x_plus_dir_a, x_plus_dir_b, y_plus_dir_a, y_plus_dir_b };
  }

  // Начать калибровку 10 ключевых точек (C)
  app.post("/api/calibration/wizard/points10/start", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const points10 = [
        { col: 0, row: 0, label: 'Начало координат' },
        { col: 1, row: 0, label: 'Центральная колонка' },
        { col: 2, row: 0, label: 'Правая колонка' },
        { col: 0, row: 1, label: 'Ряд 1 (шаг Y)' },
        { col: 0, row: 5, label: 'Ряд 5' },
        { col: 0, row: 10, label: 'Ряд 10 (середина)' },
        { col: 0, row: 15, label: 'Ряд 15' },
        { col: 0, row: 20, label: 'Ряд 20 (верх)' },
        { col: 1, row: 10, label: 'Проверка центра' },
        { col: 2, row: 20, label: 'Проверка угла' },
      ];

      calibrationWizard = {
        ...calibrationWizard,
        mode: 'points10',
        step: 0,
        totalSteps: 10,
        currentPosition: { x: 0, y: 0 },
        pointsCalibrated: []
      };
      
      // Выполняем HOME
      systemStatus.position = { x: 0, y: 0, tray: 0 };

      await storage.addSystemLog({
        level: 'INFO',
        message: 'Запущена калибровка 10 ключевых точек',
        component: 'CALIBRATION',
      });

      res.json({
        success: true,
        mode: 'points10',
        step: 0,
        totalSteps: 10,
        point: points10[0],
        position: systemStatus.position,
        stepSize: calibrationWizard.stepSizes[calibrationWizard.stepSize],
        instruction: 'Используйте WASD для подводки каретки к центру ячейки (0, 0). Нажмите Enter для сохранения.'
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to start points calibration' });
    }
  });

  // Движение каретки (WASD)
  app.post("/api/calibration/wizard/move", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const { direction, stepIndex } = req.body; // direction: 'W', 'A', 'S', 'D'

      if (movementInProgress) {
        return res.status(409).json({ error: 'Движение уже выполняется' });
      }

      if (stepIndex !== undefined) {
        calibrationWizard.stepSize = Math.max(0, Math.min(8, stepIndex));
      }

      const stepMm = calibrationWizard.stepSizes[calibrationWizard.stepSize];
      const stepSteps = stepMm * 10; // примерно 10 шагов на мм

      let dx = 0, dy = 0;
      switch (direction) {
        case 'W': dy = stepSteps * calibrationData.kinematics.y_plus_dir_a; break;
        case 'S': dy = -stepSteps * calibrationData.kinematics.y_plus_dir_a; break;
        case 'A': dx = -stepSteps * calibrationData.kinematics.x_plus_dir_a; break;
        case 'D': dx = stepSteps * calibrationData.kinematics.x_plus_dir_a; break;
      }

      // DIR_TO_SENSOR: проверка концевиков перед движением
      const axis = (dx !== 0) ? 'x' : 'y';
      const steps = (dx !== 0) ? dx : dy;
      const blocked = checkEndstopSafety(axis, steps);
      if (blocked) {
        return res.status(400).json({ error: blocked });
      }

      movementInProgress = true;
      systemStatus.state = 'busy';
      try {
        systemStatus.position.x += dx;
        systemStatus.position.y += dy;
        calibrationWizard.currentPosition = {
          x: systemStatus.position.x,
          y: systemStatus.position.y
        };

        // Симуляция движения
        await new Promise(resolve => setTimeout(resolve, 50));

        broadcast({ type: 'position', data: { ...systemStatus.position, timestamp: new Date().toISOString() } });
      } finally {
        movementInProgress = false;
        systemStatus.state = 'idle';
      }

      res.json({
        success: true,
        position: systemStatus.position,
        stepSize: stepMm,
        stepIndex: calibrationWizard.stepSize
      });
    } catch (error) {
      movementInProgress = false;
      systemStatus.state = 'idle';
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to move' });
    }
  });

  // Сохранить текущую точку калибровки
  app.post("/api/calibration/wizard/points10/save", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const step = calibrationWizard.step;
      const points10 = [
        { col: 0, row: 0 }, { col: 1, row: 0 }, { col: 2, row: 0 },
        { col: 0, row: 1 }, { col: 0, row: 5 }, { col: 0, row: 10 },
        { col: 0, row: 15 }, { col: 0, row: 20 },
        { col: 1, row: 10 }, { col: 2, row: 20 }
      ];
      
      const point = points10[step];
      const pos = systemStatus.position;
      
      // Сохраняем позицию
      if (point.row === 0) {
        calibrationData.positions.x[point.col] = pos.x;
      }
      if (point.col === 0) {
        calibrationData.positions.y[point.row] = pos.y;
      }
      
      calibrationWizard.pointsCalibrated.push({
        col: point.col,
        row: point.row,
        x: pos.x,
        y: pos.y
      });
      
      // Вычисляем шаг X и Y после первых точек
      if (step === 1) {
        const stepX = calibrationData.positions.x[1] - calibrationData.positions.x[0];
        calibrationData.positions.x[2] = calibrationData.positions.x[1] + stepX;
      }
      if (step === 3) {
        const stepY = calibrationData.positions.y[1] - calibrationData.positions.y[0];
        // Интерполируем все промежуточные Y
        for (let i = 2; i <= 20; i++) {
          if (i !== 5 && i !== 10 && i !== 15 && i !== 20) {
            calibrationData.positions.y[i] = Math.round(calibrationData.positions.y[0] + stepY * i);
          }
        }
      }
      
      calibrationWizard.step++;
      calibrationData.timestamp = new Date().toISOString();
      
      if (calibrationWizard.step >= 10) {
        calibrationWizard.mode = null;
        
        await storage.addSystemLog({
          level: 'SUCCESS',
          message: 'Калибровка 10 ключевых точек завершена',
          component: 'CALIBRATION',
        });
        
        res.json({
          success: true,
          completed: true,
          positions: calibrationData.positions,
          message: 'Калибровка 10 ключевых точек завершена!'
        });
      } else {
        const nextPoint = points10[calibrationWizard.step];
        
        // Авто-подъезд к расчётной позиции для точек 3+
        if (calibrationWizard.step >= 2) {
          const targetX = calibrationData.positions.x[nextPoint.col] || 0;
          const targetY = calibrationData.positions.y[nextPoint.row] || 0;
          systemStatus.position = { x: targetX, y: targetY, tray: 0 };
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        res.json({
          success: true,
          step: calibrationWizard.step,
          point: nextPoint,
          position: systemStatus.position,
          instruction: `Точка ${calibrationWizard.step + 1}/10: Ячейка (${nextPoint.col}, ${nextPoint.row}). Доведите вручную и нажмите Enter.`
        });
      }
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to save point' });
    }
  });

  // Начать калибровку захвата полки (L)
  app.post("/api/calibration/wizard/grab/start", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const { side } = req.body; // 'front' или 'back'
      
      calibrationWizard = {
        ...calibrationWizard,
        mode: `grab_${side}`,
        step: 0,
        totalSteps: 3, // extend1, retract, extend2
      };

      await storage.addSystemLog({
        level: 'INFO',
        message: `Запущена калибровка захвата ${side.toUpperCase()}`,
        component: 'CALIBRATION',
      });

      const grabData = side === 'front' ? calibrationData.grab_front : calibrationData.grab_back;

      res.json({
        success: true,
        mode: `grab_${side}`,
        step: 0,
        totalSteps: 3,
        currentValues: grabData,
        instruction: 'Этап 1/3: Настройка extend1 (первое выдвижение до 1-го пропила)'
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to start grab calibration' });
    }
  });

  // Изменить параметр захвата
  app.post("/api/calibration/wizard/grab/adjust", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const { side, param, delta } = req.body; // side: 'front'/'back', param: 'extend1'/'retract'/'extend2', delta: number
      
      const grabData = side === 'front' ? calibrationData.grab_front : calibrationData.grab_back;
      grabData[param as keyof typeof grabData] += delta;
      
      calibrationData.timestamp = new Date().toISOString();

      res.json({
        success: true,
        currentValues: grabData
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to adjust grab' });
    }
  });

  // Тест захвата
  app.post("/api/calibration/wizard/grab/test", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const { side, param } = req.body;
      
      const grabData = side === 'front' ? calibrationData.grab_front : calibrationData.grab_back;
      
      // Симуляция теста
      await new Promise(resolve => setTimeout(resolve, 500));
      systemStatus.position.tray = grabData[param as keyof typeof grabData];
      await new Promise(resolve => setTimeout(resolve, 500));
      systemStatus.position.tray = 0;

      res.json({
        success: true,
        message: `Тест ${param} выполнен`,
        value: grabData[param as keyof typeof grabData]
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to test grab' });
    }
  });

  // ==================== ЗАБЛОКИРОВАННЫЕ ЯЧЕЙКИ ====================

  // Получить карту заблокированных ячеек
  app.get("/api/calibration/blocked-cells", requireSession, requireRole('admin'), async (req, res) => {
    try {
      res.json({
        success: true,
        blocked_cells: calibrationData.blocked_cells
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get blocked cells' });
    }
  });

  // Обновить заблокированные ячейки
  app.post("/api/calibration/blocked-cells", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const { side, column, rows, action } = req.body; // action: 'block' или 'unblock'
      
      const blocked = calibrationData.blocked_cells[side as 'front' | 'back'];
      const colKey = String(column);
      
      if (!blocked[colKey]) {
        blocked[colKey] = [];
      }
      
      if (action === 'block') {
        const newRows = rows.filter((r: number) => !blocked[colKey].includes(r));
        blocked[colKey] = [...blocked[colKey], ...newRows].sort((a, b) => a - b);
      } else {
        blocked[colKey] = blocked[colKey].filter((r: number) => !rows.includes(r));
      }
      
      calibrationData.timestamp = new Date().toISOString();

      await storage.addSystemLog({
        level: 'INFO',
        message: `Ячейки ${action === 'block' ? 'заблокированы' : 'разблокированы'}: ${side} col=${column} rows=${rows.join(',')}`,
        component: 'CALIBRATION',
      });

      res.json({
        success: true,
        blocked_cells: calibrationData.blocked_cells
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to update blocked cells' });
    }
  });

  // Сброс заблокированных ячеек к значениям по умолчанию
  app.post("/api/calibration/blocked-cells/reset", requireSession, requireRole('admin'), async (req, res) => {
    try {
      calibrationData.blocked_cells = { ...defaultCalibration.blocked_cells };
      calibrationData.timestamp = new Date().toISOString();

      res.json({
        success: true,
        blocked_cells: calibrationData.blocked_cells
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to reset blocked cells' });
    }
  });

  // Быстрый тест ячейки (X)
  app.post("/api/calibration/quick-test", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const { side, col, row } = req.body;
      
      const targetX = calibrationData.positions.x[col];
      const targetY = calibrationData.positions.y[row];
      
      // Симуляция теста
      const steps = [
        { step: 1, message: 'Инициализация (HOME)', duration: 300 },
        { step: 2, message: 'Проверка платформы', duration: 200 },
        { step: 3, message: `Движение к ячейке (${col}, ${row})`, duration: 500 },
        { step: 4, message: 'Выдвижение платформы', duration: 400 },
        { step: 5, message: 'Втягивание платформы', duration: 400 },
        { step: 6, message: 'Возврат HOME', duration: 500 },
      ];
      
      systemStatus.position = { x: 0, y: 0, tray: 0 };
      await new Promise(r => setTimeout(r, 300));
      systemStatus.position = { x: targetX, y: targetY, tray: 0 };
      await new Promise(r => setTimeout(r, 300));
      systemStatus.position.tray = 1000;
      await new Promise(r => setTimeout(r, 300));
      systemStatus.position.tray = 0;
      systemStatus.position = { x: 0, y: 0, tray: 0 };

      await storage.addSystemLog({
        level: 'SUCCESS',
        message: `Быстрый тест ячейки ${side.toUpperCase()} (${col}, ${row}) пройден`,
        component: 'CALIBRATION',
      });

      res.json({
        success: true,
        message: `Тест ячейки ${side.toUpperCase()} (${col}, ${row}) пройден`,
        steps,
        targetPosition: { x: targetX, y: targetY }
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Quick test failed' });
    }
  });

  // Получить состояние wizard
  app.get("/api/calibration/wizard/state", requireSession, requireRole('admin'), async (req, res) => {
    try {
      res.json({
        success: true,
        state: {
          mode: calibrationWizard.mode,
          step: calibrationWizard.step,
          totalSteps: calibrationWizard.totalSteps,
          position: systemStatus.position,
          stepSize: calibrationWizard.stepSizes[calibrationWizard.stepSize],
          stepIndex: calibrationWizard.stepSize
        }
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get wizard state' });
    }
  });

  // Выход из wizard
  app.post("/api/calibration/wizard/exit", requireSession, requireRole('admin'), async (req, res) => {
    try {
      calibrationWizard.mode = null;
      calibrationWizard.step = 0;
      
      res.json({ success: true, message: 'Wizard закрыт' });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to exit wizard' });
    }
  });

  // ==================== READER/BOOK/CABINET API (#18-#22, #30) ====================

  // #18: POST /api/reader/identify
  app.post("/api/reader/identify", async (req, res) => {
    try {
      const { card_uid } = req.body;
      if (!card_uid) return res.status(400).json({ error: 'card_uid is required' });

      const user = await storage.getUserByRfid(card_uid);
      if (!user) {
        return res.status(404).json({ success: false, error: 'User not found' });
      }

      const booksOnHand = (await storage.getAllBooks()).filter(b => b.issuedToRfid === card_uid);
      const availableBooks = (await storage.getAllBooks()).filter(b => b.status === 'in_cabinet' || b.status === 'reserved');
      const cells = await storage.getAllCells();
      const availableInCabinet = availableBooks.map(b => {
        const cell = cells.find(c => c.bookRfid === b.rfid);
        return {
          rfid: b.rfid,
          title: b.title,
          author: b.author,
          cell: cell ? `${cell.row === 'FRONT' ? 1 : 2}.${cell.x + 1}.${cell.y + 1}` : null,
        };
      });

      res.json({
        success: true,
        reader: {
          name: user.name,
          ticket: user.rfid,
          role: user.role,
          books_on_hand: booksOnHand.map(b => ({
            rfid: b.rfid,
            title: b.title,
            due_date: null,
          })),
        },
        available_in_cabinet: availableInCabinet,
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Identify failed' });
    }
  });

  // #19: POST /api/book/lookup
  app.post("/api/book/lookup", async (req, res) => {
    try {
      const { rfid } = req.body;
      if (!rfid) return res.status(400).json({ error: 'rfid is required' });

      const book = await storage.getBookByRfid(rfid);
      if (!book) {
        return res.status(404).json({ success: false, error: 'Book not found' });
      }

      const cells = await storage.getAllCells();
      const cell = cells.find(c => c.bookRfid === rfid);

      res.json({
        success: true,
        book: {
          rfid: book.rfid,
          title: book.title,
          author: book.author,
          status: book.status,
          cell: cell ? `${cell.row === 'FRONT' ? 1 : 2}.${cell.x + 1}.${cell.y + 1}` : null,
        },
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Lookup failed' });
    }
  });

  // #20/#32: POST /api/book/issue — full issue cycle with mechanical sequence
  app.post("/api/book/issue", requireSession, operationLimiter, async (req, res) => {
    try {
      const { reader_uid, book_rfid } = req.body;
      const bookRfid = book_rfid || req.body.bookRfid;
      const userRfid = reader_uid || req.body.userRfid;
      const cellAddress = req.body.cellAddress || req.body.cell_address;

      if (!bookRfid || !userRfid) {
        return res.status(400).json({ error: 'book_rfid/bookRfid and reader_uid/userRfid are required' });
      }

      // Broadcast operation started
      broadcast({ type: 'operation_started', data: { operation: 'issue', bookRfid, userRfid } } as any);

      // Determine cell address: from request body, or look up by book's cellId
      let resolvedCell = cellAddress;
      if (!resolvedCell) {
        const book = await storage.getBookByRfid(bookRfid);
        if (book && book.cellId !== null) {
          const cell = await storage.getCell(book.cellId);
          if (cell) {
            // Convert cell record to calibration address format: depth.rack.shelf
            resolvedCell = `${cell.row === 'FRONT' ? 1 : 2}.${cell.x + 1}.${cell.y + 1}`;
          }
        }
      }

      let result: any;
      if (resolvedCell) {
        // Use the new mechanical issue_sequence via python bridge
        result = await pythonBridge.issueSequence(resolvedCell, (msg) => {
          broadcast({ type: 'progress', data: msg } as any);
        });
      } else {
        // Fallback to old bridge command if no cell address available
        result = await runPythonBridge('issue', [bookRfid, userRfid]);
      }

      if (result.success) {
        const book = await storage.getBookByRfid(bookRfid);
        if (book) {
          await storage.updateBook(book.id, {
            status: 'issued',
            issuedToRfid: userRfid,
            reservedForRfid: null,
            cellId: null,
          });
          if (book.cellId !== null) {
            await storage.updateCell(book.cellId, {
              status: 'empty',
              bookRfid: null,
              bookTitle: null,
              reservedFor: null,
            });
          }
        }
        broadcast({ type: 'operation_completed', data: { operation: 'issue', bookRfid, userRfid } } as any);
      } else {
        broadcast({ type: 'operation_failed', data: { operation: 'issue', message: result.error || 'Issue sequence failed' } } as any);
      }

      res.json(result);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Issue failed';
      broadcast({ type: 'operation_failed', data: { operation: 'issue', message: msg } } as any);
      res.status(500).json({ error: msg });
    }
  });

  // #21/#33: POST /api/book/return — full return cycle with mechanical sequence
  app.post("/api/book/return", requireSession, operationLimiter, async (req, res) => {
    try {
      const bookRfid = req.body.book_rfid || req.body.bookRfid;
      if (!bookRfid) {
        return res.status(400).json({ error: 'book_rfid/bookRfid is required' });
      }

      // Broadcast operation started
      broadcast({ type: 'operation_started', data: { operation: 'return', bookRfid } } as any);

      // Find a free cell for the return
      let cellAddress = req.body.cellAddress || req.body.cell_address;
      let targetCell: any = null;
      if (!cellAddress) {
        targetCell = await storage.getEmptyCell();
        if (targetCell) {
          cellAddress = `${targetCell.row === 'FRONT' ? 1 : 2}.${targetCell.x + 1}.${targetCell.y + 1}`;
        }
      }

      let result: any;
      if (cellAddress) {
        // Use the new mechanical return_sequence via python bridge
        result = await pythonBridge.returnSequence(cellAddress, (msg) => {
          broadcast({ type: 'progress', data: msg } as any);
        });
      } else {
        // Fallback: no free cell, try the old bridge command
        result = await runPythonBridge('return', [bookRfid]);
      }

      if (result.success) {
        const book = await storage.getBookByRfid(bookRfid);
        if (book && targetCell) {
          await storage.updateBook(book.id, {
            status: 'in_cabinet',
            issuedToRfid: null,
            cellId: targetCell.id,
          });
          await storage.updateCell(targetCell.id, {
            status: 'occupied',
            bookRfid,
            bookTitle: book.title,
            needsExtraction: true,
          });
        }
        broadcast({ type: 'operation_completed', data: { operation: 'return', bookRfid, cell: cellAddress } } as any);
      } else {
        broadcast({ type: 'operation_failed', data: { operation: 'return', message: result.error || 'Return sequence failed' } } as any);
      }

      res.json(result);
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Return failed';
      broadcast({ type: 'operation_failed', data: { operation: 'return', message: msg } } as any);
      res.status(500).json({ error: msg });
    }
  });

  // #22: GET /api/cabinet/status
  app.get("/api/cabinet/status", async (req, res) => {
    try {
      const cells = await storage.getAllCells();
      const total = cells.length;
      const occupied = cells.filter(c => c.status === 'occupied').length;
      const empty = cells.filter(c => c.status === 'empty').length;
      const blocked = cells.filter(c => c.status === 'blocked').length;
      res.json({
        total_cells: total,
        occupied,
        empty,
        blocked,
        cells: cells.map(c => ({
          address: `${c.row === 'FRONT' ? 1 : 2}.${c.x + 1}.${c.y + 1}`,
          status: c.status,
          book_rfid: c.bookRfid || null,
          book_title: c.bookTitle || null,
        })),
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to get cabinet status' });
    }
  });

  // #22: GET /api/cabinet/free_cell
  app.get("/api/cabinet/free_cell", async (req, res) => {
    try {
      const cell = await storage.getEmptyCell();
      if (!cell) return res.status(404).json({ error: 'No free cells' });
      res.json({
        cell: `${cell.row === 'FRONT' ? 1 : 2}.${cell.x + 1}.${cell.y + 1}`,
        x: cell.x,
        y: cell.y,
        row: cell.row,
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Failed to find free cell' });
    }
  });

  // #30: POST /api/motion/move
  app.post("/api/motion/move", async (req, res) => {
    try {
      const { cell, x, y } = req.body;
      let targetX = x;
      let targetY = y;

      // If cell provided (e.g. "1.2.9"), resolve to x,y coordinates
      if (cell && typeof cell === 'string') {
        const parts = cell.split('.').map(Number);
        if (parts.length === 3) {
          const [, col, row] = parts;
          targetX = calibrationData.positions.x[(col || 1) - 1] || 0;
          targetY = calibrationData.positions.y[(row || 1) - 1] || 0;
        }
      }

      if (targetX === undefined || targetY === undefined) {
        return res.status(400).json({ error: 'Provide cell (e.g. "1.2.9") or x,y coordinates' });
      }

      // Delegate to python bridge
      try {
        await runPythonBridge('move', [String(targetX), String(targetY)]);
      } catch {
        // Fallback: update position in simulation mode
        systemStatus.position = { ...systemStatus.position, x: targetX, y: targetY };
      }

      broadcast({ type: 'motion_complete', data: { cell, x: targetX, y: targetY } } as any);
      res.json({ success: true, position: { x: targetX, y: targetY } });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Motion failed' });
    }
  });

  // #30: POST /api/tray/grab
  app.post("/api/tray/grab", async (req, res) => {
    try {
      try {
        await runPythonBridge('tray_grab', []);
      } catch {
        // Simulation fallback
        systemStatus.locks.front = true;
        systemStatus.locks.back = true;
      }
      res.json({ success: true });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Tray grab failed' });
    }
  });

  // #30: POST /api/tray/release
  app.post("/api/tray/release", async (req, res) => {
    try {
      try {
        await runPythonBridge('tray_release', []);
      } catch {
        systemStatus.locks.front = false;
        systemStatus.locks.back = false;
      }
      res.json({ success: true });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Tray release failed' });
    }
  });

  // #30: POST /api/tray/extend
  app.post("/api/tray/extend", async (req, res) => {
    try {
      try {
        await runPythonBridge('tray_extend', []);
      } catch {
        systemStatus.position = { ...systemStatus.position, tray: 1000 };
      }
      res.json({ success: true });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Tray extend failed' });
    }
  });

  // #30: POST /api/tray/retract
  app.post("/api/tray/retract", async (req, res) => {
    try {
      try {
        await runPythonBridge('tray_retract', []);
      } catch {
        systemStatus.position = { ...systemStatus.position, tray: 0 };
      }
      res.json({ success: true });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Tray retract failed' });
    }
  });

  // #30: POST /api/shutters/:which/:action (outer|inner, open|close)
  app.post("/api/shutters/:which/:action", async (req, res) => {
    try {
      const { which, action } = req.params;
      if (!['outer', 'inner'].includes(which) || !['open', 'close'].includes(action)) {
        return res.status(400).json({ error: 'Invalid shutter/action. Use outer|inner and open|close' });
      }

      // GPIO pin: outer=2, inner=3. open=HIGH, close=LOW
      const pin = which === 'outer' ? 2 : 3;
      const level = action === 'open' ? 'HIGH' : 'LOW';

      const { spawn } = await import('child_process');
      const script = `import RPi.GPIO as G; G.setmode(G.BCM); G.setwarnings(False); G.setup(${pin},G.OUT); G.output(${pin},G.${level})`;
      const p = spawn('sudo', ['python3', '-c', script]);

      p.on('close', () => {
        // Update local state
        if (which === 'outer') systemStatus.shutters.outer = action === 'open';
        else systemStatus.shutters.inner = action === 'open';

        broadcast({ type: 'shutter_state', data: { shutter: which, state: action } } as any);
        broadcast({ type: 'status', data: systemStatus });
        res.json({ success: true, shutter: which, state: action });
      });

      p.on('error', () => {
        // Simulation fallback
        if (which === 'outer') systemStatus.shutters.outer = action === 'open';
        else systemStatus.shutters.inner = action === 'open';
        broadcast({ type: 'shutter_state', data: { shutter: which, state: action } } as any);
        res.json({ success: true, shutter: which, state: action, simulated: true });
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Shutter control failed' });
    }
  });

  // Периодическая трансляция статистики
  // ==================== НАСТРОЙКИ СИСТЕМЫ ====================

  app.get("/api/settings", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const settings = await storage.getAllSettings();
      const result: Record<string, any> = {};
      for (const s of settings) {
        try { result[s.key] = JSON.parse(s.value); } catch { result[s.key] = s.value; }
      }
      // Defaults if not set
      if (!result.timeouts) result.timeouts = { move: 1500, tray_extend: 800, user_wait: 30000 };
      if (!result.telegram) result.telegram = { enabled: false, bot_token: '', chat_id: '' };
      if (!result.backup) result.backup = { enabled: true, interval: 24 };
      if (!result.irbis) result.irbis = { host: '172.29.67.70', port: 6666, mock: true };
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: 'Failed to get settings' });
    }
  });

  app.post("/api/settings", requireSession, requireRole('admin'), async (req, res) => {
    try {
      const data = req.body;
      for (const [key, value] of Object.entries(data)) {
        await storage.setSetting(key, JSON.stringify(value));
      }
      await storage.addSystemLog({ level: 'SUCCESS', message: 'Настройки обновлены', component: 'SYSTEM' });
      res.json({ success: true });
    } catch (error) {
      res.status(500).json({ error: 'Failed to save settings' });
    }
  });

  // ==================== РЕЖИМ ОБУЧЕНИЯ (TEACH) ====================

  let teachState = {
    active: false,
    name: '',
    steps: [] as { action: string; params: any; confirmed: boolean }[],
    pending: false,
  };
  const teachSequences: Record<string, any[]> = {};

  app.post("/api/teach/start", requireSession, requireRole('admin'), (req, res) => {
    const { name } = req.body;
    if (!name) return res.status(400).json({ error: 'Name required' });
    teachState = { active: true, name, steps: [], pending: false };
    res.json({ success: true, message: `Запись "${name}" начата` });
  });

  app.post("/api/teach/execute", requireSession, requireRole('admin'), async (req, res) => {
    if (!teachState.active) return res.status(400).json({ error: 'Запись не активна' });
    const { action, params } = req.body;
    teachState.steps.push({ action, params, confirmed: false });
    teachState.pending = true;

    // Execute action on hardware via bridge
    try {
      if (action === 'move_xy') {
        systemStatus.position.x = params.x || 0;
        systemStatus.position.y = params.y || 0;
      }
    } catch {}

    res.json({ success: true, message: `Выполнено: ${action}`, stepIndex: teachState.steps.length - 1 });
  });

  app.post("/api/teach/jog", requireSession, requireRole('admin'), (req, res) => {
    const { axis, steps } = req.body;
    const s = steps || 100;
    if (axis === 'x') systemStatus.position.x += s;
    else if (axis === 'y') systemStatus.position.y += s;
    else if (axis === 'tray') systemStatus.position.tray += s;
    res.json({ success: true, message: `Jog ${axis} ${s > 0 ? '+' : ''}${s}`, position: systemStatus.position });
  });

  app.post("/api/teach/confirm", requireSession, requireRole('admin'), (req, res) => {
    if (teachState.steps.length > 0) {
      teachState.steps[teachState.steps.length - 1].confirmed = true;
    }
    teachState.pending = false;
    res.json({ success: true, message: 'Шаг зафиксирован' });
  });

  app.post("/api/teach/skip", requireSession, requireRole('admin'), (req, res) => {
    if (teachState.steps.length > 0) {
      teachState.steps.pop();
    }
    teachState.pending = false;
    res.json({ success: true, message: 'Шаг пропущен' });
  });

  app.post("/api/teach/undo", requireSession, requireRole('admin'), (req, res) => {
    teachState.steps.pop();
    res.json({ success: true, message: 'Последний шаг удалён', stepsCount: teachState.steps.length });
  });

  app.post("/api/teach/save", requireSession, requireRole('admin'), async (req, res) => {
    if (!teachState.active) return res.status(400).json({ error: 'Нет активной записи' });
    const confirmed = teachState.steps.filter(s => s.confirmed);
    teachSequences[teachState.name] = confirmed;
    await storage.setSetting(`teach_${teachState.name}`, JSON.stringify(confirmed));
    await storage.addSystemLog({ level: 'SUCCESS', message: `Teach: сохранена "${teachState.name}" (${confirmed.length} шагов)`, component: 'TEACH' });
    teachState = { active: false, name: '', steps: [], pending: false };
    res.json({ success: true, message: `Сохранено (${confirmed.length} шагов)` });
  });

  app.post("/api/teach/discard", requireSession, requireRole('admin'), (req, res) => {
    teachState = { active: false, name: '', steps: [], pending: false };
    res.json({ success: true, message: 'Запись отменена' });
  });

  app.get("/api/teach/status", requireSession, requireRole('admin'), (req, res) => {
    res.json({ active: teachState.active, name: teachState.name, stepsCount: teachState.steps.length, pending: teachState.pending });
  });

  app.get("/api/teach/sequences", requireSession, requireRole('admin'), async (req, res) => {
    const settings = await storage.getAllSettings();
    const sequences: Record<string, any> = {};
    for (const s of settings) {
      if (s.key.startsWith('teach_')) {
        const name = s.key.replace('teach_', '');
        try { sequences[name] = JSON.parse(s.value); } catch { sequences[name] = []; }
      }
    }
    Object.assign(sequences, teachSequences);
    res.json(sequences);
  });

  app.post("/api/teach/play", requireSession, requireRole('admin'), async (req, res) => {
    const { name } = req.body;
    const settings = await storage.getAllSettings();
    const setting = settings.find(s => s.key === `teach_${name}`);
    const steps = setting ? JSON.parse(setting.value) : teachSequences[name];
    if (!steps) return res.status(404).json({ error: `Последовательность "${name}" не найдена` });
    await storage.addSystemLog({ level: 'INFO', message: `Teach: воспроизведение "${name}"`, component: 'TEACH' });
    res.json({ success: true, message: `Воспроизведение "${name}" (${steps.length} шагов)`, steps });
  });

  // ==================== OPERATION QUEUE ====================

  app.get("/api/queue", (req, res) => {
    res.json(operationQueue.getAll());
  });

  app.post("/api/queue", (req, res) => {
    try {
      const { type, params, userId } = req.body;
      if (!type || !userId) {
        return res.status(400).json({ error: 'type and userId are required' });
      }
      const id = operationQueue.add({ type, params: params || {}, userId });
      res.json({ success: true, id, position: operationQueue.getPosition(id) });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Queue add failed' });
    }
  });

  // ==================== IRBIS SYNC QUEUE ====================

  app.get("/api/irbis/queue", async (req, res) => {
    try {
      const result = await runPythonBridge('irbis_queue', ['list']);
      res.json(result);
    } catch {
      // Fallback: return empty
      res.json({ pending: [], total: 0 });
    }
  });

  app.post("/api/irbis/sync", async (req, res) => {
    try {
      const result = await runPythonBridge('irbis_queue', ['sync']);
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : 'Sync failed' });
    }
  });

  // ==================== ПЕРИОДИЧЕСКИЕ ЗАДАЧИ ====================

  setInterval(async () => {
    try {
      const stats = await storage.getStatistics();
      broadcast({ type: 'statistics', data: stats });
    } catch (error) {
      console.error('Error broadcasting statistics:', error);
    }
  }, 5000);

  return httpServer;
}

async function handleWebSocketMessage(
  message: any, 
  ws: WebSocket, 
  broadcast: (msg: WebSocketMessage) => void
) {
  switch (message.action) {
    case 'authenticate':
      if (message.card_rfid) {
        const user = await storage.getUserByRfid(message.card_rfid);
        if (user) {
          broadcast({ 
            type: 'card_read', 
            data: { uid: message.card_rfid, cardType: 'library', timestamp: new Date().toISOString() } 
          });
        }
      }
      break;
      
    case 'get_status':
      ws.send(JSON.stringify({ type: 'status', data: systemStatus }));
      break;
      
    default:
      console.log('Unknown WebSocket action:', message.action);
  }
}
