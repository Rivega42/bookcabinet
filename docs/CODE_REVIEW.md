# Code Review: BookCabinet Repository

**Date:** 2026-04-10
**Reviewer:** Claude Code (automated)
**Scope:** Full repository review

---

## Project Overview

BookCabinet is an automated library book dispensing system using:
- **Frontend:** React + TypeScript + Tailwind (Vite, TanStack Query)
- **Backend:** Express.js (TypeScript) + Python (Raspberry Pi hardware control)
- **Hardware:** CoreXY mechanics, RFID readers (NFC ACR1281, UHF RRU9816, IQRFID-5102), stepper motors, servos, sensors
- **Database:** In-memory (TS) + SQLite (Python) + PostgreSQL schema (Drizzle ORM, unused?)
- **Integration:** IRBIS library system, Telegram notifications

---

## CRITICAL Issues

### 1. SQL Injection in Python Database Layer
**File:** `bookcabinet/database/db.py:191-198, 238-244`
```python
def update_cell(self, cell_id: int, **kwargs) -> bool:
    set_clause = ', '.join(f'{k} = ?' for k in kwargs.keys())
    values = list(kwargs.values()) + [cell_id]
    cursor.execute(f'UPDATE cells SET {set_clause} WHERE id = ?', values)
```
Column names from `kwargs.keys()` are interpolated directly into SQL. While values use parameterized queries, **column names are not sanitized**. If an attacker controls the keys (e.g., through the PATCH /api/cells/:id endpoint), they can inject SQL via column names like `"status = 'hacked', book_rfid"`.

**Fix:** Whitelist allowed column names before constructing the query.

### 2. Remote Code Execution via spawn()
**File:** `server/routes.ts:83-98, 202-292`
Python code is embedded in template strings and executed via `spawn('python3', ['-c', script])` and `spawn('sudo', ['python3', '-c', script])`. While the shutter actions use a whitelist (line 94-95), the RFID test endpoint at line 244 interpolates `readerId` into Python code:
```typescript
const port = readerId === 'rru9816' ? '/dev/ttyUSB0' : '/dev/ttyUSB2';
const script = `PORT = '${readerId === ...}'`;
```
The ternary prevents direct injection, but the pattern is extremely fragile. Any future changes weakening the validation could enable RCE.

**Fix:** Never embed user input in executable code. Use config files or command-line arguments.

### 3. Hardcoded Auth Daemon Path with sudo
**File:** `server/routes.ts:53-56`
```typescript
const daemonPath = '/home/admin42/bookcabinet/bookcabinet/services/auth_shutter_daemon.py';
const daemon = spawn('sudo', ['python3', daemonPath], ...);
```
The server spawns a Python daemon with `sudo` using a hardcoded path. If this path is writable by a non-root user, it becomes a privilege escalation vector. Also auto-restarts on crash (line 74), creating a persistent backdoor opportunity.

### 4. Error Handler Re-throws After Response
**File:** `server/index.ts:63-68`
```typescript
app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
    res.status(status).json({ message });
    throw err;  // BUG: re-throws after response sent
});
```
The `throw err` after `res.json()` will crash the server or trigger `uncaughtException`. This is caught by the global handler (line 11) which may call `process.exit(1)`.

**Fix:** Remove the `throw err;` line. Use a logger instead.

---

## HIGH Severity Issues

### 5. No Authentication/Authorization on API Endpoints
**File:** `server/routes.ts` (all endpoints)
No middleware validates authentication for ANY endpoint. Critical operations like `PATCH /api/cells/:id`, `POST /api/users`, `POST /api/issue`, `POST /api/load-book` are completely unprotected. Anyone on the network can:
- Create admin users
- Issue/return books
- Control shutters and motors
- Change calibration data

### 6. Single Global Session (No Multi-User Support)
**File:** `server/routes.ts:41-44`
```typescript
let currentSession: { user: User | null; expiresAt: Date | null } = { user: null, expiresAt: null };
```
A single global variable holds the current session. If two users interact simultaneously, they share/overwrite each other's session. Same issue in Python: `bookcabinet/business/auth.py:13` with `self.current_user`.

