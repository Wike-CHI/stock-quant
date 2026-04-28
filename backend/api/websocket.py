"""
WebSocket 实时行情推送

单进程多线程：每个WS连接一个处理线程，
通过 ThreadPool 管理定时拉取任务。
"""
import asyncio
import json
import logging
import time
from threading import Thread

from fastapi import WebSocket, WebSocketDisconnect

import config
from services import stock_data

logger = logging.getLogger(__name__)

PUSH_INTERVAL = 3  # 秒


class ConnectionManager:
    def __init__(self):
        self.active: dict[WebSocket, set[str]] = {}

    def connect(self, ws: WebSocket):
        self.active[ws] = set()

    def disconnect(self, ws: WebSocket):
        self.active.pop(ws, None)

    def subscribe(self, ws: WebSocket, codes: list[str]):
        if ws in self.active:
            self.active[ws].update(codes)

    def unsubscribe(self, ws: WebSocket, codes: list[str]):
        if ws in self.active:
            self.active.difference_update(codes)


manager = ConnectionManager()


def _fetch_quotes(codes: list[str]) -> list[dict]:
    """同步拉取实时行情"""
    if not codes:
        return []
    df = stock_data.get_realtime_quote(codes)
    return df.to_dict(orient="records")


async def ws_handler(ws: WebSocket):
    await ws.accept()
    manager.connect(ws)
    logger.info("WS client connected, total=%d", len(manager.active))

    loop = asyncio.get_event_loop()
    codes_subscribed: set[str] = set()

    async def _reader():
        """读取客户端消息（订阅/取消订阅）"""
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "subscribe":
                    new_codes = msg.get("codes", [])
                    codes_subscribed.update(new_codes)
                    manager.subscribe(ws, new_codes)
                elif msg_type == "unsubscribe":
                    rm_codes = msg.get("codes", [])
                    codes_subscribed.difference_update(rm_codes)
                    manager.unsubscribe(ws, rm_codes)
                elif msg_type == "ping":
                    await ws.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning("WS reader error: %s", e)

    async def _pusher():
        """定时推送行情数据"""
        try:
            while True:
                if codes_subscribed:
                    quotes = await loop.run_in_executor(None, _fetch_quotes, list(codes_subscribed))
                    await ws.send_json({"type": "quotes", "data": quotes})
                await asyncio.sleep(PUSH_INTERVAL)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning("WS pusher error: %s", e)

    try:
        await asyncio.gather(_reader(), _pusher())
    finally:
        manager.disconnect(ws)
        logger.info("WS client disconnected, total=%d", len(manager.active))
