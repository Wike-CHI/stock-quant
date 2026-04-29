import json
import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import akshare as ak
import pandas as pd
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

EM_FIELD_MAP = {
    "f2": "price", "f3": "change_pct", "f4": "change_amount",
    "f5": "volume", "f6": "turnover", "f7": "amplitude",
    "f8": "turnover_rate", "f9": "pe", "f10": "vol_ratio",
    "f12": "code", "f14": "name",
    "f15": "high", "f16": "low", "f17": "open", "f18": "prev_close",
    "f20": "total_mv", "f21": "circ_mv", "f23": "pb",
}

EM_FIELDS = ",".join(EM_FIELD_MAP.keys())
EM_CLIST_URL = "http://push2.eastmoney.com/api/qt/clist/get"
EM_ULIST_URL = "http://push2.eastmoney.com/api/qt/ulist.np/get"
EM_PARAMS_BASE = {
    "pz": 5000, "po": 0, "np": 1,
    "fltt": 2, "invt": 2, "fid": "f3",
    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
    "fields": EM_FIELDS,
}

HIST_COLUMNS = {
    "日期": "date", "股票代码": "code",
    "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "turnover",
    "振幅": "amplitude", "涨跌幅": "change_pct",
    "涨跌额": "change_amount", "换手率": "turnover_rate",
}

MIN_COLUMNS = {
    "时间": "date", "开盘": "open", "收盘": "close",
    "最高": "high", "最低": "low", "成交量": "volume",
    "成交额": "turnover", "均价": "avg_price",
}

PERIOD_CONFIG = {
    "1m":   ("1", 60),
    "5m":   ("5", 60),
    "15m":  ("15", 60),
    "30m":  ("30", 60),
    "60m":  ("60", 60),
    "daily": ("daily", 300),
    "weekly": ("weekly", 300),
    "monthly": ("monthly", 300),
}

_hist_cache_ts: dict[str, float] = {}
_hist_cache_df: dict[str, pd.DataFrame] = {}

_spot_df: Optional[pd.DataFrame] = None
SPOT_REFRESH_INTERVAL = 30


class _RWLock:
    """简单读写锁：允许多读，独占写"""
    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def acquire_read(self):
        with self._read_ready:
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()

    def release_write(self):
        self._read_ready.release()


_spot_rwlock = _RWLock()
# 保留兼容旧接口的 _spot_lock 别名（部分地方直接 with _spot_lock）
_spot_lock = threading.Lock()

_CLIST_OK = True


def _cffi_get(url: str, **kwargs) -> cffi_requests.Response:
    kwargs.setdefault("timeout", 15)
    return cffi_requests.get(url, impersonate="chrome", **kwargs)


