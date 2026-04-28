import logging
from typing import Optional

import akshare as ak
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def get_a_stock_list() -> pd.DataFrame:
    """获取A股列表（沪深两市）"""
    df = ak.stock_zh_a_spot_em()
    df = df.rename(columns={
        "序号": "index",
        "代码": "code",
        "名称": "name",
        "最新价": "price",
        "涨跌幅": "change_pct",
        "涨跌额": "change_amount",
        "成交量": "volume",
        "成交额": "turnover",
        "振幅": "amplitude",
        "最高": "high",
        "最低": "low",
        "今开": "open",
        "昨收": "prev_close",
    })
    return df[["code", "name", "price", "change_pct", "volume", "turnover", "high", "low", "open", "prev_close"]]


def get_stock_history(
    code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取个股历史行情（前复权）"""
    df = ak.stock_zh_a_hist(
        symbol=code,
        period=period,
        start_date=start_date or "20240101",
        end_date=end_date or "",
        adjust=adjust,
    )
    df = df.rename(columns={
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "turnover",
        "振幅": "amplitude",
        "涨跌幅": "change_pct",
        "涨跌额": "change_amount",
        "换手率": "turnover_rate",
    })
    return df


def get_realtime_quote(codes: list[str]) -> pd.DataFrame:
    """获取指定股票的实时行情"""
    df = get_a_stock_list()
    return df[df["code"].isin(codes)]


def get_top_gainers(limit: int = 50) -> pd.DataFrame:
    """获取涨幅排行榜"""
    df = get_a_stock_list()
    df = df.dropna(subset=["change_pct"])
    df = df.sort_values("change_pct", ascending=False)
    return df.head(limit)
