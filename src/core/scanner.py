import pandas as pd
import pandas_ta as ta

from src.utils.logger import logger


def is_us_stock(code: str) -> bool:
    return not code.strip().isdigit()


class StockScanner:
    def __init__(self):
        from src.api.kis_api import KISApi
        from src.api.alphavantage_api import AlphaVantageApi
        self.kis = KISApi()
        self.av  = AlphaVantageApi()

    # ── 볼린저밴드 ─────────────────────────────────────────────────────────

    def calculate_bollinger_bands(self, df: pd.DataFrame, length: int = 20, std: int = 2) -> pd.DataFrame:
        bb = ta.bbands(df["close"], length=length, std=std)
        return pd.concat([df, bb], axis=1)

    # ── 스캔 ───────────────────────────────────────────────────────────────

    def scan(
        self,
        category_stocks: list[dict],
        timeframe: str,
        condition: str,
    ) -> list[dict]:
        """
        Args:
            category_stocks: [{"code": "005930", "name": "삼성전자", "market": "KR"}, ...]
            timeframe: "D" | "3m"
            condition: "전체" | "하단 터치" | "상단 터치"
        Returns:
            [{"code", "name", "market", "price", "bbl", "bbu", "status"}, ...]
        """
        results = []
        for stock in category_stocks:
            code   = stock["code"]
            name   = stock.get("name", code)
            market = stock.get("market", "KR")

            df = self._fetch_df(code, market, timeframe)
            if df is None or len(df) < 20:
                logger.debug(f"[{code}] 데이터 부족, 스킵")
                continue

            df = self.calculate_bollinger_bands(df)
            last = df.iloc[-1]

            bbl_col = next((c for c in df.columns if c.startswith("BBL_")), None)
            bbu_col = next((c for c in df.columns if c.startswith("BBU_")), None)
            if not bbl_col or not bbu_col:
                continue

            price = last["close"]
            bbl   = last[bbl_col]
            bbu   = last[bbu_col]

            if pd.isna(bbl) or pd.isna(bbu):
                continue

            status = None
            if condition in ("전체", "하단 터치") and price <= bbl:
                status = "하단 터치"
            elif condition in ("전체", "상단 터치") and price >= bbu:
                status = "상단 터치"

            if status:
                logger.info(f"★ [{code}] {status} (price={price:.2f}, bbl={bbl:.2f}, bbu={bbu:.2f})")
                results.append({
                    "code":   code,
                    "name":   name,
                    "market": market,
                    "price":  price,
                    "bbl":    bbl,
                    "bbu":    bbu,
                    "status": status,
                })

        return results

    # ── 데이터 로딩 (KR/US 분기) ───────────────────────────────────────────

    def _fetch_df(self, code: str, market: str, timeframe: str) -> pd.DataFrame | None:
        if market == "US":
            return self._fetch_us(code, timeframe)
        return self._fetch_kr(code, timeframe)

    def _fetch_kr(self, code: str, timeframe: str) -> pd.DataFrame | None:
        raw = self.kis.fetch_ohlcv(code, timeframe)
        if not raw:
            return None
        df = pd.DataFrame(raw)

        if timeframe == "3m":
            col_map = {
                "stck_prpr": "close", "stck_oprc": "open",
                "stck_hgpr": "high",  "stck_lwpr": "low",
            }
        else:
            col_map = {
                "stck_clpr": "close", "stck_oprc": "open",
                "stck_hgpr": "high",  "stck_lwpr": "low",
            }

        existing = {k: v for k, v in col_map.items() if k in df.columns}
        df = df[list(existing.keys())].rename(columns=existing)
        df = df.astype(float).iloc[::-1].reset_index(drop=True)
        return df

    def _fetch_us(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        records = self.av.fetch_ohlcv(symbol, timeframe)
        if not records:
            return None
        df = pd.DataFrame(records)[["open", "high", "low", "close", "volume"]]
        df = df.astype(float).reset_index(drop=True)
        return df
