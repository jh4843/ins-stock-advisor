import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.logger import logger
from src.utils.paths import user_data_dir


class Cache:
    def __init__(self):
        db_dir = user_data_dir()
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_dir / "av_cache.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv_cache (
                    symbol   TEXT,
                    interval TEXT,
                    fetched_at TEXT,
                    data     TEXT,
                    PRIMARY KEY (symbol, interval)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS overview_cache (
                    symbol     TEXT PRIMARY KEY,
                    sector     TEXT,
                    industry   TEXT,
                    name       TEXT,
                    fetched_at TEXT
                )
            """)
            try:
                conn.execute("ALTER TABLE overview_cache ADD COLUMN raw_data TEXT")
            except Exception:
                pass

    # ── OHLCV ──────────────────────────────────────────────────────────────

    def get_ohlcv(self, symbol: str, interval: str, ttl_minutes: int) -> list | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT data, fetched_at FROM ohlcv_cache WHERE symbol=? AND interval=?",
                    (symbol, interval),
                ).fetchone()
            if not row:
                return None
            fetched_at = datetime.fromisoformat(row[1])
            if datetime.now() - fetched_at > timedelta(minutes=ttl_minutes):
                return None
            return json.loads(row[0])
        except Exception as e:
            logger.warning(f"[Cache] ohlcv 읽기 실패: {e}")
            return None

    def set_ohlcv(self, symbol: str, interval: str, data: list):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO ohlcv_cache VALUES (?, ?, ?, ?)",
                    (symbol, interval, datetime.now().isoformat(), json.dumps(data)),
                )
        except Exception as e:
            logger.warning(f"[Cache] ohlcv 저장 실패: {e}")

    # ── Overview ───────────────────────────────────────────────────────────

    def get_overview(self, symbol: str, ttl_days: int = 7) -> dict | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT sector, industry, name, fetched_at, raw_data FROM overview_cache WHERE symbol=?",
                    (symbol,),
                ).fetchone()
            if not row:
                return None
            fetched_at = datetime.fromisoformat(row[3])
            if datetime.now() - fetched_at > timedelta(days=ttl_days):
                return None
            result = {"sector": row[0], "industry": row[1], "name": row[2]}
            if row[4]:
                result.update(json.loads(row[4]))
            return result
        except Exception as e:
            logger.warning(f"[Cache] overview 읽기 실패: {e}")
            return None

    def set_overview(self, symbol: str, sector: str, industry: str, name: str, raw_data: dict | None = None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO overview_cache VALUES (?, ?, ?, ?, ?, ?)",
                    (symbol, sector, industry, name, datetime.now().isoformat(),
                     json.dumps(raw_data) if raw_data else None),
                )
        except Exception as e:
            logger.warning(f"[Cache] overview 저장 실패: {e}")
