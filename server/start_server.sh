#!/bin/bash
# скрипт запуска сервера мониторинга lidar iot network

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "[ОШИБКА] Виртуальное окружение не найдено в $SCRIPT_DIR/venv"
    exit 1
fi

echo "=================================================="
echo "   LiDAR IoT Network — Master Control Server"
echo "=================================================="
echo "Запуск Flask Web Server на http://0.0.0.0:8080"
echo "Auto-Discovery Broadcast на UDP :44444"
echo "Heartbeat Listener на UDP :5000"
echo "=================================================="

exec "$PYTHON_BIN" "$SCRIPT_DIR/app.py"
