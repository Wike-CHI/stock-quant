import os
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
WS_PING_INTERVAL = int(os.getenv("WS_PING_INTERVAL", "30"))
WS_PING_TIMEOUT = int(os.getenv("WS_PING_TIMEOUT", "10"))

DEFAULT_STOCK_COUNT = int(os.getenv("DEFAULT_STOCK_COUNT", "50"))
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "300"))
