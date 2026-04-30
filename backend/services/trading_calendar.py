"""
A股交易日历：判断当前是否处于交易时段

交易时间（北京时间）：
- 早盘：周一至周五 9:30–11:30
- 午盘：周一至周五 13:00–15:00
- 非交易日：周末 + 中国法定节假日

节假日列表每年更新，可通过 HOLIDAYS 集合扩展。
"""
import datetime
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# 交易时间边界
MORNING_OPEN = datetime.time(9, 30)
MORNING_CLOSE = datetime.time(11, 30)
AFTERNOON_OPEN = datetime.time(13, 0)
AFTERNOON_CLOSE = datetime.time(15, 0)

# 盘前缓冲（分钟）：允许在开盘前 N 分钟开始预热
PRE_MARKET_BUFFER = 5

_HOLIDAYS_FILE = Path(os.environ.get("HOLIDAYS_FILE", Path(__file__).resolve().parent.parent / "data" / "holidays.json"))

_holidays_cache: set[str] | None = None
_holidays_year: int | None = None


def _load_holidays() -> set[str]:
    """加载中国法定节假日列表（格式：'YYYY-MM-DD'）"""
    global _holidays_cache, _holidays_year
    current_year = datetime.date.today().year
    if _holidays_cache is not None and _holidays_year == current_year:
        return _holidays_cache

    holidays: set[str] = set()
    if _HOLIDAYS_FILE.exists():
        try:
            with open(_HOLIDAYS_FILE) as f:
                data = json.load(f)
                holidays = set(data.get("holidays", []))
        except Exception:
            logger.warning("Failed to load holidays file, using empty set")

    _holidays_cache = holidays
    _holidays_year = current_year
    return holidays


def is_trading_day(d: datetime.date | None = None) -> bool:
    """判断是否为交易日（周一至周五，非法定节假日）"""
    if d is None:
        d = datetime.date.today()
    if d.weekday() >= 5:
        return False
    holidays = _load_holidays()
    return d.isoformat() not in holidays


def is_trading_time(dt: datetime.datetime | None = None, buffer_minutes: int = PRE_MARKET_BUFFER) -> bool:
    """判断当前是否处于交易时段（含盘前缓冲）"""
    if dt is None:
        dt = datetime.datetime.now()
    if not is_trading_day(dt.date()):
        return False

    t = dt.time()
    morning_start = MORNING_OPEN.replace(minute=max(0, MORNING_OPEN.minute - buffer_minutes))

    return (morning_start <= t <= MORNING_CLOSE) or (AFTERNOON_OPEN <= t <= AFTERNOON_CLOSE)


# ── 期货交易时间 ──────────────────────────────────────────────
# 日盘：9:00–10:15, 10:30–11:30, 13:30–15:00
# 夜盘：21:00–次日 02:30（视品种不同，此处取最宽范围）
FUTURES_DAY_MORNING_OPEN = datetime.time(9, 0)
FUTURES_DAY_MORNING_BREAK = datetime.time(10, 15)
FUTURES_DAY_MORNING_RESUME = datetime.time(10, 30)
FUTURES_DAY_MORNING_CLOSE = datetime.time(11, 30)
FUTURES_DAY_AFTERNOON_OPEN = datetime.time(13, 30)
FUTURES_DAY_AFTERNOON_CLOSE = datetime.time(15, 0)
FUTURES_NIGHT_OPEN = datetime.time(21, 0)
FUTURES_NIGHT_CLOSE = datetime.time(23, 0)  # 大部分品种夜盘收盘
FUTURES_NIGHT_EXTENDED = datetime.time(2, 30)  # 上期所/能源中心夜盘最晚


def is_futures_trading_time(dt: datetime.datetime | None = None) -> bool:
    """判断当前是否处于期货交易时段（含日盘 + 夜盘）"""
    if dt is None:
        dt = datetime.datetime.now()
    if not is_trading_day(dt.date()):
        return False

    t = dt.time()
    # 日盘
    if (FUTURES_DAY_MORNING_OPEN <= t <= FUTURES_DAY_MORNING_BREAK):
        return True
    if (FUTURES_DAY_MORNING_RESUME <= t <= FUTURES_DAY_MORNING_CLOSE):
        return True
    if (FUTURES_DAY_AFTERNOON_OPEN <= t <= FUTURES_DAY_AFTERNOON_CLOSE):
        return True
    # 夜盘（21:00–02:30 跨日）
    if t >= FUTURES_NIGHT_OPEN or t <= FUTURES_NIGHT_EXTENDED:
        return True
    return False


def next_trading_time(dt: datetime.datetime | None = None) -> datetime.datetime:
    """返回下一个交易时段开始时间（用于日志/调度）"""
    if dt is None:
        dt = datetime.datetime.now()
    today = dt.date()
    t = dt.time()

    # 如果在早盘之前
    if t < MORNING_OPEN and is_trading_day(today):
        return datetime.datetime.combine(today, MORNING_OPEN)

    # 如果在午休期间
    if MORNING_CLOSE < t < AFTERNOON_OPEN and is_trading_day(today):
        return datetime.datetime.combine(today, AFTERNOON_OPEN)

    # 下一个交易日
    next_day = today + datetime.timedelta(days=1)
    while not is_trading_day(next_day):
        next_day += datetime.timedelta(days=1)
    return datetime.datetime.combine(next_day, MORNING_OPEN)
