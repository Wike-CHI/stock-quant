"""
实时量化预警扫描引擎

每次 spot 数据刷新后调用 scan_spot()，对全量行情做规则扫描。
历史数据类预警（均线/碗底等）走轻量缓存，不每次都调 akshare。

预警类型：
  spot_*   — 基于实时行情，无需历史数据，速度快
  hist_*   — 基于历史K线，有TTL缓存，每支股票最多扫一次/天
"""
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from services.alert_store import store, Alert
from services.stock_data import get_a_stock_list, get_stock_history
from services.bowl_rebound import detect_bowl_rebound
from services.trading_calendar import is_trading_time

logger = logging.getLogger(__name__)

# ── 实时行情预警阈值 ─────────────────────────────────────────────
THRESH = {
    "limit_up":        9.5,    # 涨停
    "limit_down":     -9.5,    # 跌停
    "surge_high":      7.0,    # 大涨预警
    "surge_low":      -7.0,    # 大跌预警
    "vol_ratio_high":  5.0,    # 量比爆量
    "vol_ratio_med":   3.0,    # 量比放量
    "turnover_high":   15.0,   # 换手率异常
    "amplitude_high":  10.0,   # 振幅异常
}

# ── 历史扫描缓存（避免重复拉 K 线）─────────────────────────────
_hist_scan_cache: dict[str, float] = {}   # code -> last scan ts
HIST_SCAN_TTL = 3600 * 6                  # 6小时内同股票不重复历史扫描
_hist_scan_lock = threading.Lock()

# ── 历史扫描线程池（不阻塞主刷新线程）──────────────────────────
_hist_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hist-scan")

# ── 每次全量历史扫描的股票上限（避免打满 API）──────────────────
HIST_SCAN_BATCH = 30   # 每轮最多扫 30 只（优先高涨幅/高量比）


# ═══════════════════════════════════════════════════════════════
# 实时行情扫描（快，每次刷新都跑）
# ═══════════════════════════════════════════════════════════════

def _make_alert(row: dict, alert_type: str, level: str, title: str, msg: str) -> Alert:
    ts = time.time()
    return Alert(
        id=f"{row['code']}_{alert_type}_{int(ts)}",
        code=row["code"],
        name=row.get("name", ""),
        alert_type=alert_type,
        level=level,
        title=title,
        message=msg,
        price=float(row.get("price") or 0),
        change_pct=float(row.get("change_pct") or 0),
        ts=ts,
        extra={
            "vol_ratio": row.get("vol_ratio"),
            "turnover_rate": row.get("turnover_rate"),
            "amplitude": row.get("amplitude"),
        },
    )


def scan_spot(df: pd.DataFrame):
    """扫描实时行情 DataFrame，触发条件型预警"""
    if df is None or df.empty:
        return

    triggered = 0
    for row in df.to_dict(orient="records"):
        chg = row.get("change_pct")
        vol_ratio = row.get("vol_ratio")
        turnover = row.get("turnover_rate")
        amplitude = row.get("amplitude")
        name = row.get("name", row.get("code", ""))

        if chg is None:
            continue

        # 涨停
        if chg >= THRESH["limit_up"]:
            a = _make_alert(row, "spot_limit_up", "high",
                            f"🔴 涨停 {name}",
                            f"{name}({row['code']}) 涨停 {chg:.2f}%，现价 {row.get('price'):.2f}")
            if store.try_add(a):
                triggered += 1

        # 跌停
        elif chg <= THRESH["limit_down"]:
            a = _make_alert(row, "spot_limit_down", "high",
                            f"🟢 跌停 {name}",
                            f"{name}({row['code']}) 跌停 {chg:.2f}%，现价 {row.get('price'):.2f}")
            if store.try_add(a):
                triggered += 1

        # 大涨（非涨停）
        elif chg >= THRESH["surge_high"]:
            a = _make_alert(row, "spot_surge_up", "medium",
                            f"⬆ 大涨 {name} +{chg:.1f}%",
                            f"{name}({row['code']}) 涨幅 {chg:.2f}%，现价 {row.get('price'):.2f}")
            if store.try_add(a):
                triggered += 1

        # 大跌（非跌停）
        elif chg <= THRESH["surge_low"]:
            a = _make_alert(row, "spot_surge_down", "medium",
                            f"⬇ 大跌 {name} {chg:.1f}%",
                            f"{name}({row['code']}) 跌幅 {chg:.2f}%，现价 {row.get('price'):.2f}")
            if store.try_add(a):
                triggered += 1

        # 爆量
        if vol_ratio and vol_ratio >= THRESH["vol_ratio_high"]:
            a = _make_alert(row, "spot_vol_explosion", "high",
                            f"💥 爆量 {name} 量比{vol_ratio:.1f}",
                            f"{name}({row['code']}) 量比 {vol_ratio:.1f}x，涨幅 {chg:.2f}%")
            if store.try_add(a):
                triggered += 1
        elif vol_ratio and vol_ratio >= THRESH["vol_ratio_med"]:
            a = _make_alert(row, "spot_vol_surge", "low",
                            f"📊 放量 {name} 量比{vol_ratio:.1f}",
                            f"{name}({row['code']}) 量比 {vol_ratio:.1f}x，涨幅 {chg:.2f}%")
            if store.try_add(a):
                triggered += 1

        # 换手率异常
        if turnover and turnover >= THRESH["turnover_high"]:
            a = _make_alert(row, "spot_turnover_spike", "low",
                            f"🔄 换手异常 {name} {turnover:.1f}%",
                            f"{name}({row['code']}) 换手率 {turnover:.1f}%，量比 {vol_ratio}")
            if store.try_add(a):
                triggered += 1

    if triggered:
        logger.info("spot_scan: %d alerts triggered", triggered)


