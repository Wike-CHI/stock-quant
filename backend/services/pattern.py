"""
涨幅规律分析引擎

识别A股历史数据中的涨幅模式：
- 连续涨停/连板模式
- 均线多头排列
- 放量突破
- 缩量回调后反弹
- V型反转
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from services.stock_data import get_stock_history
from services.bowl_rebound import detect_bowl_rebound

logger = logging.getLogger(__name__)

LIMIT_UP_THRESHOLD = 9.5  # 涨停近似阈值（考虑四舍五入）


@dataclass
class PatternMatch:
    code: str
    name: str
    pattern_type: str
    confidence: float
    description: str
    start_date: str
    end_date: str
    rise_probability: float = 0.0
    details: dict = field(default_factory=dict)


def _calc_ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def _calc_volume_ratio(volume: pd.Series) -> pd.Series:
    """量比：当日成交量 / 近5日均量"""
    ma5_vol = volume.rolling(5).mean()
    return volume / ma5_vol


def detect_limit_up_streak(df: pd.DataFrame, code: str, name: str, min_streak: int = 2) -> list[PatternMatch]:
    """连续涨停（连板）检测"""
    results = []
    change_pcts = df["change_pct"].values
    dates = df["date"].values

    streak_start = None
    streak_count = 0

    for i, pct in enumerate(change_pcts):
        if pct >= LIMIT_UP_THRESHOLD:
            if streak_start is None:
                streak_start = i
            streak_count += 1
        else:
            if streak_count >= min_streak:
                results.append(PatternMatch(
                    code=code,
                    name=name,
                    pattern_type="limit_up_streak",
                    confidence=min(streak_count / 5.0, 1.0),
                    description=f"连板{streak_count}天",
                    start_date=str(dates[streak_start]),
                    end_date=str(dates[i - 1]),
                    rise_probability=0.5 + streak_count * 0.05,
                    details={"streak_days": streak_count},
                ))
            streak_start = None
            streak_count = 0

    if streak_count >= min_streak:
        results.append(PatternMatch(
            code=code, name=name, pattern_type="limit_up_streak",
            confidence=min(streak_count / 5.0, 1.0),
            description=f"连板{streak_count}天（进行中）",
            start_date=str(dates[streak_start]), end_date=str(dates[-1]),
            rise_probability=0.5 + streak_count * 0.05,
            details={"streak_days": streak_count},
        ))
    return results


def detect_ma_bullish_alignment(df: pd.DataFrame, code: str, name: str) -> list[PatternMatch]:
    """均线多头排列：MA5 > MA10 > MA20 > MA60"""
    df = df.copy()
    df["ma5"] = _calc_ma(df["close"], 5)
    df["ma10"] = _calc_ma(df["close"], 10)
    df["ma20"] = _calc_ma(df["close"], 20)
    df["ma60"] = _calc_ma(df["close"], 60)
    df.dropna(subset=["ma60"], inplace=True)

    results = []
    bullish_mask = (df["ma5"] > df["ma10"]) & (df["ma10"] > df["ma20"]) & (df["ma20"] > df["ma60"])

    if bullish_mask.empty:
        return results

    in_streak = False
    streak_start = 0
    for i, is_bullish in enumerate(bullish_mask):
        idx = df.index[i]
        if is_bullish:
            if not in_streak:
                streak_start = i
                in_streak = True
        else:
            if in_streak and (i - streak_start) >= 5:
                results.append(PatternMatch(
                    code=code, name=name, pattern_type="ma_bullish_alignment",
                    confidence=min((i - streak_start) / 20.0, 1.0),
                    description=f"均线多头排列持续{i - streak_start}天",
                    start_date=str(df.iloc[streak_start]["date"]),
                    end_date=str(df.iloc[i - 1]["date"]),
                    rise_probability=0.6,
                    details={"duration_days": i - streak_start},
                ))
            in_streak = False

    return results[-3:]  # 只保留最近3个


def detect_volume_breakout(df: pd.DataFrame, code: str, name: str) -> list[PatternMatch]:
    """放量突破：量比>2 且 涨幅>3%"""
    df = df.copy()
    df["vol_ratio"] = _calc_volume_ratio(df["volume"])
    df.dropna(subset=["vol_ratio"], inplace=True)

    results = []
    mask = (df["vol_ratio"] > 2.0) & (df["change_pct"] > 3.0)

    for i in df[mask].index[-10:]:
        row = df.loc[i]
        results.append(PatternMatch(
            code=code, name=name, pattern_type="volume_breakout",
            confidence=min(row["vol_ratio"] / 5.0, 1.0),
            description=f"放量突破：量比{row['vol_ratio']:.1f}，涨幅{row['change_pct']:.1f}%",
            start_date=str(row["date"]), end_date=str(row["date"]),
            rise_probability=0.55,
            details={"volume_ratio": round(float(row["vol_ratio"]), 2), "change_pct": round(float(row["change_pct"]), 2)},
        ))
    return results


def detect_shrinkage_bounce(df: pd.DataFrame, code: str, name: str) -> list[PatternMatch]:
    """缩量回调后反弹：连续3天缩量下跌后放量上涨"""
    df = df.copy()
    df["vol_ratio"] = _calc_volume_ratio(df["volume"])
    df.dropna(subset=["vol_ratio"], inplace=True)

    results = []
    closes = df["close"].values
    vol_ratios = df["vol_ratio"].values
    dates = df["date"].values

    for i in range(3, len(df)):
        recent_3_decline = all(
            closes[i - j] < closes[i - j - 1] and vol_ratios[i - j] < 1.0
            for j in range(1, 4)
        )
        bounce_today = closes[i] > closes[i - 1] and vol_ratios[i] > 1.2

        if recent_3_decline and bounce_today:
            results.append(PatternMatch(
                code=code, name=name, pattern_type="shrinkage_bounce",
                confidence=0.7,
                description="缩量回调后放量反弹",
                start_date=str(dates[i - 3]), end_date=str(dates[i]),
                rise_probability=0.6,
                details={"bounce_change": round(float(closes[i] / closes[i - 1] - 1) * 100, 2)},
            ))
    return results[-5:]


def detect_v_shape_reversal(df: pd.DataFrame, code: str, name: str, lookback: int = 20) -> list[PatternMatch]:
    """V型反转：快速下跌后快速回升，底部反弹幅度超过跌幅的50%"""
    if len(df) < lookback:
        return []

    results = []
    closes = df["close"].values
    dates = df["date"].values

    window = closes[-lookback:]
    bottom_idx = int(np.argmin(window))
    top_before = np.max(window[:bottom_idx + 1]) if bottom_idx > 0 else window[0]

    if bottom_idx == 0 or top_before == 0:
        return results

    drop_pct = (top_before - window[bottom_idx]) / top_before
    recovery_pct = (window[-1] - window[bottom_idx]) / window[bottom_idx] if window[bottom_idx] > 0 else 0

    if drop_pct > 0.10 and recovery_pct > drop_pct * 0.5:
        results.append(PatternMatch(
            code=code, name=name, pattern_type="v_shape_reversal",
            confidence=min(recovery_pct / drop_pct, 1.0),
            description=f"V型反转：跌{drop_pct:.1%}后反弹{recovery_pct:.1%}",
            start_date=str(dates[-lookback]),
            end_date=str(dates[-1]),
            rise_probability=0.55,
            details={"drop_pct": round(float(drop_pct), 4), "recovery_pct": round(float(recovery_pct), 4)},
        ))
    return results


def analyze_stock(code: str, name: str = "", period_days: int = 120) -> list[dict]:
    """对单只股票执行全量模式分析"""
    df = get_stock_history(code)
    if df.empty:
        return []

    if len(df) > period_days:
        df = df.tail(period_days)
    df = df.reset_index(drop=True)

    all_patterns: list[PatternMatch] = []
    all_patterns.extend(detect_limit_up_streak(df, code, name))
    all_patterns.extend(detect_ma_bullish_alignment(df, code, name))
    all_patterns.extend(detect_volume_breakout(df, code, name))
    all_patterns.extend(detect_shrinkage_bounce(df, code, name))
    all_patterns.extend(detect_v_shape_reversal(df, code, name))

    bowl_signals = detect_bowl_rebound(df, code, name)
    all_patterns.extend(bowl_signals)

    return [p.__dict__ for p in all_patterns]


def batch_analyze(codes: list[tuple[str, str]], period_days: int = 120) -> dict[str, list[dict]]:
    """批量分析多只股票"""
    results: dict[str, list[dict]] = {}
    for code, name in codes:
        try:
            patterns = analyze_stock(code, name, period_days)
            if patterns:
                results[code] = patterns
        except Exception as e:
            logger.warning("Failed to analyze %s: %s", code, e)
    return results
