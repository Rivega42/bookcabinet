# CLAUDE.md — BookCabinet canonical project context

This file is the canonical project brief for Claude Code working on BookCabinet.
Read this file first. Treat it as the highest-level project map.
If this file conflicts with older scattered docs, prefer this file plus the current code.

---

## 1. What this project is

BookCabinet is a Raspberry Pi based automated library cabinet / smart shelf.
It combines:
- mechanical motion system for positioning and delivery,
- RFID/NFC identification of users and books,
- local server/UI on Raspberry Pi,
- future / partial integration with IRBIS library system.

The project is both:
- a real physical machine with motors, endstops, relays, servos, readers, power constraints,
- and a software system with Python backend, hardware drivers, calibration scripts, service management, logs, and UI/API.

Claude must always treat BookCabinet as a hardware-software system, not as a pure software repo.

---

## 2. Environment and reality of deployment

### Actual target environment
- Target machine: Raspberry Pi 3 on the cabinet
- Repo on device: `~/bookcabinet`
- Primary runtime language: Python
- Service name used in current quickstart: `bookcabinet`
- pigpio is used for some motion scripts and must be running for pigpio-based tools

### Important operational reality
This project has evolved in-place on real hardware.
Because of that, the repo contains:
- current code,
- historical docs,
- debug scripts,
- calibration utilities,
- experimental motion scripts,
- partially outdated assumptions.

Do not assume every `.md` file is current.
Do not assume every tool script is production-ready.
Do not assume every older decision still reflects the freshest cabinet state.

---

## 3. Mission-critical rule set for Claude Code

### Safety first
When working on BookCabinet:
1. Do not casually change motion logic that can drive real hardware into a stop.
2. Do not silently rewrite GPIO mappings from old assumptions.
3. Do not collapse experimental scripts into "production truth" without checking current code and recent notes.
4. Do not remove debug/calibration tools until their knowledge is captured elsewhere.
5. Do not assume a movement direction, home corner, or endstop polarity unless explicitly confirmed in current code and this file.

### Editing discipline
Before changing mechanics / GPIO / homing code:
1. read the current relevant file fully,
2. check matching config / docs / scripts,
3. identify contradictions,
4. preserve safe guards,
5. prefer small, testable changes.

### Physical access rule
Some things require Roman at the cabinet.
Claude can prepare code, docs, logs, scripts, and safe test flows.
Claude must not pretend to have validated real motor behavior unless Roman actually ran the test.

---

## 4. Repository purpose and main zones

This repo mixes several layers.

### Core project zones
- `bookcabinet/` — main Python application
- `bookcabinet/config.py` — GPIO mapping and core runtime constants
- `bookcabinet/hardware/` — hardware drivers and motor code
- `bookcabinet/mechanics/` — motion / calibration logic
- `tools/` — real hardware scripts, calibration tools, diagnostics, homing experiments
- `docs/` — project docs, historical decisions, logs, TODOs, troubleshooting
- `attached_assets/` — imported manuals, pasted logs, vendor / integration artifacts

### Important note
For cabinet motion and hardware truth, the most important sources are currently:
- `bookcabinet/config.py`
- `bookcabinet/hardware/motors.py`
- `tools/corexy_pigpio.py`
- `tools/homing_pigpio.py`
- `docs/HARDWARE.md`

But they do not perfectly agree. That is a known project fact.

---

## 5. High-confidence hardware map (freshest merged understanding)

Below is the freshest consolidated hardware map based on current repo state plus later cabinet discoveries already reflected in code.

### 5.1 CoreXY XY motion
- `MOTOR_A_STEP = 14`
- `MOTOR_A_DIR  = 15`
- `MOTOR_B_STEP = 19`
- `MOTOR_B_DIR  = 21`

Direction mapping currently documented / used:
- X right  => A=1, B=1
- X left   => A=0, B=0
- Y up     => A=1, B=0
- Y down   => A=0, B=1

This mapping appears in motion scripts and is one of the key cabinet truths.

