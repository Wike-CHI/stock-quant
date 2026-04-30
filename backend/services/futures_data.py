"""
期货行情数据服务

多数据源架构：
- 主力合约列表：akshare futures_display_main_sina()
- 实时行情：新浪 hq.sinajs.cn HTTP
- 历史K线：akshare futures_main_sina()
- 涨跌停状态：品种映射表

期货特有字段：open_interest（持仓量），settle（昨结算价）
"""
import logging
import threading
import time
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ── 新浪期货实时行情 ─────────────────────────────────────────────
# 新浪期货代码格式：交易所前缀 + 品种代码 + 0（主力）/ 合约代码
# 如：RB0=螺纹钢主力, C0=玉米主力, IF0=沪深300主力
SINA_FUTURES_URL = "http://hq.sinajs.cn/list="

# ── 期货涨跌停幅度（按品种前缀，常规值）─────────────────────────
_FUTURES_LIMIT_PCT: dict[str, float] = {
    "IF": 10, "IC": 10, "IH": 10, "IM": 10,
    "TS": 1.5, "TF": 2, "T": 2, "TL": 2,
    "CU": 6, "AL": 6, "ZN": 8, "PB": 6, "NI": 10,
    "SN": 8, "AU": 6, "AG": 8, "RB": 6, "HC": 6,
    "SS": 8, "BU": 8, "RU": 8, "NR": 8, "SP": 8,
    "FU": 8, "SC": 8, "LU": 8, "BC": 6, "AO": 8,
    "M": 6, "Y": 6, "P": 6, "A": 6, "B": 6,
    "C": 6, "CS": 6, "JD": 6, "LH": 8, "I": 11,
    "J": 11, "JM": 11, "EG": 8, "EB": 8, "PG": 8,
    "PP": 6, "V": 6, "L": 6, "MA": 6, "UR": 8,
    "SA": 8, "FG": 8, "TA": 6, "PF": 6, "SM": 8,
    "SF": 8, "SR": 6, "CF": 6, "CY": 6, "OI": 6,
    "RM": 6, "AP": 8, "CJ": 8, "PK": 6, "SH": 8,
    "SI": 8, "LC": 8,
}

# ── 品种→交易所映射 ──────────────────────────────────────────────
_PRODUCT_EXCHANGE: dict[str, str] = {
    "IF": "CFFEX", "IC": "CFFEX", "IH": "CFFEX", "IM": "CFFEX",
    "TS": "CFFEX", "TF": "CFFEX", "T": "CFFEX", "TL": "CFFEX",
    "CU": "SHFE", "AL": "SHFE", "ZN": "SHFE", "PB": "SHFE",
    "NI": "SHFE", "SN": "SHFE", "AU": "SHFE", "AG": "SHFE",
    "RB": "SHFE", "HC": "SHFE", "SS": "SHFE", "BU": "SHFE",
    "RU": "SHFE", "NR": "SHFE", "SP": "SHFE", "FU": "SHFE",
    "AO": "SHFE", "BC": "SHFE",
    "M": "DCE", "Y": "DCE", "P": "DCE", "A": "DCE", "B": "DCE",
    "C": "DCE", "CS": "DCE", "JD": "DCE", "LH": "DCE",
    "I": "DCE", "J": "DCE", "JM": "DCE", "EG": "DCE",
    "EB": "DCE", "PG": "DCE", "PP": "DCE", "V": "DCE", "L": "DCE",
    "MA": "CZCE", "UR": "CZCE", "SA": "CZCE", "FG": "CZCE",
    "TA": "CZCE", "PF": "CZCE", "SM": "CZCE", "SF": "CZCE",
    "SR": "CZCE", "CF": "CZCE", "CY": "CZCE", "OI": "CZCE",
    "RM": "CZCE", "AP": "CZCE", "CJ": "CZCE", "PK": "CZCE", "SH": "CZCE",
    "SC": "INE", "LU": "INE", "NR": "SHFE",
    "SI": "GFEX", "LC": "GFEX",
}


def _extract_product(code: str) -> str:
    """从合约代码提取品种前缀：RB2405→RB, C0→C, if2401→IF"""
    return code.rstrip("0123456789").upper()


def get_futures_limit_pct(code: str) -> float:
    return _FUTURES_LIMIT_PCT.get(_extract_product(code), 6.0)


