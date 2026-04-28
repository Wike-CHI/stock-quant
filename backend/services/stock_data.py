import logging
import time
from functools import lru_cache
from typing import Optional

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

SPOT_COLUMNS = {
    "序号": "index", "代码": "code", "名称": "name",
    "最新价": "price", "涨跌幅": "change_pct", "涨跌额": "change_amount",
    "成交量": "volume", "成交额": "turnover", "振幅": "amplitude",
    "最高": "high", "最低": "low", "今开": "open", "昨收": "prev_close",
    "量比": "vol_ratio", "换手率": "turnover_rate",
    "市盈率-动态": "pe", "市净率": "pb",
    "总市值": "total_mv", "流通市值": "circ_mv",
    "涨速": "speed", "5分钟涨跌": "min5_change",
    "60日涨跌幅": "d60_change", "年初至今涨跌幅": "ytd_change",
}

HIST_COLUMNS = {
    "日期": "date", "股票代码": "code",
    "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "turnover",
    "振幅": "amplitude", "涨跌幅": "change_pct",
    "涨跌额": "change_amount", "换手率": "turnover_rate",
}

_cache_ts: dict[str, float] = {}
_cache_df: dict[str, pd.DataFrame] = {}
_CACHE_TTL = 60  # seconds


def _get_cached(key: str) -> Optional[pd.DataFrame]:
    if key in _cache_df and (time.time() - _cache_ts[key]) < _CACHE_TTL:
        return _cache_df[key].copy()
    return None


def _set_cached(key: str, df: pd.DataFrame):
    _cache_df[key] = df.copy()
    _cache_ts[key] = time.time()


def get_a_stock_list() -> pd.DataFrame:
    """获取A股实时行情（沪深两市，60秒缓存）"""
    cached = _get_cached("spot")
    if cached is not None:
        return cached

    df = ak.stock_zh_a_spot_em()
    df = df.rename(columns=SPOT_COLUMNS)
    keep = [c for c in SPOT_COLUMNS.values() if c in df.columns]
    df = df[keep]
    _set_cached("spot", df)
    return df


def get_stock_history(
    code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取个股历史行情"""
    df = ak.stock_zh_a_hist(
        symbol=code,
        period=period,
        start_date=start_date or "20240101",
        end_date=end_date or "",
        adjust=adjust,
    )
    df = df.rename(columns=HIST_COLUMNS)
    keep = [c for c in HIST_COLUMNS.values() if c in df.columns]
    return df[keep]


def get_realtime_quote(codes: list[str]) -> pd.DataFrame:
    """获取指定股票的实时行情（从缓存中过滤）"""
    df = get_a_stock_list()
    return df[df["code"].isin(codes)]


def get_top_gainers(limit: int = 50) -> pd.DataFrame:
    """获取涨幅排行榜"""
    df = get_a_stock_list()
    df = df.dropna(subset=["change_pct"])
    df = df.sort_values("change_pct", ascending=False)
    return df.head(limit)
