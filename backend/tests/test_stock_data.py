"""stock_data 模块单元测试"""
import pytest
import pandas as pd
import numpy as np


def _make_spot_df(n=10):
    """构造模拟的 stock_zh_a_spot_em 返回数据"""
    return pd.DataFrame({
        "序号": range(n), "代码": [f"00000{i}" for i in range(n)],
        "名称": [f"测试股{i}" for i in range(n)],
        "最新价": [10.0 + i for i in range(n)],
        "涨跌幅": [i * 0.5 - 1.0 for i in range(n)],
        "涨跌额": [0.1] * n, "成交量": [100000] * n, "成交额": [1000000.0] * n,
        "振幅": [2.0] * n, "最高": [11.0] * n, "最低": [9.0] * n,
        "今开": [10.0] * n, "昨收": [10.0] * n,
        "量比": [1.0] * n, "换手率": [1.5] * n,
        "市盈率-动态": [20.0] * n, "市净率": [2.0] * n,
        "总市值": [1e10] * n, "流通市值": [5e9] * n,
        "涨速": [0.1] * n, "5分钟涨跌": [0.2] * n,
        "60日涨跌幅": [5.0] * n, "年初至今涨跌幅": [3.0] * n,
    })


def _make_hist_df(n=100):
    """构造模拟的 stock_zh_a_hist 返回数据"""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    np.random.seed(42)
    base = 10.0
    closes = base + np.cumsum(np.random.randn(n) * 0.3)
    opens = closes + np.random.randn(n) * 0.1
    return pd.DataFrame({
        "日期": dates.strftime("%Y-%m-%d"),
        "股票代码": ["000001"] * n,
        "开盘": opens, "收盘": closes,
        "最高": closes + abs(np.random.randn(n) * 0.2),
        "最低": closes - abs(np.random.randn(n) * 0.2),
        "成交量": np.random.randint(100000, 500000, n),
        "成交额": np.random.uniform(1e6, 5e6, n),
        "振幅": np.random.uniform(1, 5, n),
        "涨跌幅": np.random.uniform(-3, 3, n),
        "涨跌额": np.random.uniform(-0.5, 0.5, n),
        "换手率": np.random.uniform(0.5, 5, n),
    })


class TestSpotColumns:
    """验证列名映射完整性"""

    def test_spot_columns_all_mapped(self):
        from services.stock_data import SPOT_COLUMNS

        raw_cols = _make_spot_df().columns.tolist()
        for col in raw_cols:
            assert col in SPOT_COLUMNS, f"未映射列: {col}"

    def test_hist_columns_all_mapped(self):
        from services.stock_data import HIST_COLUMNS

        raw_cols = _make_hist_df().columns.tolist()
        for col in raw_cols:
            assert col in HIST_COLUMNS, f"未映射列: {col}"


class TestCache:
    """验证缓存机制"""

    def test_cache_miss_returns_none(self):
        from services.stock_data import _get_cached

        assert _get_cached("nonexistent_key") is None

    def test_cache_set_and_get(self):
        from services.stock_data import _set_cached, _get_cached

        df = _make_spot_df()
        _set_cached("test_key", df)

        cached = _get_cached("test_key")
        assert cached is not None
        assert len(cached) == len(df)


class TestDataHelpers:
    """验证数据处理辅助函数"""

    def test_make_spot_df_has_all_columns(self):
        from services.stock_data import SPOT_COLUMNS

        df = _make_spot_df()
        for col in SPOT_COLUMNS:
            assert col in df.columns, f"模拟数据缺少列: {col}"

    def test_make_hist_df_has_all_columns(self):
        from services.stock_data import HIST_COLUMNS

        df = _make_hist_df()
        for col in HIST_COLUMNS:
            assert col in df.columns, f"模拟数据缺少列: {col}"
