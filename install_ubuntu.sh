#!/bin/bash
# ==============================================================================
# Универсальный установщик LiDAR IoT Network для Ubuntu / Debian
# ==============================================================================

set -e # Прерывать выполнение при ошибках

# Цвета для красивого вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================================${NC}"
echo -e "${GREEN}   Инсталлятор LiDAR IoT Network Server (Ubuntu)${NC}"
echo -e "${BLUE}======================================================${NC}"

# Проверка на root (sudo)
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ОШИБКА] Запустите скрипт с правами суперпользователя: sudo ./install_ubuntu.sh${NC}"
  exit 1
fi

PROJECT_DIR=$(pwd)
SERVER_DIR="$PROJECT_DIR/server"

# 1. Обновление системы и установка зависимостей
echo -e "${YELLOW}[1/6] Обновление пакетов и установка зависимостей...${NC}"
apt update
apt install -y python3 python3-venv python3-pip curl git ufw mosquitto mosquitto-clients

# 2. Установка Docker и Docker Compose (если нет)
echo -e "${YELLOW}[2/6] Проверка Docker и Docker Compose...${NC}"
if ! command -v docker &> /dev/null; then
    echo "Установка Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Установка Docker Compose..."
    apt install -y docker-compose
fi

# Настройка и запуск MQTT брокера (Mosquitto)
echo -e "${YELLOW}[3/6] Настройка MQTT брокера (Mosquitto)...${NC}"
cat <<EOT > /etc/mosquitto/conf.d/lidar.conf
listener 1883 0.0.0.0
allow_anonymous true
EOT
systemctl restart mosquitto
systemctl enable mosquitto

# 3. Поднятие базы данных (MariaDB) через Docker Compose
echo -e "${YELLOW}[4/6] Запуск базы данных...${NC}"
if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" up -d
else
    echo -e "${RED}[ОШИБКА] Не найден docker-compose.yml!${NC}"
    exit 1
fi

# 4. Настройка Python-окружения и установка зависимостей
echo -e "${YELLOW}[5/6] Настройка Python-сервера...${NC}"
if [ ! -d "$SERVER_DIR" ]; then
    echo -e "${RED}[ОШИБКА] Папка server/ не найдена!${NC}"
    exit 1
fi

cd "$SERVER_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
cd "$PROJECT_DIR"

# 5. Создание Systemd Service для автоматического запуска
echo -e "${YELLOW}[6/6] Создание systemd службы...${NC}"
SERVICE_FILE="/etc/systemd/system/lidar_server.service"

cat <<EOT > $SERVICE_FILE
[Unit]
Description=LiDAR IoT Network Python Server
After=network.target docker.service mosquitto.service
Requires=docker.service mosquitto.service

[Service]
Type=simple
User=root
WorkingDirectory=$SERVER_DIR
Environment=DB_TYPE=mysql
Environment=MYSQL_HOST=127.0.0.1
Environment=MQTT_BROKER=127.0.0.1
ExecStart=$SERVER_DIR/venv/bin/python $SERVER_DIR/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOT

systemctl daemon-reload
systemctl enable lidar_server.service
systemctl restart lidar_server.service

# 6. Настройка Firewall (UFW)
echo -e "${YELLOW}[+] Настройка UFW (Firewall)...${NC}"
ufw allow 8080/tcp  # Web Dashboard
ufw allow 1883/tcp  # MQTT
ufw allow 44444/udp # Auto-Discovery
ufw allow 3306/tcp  # MySQL (опционально, если нужен удаленный доступ)
# Не включаем ufw принудительно, чтобы не оборвать SSH (оставляем на совести админа)
# ufw enable

echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   Установка успешно завершена!${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "Веб-интерфейс доступен по адресу: http://<IP_сервера>:8080"
echo -e "База данных крутится в Docker. Python-сервер запущен как systemd сервис."
echo -e "Посмотреть логи сервера: ${YELLOW}journalctl -u lidar_server.service -f${NC}"
