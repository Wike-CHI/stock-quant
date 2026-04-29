"""
WebSocket 实时行情推送

优化点：
1. diff-only 增量推送 — 只推送与上次不同的字段，减少序列化开销
2. 每个连接独立维护 last_snapshot，避免全量比较
3. 推送前检查连接状态，防止僵尸推送
"""
import asyncio
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from services import stock_data
from services.alert_store import store as alert_store, Alert

logger = logging.getLogger(__name__)

PUSH_INTERVAL = 3   # seconds between pushes
DIFF_FIELDS = ("price", "change_pct", "change_amount", "volume", "turnover",
               "high", "low", "amplitude", "vol_ratio", "turnover_rate")


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
            self.active[ws].difference_update(codes)


manager = ConnectionManager()


def _fetch_quotes(codes: list[str]) -> dict[str, dict]:
    """返回 code -> record dict，便于 diff 比较"""
    if not codes:
        return {}
    df = stock_data.get_realtime_quote(codes)
    if df.empty:
        return {}
    result = {}
    for rec in df.to_dict(orient="records"):
        code = rec.get("code")
        if code:
            result[code] = rec
    return result


def _compute_diff(new: dict[str, dict], old: dict[str, dict]) -> list[dict]:
    """
    增量 diff：只推送发生变化的字段。
    新出现的股票全量推送，已有股票只推送变化字段。
    """
    patches = []
    for code, new_rec in new.items():
        if code not in old:
            # 新增股票，全量推
            patches.append(new_rec)
            continue
        old_rec = old[code]
        patch = {"code": code}
        changed = False
        for field in DIFF_FIELDS:
            nv = new_rec.get(field)
            ov = old_rec.get(field)
            # 浮点容差比较，避免微小精度抖动触发推送
            if isinstance(nv, float) and isinstance(ov, float):
                if abs(nv - ov) > 0.0001:
                    patch[field] = nv
                    changed = True
            elif nv != ov:
                patch[field] = nv
                changed = True
        if changed:
            patches.append(patch)
    return patches


async def ws_handler(ws: WebSocket):
    await ws.accept()
    manager.connect(ws)
    logger.info("WS client connected, total=%d", len(manager.active))

    loop = asyncio.get_event_loop()
    codes_subscribed: set[str] = set()
    running = True
    last_snapshot: dict[str, dict] = {}

    # ── 预警推送回调 ──────────────────────────────────────────
    def _on_alert(alert: Alert):
        """alert_store 有新预警时，在事件循环里推送给本 WS 客户端"""
        if not running:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                ws.send_json({"type": "alert", "data": alert.to_dict()}),
                loop,
            )
        except Exception:
            pass

    alert_store.register_listener(_on_alert)

    async def _reader():
        nonlocal running
        try:
            while running:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "subscribe":
                    new_codes = msg.get("codes", [])
                    codes_subscribed.update(new_codes)
                    manager.subscribe(ws, new_codes)
                    # 订阅新股票时清除其快照，强制全量推送
                    for c in new_codes:
                        last_snapshot.pop(c, None)
                elif msg_type == "unsubscribe":
                    rm_codes = msg.get("codes", [])
                    codes_subscribed.difference_update(rm_codes)
                    manager.unsubscribe(ws, rm_codes)
                    for c in rm_codes:
                        last_snapshot.pop(c, None)
                elif msg_type == "ping":
                    await ws.send_json({"type": "pong", "ts": int(time.time() * 1000)})
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            running = False

    async def _pusher():
        nonlocal running
        try:
            while running:
                if codes_subscribed:
                    new_quotes = await loop.run_in_executor(
                        None, _fetch_quotes, list(codes_subscribed)
                    )
                    if running and new_quotes:
                        patches = _compute_diff(new_quotes, last_snapshot)
                        if patches:
                            await ws.send_json({
                                "type": "quotes",
                                "data": patches,
                                "ts": int(time.time() * 1000),
                            })
                        # 更新快照
                        last_snapshot.update(new_quotes)
                await asyncio.sleep(PUSH_INTERVAL)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug("WS pusher error: %s", e)
        finally:
            running = False

    try:
        await asyncio.gather(_reader(), _pusher())
    finally:
        running = False
        alert_store.unregister_listener(_on_alert)
        manager.disconnect(ws)
        logger.info("WS client disconnected, total=%d", len(manager.active))