### 7. Blocking time.sleep() in Async Context
**File:** `bookcabinet/hardware/motors.py:70-71, 87-88, 116, 237, etc.`
```python
while self.pi.wave_tx_busy():
    time.sleep(0.01)  # Blocks the entire event loop!
```
`time.sleep()` in `async` methods blocks the asyncio event loop, preventing all other coroutines from running. During motor operations (which can take seconds), the entire system becomes unresponsive.

**Fix:** Use `await asyncio.sleep(0.01)` instead.

### 8. Duplicate pigpio Instances
**Files:** `bookcabinet/hardware/gpio_manager.py:19`, `bookcabinet/hardware/motors.py:22`
Both `GPIOManager` and `Motors` create their own `pigpio.pi()` connection. Multiple pigpio connections can cause resource conflicts and unpredictable behavior on the Raspberry Pi.

**Fix:** Use a single shared pigpio instance (e.g., from `gpio_manager`).

### 9. Bare except Clauses
**Files:**
- `bookcabinet/rfid/card_reader.py:52` — `except:` with `break`
- `bookcabinet/rfid/card_reader.py:77` — `except:` with `pass`
- `bookcabinet/business/auth.py:151` — `except:` returns False
- `server/routes.ts:64, 302` — empty `catch {}`

Bare exceptions hide bugs, mask `KeyboardInterrupt`, and make debugging impossible.