def _parse_items(items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        row = {}
        for fcode, col in EM_FIELD_MAP.items():
            val = item.get(fcode, "-")
            row[col] = None if val == "-" or val is None else val
        rows.append(row)
    return rows


def _fetch_page(pn: int) -> list[dict]:
    r = _cffi_get(EM_CLIST_URL, params={**EM_PARAMS_BASE, "pn": pn})
    r.raise_for_status()
    return r.json()["data"]["diff"]


def _fetch_spot_clist() -> pd.DataFrame:
    global _CLIST_OK
    first_resp = _cffi_get(EM_CLIST_URL, params={**EM_PARAMS_BASE, "pn": 1})
    first_resp.raise_for_status()
    data = first_resp.json()["data"]
    total = data["total"]
    items = data["diff"]
    per_page = len(items) or 100

    if total > per_page:
        pages = math.ceil(total / per_page)
        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = [pool.submit(_fetch_page, p) for p in range(2, pages + 1)]
            for f in as_completed(futs):
                try:
                    items.extend(f.result())
                except Exception as e:
                    logger.warning("Failed to fetch page: %s", e)

    _CLIST_OK = True
    df = pd.DataFrame(_parse_items(items))
    if not df.empty:
        _save_codes_to_disk(df["code"].tolist())
    return df


def _fetch_spot_tencent() -> pd.DataFrame:
    """Fallback: Tencent Finance batch quote API (very stable)."""
    codes = _get_cached_codes()
    if not codes:
        return pd.DataFrame()

    # Tencent format: sz000001,sh600000
    tencent_codes = []
    for code in codes:
        if code.startswith(("6", "9")):
            tencent_codes.append(f"sh{code}")
        else:
            tencent_codes.append(f"sz{code}")

    batch_size = 500
    all_rows = []
    for i in range(0, len(tencent_codes), batch_size):
        batch = tencent_codes[i:i + batch_size]
        try:
            r = _cffi_get("http://qt.gtimg.cn/q=" + ",".join(batch), timeout=8)
            if r.status_code != 200:
                continue
            for line in r.text.split(";"):
                line = line.strip()
                if not line:
                    continue
                start = line.find('"')
                end = line.rfind('"')
                if start < 0 or end <= start:
                    continue
                content = line[start + 1:end]
                if not content:
                    continue
                parts = content.split("~")
                if len(parts) < 6:
                    continue
                try:
                    price = float(parts[3]) if parts[3] else None
                    if not price:
                        continue
                    change_pct = float(parts[32]) if len(parts) > 32 and parts[32] else None
                    if change_pct is None:
                        prev = float(parts[4]) if parts[4] else None
                        change_pct = round((price - prev) / prev * 100, 2) if prev and price else None
                    row = {
                        "code": parts[2], "name": parts[1],
                        "price": price,
                        "prev_close": float(parts[4]) if parts[4] else None,
                        "open": float(parts[5]) if parts[5] else None,
                        "volume": int(float(parts[6])) if parts[6] else None,
                        "turnover": float(parts[37]) if len(parts) > 37 and parts[37] else None,
                        "high": float(parts[33]) if len(parts) > 33 and parts[33] else None,
                        "low": float(parts[34]) if len(parts) > 34 and parts[34] else None,
                        "change_pct": change_pct,
                        "change_amount": float(parts[31]) if len(parts) > 31 and parts[31] else None,
                        "amplitude": None, "turnover_rate": None,
                        "pe": None, "pb": None, "vol_ratio": None,
                        "total_mv": None, "circ_mv": None,
                    }
                    all_rows.append(row)
                except (ValueError, IndexError):
                    continue
        except Exception:
            continue

    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    if not df.empty:
        _save_codes_to_disk(df["code"].tolist())
    return df


def _fetch_spot_ulist() -> pd.DataFrame:
    """Fallback: batch query via ulist endpoint."""
    global _CLIST_OK
    _CLIST_OK = False

    codes = _get_cached_codes()
    if not codes:
        return pd.DataFrame()

    secid_list = []
    for code in codes:
        if code.startswith(("6", "9")):
            secid_list.append(f"1.{code}")
        elif code.startswith(("8", "4")):
            secid_list.append(f"0.{code}")
        else:
            secid_list.append(f"0.{code}")

    batch_size = 500
    all_items = []
    for i in range(0, len(secid_list), batch_size):
        batch = secid_list[i:i + batch_size]
        try:
            r = _cffi_get(EM_ULIST_URL, params={
                "fltt": 2, "invt": 2, "fields": EM_FIELDS,
                "secids": ",".join(batch),
            })
            if r.status_code == 200:
                data = r.json().get("data", {})
                if data and "diff" in data:
                    all_items.extend(data["diff"])
        except Exception:
            pass

    df = pd.DataFrame(_parse_items(all_items)) if all_items else pd.DataFrame()
    if not df.empty:
        _save_codes_to_disk(df["code"].tolist())
    return df


_CODE_CACHE_FILE = "D:/AI/stock-quant/backend/.code_cache.txt"


def _save_codes_to_disk(codes: list[str]):
    try:
        with open(_CODE_CACHE_FILE, "w") as f:
            f.write("\n".join(codes))
    except Exception:
        pass


def _load_codes_from_disk() -> list[str] | None:
    try:
        with open(_CODE_CACHE_FILE) as f:
            codes = [l.strip() for l in f if l.strip()]
        if len(codes) > 100:
            return codes
    except Exception:
        pass
    return None


def _get_cached_codes() -> list[str]:
    _spot_rwlock.acquire_read()
    try:
        if _spot_df is not None and not _spot_df.empty:
            return _spot_df["code"].tolist()
    finally:
        _spot_rwlock.release_read()
    cached = _load_codes_from_disk()
    if cached:
        return cached
    return _get_seed_codes()


def _get_seed_codes() -> list[str]:
    codes = []
    # SZ main board: 000001-002999
    for i in range(1, 3000):
        codes.append(f"{i:06d}")
    # SZ ChiNext: 300001-301999
    for i in range(300001, 302000):
        codes.append(str(i))
    # SH main board: 600000-603999
    for i in range(600000, 604000):
        codes.append(str(i))
    # SH STAR: 688001-689000
    for i in range(688001, 689001):
        codes.append(str(i))
    return codes


def _fetch_spot() -> pd.DataFrame:
    t0 = time.time()
    logger.info("Fetching A-stock spot data...")

    # Source 1: clist (fast paginated, may be blocked)
    try:
        df = _fetch_spot_clist()
        if not df.empty:
            logger.info("Fetched %d stocks via clist in %.2fs", len(df), time.time() - t0)
            return df
    except Exception as e:
        logger.warning("clist failed (%s), trying ulist", e)

    # Source 2: ulist batch (works when clist is down, but rate-limited)
    try:
        df = _fetch_spot_ulist()
        if not df.empty:
            logger.info("Fetched %d stocks via ulist in %.2fs", len(df), time.time() - t0)
            return df
    except Exception as e:
        logger.warning("ulist failed (%s), trying tencent", e)

    # Source 3: Tencent finance API (most reliable, needs code list)
    try:
        df = _fetch_spot_tencent()
        if not df.empty:
            logger.info("Fetched %d stocks via tencent in %.2fs", len(df), time.time() - t0)
            return df
    except Exception as e:
        logger.error("tencent also failed: %s", e)

    # Last resort: stale cache
    with _spot_lock:
        if _spot_df is not None:
            logger.warning("Returning stale cache (%d stocks)", len(_spot_df))
            return _spot_df.copy()

    raise ConnectionError("All data sources unavailable")


def prewarm_spot():
    global _spot_df
    try:
        df = _fetch_spot()
        _spot_rwlock.acquire_write()
        try:
            _spot_df = df
        finally:
            _spot_rwlock.release_write()
        logger.info("Spot data prewarmed: %d stocks", len(df))
    except Exception as e:
        logger.warning("Prewarm failed: %s — will retry in background", e)


_on_refresh_callbacks: list[Callable] = []


def register_refresh_callback(cb: Callable):
    """注册数据刷新后的回调（如 scanner.run_scan）"""
    _on_refresh_callbacks.append(cb)


def background_refresh():
    global _spot_df
    while True:
        time.sleep(SPOT_REFRESH_INTERVAL)
        try:
            df = _fetch_spot()
            _spot_rwlock.acquire_write()
            try:
                _spot_df = df
            finally:
                _spot_rwlock.release_write()
            # 数据刷新后触发回调
            for cb in _on_refresh_callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.error("Refresh callback failed: %s", e)
        except Exception as e:
            logger.error("Background spot refresh failed: %s", e)


def get_a_stock_list() -> pd.DataFrame:
    _spot_rwlock.acquire_read()
    try:
        if _spot_df is not None:
            return _spot_df.copy()
    finally:
        _spot_rwlock.release_read()
    prewarm_spot()
    _spot_rwlock.acquire_read()
    try:
        return _spot_df.copy() if _spot_df is not None else pd.DataFrame()
    finally:
        _spot_rwlock.release_read()


def get_realtime_quote(codes: list[str]) -> pd.DataFrame:
    _spot_rwlock.acquire_read()
    try:
        if _spot_df is None or _spot_df.empty:
            return pd.DataFrame()
        return _spot_df[_spot_df["code"].isin(set(codes))]
    finally:
        _spot_rwlock.release_read()


def get_top_gainers(limit: int = 50) -> pd.DataFrame:
    _spot_rwlock.acquire_read()
    try:
        if _spot_df is None or _spot_df.empty:
            return pd.DataFrame()
        df = _spot_df.dropna(subset=["change_pct"]).sort_values("change_pct", ascending=False)
        return df.head(limit).copy()
    finally:
        _spot_rwlock.release_read()


def get_stock_history(
    code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "qfq",
) -> pd.DataFrame:
    """获取个股历史行情，支持分钟线/日线/周线/月线"""
    cfg = PERIOD_CONFIG.get(period)
    if cfg is None:
        return pd.DataFrame()

    ak_period, cache_ttl = cfg
    cache_key = f"hist-{code}-{period}-{start_date}-{end_date}-{adjust}"
    now = time.time()
    if cache_key in _hist_cache_df and (now - _hist_cache_ts[cache_key]) < cache_ttl:
        return _hist_cache_df[cache_key].copy()

    try:
        df = _fetch_history_ak(code, period, ak_period, start_date, end_date, adjust)
        if df.empty:
            df = _fetch_history_direct(code, period, start_date, end_date)
    except Exception as e:
        logger.warning("akshare history failed (%s), trying direct API", e)
        try:
            df = _fetch_history_direct(code, period, start_date, end_date)
        except Exception as e2:
            logger.warning("direct history failed (%s), trying tencent", e2)
            df = _fetch_history_tencent(code, period, start_date, end_date)

    keep = [c for c in df.columns if c in ("date", "code", "open", "close", "high", "low", "volume", "turnover")]
    df = df[[c for c in keep if c in df.columns]]

    if "change_pct" not in df.columns and "close" in df.columns and "prev_close" not in df.columns:
        df["change_pct"] = df["close"].pct_change().fillna(0) * 100

    df = df.fillna(0)

    _hist_cache_df[cache_key] = df.copy()
    _hist_cache_ts[cache_key] = time.time()
    return df


def _fetch_history_ak(code, period, ak_period, start_date, end_date, adjust):
    if period in ("1m", "5m", "15m", "30m", "60m"):
        df = ak.stock_zh_a_hist_min_em(symbol=code, period=ak_period, adjust=adjust)
        df = df.rename(columns=MIN_COLUMNS)
    else:
        kwargs = {
            "symbol": code, "period": ak_period,
            "start_date": start_date or "20240101",
            "adjust": adjust,
        }
        if end_date:
            kwargs["end_date"] = end_date
        df = ak.stock_zh_a_hist(**kwargs)
        df = df.rename(columns=HIST_COLUMNS)
    return df


def _fetch_history_direct(code, period, start_date, end_date):
    """Fallback: fetch K-line directly from eastmoney push2his API."""
    klt_map = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60,
               "daily": 101, "weekly": 102, "monthly": 103}
    klt = klt_map.get(period, 101)
    market = "1" if code.startswith(("6", "9")) else "0"
    secid = f"{market}.{code}"

    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": klt, "fqt": 1, "secid": secid,
        "beg": start_date.replace("-", "") if start_date else "20240101",
        "end": end_date.replace("-", "") if end_date else "20500101",
    }
    r = _cffi_get("http://push2his.eastmoney.com/api/qt/stock/kline/get", params=params)
    r.raise_for_status()
    data = r.json().get("data", {})
    klines = data.get("klines", [])
    if not klines:
        return pd.DataFrame()

    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) >= 7:
            rows.append({
                "date": parts[0], "open": float(parts[1]), "close": float(parts[2]),
                "high": float(parts[3]), "low": float(parts[4]),
                "volume": int(float(parts[5])), "turnover": float(parts[6]),
            })
    return pd.DataFrame(rows)


