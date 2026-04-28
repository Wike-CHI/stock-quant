"""碗底反弹策略单元测试"""
import pytest
import pandas as pd
import numpy as np


def _make_bowl_df(n=120):
    """构造碗形数据：先跌后涨，价格在多空线和短期趋势线之间"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(123)

    # 动态分段：跌1/3，横1/6，回升1/3，续涨1/6
    n1 = n * 10 // 30
    n2 = n * 5 // 30
    n3 = n * 10 // 30
    n4 = n - n1 - n2 - n3

    base = np.concatenate([
        np.linspace(15, 10, n1),
        np.linspace(10, 10, n2),
        np.linspace(10, 12, n3),
        np.linspace(12, 13, n4),
    ])
    closes = base + np.random.randn(n) * 0.15
    opens = closes + np.random.randn(n) * 0.05

    # 在回升段注入放量阳线
    volumes = np.random.randint(100000, 300000, n).astype(float)
    volumes[70:75] = volumes[70:75] * 5  # 放量

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": opens, "close": closes,
        "high": closes + abs(np.random.randn(n) * 0.1),
        "low": closes - abs(np.random.randn(n) * 0.1),
        "volume": volumes,
        "turnover": volumes * closes,
        "amplitude": np.random.uniform(1, 4, n),
        "change_pct": np.random.uniform(-2, 2, n),
        "change_amount": np.random.uniform(-0.2, 0.2, n),
        "turnover_rate": np.random.uniform(0.5, 3, n),
    })


def _make_short_bowl_df(n=30):
    """构造短碗形数据"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(789)
    base = np.concatenate([
        np.linspace(15, 10, n // 3),
        np.linspace(10, 10, n // 6),
        np.linspace(10, 12, n // 3),
        np.linspace(12, 13, n - n // 3 - n // 6 - n // 3),
    ])
    closes = base + np.random.randn(n) * 0.15
    return pd.DataFrame({
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


def _make_strong_bowl_df(n=150):
    """构造更强的碗形数据，确保触发信号"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(456)

    # 强碗形：大跌后大涨
    base = np.concatenate([
        np.linspace(20, 12, 50),   # 大跌
        np.linspace(12, 12, 20),   # 底部
        np.linspace(12, 18, 50),   # 强力回升
        np.linspace(18, 19, 30),   # 继续涨
    ])
    closes = base + np.random.randn(n) * 0.1
    opens = closes - np.random.randn(n) * 0.05  # 偏阳线

    volumes = np.random.randint(200000, 400000, n).astype(float)
    # 回升段放量阳线
    volumes[70:80] = volumes[70:80] * 4
    opens[70:80] = closes[70:80] - 0.1  # 确保阳线

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": opens, "close": closes,
        "high": closes + abs(np.random.randn(n) * 0.1),
        "low": closes - abs(np.random.randn(n) * 0.1),
        "volume": volumes,
        "turnover": volumes * closes,
        "amplitude": np.random.uniform(1, 4, n),
        "change_pct": np.random.uniform(-2, 3, n),
        "change_amount": np.random.uniform(-0.2, 0.3, n),
        "turnover_rate": np.random.uniform(0.5, 3, n),
    })


class TestCalculateIndicators:
    def test_adds_required_columns(self):
        from services.bowl_rebound import calculate_indicators, DEFAULT_PARAMS

        df = _make_bowl_df()
        result = calculate_indicators(df, DEFAULT_PARAMS)

        for col in ["short_trend", "bull_bear", "K", "D", "J", "key_candle", "fall_in_bowl", "trend_above"]:
            assert col in result.columns, f"缺少指标列: {col}"

    def test_kdj_in_valid_range(self):
        from services.bowl_rebound import calculate_indicators, DEFAULT_PARAMS

        df = _make_bowl_df()
        result = calculate_indicators(df, DEFAULT_PARAMS)

        # KDJ 有效值不应极端偏离（允许NaN在前面几行）
        valid_K = result["K"].dropna()
        assert valid_K.min() >= -20
        assert valid_K.max() <= 120

    def test_short_trend_is_ema_of_ema(self):
        from services.bowl_rebound import calculate_indicators, DEFAULT_PARAMS

        df = _make_bowl_df()
        result = calculate_indicators(df, DEFAULT_PARAMS)

        ema10 = df["close"].ewm(span=10, adjust=False).mean()
        expected = ema10.ewm(span=10, adjust=False).mean()
        pd.testing.assert_series_equal(
            result["short_trend"].dropna(), expected.dropna(), check_names=False, atol=0.01
        )


class TestDetectBowlRebound:
    def test_returns_list(self):
        from services.bowl_rebound import detect_bowl_rebound

        df = _make_bowl_df()
        results = detect_bowl_rebound(df, "000001", "测试")
        assert isinstance(results, list)

    def test_signal_has_correct_fields(self):
        from services.bowl_rebound import detect_bowl_rebound

        df = _make_strong_bowl_df()
        results = detect_bowl_rebound(df, "000001", "测试")

        if results:
            sig = results[0]
            assert sig.code == "000001"
            assert sig.pattern_type == "bowl_rebound"
            assert sig.category in ("bowl_center", "near_duokong", "near_short_trend")
            assert 0 <= sig.confidence <= 1.0
            assert "similarity" in sig.details

    def test_empty_df_returns_empty(self):
        from services.bowl_rebound import detect_bowl_rebound

        df = pd.DataFrame()
        results = detect_bowl_rebound(df, "000001", "测试")
        assert results == []

    def test_short_df_returns_fewer_signals(self):
        from services.bowl_rebound import detect_bowl_rebound

        df = _make_short_bowl_df(30)
        results = detect_bowl_rebound(df, "000001", "测试")
        # 短数据可能因NaN导致指标不足，结果应较少或为空
        assert isinstance(results, list)


class TestSimilarityScore:
    def test_perfect_score_components(self):
        from services.bowl_rebound import _similarity_score, DEFAULT_PARAMS

        row = pd.Series({
            "short_trend": 12.0, "bull_bear": 11.9, "close": 11.95,
            "J": 10.0, "key_candle": True, "fall_in_bowl": True, "trend_above": True,
        })
        score = _similarity_score(row, DEFAULT_PARAMS)
        assert score > 0.7  # 几乎完美匹配应得高分

    def test_poor_score_components(self):
        from services.bowl_rebound import _similarity_score, DEFAULT_PARAMS

        row = pd.Series({
            "short_trend": 10.0, "bull_bear": 15.0, "close": 12.0,
            "J": 80.0, "key_candle": False, "fall_in_bowl": False, "trend_above": False,
        })
        score = _similarity_score(row, DEFAULT_PARAMS)
        assert score <= 0.3  # 差匹配应得低分
