#!/bin/bash
set -euo pipefail

# ======================================================
# универсальный скрипт установки lidar iot network сервера
# поддержка: ubuntu 22.04 / 24.04 (любая локальная сеть)
# использование: sudo bash install_server.sh
# ======================================================

# цветной вывод
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# проверяем права суперпользователя
if [ "$EUID" -ne 0 ]; then
  fail "Запустите скрипт с правами root: sudo bash install_server.sh"
fi

# определяем ip адрес сервера в локальной сети
SERVER_IP=$(ip -4 route get 8.8.8.8 2>/dev/null | awk '{print $7; exit}' || hostname -I | awk '{print $1}')
log "IP-адрес сервера в локальной сети: $SERVER_IP"

INSTALL_DIR="/opt/lidar-server"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# =========================
# 1. системные зависимости
# =========================
log "Обновление списков пакетов..."
apt-get update -qq

log "Установка системных пакетов..."
apt-get install -y -qq python3 python3-pip python3-venv mosquitto mosquitto-clients ufw curl git > /dev/null

# =========================
# 2. docker
# =========================
if ! command -v docker &> /dev/null; then
    log "Установка Docker..."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sh /tmp/get-docker.sh > /dev/null 2>&1
    rm /tmp/get-docker.sh
    log "Docker установлен"
else
    log "Docker уже установлен ($(docker --version | head -1))"
fi

# docker compose plugin
if ! docker compose version &> /dev/null; then
    apt-get install -y -qq docker-compose-plugin > /dev/null 2>&1 || true
fi

# =========================
# 3. копирование проекта
# =========================
log "Копирование проекта в $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='venv' \
      --exclude='.pio' --exclude='*.db' --exclude='firmware/.pio' \
      "$PROJECT_DIR/" "$INSTALL_DIR/" 2>/dev/null || cp -rT "$PROJECT_DIR" "$INSTALL_DIR" 2>/dev/null || true

# =========================
# 4. python виртуальное окружение
# =========================
log "Настройка Python виртуального окружения..."
if [ ! -d "$INSTALL_DIR/server/venv" ]; then
    python3 -m venv "$INSTALL_DIR/server/venv"
fi

"$INSTALL_DIR/server/venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/server/venv/bin/pip" install -r "$INSTALL_DIR/server/requirements.txt" -q
log "Python зависимости установлены"

# =========================
# 5. mosquitto mqtt брокер
# =========================
log "Настройка Mosquitto MQTT брокера..."

# разрешаем анонимные подключения (для iot сети)
cat > /etc/mosquitto/conf.d/lidar.conf << 'MQTTCONF'
listener 1883 0.0.0.0
allow_anonymous true
MQTTCONF

systemctl enable mosquitto > /dev/null 2>&1
systemctl restart mosquitto
log "Mosquitto запущен и настроен (порт 1883)"

# =========================
# 6. mariadb через docker
# =========================
if [ -f "$INSTALL_DIR/docker-compose.yml" ]; then
    log "Запуск MariaDB через Docker Compose..."
    cd "$INSTALL_DIR" && docker compose up -d 2>/dev/null
    log "MariaDB контейнер запущен"
fi

# =========================
# 7. systemd сервис flask
# =========================
log "Создание systemd сервиса..."

cat > /etc/systemd/system/lidar-server.service << EOF
[Unit]
Description=LiDAR IoT Network - Flask Server
After=network.target mosquitto.service docker.service
Wants=mosquitto.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/server
ExecStart=$INSTALL_DIR/server/venv/bin/python3 $INSTALL_DIR/server/app.py
Restart=always
RestartSec=3
Environment=DB_TYPE=sqlite
Environment=MQTT_BROKER=127.0.0.1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable lidar-server > /dev/null 2>&1
systemctl restart lidar-server
log "Flask сервер запущен как systemd сервис"

# =========================
# 8. firewall
# =========================
log "Настройка файрвола (UFW)..."
ufw allow 22/tcp   > /dev/null 2>&1 || true
ufw allow 8080/tcp > /dev/null 2>&1 || true
ufw allow 1883/tcp > /dev/null 2>&1 || true
ufw allow 44444/udp > /dev/null 2>&1 || true
ufw allow 5000/udp > /dev/null 2>&1 || true
ufw --force enable > /dev/null 2>&1 || true
log "Порты открыты: 8080(web), 1883(mqtt), 44444(discovery), 5000(heartbeat)"

# =========================
# 9. финальная проверка
# =========================
echo ""
echo "========================================"
echo "       ПРОВЕРКА ВСЕХ КОМПОНЕНТОВ"
echo "========================================"

sleep 2

check_service() {
    if systemctl is-active --quiet "$1" 2>/dev/null; then
        log "$2: РАБОТАЕТ"
    else
        warn "$2: НЕ ЗАПУЩЕН"
    fi
}

check_service "mosquitto" "MQTT Брокер (Mosquitto)"
check_service "lidar-server" "Flask Сервер (LiDAR)"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q lidar_mysql; then
    log "MariaDB (Docker): РАБОТАЕТ"
else
    warn "MariaDB (Docker): контейнер не найден (SQLite используется по умолчанию)"
fi

# проверка http api
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8080/api/stats" | grep -q "200"; then
    log "HTTP API: ДОСТУПЕН (http://$SERVER_IP:8080)"
else
    warn "HTTP API: недоступен, проверьте логи: journalctl -u lidar-server -f"
fi

echo ""
echo "========================================"
echo "  УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
echo ""
echo "  Веб-дашборд: http://$SERVER_IP:8080"
echo "  MQTT брокер:  $SERVER_IP:1883"
echo "  Логи сервера: journalctl -u lidar-server -f"
echo "========================================"