### 10. Database Schema Mismatch
**File:** `shared/schema.ts` vs `bookcabinet/database/db.py`
The TypeScript schema uses Drizzle ORM with PostgreSQL (`pgTable`), but the Python backend uses SQLite. Field names differ (camelCase vs snake_case), schemas have different columns (e.g., TS has `email`, `phone`, `blocked` on users; Python doesn't). The in-memory TS storage and the SQLite DB will drift.

---

## MEDIUM Severity Issues

### 11. .gitignore Malformed Entry
**File:** `.gitignore:6`
```
*.tar.gz__pycache__/
```
Missing newline between `*.tar.gz` and `__pycache__/`. This means `__pycache__/` directories are NOT ignored and `.tar.gz` files are also not properly matched.

**Fix:**
```
*.tar.gz
__pycache__/
```

### 12. Hardcoded Absolute Paths
**Files:**
- `bookcabinet/config.py:88` — `DATABASE_PATH = '/home/admin42/bookcabinet/...'`
- `bookcabinet/config.py:89` — `LOG_FILE = '/home/admin42/bookcabinet/...'`
- `server/routes.ts:53` — daemon path `/home/admin42/...`

These will break on any machine where the user isn't `admin42`.

### 13. No Input Validation on API Bodies
**File:** `server/routes.ts:420-428, 461-468, 510-517`
`req.body` is passed directly to storage functions without validation. Despite having Zod schemas defined in `shared/schema.ts`, they are never used to validate incoming request data.

### 14. WebSocket Messages Not Validated
**File:** `server/routes.ts:154-161`
Incoming WebSocket messages are parsed from JSON but never validated against a schema. Malformed or malicious messages could cause unexpected behavior.

### 15. No Rate Limiting
**File:** `server/routes.ts` (all endpoints)
No rate limiting on any endpoint. An attacker could flood the RFID test endpoint (spawning unlimited Python processes) or the motor control endpoints.

### 16. GPIO Pin Conflicts in Config
**File:** `bookcabinet/config.py:17-18, 33-34`
```python
'SENSOR_LEFT': 9,
'SENSOR_RIGHT': 10,
...
'SENSOR_X_BEGIN': 9,   # = SENSOR_LEFT
'SENSOR_X_END': 10,    # = SENSOR_RIGHT
```
Aliases defined for backward compatibility, but having two names for the same pin could lead to double initialization or conflicting configurations.

### 17. CoreXY Kinematics Inconsistency
**Files:** `bookcabinet/mechanics/corexy.py:51-52` vs `bookcabinet/hardware/motors.py:104-105`
```python
# corexy.py
steps_a = dx * kin['x_plus_dir_a'] + dy * kin['y_plus_dir_a']
steps_b = dx * kin['x_plus_dir_b'] + dy * kin['y_plus_dir_b']

# motors.py
steps_a = dx + dy
steps_b = -dx + dy
```
Two different CoreXY kinematics implementations. `motors.py` uses hardcoded signs, while `corexy.py` uses calibrated signs. If both are used, the machine will move in wrong directions.

### 18. `as any` Type Safety Bypass
**File:** `client/src/pages/kiosk.tsx` (13+ instances)
Calibration speed/servo mutations bypass TypeScript type checking with `as any`, allowing invalid values to be sent to the hardware control API.

### 19. Missing .env.example
No `.env.example` file documenting required environment variables. The project uses `MOCK_MODE`, `HOST`, `PORT`, `DATABASE_PATH`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `IRBIS_HOST`, `IRBIS_PORT`, etc., but new developers won't know what to set.

---

## LOW Severity Issues

### 20. Console Logging in Production
Multiple files use `print()` and `console.log()` instead of structured logging. Makes production debugging difficult.

### 21. No Tests
No test files, no test configuration, no CI pipeline. Zero test coverage for a system controlling physical hardware.

### 22. Dead Code — Monitor Loop
**File:** `bookcabinet/rfid/card_reader.py:48-53`
```python
async def _monitor_loop(self):
    while self._running:
        try:
            await asyncio.sleep(0.5)
        except:
            break
```
This loop does nothing — it just sleeps. The actual card monitoring is not implemented.

### 23. KioskPage Component Too Large
**File:** `client/src/pages/kiosk.tsx` (~1800 lines, 28 useState calls)
Single component handles all kiosk UI logic. Should be broken into smaller components for maintainability.

### 24. Unused Drizzle ORM Configuration
**Files:** `drizzle.config.ts`, `shared/schema.ts`
Drizzle ORM is configured for PostgreSQL, but the actual data storage is in-memory (TS side) and SQLite (Python side). The Drizzle schemas are used only for type definitions, never for actual DB queries.

### 25. Missing Error Boundary in React
**File:** `client/src/App.tsx`
No React Error Boundary. Any component error crashes the entire kiosk UI.

### 26. Accessibility Issues
**File:** `client/src/pages/kiosk.tsx`
No ARIA labels, no keyboard navigation, color-only status indicators. This is a public-facing kiosk system.

### 27. No CI/CD Pipeline
**File:** `.github/` — only contains `copilot-instructions.md`
No GitHub Actions workflows for linting, testing, building, or deploying.

### 28. Install Script Uses --break-system-packages
**File:** `bookcabinet/install_raspberry.sh:167`
```bash
pip3 install --break-system-packages pyscard
```
This flag bypasses Python package manager protections on modern Debian and can corrupt the system Python.

---

## Architecture Observations

### Positive
- Clean separation between hardware abstraction and business logic in Python backend
- Good mock mode support for development without hardware
- WebSocket for real-time updates is well-structured
- Calibration system is comprehensive for the CoreXY mechanism
- Defensive coding for GPIO operations with fallback to mock mode

### Concerns
- **Two separate backends** (Express.js + Python) managing different aspects of the same system, leading to state synchronization issues
- **Three different databases** in use conceptually (in-memory TS, SQLite Python, PostgreSQL schema defined but unused)
- **No clear deployment story** — Replit config suggests cloud development, but the system requires physical Raspberry Pi hardware
- **Auth is essentially disabled** — no API middleware, single global session
- **No automated testing** for a system that controls physical motors and dispensing mechanisms

---

## Priority Recommendations

1. **Immediately:** Fix SQL injection in `db.py` column name interpolation
2. **Immediately:** Add authentication middleware to Express API
3. **Immediately:** Fix `throw err` in error handler
4. **Soon:** Replace `time.sleep()` with `await asyncio.sleep()` in motor code
5. **Soon:** Consolidate to a single database strategy
6. **Soon:** Add input validation using existing Zod schemas
7. **Soon:** Fix `.gitignore` malformed entry
8. **Later:** Add CI/CD pipeline with tests
9. **Later:** Break up large components (kiosk.tsx)
10. **Later:** Add React Error Boundary and accessibility features
