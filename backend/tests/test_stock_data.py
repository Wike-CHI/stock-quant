"""stock_data 模块单元测试"""
import pytest
import pandas as pd
import numpy as np


def _make_em_response(n=10):
    """模拟东方财富 push2 API 响应"""
    diff = []
    for i in range(n):
        diff.append({
            "f2": 10.0 + i, "f3": i * 0.5 - 1.0, "f4": 0.1,
            "f5": 100000, "f6": 1000000.0, "f7": 2.0,
            "f8": 1.5, "f9": 20.0, "f10": 1.0,
            "f12": f"00000{i}", "f14": f"测试股{i}",
            "f15": 11.0, "f16": 9.0, "f17": 10.0, "f18": 10.0,
            "f20": 1e10, "f21": 5e9, "f23": 2.0,
        })
    return {"data": {"total": n, "diff": diff}}


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


def _mock_prewarm(mod, n=10):
    """辅助：直接设置内存数据，跳过网络"""
    resp = _make_em_response(n)
    rows = []
    for item in resp["data"]["diff"]:
        row = {}
        for fcode, col in mod.EM_FIELD_MAP.items():
            val = item.get(fcode, "-")
            row[col] = None if val == "-" else val
        rows.append(row)
    mod._spot_df = pd.DataFrame(rows)


class TestSpotColumns:
    """验证列名映射完整性"""

    def test_em_field_map_covers_required_columns(self):
        from services.stock_data import EM_FIELD_MAP

        required = {"code", "name", "price", "change_pct", "volume", "turnover",
                    "high", "low", "open", "prev_close", "turnover_rate", "pe", "pb"}
        for col in required:
            assert col in EM_FIELD_MAP.values(), f"缺少映射: {col}"

    def test_hist_columns_all_mapped(self):
        from services.stock_data import HIST_COLUMNS

        raw_cols = _make_hist_df().columns.tolist()
        for col in raw_cols:
            assert col in HIST_COLUMNS, f"未映射列: {col}"


class TestCache:
    """验证内存缓存机制"""

    def test_prewarm_sets_spot_data(self):
        import services.stock_data as mod

        _mock_prewarm(mod, 10)
        with mod._spot_lock:
            assert mod._spot_df is not None
            assert len(mod._spot_df) == 10

    def test_get_stock_list_returns_from_memory(self):
        import services.stock_data as mod

        _mock_prewarm(mod, 10)
        df = mod.get_a_stock_list()
        assert len(df) == 10
        assert "code" in df.columns

    def test_realtime_quote_filters_by_codes(self):
        import services.stock_data as mod

        _mock_prewarm(mod, 10)
        df = mod.get_realtime_quote(["000000", "000001"])
        assert len(df) == 2

    def test_hist_cache(self):
        import services.stock_data as mod
        from unittest.mock import patch

        mod._hist_cache_ts.clear()
        mod._hist_cache_df.clear()

        call_count = 0
        def mock_hist(*a, **kw):
            nonlocal call_count
            call_count += 1
            return _make_hist_df()

        with patch.object(mod.ak, "stock_zh_a_hist", side_effect=mock_hist):
            df1 = mod.get_stock_history("000001")
            assert call_count == 1

            df2 = mod.get_stock_history("000001")
            assert call_count == 1  # cached
            assert len(df1) == len(df2)


class TestDataHelpers:
    """验证数据处理辅助函数"""

    def test_make_em_response_has_all_fields(self):
        from services.stock_data import EM_FIELD_MAP

        resp = _make_em_response()
        for fcode in EM_FIELD_MAP:
            assert fcode in resp["data"]["diff"][0], f"模拟数据缺少字段: {fcode}"

    def test_make_hist_df_has_all_columns(self):
        from services.stock_data import HIST_COLUMNS

        df = _make_hist_df()
        for col in HIST_COLUMNS:
            assert col in df.columns, f"模拟数据缺少列: {col}"
