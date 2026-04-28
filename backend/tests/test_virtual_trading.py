"""虚拟交易引擎单元测试"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np


def _mock_quote(code, price=10.0):
    """构造模拟行情返回"""
    return pd.DataFrame([{
        "code": code, "name": f"测试{code}",
        "price": price, "change_pct": 1.0,
        "volume": 100000, "turnover": 1e6,
        "high": price + 0.2, "low": price - 0.2,
        "open": price, "prev_close": price - 0.1,
    }])


@pytest.fixture(autouse=True)
def isolated_account(tmp_path, monkeypatch):
    """每个测试用独立账户文件"""
    import services.virtual_trading as vt
    data_file = tmp_path / "account.json"
    monkeypatch.setattr(vt, "DATA_FILE", data_file)

    # 重置全局账户
    vt._account = None
    yield
    vt._account = None


@patch("services.virtual_trading.get_realtime_quote")
class TestPlaceOrder:
    def test_buy_success(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        result = vt.place_order("000001", "测试", "buy", 100)
        assert result["status"] == "filled"
        assert result["filled_price"] > 0
        assert "000001" in vt._get_account().positions

    def test_buy_insufficient_funds(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 100000.0)

        result = vt.place_order("000001", "测试", "buy", 100)
        assert result["status"] == "rejected"
        assert "资金不足" in result["reason"]

    def test_sell_success(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        # 先买入
        vt.place_order("000001", "测试", "buy", 100)
        # T+1 日结
        vt.settle_day()
        # 再卖出
        result = vt.place_order("000001", "测试", "sell", 100)
        assert result["status"] == "filled"

    def test_sell_no_position(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000002", 10.0)

        result = vt.place_order("000002", "测试", "sell", 100)
        assert result["status"] == "rejected"

    def test_sell_t1_locked(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        # 买入后未日结，不可卖
        vt.place_order("000001", "测试", "buy", 100)
        result = vt.place_order("000001", "测试", "sell", 100)
        assert result["status"] == "rejected"
        assert "可卖不足" in result["reason"]


@patch("services.virtual_trading.get_realtime_quote")
class TestAccount:
    def test_initial_cash(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = pd.DataFrame()

        info = vt.get_account_info()
        assert info["cash"] == 1_000_000
        assert len(info["positions"]) == 0

    def test_total_assets_after_buy(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        vt.place_order("000001", "测试", "buy", 1000)
        info = vt.get_account_info()
        assert info["total_assets"] > 0
        assert len(info["positions"]) == 1

    def test_persistence(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        vt.place_order("000001", "测试", "buy", 100)

        # 重置内存，从文件加载
        vt._account = None
        acc = vt._get_account()
        assert "000001" in acc.positions
        assert acc.positions["000001"].quantity == 100

    def test_reset_account(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        vt.place_order("000001", "测试", "buy", 100)
        vt.reset_account()
        info = vt.get_account_info()
        assert info["cash"] == 1_000_000
        assert len(info["positions"]) == 0


@patch("services.virtual_trading.get_realtime_quote")
class TestSettleDay:
    def test_settle_makes_available(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        vt.place_order("000001", "测试", "buy", 200)
        acc = vt._get_account()
        assert acc.positions["000001"].available == 0

        vt.settle_day()
        acc = vt._get_account()
        assert acc.positions["000001"].available == 200


@patch("services.virtual_trading.get_realtime_quote")
class TestCommission:
    def test_commission_deducted(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        initial_cash = vt._get_account().cash
        vt.place_order("000001", "测试", "buy", 100)
        cost = initial_cash - vt._get_account().cash
        # 成交额 1000 + 佣金(>=5) + 滑点
        assert cost > 1000
        assert cost < 1020

    def test_sell_with_stamp_tax(self, mock_quote):
        import services.virtual_trading as vt
        mock_quote.return_value = _mock_quote("000001", 10.0)

        vt.place_order("000001", "测试", "buy", 100)
        vt.settle_day()

        cash_before = vt._get_account().cash
        vt.place_order("000001", "测试", "sell", 100)
        received = vt._get_account().cash - cash_before
        # 收到约1000 - 佣金5 - 印花税1 - 滑点
        assert received < 1000
        assert received > 980
