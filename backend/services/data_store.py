"""
SQLite 数据持久化层：K 线历史存储、查询、导出
"""
import csv
import io
import json
import logging
import sqlite3
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "stock.db"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_bar (
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, close REAL, high REAL, low REAL,
    volume INTEGER, turnover REAL,
    change_pct REAL,
    collected_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code, date)
);

CREATE TABLE IF NOT EXISTS minute_bar (
    code TEXT NOT NULL,
    period TEXT NOT NULL,
    ts TEXT NOT NULL,
    open REAL, close REAL, high REAL, low REAL,
    volume INTEGER, turnover REAL,
    collected_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code, period, ts)
);

CREATE TABLE IF NOT EXISTS collection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    codes_count INTEGER DEFAULT 0,
    new_rows INTEGER DEFAULT 0,
    elapsed_sec REAL DEFAULT 0,
    collected_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_bar(date);
CREATE INDEX IF NOT EXISTS idx_daily_code ON daily_bar(code);

CREATE TABLE IF NOT EXISTS alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT DEFAULT '',
    alert_type TEXT NOT NULL,
    message TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_alert_code ON alert(code);
CREATE INDEX IF NOT EXISTS idx_alert_time ON alert(created_at);

CREATE TABLE IF NOT EXISTS pattern_cache (
    code TEXT NOT NULL,
    results TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code)
);

CREATE TABLE IF NOT EXISTS prediction_cache (
    code TEXT NOT NULL,
    results TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (code)
);
"""

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.executescript(_SCHEMA)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        logger.info("SQLite opened: %s", _DB_PATH)
    return _conn


# ── 写入 ──────────────────────────────────────────

def save_daily_bars(rows: list[dict]) -> int:
    """批量写入日线，返回新增行数"""
    if not rows:
        return 0
    conn = _get_conn()
    sql = """INSERT OR IGNORE INTO daily_bar
             (code, date, open, close, high, low, volume, turnover, change_pct)
             VALUES (:code, :date, :open, :close, :high, :low, :volume, :turnover, :change_pct)"""
    cur = conn.executemany(sql, rows)
    conn.commit()
    return cur.rowcount


def save_minute_bars(rows: list[dict], period: str) -> int:
    """批量写入分钟线，rows 需含 code/ts/open/close/high/low/volume/turnover"""
    if not rows:
        return 0
    for r in rows:
        r["period"] = period
    conn = _get_conn()
    sql = """INSERT OR IGNORE INTO minute_bar
             (code, period, ts, open, close, high, low, volume, turnover)
             VALUES (:code, :period, :ts, :open, :close, :high, :low, :volume, :turnover)"""
    cur = conn.executemany(sql, rows)
    conn.commit()
    return cur.rowcount


def log_collection(task_type: str, codes_count: int, new_rows: int, elapsed: float):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO collection_log (task_type, codes_count, new_rows, elapsed_sec) VALUES (?, ?, ?, ?)",
        (task_type, codes_count, new_rows, elapsed),
    )
    conn.commit()


# ── 查询 ──────────────────────────────────────────

def query_daily(code: str = "", start_date: str = "", end_date: str = "",
                limit: int = 0) -> pd.DataFrame:
    """查询日线数据"""
    conn = _get_conn()
    sql = "SELECT * FROM daily_bar WHERE 1=1"
    params: list = []
    if code:
        sql += " AND code = ?"
        params.append(code)
    if start_date:
        sql += " AND date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND date <= ?"
        params.append(end_date)
    sql += " ORDER BY date"
    if limit:
        sql += f" LIMIT {limit}"
    return pd.read_sql_query(sql, conn, params=params)


def query_minute(code: str, period: str = "5m", limit: int = 0) -> pd.DataFrame:
    conn = _get_conn()
    sql = "SELECT * FROM minute_bar WHERE code = ? AND period = ? ORDER BY ts"
    params = [code, period]
    if limit:
        sql += f" LIMIT {limit}"
    return pd.read_sql_query(sql, conn, params=params)


def get_stats() -> dict:
    """返回数据集统计信息"""
    conn = _get_conn()
    daily_count = conn.execute("SELECT COUNT(*) FROM daily_bar").fetchone()[0]
    minute_count = conn.execute("SELECT COUNT(*) FROM minute_bar").fetchone()[0]
    stock_count = conn.execute("SELECT COUNT(DISTINCT code) FROM daily_bar").fetchone()[0]
    date_range = conn.execute("SELECT MIN(date), MAX(date) FROM daily_bar").fetchone()
    last_log = conn.execute(
        "SELECT task_type, new_rows, collected_at FROM collection_log ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return {
        "daily_bars": daily_count,
        "minute_bars": minute_count,
        "stock_count": stock_count,
        "date_range": list(date_range) if date_range[0] else [],
        "recent_collections": [
            {"task_type": r[0], "new_rows": r[1], "collected_at": r[2]}
            for r in last_log
        ],
    }


# ── 导出 ──────────────────────────────────────────

def export_csv(code: str = "", start_date: str = "", end_date: str = "") -> str:
    """导出日线为 CSV 字符串"""
    df = query_daily(code, start_date, end_date)
    if df.empty:
        return ""
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def export_json(code: str = "", start_date: str = "", end_date: str = "") -> str:
    """导出日线为 JSON 字符串"""
    df = query_daily(code, start_date, end_date)
    if df.empty:
        return "[]"
    return df.to_json(orient="records", date_format="iso")


# ── 预警持久化 ──────────────────────────────────

def save_alert(code: str, name: str, alert_type: str, message: str, details: str = "{}"):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO alert (code, name, alert_type, message, details) VALUES (?, ?, ?, ?, ?)",
        (code, name, alert_type, message, details),
    )
    conn.commit()


def get_alerts(limit: int = 100, code: str = "") -> list[dict]:
    conn = _get_conn()
    sql = "SELECT * FROM alert"
    params: list = []
    if code:
        sql += " WHERE code = ?"
        params.append(code)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM alert LIMIT 0").description]
    return [dict(zip(cols, r)) for r in rows]


def clear_alerts():
    conn = _get_conn()
    conn.execute("DELETE FROM alert")
    conn.commit()


# ── 规律缓存 ──────────────────────────────────

def save_pattern_cache(code: str, results: list[dict]):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO pattern_cache (code, results) VALUES (?, ?)",
        (code, json.dumps(results, ensure_ascii=False)),
    )
    conn.commit()


def load_pattern_cache(code: str) -> list[dict] | None:
    conn = _get_conn()
    row = conn.execute("SELECT results FROM pattern_cache WHERE code = ?", (code,)).fetchone()
    if row:
        return json.loads(row[0])
    return None


# ── 预测缓存 ──────────────────────────────────

def save_prediction_cache(code: str, results: dict):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO prediction_cache (code, results) VALUES (?, ?)",
        (code, json.dumps(results, ensure_ascii=False)),
    )
    conn.commit()


def load_prediction_cache(code: str, max_age_sec: float = 300) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT results, updated_at FROM prediction_cache WHERE code = ?", (code,)).fetchone()
    if not row:
        return None
    updated = time.mktime(time.strptime(row[1], "%Y-%m-%d %H:%M:%S"))
    if time.time() - updated > max_age_sec:
        return None
    return json.loads(row[0])
