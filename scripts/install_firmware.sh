#!/bin/bash
set -euo pipefail

# ======================================================
# скрипт автопрошивки esp32-s3 готовым бинарником
# использование: bash install_firmware.sh [/dev/ttyUSB0]
# ======================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
fail() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_PATH="$SCRIPT_DIR/../bin/firmware.bin"

# проверка наличия бинарника
if [ ! -f "$BIN_PATH" ]; then
    fail "Бинарник не найден: $BIN_PATH"
fi

log "Бинарник найден: $BIN_PATH ($(stat -c%s "$BIN_PATH") байт)"

# установка esptool если не установлен
if ! command -v esptool.py &> /dev/null; then
    log "Установка esptool.py..."
    pip3 install esptool --break-system-packages 2>/dev/null || pip3 install esptool
fi

# автоопределение порта или использование аргумента
if [ -n "${1:-}" ]; then
    PORT="$1"
else
    # поиск подключенного esp32
    PORT=""
    for dev in /dev/ttyUSB* /dev/ttyACM* /dev/cu.usbserial*; do
        if [ -e "$dev" ]; then
            PORT="$dev"
            break
        fi
    done

    if [ -z "$PORT" ]; then
        fail "ESP32 не обнаружен. Подключите плату и попробуйте снова, или укажите порт: bash install_firmware.sh /dev/ttyUSB0"
    fi
fi

log "Используется порт: $PORT"

echo ""
echo "================================================"
echo "  ПРОШИВКА ESP32-S3"
echo "  Порт: $PORT"
echo "  Файл: $BIN_PATH"
echo "================================================"
echo ""

# запуск прошивки
esptool.py \
    --chip esp32s3 \
    -p "$PORT" \
    -b 460800 \
    --before default_reset \
    --after hard_reset \
    write_flash \
    --flash_mode dio \
    --flash_size detect \
    --flash_freq 80m \
    0x0 "$BIN_PATH"

echo ""
log "Прошивка завершена успешно!"
log "Откройте монитор порта для проверки: screen $PORT 115200"
