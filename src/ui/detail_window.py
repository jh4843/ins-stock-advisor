import pandas as pd
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.core.scanner import StockScanner
from src.utils.logger import logger


def _is_us(symbol: str) -> bool:
    return not symbol.strip().isdigit()


class DetailWindow(QWidget):
    def __init__(self, symbol: str, stock_name: str, timeframe_text: str = "일봉", parent=None):
        super().__init__(parent)
        self.symbol        = symbol
        self.stock_name    = stock_name
        self.timeframe_text = timeframe_text
        self.scanner       = StockScanner()
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        from src.ui.components.chart_view import StockChart
        layout = QVBoxLayout(self)

        self.info_label = QLabel(f"[{self.stock_name}({self.symbol})] 데이터 분석 중... ({self.timeframe_text})")
        self.info_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #4a90e2; padding: 5px;"
        )
        layout.addWidget(self.info_label)

        self.chart = StockChart()
        layout.addWidget(self.chart)

    def _load_data(self):
        tf_map = {"일봉": "D", "주봉": "W", "월봉": "M", "3분봉": "3m"}
        api_tf = tf_map.get(self.timeframe_text, "D")

        if _is_us(self.symbol):
            df = self._load_us(api_tf)
        else:
            df = self._load_kr(api_tf)

        if df is None or df.empty:
            return

        if len(df) < 20:
            self.info_label.setText(
                f"{self.symbol} - 데이터 부족 (최소 20개 필요, 현재 {len(df)}개)"
            )
            return

        try:
            df = self.scanner.calculate_bollinger_bands(df)
            self.chart.update_chart(df)
        except Exception as e:
            self.info_label.setText(f"[{self.symbol}] 차트 계산 에러: {e}")
            return

        price    = df.iloc[-1]["close"]
        currency = "USD" if _is_us(self.symbol) else "원"
        fmt      = f"{price:,.2f}" if _is_us(self.symbol) else f"{int(price):,}"
        self.info_label.setText(
            f"{self.stock_name}({self.symbol}) | 현재가: {fmt}{currency} | {self.timeframe_text}"
        )

    # ── KR ────────────────────────────────────────────────────────────────

    def _load_kr(self, api_tf: str) -> pd.DataFrame | None:
        from src.api.kis_api import KISApi
        api = KISApi()
        raw = api.fetch_ohlcv(self.symbol, timeframe=api_tf)
        if not raw:
            self.info_label.setText(f"{self.symbol} - 데이터 수집 실패")
            return None

        df = pd.DataFrame(raw)

        if api_tf == "3m":
            col_map = {
                "stck_bsop_date": "date", "stck_cntg_hour": "time",
                "stck_prpr": "close", "stck_oprc": "open",
                "stck_hgpr": "high",  "stck_lwpr": "low",
                "cntg_vol": "volume",
            }
        else:
            col_map = {
                "stck_bsop_date": "date",
                "stck_clpr": "close", "stck_oprc": "open",
                "stck_hgpr": "high",  "stck_lwpr": "low",
                "acml_vol": "volume",
            }

        existing = {k: v for k, v in col_map.items() if k in df.columns}
        df = df[list(existing.keys())].rename(columns=existing)

        for col in ["close", "open", "high", "low", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.iloc[::-1].reset_index(drop=True)

        # 1분봉 → 3분봉 리샘플링
        if api_tf == "3m" and "time" in df.columns:
            try:
                df["datetime"] = pd.to_datetime(
                    df["date"].astype(str) + df["time"].astype(str).str.zfill(6),
                    format="%Y%m%d%H%M%S",
                )
                df.set_index("datetime", inplace=True)
                df = (
                    df.resample("3min")
                    .agg({"date": "last", "time": "last",
                          "open": "first", "high": "max",
                          "low": "min",   "close": "last",
                          "volume": "sum"})
                    .dropna()
                    .reset_index(drop=True)
                )
            except Exception as e:
                self.info_label.setText(f"3분봉 변환 에러: {e}")
                return None

        return df

    # ── US ────────────────────────────────────────────────────────────────

    def _load_us(self, api_tf: str) -> pd.DataFrame | None:
        from src.api.alphavantage_api import AlphaVantageApi
        av = AlphaVantageApi()
        records = av.fetch_ohlcv(self.symbol, api_tf)
        if not records:
            self.info_label.setText(f"{self.symbol} - AlphaVantage 데이터 없음 (API 한도 확인)")
            return None

        df = pd.DataFrame(records)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.reset_index(drop=True)
