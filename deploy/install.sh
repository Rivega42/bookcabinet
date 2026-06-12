#!/bin/bash
#
# BookCabinet — установка systemd сервисов
# Запуск: sudo bash deploy/install.sh
#
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  BookCabinet — Установка сервисов"
echo "========================================"

# Проверка прав
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Ошибка: запустите с sudo${NC}"
    exit 1
fi

SERVICE_USER=${SUDO_USER:-admin42}
PROJECT_DIR="/home/$SERVICE_USER/bookcabinet"
DEPLOY_DIR="$PROJECT_DIR/deploy"

echo "Пользователь: $SERVICE_USER"
echo "Проект: $PROJECT_DIR"
echo ""

# 1. Остановить старый сервис
echo -e "${YELLOW}[1/6] Остановка старых сервисов...${NC}"
systemctl stop bookcabinet 2>/dev/null || true
systemctl disable bookcabinet 2>/dev/null || true
echo -e "${GREEN}OK${NC}"

# 2. Сборка Node.js
echo -e "${YELLOW}[2/6] Сборка Node.js UI...${NC}"
cd "$PROJECT_DIR"
su -c "npm install && npm run build" "$SERVICE_USER"
echo -e "${GREEN}OK${NC}"

# 2a. Миграции БД — только с бэкапом (правило CLAUDE.md).
# Ошибку молча глотать нельзя: схема v2 откажется стартовать поверх старой.
echo -e "${YELLOW}[2a/6] Бэкап БД + миграции (alembic upgrade head)...${NC}"
DB_PATH="$PROJECT_DIR/bookcabinet/data/shelf_data.db"
if [ -f "$DB_PATH" ]; then
    su -c "cd '$PROJECT_DIR' && python3 -c \"
from bookcabinet.monitoring.backup import backup_manager
print('Бэкап:', backup_manager.create_backup('pre-install'))
\"" "$SERVICE_USER"
fi
su -c "cd '$PROJECT_DIR' && python3 -m alembic upgrade head" "$SERVICE_USER"
echo -e "${GREEN}OK${NC}"

# 3. Копирование systemd units
echo -e "${YELLOW}[3/6] Установка systemd сервисов...${NC}"
cp "$DEPLOY_DIR/bookcabinet-calibration.service" /etc/systemd/system/
cp "$DEPLOY_DIR/bookcabinet-daemon.service" /etc/systemd/system/
cp "$DEPLOY_DIR/bookcabinet-ui.service" /etc/systemd/system/
cp "$DEPLOY_DIR/chromium-kiosk.service" /etc/systemd/system/
systemctl daemon-reload
echo -e "${GREEN}OK${NC}"

# 4. Включение сервисов
echo -e "${YELLOW}[4/6] Включение автозапуска...${NC}"
systemctl enable pigpiod 2>/dev/null || true
systemctl enable bookcabinet-calibration
systemctl enable bookcabinet-daemon
systemctl enable bookcabinet-ui
systemctl enable chromium-kiosk
echo -e "${GREEN}OK${NC}"

# 5. Запуск
echo -e "${YELLOW}[5/6] Запуск сервисов...${NC}"
systemctl start pigpiod 2>/dev/null || true
systemctl start bookcabinet-calibration || echo -e "${YELLOW}  ⚠ Калибровка пропущена (нет железа?)${NC}"
systemctl start bookcabinet-daemon
systemctl start bookcabinet-ui
echo -e "${GREEN}OK${NC}"

# 6. Проверка
echo -e "${YELLOW}[6/6] Проверка...${NC}"
sleep 3

echo ""
echo "Статус сервисов:"
echo "-----------------"
for svc in pigpiod bookcabinet-calibration bookcabinet-daemon bookcabinet-ui; do
    if systemctl is-active --quiet "$svc"; then
        echo -e "${GREEN}  ✓ $svc — работает${NC}"
    else
        echo -e "${RED}  ✗ $svc — не работает${NC}"
        echo "    journalctl -u $svc -n 10"
    fi
done

# Проверка HTTP
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 | grep -q "200\|304"; then
    echo -e "${GREEN}  ✓ HTTP :5000 — отвечает${NC}"
else
    echo -e "${YELLOW}  ⚠ HTTP :5000 — ещё запускается (подождите 10 сек)${NC}"
fi

echo ""
echo "========================================"
echo -e "${GREEN}  УСТАНОВКА ЗАВЕРШЕНА${NC}"
echo "========================================"
echo ""
echo "UI: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Управление:"
echo "  sudo systemctl status bookcabinet-ui"
echo "  sudo systemctl restart bookcabinet-ui"
echo "  journalctl -u bookcabinet-ui -f"
echo ""
echo "Chromium kiosk запустится после reboot"
echo "или: sudo systemctl start chromium-kiosk"
echo "========================================"
