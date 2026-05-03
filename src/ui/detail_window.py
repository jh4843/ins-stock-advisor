from typing import Callable

import pandas as pd
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.scanner import StockScanner
from src.utils.logger import logger


def _is_us(symbol: str) -> bool:
    return not symbol.strip().isdigit()


# ── 정보 조회 스레드 ────────────────────────────────────────────────────────

class InfoLoaderThread(QThread):
    loaded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, symbol: str, is_us: bool):
        super().__init__()
        self.symbol = symbol
        self.is_us  = is_us

    def run(self):
        try:
            if self.is_us:
                from src.api.alphavantage_api import AlphaVantageApi
                data = AlphaVantageApi().fetch_overview(self.symbol)
            else:
                from src.api.kis_api import KISApi
                data = KISApi().fetch_stock_fundamental(self.symbol)
            self.loaded.emit(data or {})
        except Exception as e:
            self.failed.emit(str(e))


# ── 종목 정보 다이얼로그 ────────────────────────────────────────────────────

class StockInfoDialog(QDialog):
    def __init__(self, symbol: str, name: str, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.name   = name
        self.is_us  = _is_us(symbol)
        self._thread: InfoLoaderThread | None = None

        self.setWindowTitle(f"{name} ({symbol}) 기본 정보")
        self.setMinimumWidth(360)
        self.setModal(False)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(10)

        self._status = QLabel("정보 로딩 중...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color: #888; font-size: 13px;")
        self._layout.addWidget(self._status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._form_widget = QWidget()
        self._form = QFormLayout(self._form_widget)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form.setSpacing(8)
        scroll.setWidget(self._form_widget)
        self._layout.addWidget(scroll)

        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(80)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        self._layout.addLayout(btn_row)

        self._fetch()

    def _fetch(self):
        self._thread = InfoLoaderThread(self.symbol, self.is_us)
        self._thread.loaded.connect(self._on_loaded)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _on_loaded(self, data: dict):
        self._status.hide()
        if self.is_us:
            self._fill_us(data)
        else:
            self._fill_kr(data)

    def _on_failed(self, msg: str):
        self._status.setText(f"로딩 실패: {msg}")
        self._status.setStyleSheet("color: #e74c3c; font-size: 13px;")

    def _add_row(self, label: str, value: str, color: str | None = None):
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #888; font-size: 12px;")
        val = QLabel(value or "—")
        if color:
            val.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
        else:
            val.setStyleSheet("color: #ddd; font-size: 13px;")
        self._form.addRow(lbl, val)

    def _fill_kr(self, d: dict):
        def fmt_num(v, suffix=""):
            try:
                return f"{int(v):,}{suffix}"
            except Exception:
                return v or "—"

        sign = d.get("prdy_vrss_sign", "3")
        sign_text = {"1": "▲▲", "2": "▲", "3": "—", "4": "▼▼", "5": "▼"}.get(sign, "—")
        sign_color = {"1": "#ff4444", "2": "#ff6666", "4": "#4488ff", "5": "#6699ff"}.get(sign, "#888888")

        self._add_row("현재가",   fmt_num(d.get("stck_prpr", ""), "원"))
        self._add_row("전일대비", f"{sign_text} {d.get('prdy_vrss', '—')}원", sign_color)
        self._add_row("등락률",   f"{d.get('prdy_ctrt', '—')}%", sign_color)
        self._add_row("거래량",   fmt_num(d.get("acml_vol", "")))
        cap = d.get("hts_avls", "")
        self._add_row("시가총액", f"{fmt_num(cap)}억원" if cap else "—")
        self._add_row("PER",      d.get("per", "—"))
        self._add_row("PBR",      d.get("pbr", "—"))
        self._add_row("EPS",      fmt_num(d.get("eps", ""), "원"))
        self._add_row("52주 최고", fmt_num(d.get("w52_hgpr", ""), "원"))
        self._add_row("52주 최저", fmt_num(d.get("w52_lwpr", ""), "원"))

    def _fill_us(self, d: dict):
        def fmt_cap(v):
            try:
                n = int(v)
                if n >= 1_000_000_000_000:
                    return f"${n/1_000_000_000_000:.2f}T"
                if n >= 1_000_000_000:
                    return f"${n/1_000_000_000:.2f}B"
                return f"${n/1_000_000:.2f}M"
            except Exception:
                return v or "—"

        def fmt_pct(v):
            try:
                return f"{float(v)*100:.2f}%"
            except Exception:
                return v or "—"

        self._add_row("이름",      d.get("name", "—"))
        self._add_row("섹터",      d.get("sector", "—"))
        self._add_row("업종",      d.get("industry", "—"))
        self._add_row("시가총액",  fmt_cap(d.get("market_cap", "")))
        self._add_row("PER",       d.get("per", "—"))
        self._add_row("EPS",       f"${d.get('eps', '—')}")
        self._add_row("배당수익률", fmt_pct(d.get("dividend_yield", "")))
        self._add_row("Beta",      d.get("beta", "—"))
        self._add_row("장부가",    f"${d.get('book_value', '—')}")
        self._add_row("52주 최고", f"${d.get('w52_high', '—')}")
        self._add_row("52주 최저", f"${d.get('w52_low', '—')}")

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.loaded.disconnect()
            self._thread.requestInterruption()
        super().closeEvent(event)


# ── 차트 뷰 ─────────────────────────────────────────────────────────────────

class DetailWindow(QWidget):
    def __init__(
        self,
        symbol: str,
        stock_name: str,
        timeframe_text: str = "일봉",
        back_callback: Callable | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.symbol         = symbol
        self.stock_name     = stock_name
        self.timeframe_text = timeframe_text
        self._back_callback = back_callback
        self.scanner        = StockScanner()
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        from src.ui.components.chart_view import StockChart
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 상단 바: [← 뒤로] + 제목 + [ℹ 정보]
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(6, 4, 6, 0)

        if self._back_callback:
            back_btn = QPushButton("← 뒤로")
            back_btn.setFixedWidth(70)
            back_btn.setStyleSheet("background-color: #2c3e50; color: #aaa; height: 28px;")
            back_btn.clicked.connect(self._back_callback)
            top_bar.addWidget(back_btn)

        self.info_label = QLabel(
            f"[{self.stock_name}({self.symbol})] 데이터 분석 중... ({self.timeframe_text})"
        )
        self.info_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #4a90e2; padding: 5px;"
        )
        top_bar.addWidget(self.info_label, stretch=1)

        info_btn = QPushButton("ℹ 정보")
        info_btn.setFixedWidth(60)
        info_btn.setStyleSheet("background-color: #1a5276; color: #7fb3d3; height: 28px;")
        info_btn.clicked.connect(self._open_info_dialog)
        top_bar.addWidget(info_btn)

        layout.addLayout(top_bar)

        self.chart = StockChart()
        self.chart.set_currency("USD" if _is_us(self.symbol) else "원")
        layout.addWidget(self.chart)

    def _open_info_dialog(self):
        dlg = StockInfoDialog(self.symbol, self.stock_name, parent=self)
        dlg.show()

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
