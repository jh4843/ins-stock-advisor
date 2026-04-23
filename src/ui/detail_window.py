import pandas as pd
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from src.api.kis_api import KISApi
from src.core.scanner import StockScanner
from src.ui.components.chart_view import StockChart


class DetailWindow(QDialog):
    def __init__(self, symbol, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.api = KISApi()
        self.scanner = StockScanner()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setWindowTitle(f"종목 상세 분석 - {self.symbol}")
        self.resize(1000, 700)
        layout = QVBoxLayout(self)

        # 상단 재무 정보 섹션
        self.info_label = QLabel("데이터 로딩 중...")
        self.info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a90e2;")
        layout.addWidget(self.info_label)

        # 중앙 차트 섹션
        self.chart = StockChart()
        layout.addWidget(self.chart)

    def load_data(self):
        # 1. 차트 데이터 (볼린저밴드 포함)
        raw_ohlcv = self.api.fetch_ohlcv(self.symbol)
        df = pd.DataFrame(raw_ohlcv)
        df.columns = ['date', 'close', 'open', 'high', 'low', 'volume']
        df = df.astype({'close': float, 'open': float, 'high': float, 'low': float})
        df = df.iloc[::-1].reset_index(drop=True)
        df = self.scanner.calculate_bollinger_bands(df)
        self.chart.update_chart(df)

        # 2. 재무 데이터
        fund = self.api.fetch_stock_fundamental(self.symbol)
        market_cap = fund.get("hts_avls", "N/A") # 시가총액
        per = fund.get("per", "N/A")
        
        info_text = f"종목코드: {self.symbol} | 시가총액: {market_cap}억 | PER: {per}"
        self.info_label.setText(info_text)