### 5.2 XY endstops
- `SENSOR_LEFT   = 9`
- `SENSOR_RIGHT  = 10`
- `SENSOR_BOTTOM = 8`
- `SENSOR_TOP    = 11`

Current motion scripts use these as the XY limit inputs.

### 5.3 Tray / platform motor
- `TRAY_STEP = 18`
- `TRAY_DIR  = 27`
- `TRAY_ENA_1 = 25`
- `TRAY_ENA_2 = 26`

Critical fact:
- pins 25 and 26 must be driven LOW before tray motor movement.

### 5.4 Tray endstops
- `SENSOR_TRAY_END   = 7`
- `SENSOR_TRAY_BEGIN = 20`

Known issue:
- pin 20 is noisy / bouncing and requires software debounce.

### 5.5 Locks (servos)
- `LOCK_FRONT = 12`
- `LOCK_REAR  = 13`
- PWM 50 Hz
- open  => duty ~2.5
- close => duty ~7.5

Critical terminology inversion:
- "open" means tongue lowered / shelf is free,
- "close" means tongue raised / shelf is locked.

### 5.6 Shutters (relay outputs)
Freshest code-level mapping in `bookcabinet/config.py`:
- `SHUTTER_OUTER = 2`
- `SHUTTER_INNER = 3`
- LOW = closed
- HIGH = open

Important:
- `docs/HARDWARE.md` is outdated here, it still says shutters were not found.
- Current code says shutters are on pins 2 and 3, and this is the fresher truth.

---

## 6. Cabinet geometry and logical model

Current `bookcabinet/config.py` states:
- 2 rows: `FRONT`, `BACK`
- 3 columns
- 21 positions
- total cells = 126
- window = `{ row: FRONT, x: 1, y: 9 }`

This means the cabinet logic is modeled as a grid / addressing system layered on top of physical XY + tray + locks.

Additional historical physical calibration knowledge used in prior work:
- shelf Y spacing was previously treated as roughly linear,
- real calibration utilities exist in `tools/calib_4endstops.py`, `tools/calib_racks.py`, `tools/calibrate_xy.py`,
- do not rewrite coordinate assumptions without checking those tools and the latest measured data.

---

## 7. Motion architecture and patterns

### 7.1 Two motion worlds exist in this repo
There are two important motion approaches in the project history:

1. older / app-level motion in `bookcabinet/hardware/motors.py`
2. newer pigpio-based real homing / diagnostic scripts in `tools/*.py`

They are related, but not identical.

### 7.2 App-level motor layer
`bookcabinet/hardware/motors.py`:
- controls XY and tray,
- contains CoreXY kinematics,
- uses pigpio if available, otherwise mock mode,
- has emergency stop support,
- includes a `home_with_sensors()` implementation, but it is not the only truth in the repo.

This file is important but should not be treated as the only authoritative homing implementation.

### 7.3 Current safe / important pigpio movement pattern
`tools/corexy_pigpio.py` is one of the most important current references.
It uses:
- pigpio wave_chain,
- callback-triggered endstop stop,
- `wave_tx_stop()` for immediate stop on endstop,
- glitch filters on endstops,
- direction-to-endstop blocking via `DIR_TO_SENSOR`.

Key parameters in this historical diagnostic script:
- `FAST = 1500`
- `SLOW = 400`
- `BACK = 200`
- `WAVE_SEG = 200`

Current live-confirmed motion baseline is now in `tools/corexy_motion_v2.py`.
`tools/homing_pigpio.py` is now the stable CLI wrapper around that layer:
- `FAST = 800`
- `SLOW = 300`
- X backoff = 300
- Y backoff = 500
- stop condition = callback plus direct polling fallback of `pi.read(stop_sensor)`

Known safe lessons from cabinet work:
- speed above roughly 3000 could stall,
- callback alone was not reliable enough in long `wave_chain`,
- endstop glitch filtering is essential,
- 1500/400 caused belt slip in a live session on 2026-04-10, so 800/300 is the safer baseline.

