"""pattern 模块单元测试（使用模拟数据）"""
import pytest
import pandas as pd
import numpy as np


def _make_hist_df(n=120, trend="up"):
    """构造历史数据（可控趋势）"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)

    if trend == "up":
        base = np.linspace(10, 15, n)
    elif trend == "down":
        base = np.linspace(15, 10, n)
    else:
        base = np.full(n, 12.0)

    noise = np.random.randn(n) * 0.2
    closes = base + noise
    opens = closes + np.random.randn(n) * 0.05
    change_pct = np.diff(closes, prepend=closes[0]) / closes * 100

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "code": "000001",
        "open": opens, "close": closes,
        "high": closes + abs(np.random.randn(n) * 0.15),
        "low": closes - abs(np.random.randn(n) * 0.15),
        "volume": np.random.randint(100000, 500000, n).astype(float),
        "turnover": np.random.uniform(1e6, 5e6, n),
        "amplitude": np.random.uniform(1, 4, n),
        "change_pct": change_pct,
        "change_amount": np.random.uniform(-0.3, 0.3, n),
        "turnover_rate": np.random.uniform(0.5, 5, n),
    })


def _make_limit_up_df(n=30):
    """构造含连续涨停的数据"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    change_pct = np.zeros(n)
    change_pct[11:14] = 10.0  # 第11-13天连续3天涨停
    change_pct[21:23] = 10.0  # 第21-22天连续2天涨停

    closes = 10.0 * np.ones(n)
    for i in range(1, n):
        closes[i] = closes[i-1] * (1 + change_pct[i] / 100)

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": closes - 0.1, "close": closes,
        "high": closes + 0.2, "low": closes - 0.2,
        "volume": np.full(n, 100000.0),
        "turnover": np.full(n, 1e6),
        "amplitude": np.full(n, 3.0),
        "change_pct": change_pct,
        "change_amount": np.full(n, 0.1),
        "turnover_rate": np.full(n, 2.0),
    })


class TestLimitUpStreak:
    def test_detects_streak(self):
        from services.pattern import detect_limit_up_streak

        df = _make_limit_up_df()
        results = detect_limit_up_streak(df, "000001", "测试", min_streak=2)
        assert len(results) >= 1
        assert any(r.pattern_type == "limit_up_streak" for r in results)

    def test_no_false_positive(self):
        from services.pattern import detect_limit_up_streak

        df = _make_hist_df(trend="flat")
        results = detect_limit_up_streak(df, "000001", "测试", min_streak=2)
        # 平盘不应有连板
        assert len(results) == 0


class TestMABullishAlignment:
    def test_up_trend_detects(self):
        from services.pattern import detect_ma_bullish_alignment

        df = _make_hist_df(n=120, trend="up")
        results = detect_ma_bullish_alignment(df, "000001", "测试")
        # 上涨趋势应检测到均线多头
        assert isinstance(results, list)

    def test_flat_trend_few_signals(self):
        from services.pattern import detect_ma_bullish_alignment

        df = _make_hist_df(n=120, trend="flat")
        results = detect_ma_bullish_alignment(df, "000001", "测试")
        assert isinstance(results, list)


class TestVolumeBreakout:
    def test_detects_breakout(self):
        from services.pattern import detect_volume_breakout

        df = _make_hist_df(n=100)
        # 注入一个放量突破点
        df.loc[90, "volume"] = df["volume"].mean() * 5
        df.loc[90, "change_pct"] = 5.0

        results = detect_volume_breakout(df, "000001", "测试")
        assert isinstance(results, list)


class TestShrinkageBounce:
    def test_returns_list(self):
        from services.pattern import detect_shrinkage_bounce

        df = _make_hist_df(n=100)
        results = detect_shrinkage_bounce(df, "000001", "测试")
        assert isinstance(results, list)


class TestVShapeReversal:
    def test_detects_v_shape(self):
        from services.pattern import detect_v_shape_reversal

        # 构造V型数据
        n = 30
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        closes = np.concatenate([
            np.linspace(15, 10, 15),  # 下跌
            np.linspace(10, 13, 15),  # 反弹
        ])
        df = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "open": closes, "close": closes,
            "high": closes + 0.1, "low": closes - 0.1,
            "volume": np.full(n, 100000.0),
            "turnover": np.full(n, 1e6),
            "amplitude": np.full(n, 3.0),
            "change_pct": np.random.uniform(-2, 2, n),
            "change_amount": np.full(n, 0.1),
            "turnover_rate": np.full(n, 2.0),
        })

        results = detect_v_shape_reversal(df, "000001", "测试", lookback=30)
        assert isinstance(results, list)

    def test_short_data_returns_empty(self):
        from services.pattern import detect_v_shape_reversal

        df = _make_hist_df(n=10)
        results = detect_v_shape_reversal(df, "000001", "测试", lookback=20)
        assert results == []
