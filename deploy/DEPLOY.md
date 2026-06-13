# Выкладка новой версии на шкаф (RPi) — runbook

> Цель: выложить модернизированный код (PR #86–#90) на боевой шкаф БЕЗ потерь и БЕЗ
> опасного движения. Делать ТОЛЬКО когда Роман у шкафа (есть движение: хоминг).
> Состояние устройства до выкладки — в `.local-dev/rpi-snapshot-2026-06-13/NOTES.md`.

## Предпосылки (важно понимать)
- На устройстве — старый клон (remote `Rivega42/-`, токен в URL → СНАЧАЛА ротировать токен).
- Боевой сервис — `bookcabinet.service` (python `main.py`), НЕ Node. БД — v1.
- Новый код = v2-схема БД + aiohttp-консолидация. Полевые скрипты механики и фиксы
  считывателей УЖЕ сведены в канон (PR #90, #-этой-ветки) — выкладка их не потеряет.
- ⚠️ Старт `main.py` ДВИГАЕТ механику (замки→500, хоминг XY, хоминг лотка). Рестарт = движение.

## Фаза 0 — заранее (laptop, без устройства)
1. Смержить стек PR в `main` (порядок: #86→#87→#88→#89→#90) ИЛИ выбрать деплой-ветку (tip = chore/deploy-reconcile).
2. `npm run build` → `dist/public` (aiohttp отдаёт фронт сам).

## Фаза 1 — БЭКАП на устройстве (read-only, без движения)
```
ssh admin42@<ip>
cd ~/bookcabinet
# код: спасти текущее состояние (вкл. незакоммиченное) в ветку
git stash list; git status -s
git branch backup/pre-deploy-$(date +%Y%m%d) 2>/dev/null || true
git stash push -u -m pre-deploy 2>/dev/null || true
# БД + calibration.json:
python3 -c "from bookcabinet.monitoring.backup import backup_manager; print(backup_manager.create_backup('pre-deploy'))"
# конфиги, что правили на шкафу 2026-06-13 (уже в каноне, но на всякий):
cp bookcabinet/config.py /tmp/config.py.pre-deploy
sudo cp /etc/udev/rules.d/99-bookcabinet-rfid.rules /tmp/
sudo cp /etc/systemd/system/bookcabinet.service /tmp/
```
Также: tar всего `~/bookcabinet` в /tmp и забрать на ноут (как 2026-06-13).

## Фаза 2 — выложить код (без движения)
Вариант А (git): обновить remote на новый репозиторий и подтянуть код.
```
git remote set-url origin https://github.com/Rivega42/bookcabinet.git   # без токена; авторизация отдельно
git fetch origin
git checkout main && git reset --hard origin/main   # ОСТОРОЖНО: рабочее дерево уже в бэкапе (фаза 1)
```
Вариант Б (rsync с ноута) — если git на устройстве трогать не хочется.
Затем собрать фронт на устройстве или скопировать `dist/`.

Проверить, что фиксы на месте: `grep rfid_uhf_card bookcabinet/config.py`,
`grep 1-1.3.1 /etc/udev/rules.d/99-bookcabinet-rfid.rules` (udev-правило обновить из репо при необходимости).

NFC/pcscd (сверено 2026-06-13): должен быть ОДИН постоянный pcscd через `pcscd-daemon.service`,
а штатные `pcscd.service`/`pcscd.socket` — отключены (иначе дубль → LIBUSB_BUSY, NFC не встаёт).
На устройстве уже настроено; для воспроизводимости/чистой установки:
```
sudo cp deploy/pcscd-daemon.service /etc/systemd/system/
sudo systemctl disable --now pcscd.service pcscd.socket
sudo systemctl daemon-reload && sudo systemctl enable --now pcscd-daemon.service
python3 -c "from smartcard.System import readers; print(readers())"   # → видит ACR (3 интерфейса)
```
Юнит сервиса зависит от `pcscd-daemon.service` (ридер заклеймлен ДО старта → NFC без гонки).

## Фаза 3 — миграция БД (с бэкапом, без движения)
```
sudo bash deploy/migrate.sh   # стоп сервиса → бэкап → alembic upgrade head → старт → проверка
```
migrate.sh останавливает сервис ПЕРЕД миграцией. Старт сервиса в конце = ДВИЖЕНИЕ (хоминг) —
поэтому фазу 3 запускать уже при готовности к движению (см. ворота ниже).
Если миграция упала — БД из бэкапа, разбираться ДО рестарта.

## 🚦 ВОРОТА ДВИЖЕНИЯ (перед стартом сервиса)
Подтвердить вслух: путь каретки свободен, лоток не зажат, людей у механизма нет.
Только после этого — старт сервиса.

## Фаза 4 — проверка по подсистемам (Роман у шкафа)
1. **Старт сервиса** → в журнале: `locks reset → homing ok → tray_homing ok`.
   `journalctl -u bookcabinet -b | grep -E "recovery|homing|tray_homing|locks"`
   Любая ошибка концевика/хоминга = СТОП, разбор, при необходимости откат (фаза 5).
2. **Считыватели:** журнал `RFID карты UHF ✅`, `RFID книги ✅` (NFC — follow-up).
3. **Киоск:** `curl -s localhost:5000/api/status` → 200; на экране — приветствие.
4. **Сухой прогон выдачи/возврата** на ТЕСТОВОЙ книге, по одному циклу, под наблюдением.
   Первое физическое касание лотка — только после успешного `tray_homing`.

## Фаза 5 — ОТКАТ (если что-то не так)
```
sudo systemctl stop bookcabinet
cd ~/bookcabinet
git checkout backup/pre-deploy-<дата>        # вернуть старый код
# БД: восстановить из бэкапа pre-deploy (monitoring/backup.py restore или вручную из backups/)
sudo systemctl start bookcabinet             # ВОРОТА ДВИЖЕНИЯ снова
```

## После выкладки
- Обновить docs/STATE.md (что на шкафу теперь новая версия).
- NFC (ACR1281) — отдельным заходом (постоянный pcscd + ретрай в коде).
- Старый Node-стек (server/) — в `_attic/`, если больше не нужен.