### 7.4 Direction safety pattern
`tools/corexy_pigpio.py` includes a protective map:
- moving toward bottom => blocked by bottom sensor
- moving toward top    => blocked by top sensor
- moving toward right  => blocked by right sensor
- moving toward left   => blocked by left sensor

This is exactly the kind of guard that must not be removed lightly.

---

## 8. Resolved home truth: HOME corner confirmed in live cabinet session

On 2026-04-10, a live cabinet session confirmed the actual physical home corner.
The confirmation path was:
- reading live endstop states without movement,
- making micro-movements and verifying sensor transitions,
- fixing the long `wave_chain` stop bug in `tools/homing_pigpio.py`,
- successfully completing full homing on the real cabinet.

### Canonical truth now
- physical HOME = `LEFT + BOTTOM`
- `bookcabinet/config.py` must use `LEFT_BOTTOM`
- `tools/corexy_motion_v2.py` is the canonical motion / homing layer
- `tools/homing_pigpio.py` is the stable operator entrypoint / wrapper
- older `RIGHT+BOTTOM` mentions are historical and stale

### Working rule
Do not reintroduce `RIGHT_BOTTOM` into config or docs unless Roman confirms a different physical truth in a new live cabinet session.

### Historical note
`tools/corexy_pigpio.py` and some older docs still preserve the earlier `RIGHT+BOTTOM` assumption.
Treat those as investigation history, not as the current final truth.

---

## 9. Endstop electrical logic is also inconsistent across old docs

This project contains historical contradictions about endstop polarity and pull mode.

Examples:
- `docs/HARDWARE.md` says endstops are `INPUT, PUD_UP, HIGH = triggered`
- `tools/corexy_motion_v2.py` keeps the current XY endstop assumptions: `pressed = 1`, `free = 0`, `PUD_OFF`
- older docs elsewhere discuss LOW-triggered sensor logic for some sensor classes

### Working rule for Claude
Do not generalize one sensor rule to all sensors.
There are at least two sensor families / histories in the project:
- optical cabinet / RFID-adjacent sensor logic from older software layers,
- XY/tray endstop logic used in recent motion scripts.

When changing endstop code:
1. inspect the actual current script,
2. verify its current pull mode and edge callback,
3. do not "normalize" the logic just because older docs say something else.

---

## 10. RFID / identification subsystem

The repo documents three reader lines:
- `ACR1281U-C` — NFC / cards / ЕКП, working
- `IQRFID-5102` — UHF, short range, protocol-focused, serial
- `RRU9816` — UHF reader, historically investigated / partially integrated

### Current repo inconsistency
- `QUICKSTART.md` says `RRU9816` works ~20 cm
- `PROJECT_INSTRUCTIONS.md` says `RRU9816` is not used because it requires Windows DLL

So Claude must not claim a single final truth without checking the active code path.

### High-confidence practical truth
- NFC path exists and is important.
- IQRFID-5102 is important and has hardware range limitations.
- RRU9816 status in docs is inconsistent and should be treated as unresolved / context-dependent.

### Protocol facts that are repeated and probably important
- UHF protocol family around IQRFID-5102 uses `0xA0`, not `0x04`
- checksum historically documented as `(~SUM + 1) & 0xFF`
- IRBIS uses TCP port `6666` and `cp1251`

---

## 11. Freshest known cabinet truths that override stale docs

These are especially important for avoiding repeated mistakes.

### 11.1 Shutters are found
Current code indicates shutters are mapped as:
- outer shutter => pin 2
- inner shutter => pin 3

If an old doc says shutters are unknown, that doc is stale.

### 11.2 Tray enable pins matter
Pins 25 and 26 are not optional trivia.
They must be initialized LOW before tray movement.

### 11.3 Motion safety relies on conservative speeds
Current confirmed safe homing baseline after live cabinet testing on 2026-04-10:
- FAST = 800
- SLOW = 300

Historical 1500/400 settings can still appear in older scripts, but they are no longer the recommended homing baseline after belt slip was observed.
Do not increase speeds casually.

