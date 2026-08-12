"""DataStore — SQLite 持久层

管理所有历史数据的存储、查询、增量写入。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

import pandas as pd


KLINE_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]


class DataStore:
    """SQLite 数据存储"""

    def __init__(self, db_path: str = "crocodile.db"):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    # ── 初始化 ──────────────────────────────────

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                -- 日线行情
                CREATE TABLE IF NOT EXISTS kline_daily (
                    symbol     TEXT NOT NULL,
                    date       TEXT NOT NULL,
                    open       REAL,
                    high       REAL,
                    low        REAL,
                    close      REAL,
                    volume     REAL,
                    amount     REAL,
                    PRIMARY KEY (symbol, date)
                );
                CREATE INDEX IF NOT EXISTS idx_kline_daily_symbol ON kline_daily(symbol);
                CREATE INDEX IF NOT EXISTS idx_kline_daily_date   ON kline_daily(date);

                -- 分钟线行情
                CREATE TABLE IF NOT EXISTS kline_minute (
                    symbol     TEXT NOT NULL,
                    datetime   TEXT NOT NULL,
                    freq       TEXT NOT NULL DEFAULT '1m',
                    open       REAL,
                    high       REAL,
                    low        REAL,
                    close      REAL,
                    volume     REAL,
                    amount     REAL,
                    PRIMARY KEY (symbol, datetime, freq)
                );
                CREATE INDEX IF NOT EXISTS idx_kline_minute_sym ON kline_minute(symbol, freq);

                -- 拉取日志（增量去重用）
                CREATE TABLE IF NOT EXISTS fetch_log (
                    symbol     TEXT NOT NULL,
                    freq       TEXT NOT NULL DEFAULT '1d',
                    source     TEXT NOT NULL,
                    start_date TEXT,
                    end_date   TEXT,
                    fetch_time TEXT NOT NULL,
                    row_count  INTEGER,
                    PRIMARY KEY (symbol, freq, source)
                );

                -- 股票基本信息
                CREATE TABLE IF NOT EXISTS symbol_info (
                    symbol     TEXT PRIMARY KEY,
                    name       TEXT,
                    market     TEXT,
                    type       TEXT,
                    list_date  TEXT,
                    updated_at TEXT
                );
            """)

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # ── 写入 ─────────────────────────────────────

    def upsert_daily(self, df: pd.DataFrame) -> int:
        """写入/更新日线数据，返回写入行数"""
        if df.empty:
            return 0

        # 确保列存在
        for col in KLINE_COLUMNS:
            if col not in df.columns:
                df[col] = None

        if "symbol" not in df.columns:
            raise ValueError("DataFrame 缺少 symbol 列")

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        rows = df[["symbol", "date", "open", "high", "low", "close", "volume", "amount"]].values.tolist()

        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO kline_daily
                   (symbol, date, open, high, low, close, volume, amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        return len(rows)

    def upsert_minute(self, df: pd.DataFrame, freq: str = "1m") -> int:
        """写入分钟线"""
        if df.empty:
            return 0

        df = df.copy()
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")

        rows = []
        for _, r in df.iterrows():
            rows.append((
                r.get("symbol", ""),
                r["datetime"],
                freq,
                r.get("open"), r.get("high"), r.get("low"),
                r.get("close"), r.get("volume"), r.get("amount"),
            ))

        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO kline_minute
                   (symbol, datetime, freq, open, high, low, close, volume, amount)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        return len(rows)

    # ── 查询 ─────────────────────────────────────

    def get_daily(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """查询日线"""
        sql = "SELECT date, open, high, low, close, volume, amount FROM kline_daily WHERE symbol = ?"
        params = [symbol]
        if start_date:
            sql += " AND date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND date <= ?"
            params.append(end_date)
        sql += " ORDER BY date ASC"

        with self._conn() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
        return df

    def get_minute(
        self,
        symbol: str,
        freq: str = "1m",
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """查询分钟线"""
        sql = "SELECT datetime, open, high, low, close, volume, amount FROM kline_minute WHERE symbol = ? AND freq = ?"
        params = [symbol, freq]
        if start:
            sql += " AND datetime >= ?"
            params.append(start)
        if end:
            sql += " AND datetime <= ?"
            params.append(end)
        sql += " ORDER BY datetime ASC"

        with self._conn() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        if not df.empty:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)
        return df

    def get_symbols(self, market: Optional[str] = None) -> pd.DataFrame:
        """查询已存储的股票列表及数据范围"""
        sql = """
            SELECT symbol, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as bars
            FROM kline_daily GROUP BY symbol ORDER BY symbol
        """
        with self._conn() as conn:
            return pd.read_sql_query(sql, conn)

    def has_data(self, symbol: str, start: str, end: str) -> bool:
        """检查是否已覆盖指定日期范围"""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) FROM kline_daily
                   WHERE symbol = ? AND date >= ? AND date <= ?""",
                (symbol, start, end),
            ).fetchone()
        return row and row[0] > 0

    # ── 拉取日志 ─────────────────────────────────

    def get_fetch_range(self, symbol: str, freq: str = "1d", source: str = "akshare") -> Optional[Tuple[str, str]]:
        """获取上次拉取范围，用于增量更新"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT start_date, end_date FROM fetch_log WHERE symbol=? AND freq=? AND source=?",
                (symbol, freq, source),
            ).fetchone()
        return row if row else None

    def log_fetch(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        row_count: int,
        freq: str = "1d",
        source: str = "akshare",
    ):
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO fetch_log
                   (symbol, freq, source, start_date, end_date, fetch_time, row_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (symbol, freq, source, start_date, end_date, datetime.now().isoformat(), row_count),
            )

    # ── 股票信息 ─────────────────────────────────

    def upsert_symbol_info(self, df: pd.DataFrame):
        """写入股票基本信息"""
        if df.empty:
            return
        cols = [c for c in ["symbol", "name", "market", "type", "list_date"] if c in df.columns]
        with self._conn() as conn:
            for _, r in df[cols].iterrows():
                conn.execute(
                    """INSERT OR REPLACE INTO symbol_info (symbol, name, market, type, list_date, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (r.get("symbol"), r.get("name"), r.get("market"),
                     r.get("type"), r.get("list_date"), datetime.now().isoformat()),
                )

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM symbol_info WHERE symbol=?", (symbol,)
            ).fetchone()
        if row is None:
            return None
        cols = ["symbol", "name", "market", "type", "list_date", "updated_at"]
        return dict(zip(cols, row))

    def __repr__(self):
        with self._conn() as conn:
            daily = conn.execute("SELECT COUNT(*) FROM kline_daily").fetchone()[0]
            minu = conn.execute("SELECT COUNT(*) FROM kline_minute").fetchone()[0]
            symbols = conn.execute("SELECT COUNT(DISTINCT symbol) FROM kline_daily").fetchone()[0]
        return f"DataStore({self.db_path}, symbols={symbols}, daily={daily}, minute={minu})"