def get_futures_exchange(code: str) -> str:
    return _PRODUCT_EXCHANGE.get(_extract_product(code), "SHFE")


def get_futures_status(price: float | None, prev_close: float | None, code: str) -> str:
    if price is None or prev_close is None or prev_close == 0:
        return "normal"
    limit_pct = get_futures_limit_pct(code)
    limit_up = round(prev_close * (1 + limit_pct / 100), 2)
    limit_down = round(prev_close * (1 - limit_pct / 100), 2)
    if price >= limit_up:
        return "limit_up"
    if price <= limit_down:
        return "limit_down"
    chg = (price - prev_close) / prev_close * 100
    if chg >= limit_pct * 0.85:
        return "near_limit_up"
    if chg <= -limit_pct * 0.85:
        return "near_limit_down"
    return "normal"


# ── 行情缓存 ──────────────────────────────────────────────────────
_futures_df: Optional[pd.DataFrame] = None
_futures_lock = threading.Lock()
FUTURES_REFRESH_INTERVAL = 30

_hist_cache_ts: dict[str, float] = {}
_hist_cache_df: dict[str, pd.DataFrame] = {}
_HIST_CACHE_MAX = 2000


# ── 新浪行情解析 ─────────────────────────────────────────────────

def _fetch_sina_quotes(symbols: list[str]) -> pd.DataFrame:
    """
    新浪期货实时行情
    返回字段：0:名称 1:代码 2:现价 3:昨结 4:开盘 5:最高 6:最低
             7:买价 8:卖价 9:成交量 10:持仓量 13:日期
    主力合约代码如 RB0, C0, IF0 (新浪格式)
    """
    if not symbols:
        return pd.DataFrame()

    rows = []
    batch_size = 80
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        try:
            url = SINA_FUTURES_URL + ",".join(batch)
            r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=10)
            if r.status_code != 200:
                continue
            # 新浪返回 GBK 编码
            r.encoding = "gbk"
            for line in r.text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # 格式: var hq_str_RB0="螺纹钢连续,3195,3177,...";
                eq = line.find("=")
                if eq < 0:
                    continue
                var_name = line[:eq]
                # 提取代码：hq_str_RB0 → RB0
                symbol = var_name.replace("var hq_str_", "").strip()
                content_start = line.find('"', eq)
                content_end = line.rfind('"')
                if content_start < 0 or content_end <= content_start:
                    continue
                parts = line[content_start + 1:content_end].split(",")
                if len(parts) < 6:
                    continue
                try:
                    price = float(parts[2]) if parts[2] else None
                    if not price or price == 0:
                        continue
                    prev = float(parts[3]) if parts[3] else None
                    open_ = float(parts[4]) if parts[4] else None
                    high = float(parts[5]) if parts[5] else None
                    low = float(parts[6]) if parts[6] else None
                    volume = int(float(parts[9])) if len(parts) > 9 and parts[9] else 0
                    oi = int(float(parts[10])) if len(parts) > 10 and parts[10] else 0

                    chg = round((price - prev) / prev * 100, 2) if prev and price else None

                    rows.append({
                        "code": symbol,
                        "name": parts[0],
                        "price": price,
                        "prev_close": prev,
                        "open": open_,
                        "high": high,
                        "low": low,
                        "volume": volume,
                        "open_interest": oi,
                        "change_pct": chg,
                        "turnover": None,
                    })
                except (ValueError, IndexError) as e:
                    continue
        except Exception as e:
            logger.warning("Sina futures fetch failed for batch: %s", e)
            continue

    return pd.DataFrame(rows)