# ═══════════════════════════════════════════════════════════════
# 历史K线扫描（慢，异步执行，有缓存）
# ═══════════════════════════════════════════════════════════════

def _should_hist_scan(code: str) -> bool:
    with _hist_scan_lock:
        last = _hist_scan_cache.get(code, 0)
        if time.time() - last < HIST_SCAN_TTL:
            return False
        _hist_scan_cache[code] = time.time()
        return True


def _scan_hist_one(row: dict):
    """对单只股票做历史K线预警扫描"""
    code = row["code"]
    name = row.get("name", code)
    try:
        df = get_stock_history(code)
        if df.empty or len(df) < 20:
            return

        df = df.tail(120).reset_index(drop=True)
        close = df["close"]

        # ── 均线金叉：MA5 上穿 MA10 ──────────────────────────
        if len(df) >= 10:
            ma5 = close.rolling(5).mean()
            ma10 = close.rolling(10).mean()
            if (ma5.iloc[-2] <= ma10.iloc[-2]) and (ma5.iloc[-1] > ma10.iloc[-1]):
                a = Alert(
                    id=f"{code}_hist_ma_cross_{int(time.time())}",
                    code=code, name=name,
                    alert_type="hist_ma_cross",
                    level="medium",
                    title=f"📈 金叉 {name}",
                    message=f"{name}({code}) MA5上穿MA10，现价 {row.get('price'):.2f}，涨幅 {row.get('change_pct'):.2f}%",
                    price=float(row.get("price") or 0),
                    change_pct=float(row.get("change_pct") or 0),
                    extra={"ma5": round(float(ma5.iloc[-1]), 3), "ma10": round(float(ma10.iloc[-1]), 3)},
                )
                store.try_add(a)

        # ── 均线死叉：MA5 下穿 MA10 ──────────────────────────
        if len(df) >= 10:
            if (ma5.iloc[-2] >= ma10.iloc[-2]) and (ma5.iloc[-1] < ma10.iloc[-1]):
                a = Alert(
                    id=f"{code}_hist_ma_dead_{int(time.time())}",
                    code=code, name=name,
                    alert_type="hist_ma_dead_cross",
                    level="medium",
                    title=f"📉 死叉 {name}",
                    message=f"{name}({code}) MA5下穿MA10，现价 {row.get('price'):.2f}",
                    price=float(row.get("price") or 0),
                    change_pct=float(row.get("change_pct") or 0),
                    extra={},
                )
                store.try_add(a)

        # ── 碗底反弹信号 ──────────────────────────────────────
        bowl_signals = detect_bowl_rebound(df, code, name)
        for sig in bowl_signals:
            if sig.confidence >= 0.6:
                a = Alert(
                    id=f"{code}_hist_bowl_{int(time.time())}",
                    code=code, name=name,
                    alert_type="hist_bowl_rebound",
                    level="high",
                    title=f"🥣 碗底反弹 {name}",
                    message=f"{name}({code}) 碗底反弹信号，置信度 {sig.confidence:.0%}，{sig.description}",
                    price=float(row.get("price") or 0),
                    change_pct=float(row.get("change_pct") or 0),
                    extra=sig.details,
                )
                store.try_add(a)
                break   # 一只股票只触发一次碗底

        # ── 新高突破：创近60日收盘新高 ───────────────────────
        if len(df) >= 60:
            high60 = close.iloc[-61:-1].max()
            if close.iloc[-1] > high60:
                a = Alert(
                    id=f"{code}_hist_new_high_{int(time.time())}",
                    code=code, name=name,
                    alert_type="hist_new_high",
                    level="medium",
                    title=f"🏔 60日新高 {name}",
                    message=f"{name}({code}) 突破近60日新高 {high60:.2f}，现价 {close.iloc[-1]:.2f}",
                    price=float(row.get("price") or 0),
                    change_pct=float(row.get("change_pct") or 0),
                    extra={"prev_high60": round(float(high60), 2)},
                )
                store.try_add(a)

    except Exception as e:
        logger.debug("hist_scan %s failed: %s", code, e)


def scan_hist_async(df: pd.DataFrame):
    """
    从实时行情中挑选候选股票，异步提交历史扫描。
    优先：高涨幅 + 高量比 + 未近期扫描过
    """
    if df is None or df.empty:
        return

    # 筛选候选：涨幅 > 2% 或 量比 > 2
    mask = (df["change_pct"].fillna(0) > 2.0) | (df["vol_ratio"].fillna(0) > 2.0)
    candidates = df[mask].copy()
    if candidates.empty:
        return

    # 按 change_pct 排序，取 top N
    candidates = candidates.sort_values("change_pct", ascending=False).head(HIST_SCAN_BATCH)
    rows = candidates.to_dict(orient="records")

    for row in rows:
        if _should_hist_scan(row["code"]):
            _hist_pool.submit(_scan_hist_one, row)


# ═══════════════════════════════════════════════════════════════
# 主入口：由 stock_data.background_refresh 调用
# ═══════════════════════════════════════════════════════════════

def run_scan():
    """每次 spot 数据刷新后调用"""
    if not is_trading_time():
        return
    from services import stock_data
    try:
        df = stock_data.get_a_stock_list()
        if df.empty:
            return
        scan_spot(df)
        scan_hist_async(df)
    except Exception as e:
        logger.error("scanner run_scan failed: %s", e)
