#!/bin/bash
#
# BookCabinet — безопасная миграция БД на шкафу.
# Запуск: sudo bash deploy/migrate.sh
#
# Порядок (правило CLAUDE.md: перед миграциями — бэкап):
#   1. стоп сервисов  2. бэкап БД  3. alembic upgrade head
#   4. старт сервисов 5. проверка /api/status
# Любая ошибка прерывает скрипт ДО рестарта сервисов.
#
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Ошибка: запустите с sudo${NC}"; exit 1
fi

SERVICE_USER=${SUDO_USER:-admin42}
PROJECT_DIR="/home/$SERVICE_USER/bookcabinet"
cd "$PROJECT_DIR"

echo "========================================"
echo "  BookCabinet — миграция БД"
echo "========================================"

echo -e "${YELLOW}[1/5] Остановка сервисов...${NC}"
systemctl stop bookcabinet 2>/dev/null || true
echo -e "${GREEN}OK${NC}"

echo -e "${YELLOW}[2/5] Бэкап БД...${NC}"
BACKUP=$(su -c "cd '$PROJECT_DIR' && python3 -c \"
from bookcabinet.monitoring.backup import backup_manager
print(backup_manager.create_backup('pre-migration'))
\"" "$SERVICE_USER")
echo -e "${GREEN}OK: $BACKUP${NC}"

echo -e "${YELLOW}[3/5] alembic upgrade head...${NC}"
su -c "cd '$PROJECT_DIR' && python3 -m alembic upgrade head" "$SERVICE_USER"
echo -e "${GREEN}OK${NC}"

echo -e "${YELLOW}[4/5] Старт сервиса (ВНИМАНИЕ: старт = ДВИЖЕНИЕ — замки→хоминг XY→калибровка лотка)...${NC}"
systemctl start bookcabinet
echo -e "${GREEN}OK${NC}"

echo -e "${YELLOW}[5/5] Проверка /api/status (до 60с — старт включает калибровку лотка)...${NC}"
for i in $(seq 1 60); do
    if curl -sf http://localhost:5000/api/status > /dev/null; then
        echo -e "${GREEN}Сервер отвечает. Миграция завершена.${NC}"
        exit 0
    fi
    sleep 1
done
echo -e "${RED}Сервер не ответил за 30 с (старт ~40с из-за калибровки лотка — подожди ещё). Проверь: journalctl -u bookcabinet -n 50${NC}"
echo -e "${YELLOW}Бэкап для отката: $BACKUP${NC}"
exit 1
