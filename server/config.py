import os

# режим работы базы данных: "sqlite" или "mysql"
DB_TYPE = os.getenv("DB_TYPE", "sqlite")

# настройки подключения для mysql (применимо только если DB_TYPE == "mysql")
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "lidar_network")

# путь к файлу sqlite (применимо только если DB_TYPE == "sqlite")
SQLITE_PATH = os.path.join(os.path.dirname(__file__), "lidar_network.db")

# параметры mqtt брокера
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# порт для udp автодискавери
DISCOVERY_PORT = int(os.getenv("DISCOVERY_PORT", 44444))

# веб-сервер
WEB_PORT = int(os.getenv("WEB_PORT", 8080))
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
