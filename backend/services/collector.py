"""
定时采集任务：从数据源拉取 K 线数据并持久化到 SQLite
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from services import stock_data
from services.data_store import save_daily_bars, save_minute_bars, log_collection

logger = logging.getLogger(__name__)

COLLECT_INTERVAL = 300  # 5 分钟
MINUTE_PERIODS = ("5m", "15m", "30m", "60m")


def collect_daily(codes: list[str] | None = None) -> int:
    """采集日线数据并写入 SQLite，返回新增行数"""
    if codes is None:
        codes = _get_all_codes()
    if not codes:
        return 0

    t0 = time.time()
    new_total = 0

    def _fetch_one(code: str) -> list[dict]:
        try:
            df = stock_data.get_stock_history(code, period="daily")
            if df.empty:
                return []
            df["code"] = code
            return df.to_dict(orient="records")
        except Exception as e:
            logger.warning("collect_daily %s failed: %s", code, e)
            return []

    batch_size = 50
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        all_rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = {pool.submit(_fetch_one, c): c for c in batch}
            for f in as_completed(futs):
                all_rows.extend(f.result())

        new_total += save_daily_bars(all_rows)

    elapsed = time.time() - t0
    log_collection("daily", len(codes), new_total, elapsed)
    logger.info("collect_daily: %d codes, %d new rows, %.1fs", len(codes), new_total, elapsed)
    return new_total


def collect_minute(codes: list[str] | None = None, periods: tuple[str, ...] = MINUTE_PERIODS) -> int:
    """采集分钟线数据并写入 SQLite"""
    if codes is None:
        codes = _get_all_codes()
    if not codes:
        return 0

    t0 = time.time()
    new_total = 0

    def _fetch_one(args: tuple) -> list[dict]:
        code, period = args
        try:
            df = stock_data.get_stock_history(code, period=period)
            if df.empty:
                return []
            records = df.to_dict(orient="records")
            for r in records:
                r["code"] = code
                r["ts"] = r.pop("date", "")
            return records
        except Exception as e:
            logger.warning("collect_minute %s/%s failed: %s", code, period, e)
            return []

    tasks = [(c, p) for c in codes for p in periods]
    for i in range(0, len(tasks), 50):
        batch = tasks[i:i + 50]
        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = {pool.submit(_fetch_one, t): t for t in batch}
            for f in as_completed(futs):
                rows = f.result()
                _, period = futs[f]
                new_total += save_minute_bars(rows, period)

    elapsed = time.time() - t0
    log_collection("minute", len(codes), new_total, elapsed)
    logger.info("collect_minute: %d codes x %d periods, %d new rows, %.1fs",
                len(codes), len(periods), new_total, elapsed)
    return new_total


def background_collector(daily_interval: int = COLLECT_INTERVAL,
                         include_minute: bool = False):
    """后台定时采集线程"""
    logger.info("Background collector started (interval=%ds, minute=%s)",
                daily_interval, include_minute)
    while True:
        time.sleep(daily_interval)
        try:
            codes = _get_all_codes()
            collect_daily(codes)
            if include_minute:
                collect_minute(codes[:200])
        except Exception as e:
            logger.error("Background collector error: %s", e)


def _get_all_codes() -> list[str]:
    df = stock_data.get_a_stock_list()
    if df.empty:
        return []
    return df["code"].tolist()
