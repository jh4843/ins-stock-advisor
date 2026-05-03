import requests

from src.core.cache import Cache
from src.utils.config import Config
from src.utils.logger import logger


class AlphaVantageApi:
    BASE_URL = "https://www.alphavantage.co/query"

    # OHLCV 캐시 TTL (분 단위)
    TTL_INTRADAY = 3       # 3분봉: 3분
    TTL_DAILY = 60 * 24    # 일봉: 24시간

    def __init__(self):
        self.api_key = Config.ALPHA_API_KEY
        self.cache = Cache()

    # ── OHLCV ──────────────────────────────────────────────────────────────

    def fetch_ohlcv(self, symbol: str, timeframe: str = "D") -> list[dict]:
        """
        Returns list of dicts (oldest first):
            {date, time, open, high, low, close, volume}
        timeframe: "3m" | "D" | "W" | "M"
        """
        if timeframe == "3m":
            return self._fetch_intraday(symbol)
        return self._fetch_daily(symbol)

    def _fetch_intraday(self, symbol: str) -> list[dict]:
        cached = self.cache.get_ohlcv(symbol, "3min", self.TTL_INTRADAY)
        if cached:
            logger.debug(f"[AV:{symbol}] 캐시 히트 (3min)")
            return cached

        logger.info(f"[AV:{symbol}] API 호출 (intraday 3min)")
        data = self._get({
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": "3min",
            "outputsize": "compact",
            "adjusted": "true",
        })
        if not data:
            return []

        ts = data.get("Time Series (3min)", {})
        records = self._parse_ts(ts, intraday=True)
        if records:
            self.cache.set_ohlcv(symbol, "3min", records)
        return records

    def _fetch_daily(self, symbol: str) -> list[dict]:
        cached = self.cache.get_ohlcv(symbol, "daily", self.TTL_DAILY)
        if cached:
            logger.debug(f"[AV:{symbol}] 캐시 히트 (daily)")
            return cached

        logger.info(f"[AV:{symbol}] API 호출 (daily)")
        data = self._get({
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",
        })
        if not data:
            return []

        ts = data.get("Time Series (Daily)", {})
        records = self._parse_ts(ts, intraday=False)
        if records:
            self.cache.set_ohlcv(symbol, "daily", records)
        return records

    # ── Overview (카테고리 분류용) ──────────────────────────────────────────

    def fetch_overview(self, symbol: str) -> dict:
        cached = self.cache.get_overview(symbol)
        if cached:
            logger.debug(f"[AV:{symbol}] OVERVIEW 캐시 히트")
            return cached

        logger.info(f"[AV:{symbol}] OVERVIEW API 호출")
        data = self._get({"function": "OVERVIEW", "symbol": symbol})
        if not data or "Symbol" not in data:
            return {}

        result = {
            "sector":   data.get("Sector", ""),
            "industry": data.get("Industry", ""),
            "name":     data.get("Name", symbol),
        }
        self.cache.set_overview(symbol, result["sector"], result["industry"], result["name"])
        return result

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────────

    def _get(self, params: dict) -> dict | None:
        params["apikey"] = self.api_key
        try:
            res = requests.get(self.BASE_URL, params=params, timeout=10)
            data = res.json()
            if "Note" in data or "Information" in data:
                logger.warning(f"[AV] API 한도 초과: {data.get('Note', data.get('Information', ''))[:80]}")
                return None
            return data
        except Exception as e:
            logger.error(f"[AV] 요청 실패: {e}")
            return None

    @staticmethod
    def _parse_ts(ts: dict, intraday: bool) -> list[dict]:
        records = []
        for dt_str, v in ts.items():
            if intraday:
                date_part, time_part = dt_str.split(" ")
                time_compact = time_part.replace(":", "")
            else:
                date_part = dt_str
                time_compact = "000000"

            close_key = "4. close" if "4. close" in v else "5. adjusted close"
            vol_key   = "5. volume" if "5. volume" in v else "6. volume"

            records.append({
                "date":   date_part,
                "time":   time_compact,
                "open":   float(v["1. open"]),
                "high":   float(v["2. high"]),
                "low":    float(v["3. low"]),
                "close":  float(v[close_key]),
                "volume": float(v.get(vol_key, 0)),
            })

        records.sort(key=lambda x: x["date"] + x["time"])
        return records
