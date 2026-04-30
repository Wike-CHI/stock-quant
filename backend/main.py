import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api.routes import router
from api.websocket import ws_handler
from services.thread_pool import ThreadPool
from services import stock_data
from services import scanner
from services import collector

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = ThreadPool.get_instance()

    # Pre-warm spot data on startup
    stock_data.prewarm_spot()

    # Register refresh callback (breaks circular dep between stock_data ↔ scanner)
    stock_data.register_refresh_callback(scanner.run_scan)

    # Start background refresh daemon thread
    refresh_thread = threading.Thread(
        target=stock_data.background_refresh,
        daemon=True,
        name="spot-refresh",
    )
    refresh_thread.start()

    # Start background data collector (SQLite persistence)
    collector_thread = threading.Thread(
        target=collector.background_collector,
        kwargs={"daily_interval": config.COLLECT_INTERVAL, "include_minute": False},
        daemon=True,
        name="data-collector",
    )
    collector_thread.start()

    yield
    pool.shutdown()


app = FastAPI(
    title="Stock Quant - A股涨幅规律分析",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.websocket("/ws")(ws_handler)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        ws_ping_interval=config.WS_PING_INTERVAL,
        ws_ping_timeout=config.WS_PING_TIMEOUT,
    )
