"""
AKQuant 回测服务

封装 AKQuant 回测引擎，提供：
- 碗底反弹策略回测
- 自定义策略回测
- 回测报告生成
"""
import logging
from dataclasses import dataclass

import akquant as aq
from akquant import Strategy, Bar
import numpy as np
import pandas as pd

from services.stock_data import get_stock_history

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    t_plus_one: bool = True
    lot_size: int = 100
    slippage: float = 0.0


DEFAULT_BT_CONFIG = BacktestConfig()


class BowlReboundBTStrategy(Strategy):
    """碗底反弹回测策略

    基于双趋势线 + KDJ + 放量阳线信号进行买卖。
    买入条件：回落碗中 + KDJ低位 + 近期有放量阳线
    卖出条件：止盈10% 或 止损5% 或 离开碗口
    """

    def __init__(self, params: dict | None = None):
        super().__init__()
        from services.bowl_rebound import DEFAULT_PARAMS
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.entry_prices: dict[str, float] = {}
        self.short_window = 10
        self.ma_periods = [self.params["M1"], self.params["M2"], self.params["M3"], self.params["M4"]]
        self.max_lookback = max(self.ma_periods) + 10
        self.warmup_period = self.max_lookback + 1

    def on_bar(self, bar: Bar):
        symbol = bar.symbol
        pos = self.position
        close = bar.close

        # get_history 不含当前 bar，+1 以包含足够数据
        closes = self.get_history(count=self.max_lookback, field="close")
        if len(closes) < self.max_lookback:
            return

        highs = self.get_history(count=9, field="high")
        lows = self.get_history(count=9, field="low")
        volumes = self.get_history(count=int(self.params["M"]), field="volume")
        opens = self.get_history(count=int(self.params["M"]), field="open")

        # 短期趋势线（含当前bar的close）
        all_closes = np.append(closes, close)
        ema10 = pd.Series(all_closes).ewm(span=self.short_window, adjust=False).mean()
        short_trend = float(ema10.ewm(span=self.short_window, adjust=False).mean().values[-1])

        # 多空线
        ma_vals = []
        for p in self.ma_periods:
            if len(all_closes) >= p:
                ma_vals.append(float(all_closes[-p:].mean()))
        if len(ma_vals) < 4:
            return
        bull_bear = sum(ma_vals) / len(ma_vals)

        # KDJ（用 history 的 high/low + 当前 bar）
        all_highs = np.append(highs, bar.high)
        all_lows = np.append(lows, bar.low)
        low_9 = float(all_lows[-9:].min())
        high_9 = float(all_highs[-9:].max())
        denom = high_9 - low_9 if high_9 != low_9 else 1
        rsv = (close - low_9) / denom * 100

        # 近似 J 值（简化版，完整 KDJ 需要累积状态）
        j_val = rsv  # 简化为 RSV 作为 J 的近似

        # 判断碗底信号
        fall_in_bowl = (close > bull_bear) and (close < short_trend) and (bull_bear < short_trend)
        near_duokong = abs(close - bull_bear) / bull_bear * 100 <= self.params["duokong_pct"]
        near_short = abs(close - short_trend) / short_trend * 100 <= self.params["short_pct"]

        bowl_signal = fall_in_bowl or near_duokong or near_short

        # 关键K线：近期放量阳线
        vol_threshold = float(volumes.mean() * self.params["N"]) if len(volumes) > 0 else 0
        has_key_candle = False
        for k in range(len(volumes)):
            if float(volumes[k]) >= vol_threshold and float(closes[k]) > float(opens[k]):
                has_key_candle = True
                break

        # 买入
        if pos.size == 0 and bowl_signal and j_val <= self.params["J_VAL"] and has_key_candle:
            self.order_target_percent(target_percent=0.3, symbol=symbol)
            self.entry_prices[symbol] = close
            return

        # 卖出
        if pos.size > 0 and pos.available > 0:
            entry = self.entry_prices.get(symbol, close)
            pnl = (close - entry) / entry

            if pnl >= 0.10:
                self.sell(symbol, pos.available)
            elif pnl <= -0.05:
                self.sell(symbol, pos.available)
            elif close > short_trend * 1.02:
                self.sell(symbol, pos.available)


def run_backtest(
    code: str,
    strategy_class: type | None = None,
    start_date: str = "20240101",
    end_date: str = "",
    config: BacktestConfig | None = None,
    strategy_params: dict | None = None,
) -> dict:
    """执行回测"""
    cfg = config or DEFAULT_BT_CONFIG
    strat_cls = strategy_class or BowlReboundBTStrategy

    df = get_stock_history(code, start_date=start_date, end_date=end_date or None)
    if df.empty:
        return {"error": f"无数据: {code}"}

    df = df.copy()
    df["symbol"] = code

    strat_instance = strat_cls(params=strategy_params) if strategy_params else strat_cls()

    result = aq.run_backtest(
        strategy=strat_instance,
        data=df,
        symbols=code,
        initial_cash=cfg.initial_cash,
        commission_rate=cfg.commission_rate,
        stamp_tax_rate=cfg.stamp_tax_rate,
        t_plus_one=cfg.t_plus_one,
        lot_size=cfg.lot_size,
        slippage=cfg.slippage,
    )

    metrics = result.metrics
    raw = metrics._raw
    return {
        "code": code,
        "total_return_pct": round(raw.total_return_pct, 2),
        "sharpe_ratio": round(raw.sharpe_ratio, 2),
        "max_drawdown_pct": round(raw.max_drawdown_pct, 2),
        "end_market_value": round(raw.end_market_value, 2),
        "total_bars": raw.total_bars,
        "win_rate": round(raw.win_rate, 2) if raw.win_rate else 0,
    }