_TENCENT_KLINE_MAP = {
    "1m": ("m1", "kline_m1qfq", "qfqmin"),
    "5m": ("m5", "kline_m5qfq", "qfqmin"),
    "15m": ("m15", "kline_m15qfq", "qfqmin"),
    "30m": ("m30", "kline_m30qfq", "qfqmin"),
    "60m": ("m60", "kline_m60qfq", "qfqmin"),
    "daily": ("day", "kline_dayqfq", "qfqday"),
    "weekly": ("week", "kline_weekqfq", "qfqweek"),
    "monthly": ("month", "kline_monthqfq", "qfqmonth"),
}


def _fetch_history_tencent(code, period, start_date, end_date):
    """Fallback: fetch K-line from Tencent web.ifzq API."""
    entry = _TENCENT_KLINE_MAP.get(period)
    if not entry:
        return pd.DataFrame()

    tencent_period, var_name, data_key = entry
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    count = 320 if period in ("1m", "5m", "15m", "30m", "60m") else 600

    params = {
        "_var": var_name,
        "param": f"{prefix}{code},{tencent_period},,,{count},qfq",
    }
    r = _cffi_get("http://web.ifzq.gtimg.cn/appstock/app/fqkline/get", params=params, timeout=15)
    r.raise_for_status()

    text = r.text
    eq_pos = text.index("=") + 1
    data = json.loads(text[eq_pos:])
    stock_data = data.get("data", {}).get(prefix + code, {})
    klines = stock_data.get(data_key, [])
    if not klines:
        return pd.DataFrame()

    rows = []
    for item in klines:
        if len(item) < 6:
            continue
        rows.append({
            "date": item[0], "open": float(item[1]), "close": float(item[2]),
            "high": float(item[3]), "low": float(item[4]),
            "volume": int(float(item[5])),
        })
    return pd.DataFrame(rows)
