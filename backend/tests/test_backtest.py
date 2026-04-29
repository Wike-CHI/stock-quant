"""AKQuant 回测服务单元测试"""
import pytest
import pandas as pd
import numpy as np


def _make_bt_data(n=200, symbol="000001"):
    """构造回测数据"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)
    base = np.linspace(10, 12, n)
    noise = np.random.randn(n) * 0.3
    closes = base + noise
    opens = closes + np.random.randn(n) * 0.05

    # 注入碗形段（后半段先跌后涨）
    n2 = n // 2
    closes[n2:] = np.concatenate([
        np.linspace(13, 10, n2 // 3),
        np.linspace(10, 10, n2 // 6),
        np.linspace(10, 12, n2 // 3),
        np.linspace(12, 13, n2 - n2 // 3 - n2 // 6 - n2 // 3),
    ])
    opens[n2:] = closes[n2:] + np.random.randn(n2) * 0.02

    volumes = np.random.randint(100000, 500000, n).astype(float)
    volumes[n2 + n2 // 3: n2 + n2 // 3 + 5] *= 4  # 放量段

    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "timestamp": dates.astype("int64") // 10**6,
        "symbol": symbol,
        "open": opens, "close": closes,
        "high": closes + abs(np.random.randn(n) * 0.1),
        "low": closes - abs(np.random.randn(n) * 0.1),
        "volume": volumes,
    })


class TestBowlReboundBTStrategy:
    def test_strategy_runs_without_error(self):
        from services.backtest import BowlReboundBTStrategy
        import akquant as aq

        df = _make_bt_data()
        result = aq.run_backtest(
            strategy=BowlReboundBTStrategy(),
            data=df,
            symbols="000001",
            initial_cash=100_000,
            commission_rate=0.0003,
            stamp_tax_rate=0.001,
            t_plus_one=True,
            lot_size=100,
        )
        assert result is not None
        assert result.metrics is not None

    def test_strategy_has_metrics(self):
        from services.backtest import BowlReboundBTStrategy
        import akquant as aq

        df = _make_bt_data()
        result = aq.run_backtest(
            strategy=BowlReboundBTStrategy(),
            data=df,
            symbols="000001",
            initial_cash=100_000,
            t_plus_one=True,
        )
        metrics = result.metrics
        assert hasattr(metrics, "total_return_pct")
        assert hasattr(metrics, "sharpe_ratio")
        assert hasattr(metrics, "max_drawdown_pct")
        assert hasattr(metrics, "end_market_value")

    def test_strategy_with_custom_params(self):
        from services.backtest import BowlReboundBTStrategy
        import akquant as aq

        df = _make_bt_data()
        params = {"N": 3.0, "J_VAL": 20, "M1": 14, "M2": 28, "M3": 57, "M4": 114}
        result = aq.run_backtest(
            strategy=BowlReboundBTStrategy(params=params),
            data=df,
            symbols="000001",
            initial_cash=100_000,
        )
        assert result is not None


class TestBacktestConfig:
    def test_default_config(self):
        from services.backtest import BacktestConfig

        cfg = BacktestConfig()
        assert cfg.initial_cash == 1_000_000
        assert cfg.t_plus_one is True
        assert cfg.lot_size == 100
        assert cfg.stamp_tax_rate == 0.001

    def test_custom_config(self):
        from services.backtest import BacktestConfig

        cfg = BacktestConfig(initial_cash=500_000, slippage=0.001)
        assert cfg.initial_cash == 500_000
        assert cfg.slippage == 0.001