def _enrich_futures_status(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    codes = df["code"].astype(str)
    prices = df.get("price")
    prevs = df.get("prev_close")
    if prices is None or prevs is None:
        return df

    df["limit_pct"] = codes.apply(get_futures_limit_pct)
    df["limit_up_price"] = (prevs * (1 + df["limit_pct"] / 100)).round(2)
    df["limit_down_price"] = (prevs * (1 - df["limit_pct"] / 100)).round(2)
    df["exchange"] = codes.apply(get_futures_exchange)

    statuses = []
    for i in range(len(df)):
        statuses.append(get_futures_status(
            float(prices.iloc[i]) if pd.notna(prices.iloc[i]) else None,
            float(prevs.iloc[i]) if pd.notna(prevs.iloc[i]) else None,
            codes.iloc[i],
        ))
    df["status"] = statuses
    return df


# ── 主力合约列表 ──────────────────────────────────────────────────

def _get_main_symbols() -> list[str]:
    """获取主力合约代码列表（新浪格式：如 RB0, C0）"""
    try:
        import akshare as ak
        df = ak.futures_display_main_sina()
        if not df.empty:
            return df["symbol"].tolist()
    except Exception as e:
        logger.warning("akshare futures_display_main_sina failed: %s", e)

    # Fallback: hardcoded list of major contracts
    return [
        "IF0", "IC0", "IH0", "IM0", "TS0", "TF0", "T0", "TL0",
        "CU0", "AL0", "ZN0", "PB0", "NI0", "SN0", "AU0", "AG0",
        "RB0", "HC0", "SS0", "BU0", "RU0", "SP0", "FU0",
        "M0", "Y0", "P0", "A0", "B0", "C0", "CS0", "JD0", "LH0",
        "I0", "J0", "JM0", "EG0", "EB0", "PG0", "PP0", "V0", "L0",
        "MA0", "UR0", "SA0", "FG0", "TA0", "PF0", "SM0", "SF0",
        "SR0", "CF0", "CY0", "OI0", "RM0", "AP0", "CJ0", "PK0",
        "SC0", "LU0", "SI0", "LC0",
    ]


# ── 公开接口 ──────────────────────────────────────────────────────

def prewarm_futures():
    global _futures_df
    try:
        symbols = _get_main_symbols()
        logger.info("Fetching %d futures symbols from sina...", len(symbols))
        df = _fetch_sina_quotes(symbols)
        if not df.empty:
            df = _enrich_futures_status(df)
            with _futures_lock:
                _futures_df = df
            logger.info("Futures prewarmed: %d contracts", len(df))
        else:
            logger.warning("Futures prewarm returned empty — market may be closed")
    except Exception as e:
        logger.error("Futures prewarm failed: %s", e)


def background_futures_refresh():
    global _futures_df
    from services.trading_calendar import is_futures_trading_time
    while True:
        time.sleep(FUTURES_REFRESH_INTERVAL)
        if not is_futures_trading_time():
            continue
        try:
            symbols = _get_main_symbols()
            df = _fetch_sina_quotes(symbols)
            if not df.empty:
                df = _enrich_futures_status(df)
                with _futures_lock:
                    _futures_df = df
        except Exception as e:
            logger.error("Futures refresh failed: %s", e)


def get_futures_list() -> pd.DataFrame:
    with _futures_lock:
        if _futures_df is not None and not _futures_df.empty:
            return _futures_df.copy()
        return pd.DataFrame()


def get_main_contracts() -> pd.DataFrame:
    """主力合约 = 全量列表按成交量排序取前 60"""
    df = get_futures_list()
    if df.empty:
        return df
    return df[df["volume"] > 0].sort_values("volume", ascending=False).head(60)


def get_futures_history(
    code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """获取期货历史K线（akshare 新浪源）"""
    cache_key = f"fut-{code}-{period}-{start_date}-{end_date}"
    now = time.time()
    if cache_key in _hist_cache_df and (now - _hist_cache_ts[cache_key]) < 60:
        return _hist_cache_df[cache_key].copy()

    try:
        import akshare as ak
        if not start_date:
            start_date = "20240101"
        df = ak.futures_main_sina(symbol=code, start_date=start_date)
        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            "日期": "date", "开盘价": "open", "收盘价": "close",
            "最高价": "high", "最低价": "low",
            "成交量": "volume", "持仓量": "open_interest",
        })
        keep = [c for c in ["date", "open", "close", "high", "low", "volume", "open_interest"]
                if c in df.columns]
        df = df[keep]

        _hist_cache_df[cache_key] = df.copy()
        _hist_cache_ts[cache_key] = time.time()
        while len(_hist_cache_df) > _HIST_CACHE_MAX:
            oldest = min(_hist_cache_ts, key=_hist_cache_ts.get)
            _hist_cache_df.pop(oldest, None)
            _hist_cache_ts.pop(oldest, None)
        return df
    except Exception as e:
        logger.warning("Futures history fetch failed for %s: %s", code, e)
        return pd.DataFrame()
