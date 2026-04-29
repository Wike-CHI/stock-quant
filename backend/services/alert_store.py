"""
预警存储 — 内存环形缓冲 + 去重 + 冷却期

设计原则：
- 同一股票同一预警类型，冷却期内不重复触发
- 最多保留 MAX_ALERTS 条历史记录（环形覆盖）
- 线程安全，供 scanner 和 WS handler 并发访问
"""
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict

MAX_ALERTS = 500          # 最多保留记录数
COOLDOWN_SECONDS = 300    # 同股票同类型预警冷却期（5分钟）


@dataclass
class Alert:
    id: str                  # f"{code}_{alert_type}_{ts}"
    code: str
    name: str
    alert_type: str          # 预警类型
    level: str               # "high" | "medium" | "low"
    title: str               # 短标题，用于通知推送
    message: str             # 详细描述
    price: float
    change_pct: float
    ts: float = field(default_factory=time.time)   # Unix 时间戳
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ts_ms"] = int(self.ts * 1000)
        return d


class AlertStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._alerts: deque[Alert] = deque(maxlen=MAX_ALERTS)
        # 去重 key -> last_trigger_ts
        self._cooldown: dict[str, float] = {}
        # 新增预警的回调列表（供 WS 推送）
        self._listeners: list = []

    def register_listener(self, cb):
        with self._lock:
            self._listeners.append(cb)

    def unregister_listener(self, cb):
        with self._lock:
            try:
                self._listeners.remove(cb)
            except ValueError:
                pass

    def try_add(self, alert: Alert) -> bool:
        """
        尝试添加预警。若在冷却期内返回 False（不触发）。
        返回 True 表示成功添加。
        """
        key = f"{alert.code}:{alert.alert_type}"
        now = time.time()
        with self._lock:
            last = self._cooldown.get(key, 0)
            if now - last < COOLDOWN_SECONDS:
                return False
            self._cooldown[key] = now
            self._alerts.appendleft(alert)
            listeners = list(self._listeners)
            # 清理超过 2 倍冷却期的过期条目，防止内存泄漏
            expired_keys = [k for k, v in self._cooldown.items() if now - v > COOLDOWN_SECONDS * 2]
            for k in expired_keys:
                del self._cooldown[k]

        # 回调在锁外执行，避免死锁
        for cb in listeners:
            try:
                cb(alert)
            except Exception:
                pass
        return True

    def get_recent(self, limit: int = 100, code: str = "") -> list[dict]:
        with self._lock:
            alerts = list(self._alerts)
        if code:
            alerts = [a for a in alerts if a.code == code]
        return [a.to_dict() for a in alerts[:limit]]

    def clear(self):
        with self._lock:
            self._alerts.clear()
            self._cooldown.clear()


# 全局单例
store = AlertStore()
