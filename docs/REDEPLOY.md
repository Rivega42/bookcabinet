# Редеплой `main` → шкаф (RPi) — рантбук

> Цель: выкатить наш `main` (со всеми #96–101) на шкаф, ничего не потеряв.
> Делать ТОЛЬКО при Романе у шкафа (старт сервиса = движение). Не на ходу.
> Состояние RPi на 2026-06-20: HEAD `ca56bfd` (старый), рабочее дерево = наши же
> прошлые фиксы незакоммичены + CRLF-шум + наш код поверх (untracked). Сверено:
> уникального hardware-кода на шкафу нет (см. `docs/STATE.md`/PR #101). Поэтому
> сводим жёстко на `origin/main` ПОСЛЕ бэкапа.

Хост: `admin42@10.94.22.193` (IP меняется — проверять). Репо: `~/bookcabinet`.

## 0. Предусловия
- Роман у шкафа. Никто не пользуется киоском.
- `pigpiod` поднят (`pigs t`).

## 1. Бэкап (обязательно, до всего)
```bash
cd ~/bookcabinet
TS=$(date +%Y%m%d_%H%M%S)
# БД
cp bookcabinet/data/shelf_data.db ~/backup_db_$TS.db
# Полный слепок текущего рабочего дерева (включая .env, untracked)
tar czf ~/backup_worktree_$TS.tgz --exclude=node_modules --exclude=.git .
# Git-слепок (история + ветки)
git bundle create ~/backup_repo_$TS.bundle --all
# Текущий незакоммиченный дифф — на всякий
git diff > ~/backup_uncommitted_$TS.diff
echo "Бэкапы: ~/backup_*_$TS.*"
```

## 2. Сохранить device-config (НЕ в git)
```bash
cp ~/bookcabinet/.env ~/env_backup_$TS 2>/dev/null || echo "нет .env (config из окружения/юнита)"
```
`.env` gitignored → checkout его не трогает. Корневой `calibration.json` (полевые racks/shelves)
у нас в репо ИДЕНТИЧЕН шкафу — reset его не испортит. `bookcabinet/calibration.json` отсутствует
(и не нужен: XY берётся из полевого резолвера, #98).

## 3. Остановить сервис
```bash
sudo systemctl stop bookcabinet
pigs t   # pigpiod должен остаться живым
```

## 4. Свести репо на наш main (жёстко, после бэкапа)
```bash
cd ~/bookcabinet
git fetch origin
git stash push -u -m "rpi-local-$TS"   # убрать незакоммиченное+untracked (уже в бэкапе)
git checkout main 2>/dev/null || git checkout -B main origin/main
git reset --hard origin/main           # рабочее дерево == наш main (#96–101)
git log --oneline -1                   # ждём 0ffeb06+ (Merge #100) или новее
```
Локальный коммит `ca56bfd` (geometry.md) терять не страшно — он уже в `main` (PR #101).
`git stash` оставляем как ещё один бэкап; не применять.

## 5. Зависимости + сборка фронта
```bash
# Python deps (venv шкафа): aiohttp alembic pyserial pigpio + прочее
pip install -r requirements.txt 2>/dev/null || pip install aiohttp alembic pyserial
# Фронт → dist/public (наш клиент)
npm ci && npm run build
ls dist/public/index.html   # должен появиться
```

## 6. Миграция БД (db v2, alembic) — через готовый скрипт
```bash
sudo bash deploy/migrate.sh
# скрипт: бэкап БД → alembic upgrade head → старт сервиса → проверка /api/status (до 60с)
```
Если БД уже v2 — alembic идемпотентен (no-op). Перед миграцией скрипт сам делает бэкап.

## 7. Юнит сервиса
Свериться, что `bookcabinet.service` запускает наш путь:
`python3 -m bookcabinet.main`, `HOST=127.0.0.1`, `After/Wants pcscd-daemon.service`.
Эталоны: `deploy/bookcabinet-api.service`, `deploy/pcscd-daemon.service`. При расхождении —
обновить юнит и `systemctl daemon-reload`.

## 8. Старт + проверка (ВНИМАНИЕ: старт = движение)
`migrate.sh` уже стартует сервис. Старт = замки 500 → хоминг XY (LEFT+BOTTOM) →
калибровка лотка (FRONT→BACK→CENTER, ~40 c). Затем:
```bash
curl -s http://127.0.0.1:5000/api/status | python3 -m json.tool | grep -E "state|position"
journalctl -u bookcabinet -n 50 --no-pager
```
Ожидаем `state: idle`, позиция `(0,0)`.

## 9. Сухой прогон (после редеплоя)
1. **XY по полевой калибровке (#98):** `goto.py 1.2.9` и пара ячеек — каретка в верные точки.
2. **Перехват (`docs/PEREHVAT.md`):** сперва голый `python3 tools/cross_operations_v2.py rear_to_front` — сверить.
3. **Полная выдача/возврат** через киоск: авторизация → выдача → детект «забрали» (RRU9816) → возврат.
4. **Библиотекарь:** загрузка/изъятие (camelize-фиксы #99 → список изъятия не пустой).

## 10. Откат (если что-то не так)
```bash
sudo systemctl stop bookcabinet
cd ~ && rm -rf bookcabinet && mkdir bookcabinet && tar xzf ~/backup_worktree_$TS.tgz -C bookcabinet
cp ~/backup_db_$TS.db ~/bookcabinet/bookcabinet/data/shelf_data.db
sudo systemctl start bookcabinet
```

## Заметки
- ⚠️ GitHub-токен зашит в git-remote RPi (`ghp_…`) — по возможности ротировать и убрать из URL
  (`git remote set-url origin https://github.com/Rivega42/bookcabinet.git`); тянуть по ssh-ключу/gh-CLI.
- Имя репо на remote — старое `Rivega42/-` (редиректит на `bookcabinet`); fetch работает.
- На ноуте железа нет — этот рантбук исполняется на RPi при Романе.