### 11.4 Endstop filtering matters
Recent working motion scripts use glitch filters.
Removing them is dangerous and likely to reintroduce false triggers / missed stops.

### 11.5 The repo contains real debug value
Files like:
- `patch_*.py`
- `x_homing_debug*.py`
- `tools/calib_*.py`
- backups of homing scripts
are not elegant, but they encode real cabinet investigation history.
Do not delete them unless their knowledge is migrated.

---

## 12. Operational commands Claude should know

### Basic repo / service workflow
```bash
cd ~/bookcabinet
sudo systemctl restart bookcabinet
sudo systemctl status bookcabinet
journalctl -u bookcabinet -f
```

### pigpio sanity
```bash
pigs t
```
If this fails, pigpio-based motion scripts may not work correctly.

### Motion / homing scripts of interest
```bash
python3 tools/corexy_pigpio.py
python3 tools/homing_pigpio.py
```

### Calibration-related tools
```bash
python3 tools/calib_4endstops.py
python3 tools/calib_racks.py
python3 tools/calibrate_xy.py
```

Use these only with explicit awareness that they may move hardware.

---

## 13. Current documentation quality assessment

This repo already has a lot of useful documentation, but not yet one perfectly synchronized spec.

### Good documents
- `QUICKSTART.md`
- `docs/HARDWARE.md`
- `docs/DECISIONS.md`
- `docs/DEVLOG.md`
- `docs/TODO.md`
- `docs/GLOSSARY.md`

### But they have problems
- some are outdated,
- some contradict current code,
- some contradict later field discoveries,
- some reflect historical hardware states, not final current truth.

This `CLAUDE.md` exists specifically to reduce those errors.

---

## 14. How Claude should work in this repo

### Default workflow
1. Read this `CLAUDE.md` first.
2. Identify which subsystem is being touched:
   - mechanics,
   - GPIO / motion,
   - tray,
   - shutters / locks,
   - RFID,
   - IRBIS integration,
   - UI / API.
3. Read only the files relevant to that subsystem.
4. Check whether there are contradictions with docs or config.
5. If mechanics or GPIO are involved, preserve safety assumptions.
6. Prefer explicit notes in code / docs when a contradiction exists.

### When editing motion code
Always check together:
- `bookcabinet/config.py`
- `bookcabinet/hardware/motors.py`
- `tools/corexy_pigpio.py`
- `tools/corexy_motion_v2.py`
- `tools/homing_pigpio.py`
- `docs/HARDWARE.md`

### When editing documentation
Do not simply copy stale doc content into a new file.
Reconcile it with current code.
If there is uncertainty, document the uncertainty explicitly.

---

## 15. Current unresolved contradictions / risks to keep visible

1. **HOME corner conflict**
   - repo-level stable docs point to RIGHT+BOTTOM
   - experimental homing script points to LEFT+BOTTOM

2. **Endstop polarity / pull mode history is inconsistent**
   - some docs imply PUD_UP/HIGH-triggered
   - newer homing script uses PUD_OFF and pressed=1

3. **RRU9816 status is inconsistent across docs**
   - partly active in some docs,
   - deprecated / not used in others.

4. **Some docs are stale**
   - especially around shutters and certain hardware assumptions.

5. **TODO / DEVLOG lag reality**
   - some newer cabinet work exists in code and ad-hoc scripts more than in curated docs.

---

## 16. What this file should prevent

This file exists to prevent Claude Code from making these classic mistakes:
- assuming stale hardware mapping from old markdown,
- "cleaning up" debug scripts that still carry field knowledge,
- picking the wrong HOME corner by reading only one file,
- changing GPIO logic without checking current motion scripts,
- treating BookCabinet as a pure app instead of a real machine.

---

## 17. If you need to update this file

When updating `CLAUDE.md`:
- prefer freshest code over stale docs,
- explicitly call out contradictions,
- preserve safety notes,
- include only facts or clearly marked uncertainties,
- do not pretend unresolved hardware truth is resolved.

If Roman confirms a physical truth during a live cabinet session, update this file accordingly.

