import pandas as pd
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.api.kis_api import KISApi
from src.core.scanner import StockScanner
from src.ui.components.chart_view import StockChart


class DetailWindow(QWidget):
    def __init__(self, symbol, timeframe_text="일봉", parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.timeframe_text = timeframe_text
        self.api = KISApi()
        self.scanner = StockScanner()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.info_label = QLabel(
            f"[{self.symbol}] 데이터 분석 중... ({self.timeframe_text})"
        )
        self.info_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #4a90e2; padding: 5px;"
        )
        layout.addWidget(self.info_label)

        self.chart = StockChart()
        layout.addWidget(self.chart)

    def load_data(self):
        # 1. 주기 매핑
        tf_map = {"일봉": "D", "주봉": "W", "월봉": "M", "3분봉": "3m"}
        api_tf = tf_map.get(self.timeframe_text, "D")

        raw_ohlcv = self.api.fetch_ohlcv(self.symbol, timeframe=api_tf)
        if not raw_ohlcv:
            self.info_label.setText(f"{self.symbol} - 데이터 수집 실패")
            return

        # 2. 데이터프레임 처리
        df = pd.DataFrame(raw_ohlcv)
        if api_tf == "3m":
            column_map = {
                "stck_bsop_date": "date",
                "stck_cntg_hour": "time",
                "stck_prpr": "close",
                "stck_oprc": "open",
                "stck_hgpr": "high",
                "stck_lwpr": "low",
                "cntg_vol": "volume",
            }
        else:
            column_map = {
                "stck_bsop_date": "date",
                "stck_clpr": "close",
                "stck_oprc": "open",
                "stck_hgpr": "high",
                "stck_lwpr": "low",
                "acml_vol": "volume",
            }

        existing_cols = [k for k in column_map.keys() if k in df.columns]
        df = df[existing_cols].rename(columns=column_map)

        # 타입 변환 및 과거 날짜가 위로 오도록 정렬
        numeric_cols = ["close", "open", "high", "low", "volume"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.iloc[::-1].reset_index(drop=True)

        # --- ✨ 핵심: 1분봉 데이터를 3분봉으로 리샘플링(Resampling) ---
        if api_tf == "3m" and "time" in df.columns:
            try:
                # 1. 날짜와 시간을 합쳐서 진짜 시간(Datetime) 인덱스로 만들기
                df["datetime"] = pd.to_datetime(
                    df["date"].astype(str) + df["time"].astype(str).str.zfill(6),
                    format="%Y%m%d%H%M%S",
                )
                df.set_index("datetime", inplace=True)

                # 2. 3분 단위('3min')로 그룹화하여 시가, 고가, 저가, 종가, 거래량 재계산
                df = (
                    df.resample("3min")
                    .agg(
                        {
                            "date": "last",
                            "time": "last",
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        }
                    )
                    .dropna()
                    .reset_index(drop=True)
                )
            except Exception as e:
                self.info_label.setText(f"3분봉 변환 에러: {e}")
                return
        # -------------------------------------------------------------

        # 볼린저 밴드를 그리기 위해선 최소 20개의 데이터(캔들)가 필요함
        if len(df) < 20:
            self.info_label.setText(
                f"{self.symbol} - 데이터 부족 (최소 20개 캔들 필요, 현재 {len(df)}개)"
            )
            return

        # 3. 지표 계산 및 차트 업데이트
        try:
            df = self.scanner.calculate_bollinger_bands(df)
            self.chart.update_chart(df)
        except Exception as e:
            self.info_label.setText(f"[{self.symbol}] 차트 지표 계산 에러: {e}")
            return

        # 4. 상단 종목명 및 현재가 업데이트
        fund = self.api.fetch_stock_fundamental(self.symbol)
        name = self.symbol
        price = 0

        if fund:
            name = fund.get("hts_kor_isnm", self.symbol)
            raw_price = fund.get("stck_prpr", 0)
            try:
                price = int(raw_price) if raw_price else 0
            except (ValueError, TypeError):
                price = 0

        self.info_label.setText(
            f"{name} ({self.symbol}) | 현재가: {price:,}원 | {self.timeframe_text}"
        )
