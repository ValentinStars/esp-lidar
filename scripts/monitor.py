#!/usr/bin/env python3
# скрипт мониторинга вывода esp32-s3 в реальном времени

import serial
import sys
import time

# порт по умолчанию для linux
DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 115200

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD

    print(f"=== Подключение к {port} ({baud} baud) ===")
    print("Нажмите Ctrl+C для выхода\n")

    try:
        ser = serial.Serial(port, baud, timeout=0.1)
        ser.dtr = True
        ser.rts = True
        
        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                sys.stdout.write(data)
                sys.stdout.flush()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nМониторинг остановлен пользователем")
    except Exception as e:
        print(f"\nОшибка последовательного порта: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
