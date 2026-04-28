"""
碗底反弹策略（参考 A-Share Quant Selector）

基于双趋势线 + KDJ + 放量阳线的量化选股策略。
信号分类：bowl_center / near_duokong / near_short_trend
相似度评分：四维加权（双线结构 + KDJ + 量能 + 价格形态）
"""
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from services.stock_data import get_stock_history

logger = logging.getLogger(__name__)

DEFAULT_PARAMS = {
    "N": 2.4,              # 关键K线成交量倍数
    "M": 20,               # 回溯天数
    "CAP": 4e9,            # 流通市值门槛（40亿）
    "J_VAL": 30,           # J值上限
    "duokong_pct": 3,      # 靠近多空线范围 ±3%
    "short_pct": 2,        # 靠近短期趋势线范围 ±2%
    "M1": 14, "M2": 28, "M3": 57, "M4": 114,  # 多空线MA周期
}


@dataclass
class BowlSignal:
    code: str
    name: str
    pattern_type: str  # bowl_rebound
    category: str      # bowl_center / near_duokong / near_short_trend
    confidence: float
    description: str
    start_date: str
    end_date: str
    rise_probability: float
    details: dict


def _calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    low_9 = low.rolling(9).min()
    high_9 = high.rolling(9).max()
    denom = high_9 - low_9
    denom = denom.where(denom != 0, 1)
    rsv = (close - low_9) / denom * 100
    K = rsv.ewm(com=2, adjust=False).mean()
    D = K.ewm(com=2, adjust=False).mean()
    J = 3 * K - 2 * D
    return K, D, J


def calculate_indicators(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """计算技术指标：双趋势线 + KDJ + 关键K线"""
    df = df.copy()
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]

    # 短期趋势线 = EMA(EMA(CLOSE, 10), 10)
    ema10 = close.ewm(span=10, adjust=False).mean()
    df["short_trend"] = ema10.ewm(span=10, adjust=False).mean()

    # 多空线 = (MA14 + MA28 + MA57 + MA114) / 4
    df["bull_bear"] = (
        close.rolling(params["M1"]).mean()
        + close.rolling(params["M2"]).mean()
        + close.rolling(params["M3"]).mean()
        + close.rolling(params["M4"]).mean()
    ) / 4

    # KDJ
    df["K"], df["D"], df["J"] = _calc_kdj(high, low, close)

    # 关键K线：放量阳线
    vol_shift = volume.shift(1)
    is_yang = close > df["open"]
    is_vol_up = volume >= vol_shift * params["N"]
    df["key_candle"] = is_yang & is_vol_up

    # 分类
    df["fall_in_bowl"] = (
        (close > df["bull_bear"]) & (close < df["short_trend"])
        & (df["bull_bear"] < df["short_trend"])
    )
    df["trend_above"] = df["short_trend"] > df["bull_bear"]

    return df


def _similarity_score(row: pd.Series, params: dict) -> float:
    """四维相似度评分"""
    score = 0.0

    # 双线结构 30%：短期/多空比值偏离度
    if row["bull_bear"] > 0:
        ratio = row["short_trend"] / row["bull_bear"]
        score += 0.30 * max(0, 1 - abs(ratio - 1) / params["duokong_pct"] * 0.01)

    # KDJ状态 20%：J值低位加分
    j_val = row["J"] if not pd.isna(row["J"]) else 50
    if j_val <= params["J_VAL"]:
        score += 0.20
    elif j_val <= 50:
        score += 0.20 * (50 - j_val) / (50 - params["J_VAL"])

    # 量能 25%：关键K线存在加分
    if row["key_candle"]:
        score += 0.25

    # 价格形态 25%：回落碗中加分
    if row["fall_in_bowl"]:
        score += 0.25
    elif row["trend_above"]:
        score += 0.10

    return round(min(score, 1.0), 3)


def detect_bowl_rebound(df: pd.DataFrame, code: str, name: str, params: dict | None = None) -> list[BowlSignal]:
    """检测碗底反弹信号"""
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = calculate_indicators(df, p)

    results: list[BowlSignal] = []
    lookback = min(p["M"], len(df))
    recent = df.tail(lookback)

    for _, row in recent.iterrows():
        close = row["close"]
        if pd.isna(row["bull_bear"]) or pd.isna(row["short_trend"]):
            continue

        category = None
        reasons = []

        # 回落碗中
        if row["fall_in_bowl"]:
            category = "bowl_center"
            reasons.append("回落碗中")
        # 靠近多空线
        elif abs(close - row["bull_bear"]) / row["bull_bear"] * 100 <= p["duokong_pct"]:
            category = "near_duokong"
            reasons.append(f"靠近多空线(±{p['duokong_pct']}%)")
        # 靠近短期趋势线
        elif abs(close - row["short_trend"]) / row["short_trend"] * 100 <= p["short_pct"]:
            category = "near_short_trend"
            reasons.append(f"靠近短期趋势线(±{p['short_pct']}%)")

        if not category:
            continue

        # 检查近期是否有放量阳线
        has_key_candle = df["key_candle"].tail(p["M"]).any()

        # 相似度评分
        sim = _similarity_score(row, p)
        if not has_key_candle:
            sim *= 0.7  # 无关键K线打折

        results.append(BowlSignal(
            code=code, name=name,
            pattern_type="bowl_rebound",
            category=category,
            confidence=sim,
            description=f"{'+'.join(reasons)}，J值{row['J']:.1f}" if not pd.isna(row["J"]) else "+".join(reasons),
            start_date=str(row["date"]),
            end_date=str(row["date"]),
            rise_probability=round(0.4 + sim * 0.3, 3),
            details={
                "category": category,
                "J": round(float(row["J"]), 2) if not pd.isna(row["J"]) else None,
                "short_trend": round(float(row["short_trend"]), 2),
                "bull_bear": round(float(row["bull_bear"]), 2),
                "has_key_candle": has_key_candle,
                "similarity": sim,
            },
        ))

    # 去重：只保留每个类别的最近一条
    seen: set[str] = set()
    deduped: list[BowlSignal] = []
    for sig in reversed(results):
        if sig.category not in seen:
            seen.add(sig.category)
            deduped.append(sig)
    return list(reversed(deduped))


def analyze_bowl_rebound(code: str, name: str = "", period_days: int = 120, params: dict | None = None) -> list[dict]:
    """分析单只股票的碗底反弹信号"""
    df = get_stock_history(code)
    if df.empty:
        return []
    if len(df) > period_days:
        df = df.tail(period_days)
    df = df.reset_index(drop=True)

    signals = detect_bowl_rebound(df, code, name, params)
    return [s.__dict__ for s in signals]
