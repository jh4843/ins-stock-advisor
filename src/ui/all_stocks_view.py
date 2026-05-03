import math

import pandas as pd
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.utils.logger import logger

PAGE_SIZE = 20

# prdy_vrss_sign → (표시 텍스트, 16진 색상)
SIGN_MAP = {
    "1": ("▲▲", "#ff4444"),  # 상한
    "2": ("▲",  "#ff6666"),  # 상승
    "3": ("—",  "#888888"),  # 보합
    "4": ("▼▼", "#4488ff"),  # 하한
    "5": ("▼",  "#6699ff"),  # 하락
}


# ── 백그라운드 가격 조회 ────────────────────────────────────────────────────

class PriceLoaderThread(QThread):
    price_loaded = pyqtSignal(str, str, str)  # code, price_str, sign

    def __init__(self, codes: list[str]):
        super().__init__()          # parent 없음 - 수명을 AllStocksView가 직접 관리
        self.codes = codes

    def run(self):
        from src.api.kis_api import KISApi
        api = KISApi()
        for code in self.codes:
            if self.isInterruptionRequested():
                break
            try:
                fund  = api.fetch_stock_fundamental(code)
                price = fund.get("stck_prpr", "")
                sign  = fund.get("prdy_vrss_sign", "3")
                if price:
                    price = f"{int(price):,}"
                self.price_loaded.emit(code, price or "—", sign)
            except Exception as e:
                logger.debug(f"[{code}] 가격 조회 실패: {e}")
                self.price_loaded.emit(code, "—", "3")


# ── 전체 종목 테이블 뷰 ────────────────────────────────────────────────────

class AllStocksView(QWidget):
    """
    all_stocks_df 의 전체 종목을 페이지네이션 테이블로 표시한다.
    현재가 / 등락은 PriceLoaderThread 가 비동기로 채운다.
    """

    stock_selected = pyqtSignal(str, str)  # code, name (차트 열기용)

    def __init__(
        self,
        all_stocks_df: pd.DataFrame,
        code_to_theme: dict[str, str],
        parent=None,
    ):
        super().__init__(parent)
        self._full_df      = all_stocks_df.copy()
        self._code_to_theme = code_to_theme
        self._filtered_df  = self._full_df
        self._current_page = 0
        self._code_row_map: dict[str, int] = {}   # code → 현재 페이지 행 인덱스
        self._price_thread: PriceLoaderThread | None = None
        self._retired_threads: list[PriceLoaderThread] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_search)

        self._init_ui()
        self._render_page()

    # ── UI ────────────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 상단: 제목 + 검색
        top = QHBoxLayout()
        title = QLabel("📋 전체 종목")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #4a90e2;")
        self._search = QLineEdit()
        self._search.setPlaceholderText("종목명 또는 코드 검색...")
        self._search.setFixedWidth(220)
        self._search.textChanged.connect(self._on_search_changed)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self._search)
        layout.addLayout(top)

        # 테이블
        headers = ["종목명", "코드", "시장", "테마", "현재가", "등락"]
        self._table = QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 70)
        self._table.setColumnWidth(4, 100)
        self._table.setColumnWidth(5, 60)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self._table)

        # 페이지네이션
        pag = QHBoxLayout()
        self._prev_btn  = QPushButton("‹ 이전")
        self._next_btn  = QPushButton("다음 ›")
        self._page_label = QLabel()
        self._prev_btn.setFixedWidth(70)
        self._next_btn.setFixedWidth(70)
        self._prev_btn.clicked.connect(self._on_prev)
        self._next_btn.clicked.connect(self._on_next)
        pag.addStretch()
        pag.addWidget(self._prev_btn)
        pag.addWidget(self._page_label)
        pag.addWidget(self._next_btn)
        pag.addStretch()
        layout.addLayout(pag)

    # ── 검색 ──────────────────────────────────────────────────────────────

    def _on_search_changed(self):
        self._search_timer.start()   # debounce 300ms

    def _apply_search(self):
        q = self._search.text().strip()
        if q:
            mask = (
                self._full_df["종목명"].str.contains(q, na=False)
                | self._full_df["종목코드"].str.contains(q, na=False)
            )
            self._filtered_df = self._full_df[mask].reset_index(drop=True)
        else:
            self._filtered_df = self._full_df
        self._current_page = 0
        self._render_page()

    # ── 페이지네이션 ──────────────────────────────────────────────────────

    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self._filtered_df) / PAGE_SIZE))

    def _on_prev(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._render_page()

    def _on_next(self):
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self._render_page()

    # ── 렌더링 ────────────────────────────────────────────────────────────

    def _render_page(self):
        # 이전 가격 조회 스레드 중단
        if self._price_thread and self._price_thread.isRunning():
            self._retire_thread(self._price_thread)

        offset   = self._current_page * PAGE_SIZE
        page_df  = self._filtered_df.iloc[offset : offset + PAGE_SIZE]
        total    = self._total_pages()

        self._page_label.setText(f"{self._current_page + 1} / {total}")
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < total - 1)

        self._table.setRowCount(len(page_df))
        self._code_row_map = {}

        for row, (_, rec) in enumerate(page_df.iterrows()):
            code  = str(rec["종목코드"])
            name  = str(rec["종목명"])
            market = str(rec["시장코드"])
            theme = self._code_to_theme.get(code, "—")

            self._set_cell(row, 0, name)
            self._set_cell(row, 1, code,   align=Qt.AlignmentFlag.AlignCenter)
            self._set_cell(row, 2, market, align=Qt.AlignmentFlag.AlignCenter)
            self._set_cell(row, 3, theme)
            self._set_cell(row, 4, "로딩 중...", color="#555555", align=Qt.AlignmentFlag.AlignRight)
            self._set_cell(row, 5, "—",        color="#888888", align=Qt.AlignmentFlag.AlignCenter)

            self._code_row_map[code] = row

        # 백그라운드 가격 조회
        codes = [str(r["종목코드"]) for _, r in page_df.iterrows()]
        if not codes:
            self._price_thread = None
            return
        self._price_thread = PriceLoaderThread(codes=codes)
        self._price_thread.price_loaded.connect(self._on_price_loaded)
        self._price_thread.finished.connect(self._on_price_thread_done)
        self._price_thread.start()

    def _on_price_thread_done(self):
        # 정상 완료 시 참조 해제 — C++ 객체 삭제 후 isRunning() 호출 방지
        self._price_thread = None

    def _on_price_loaded(self, code: str, price: str, sign: str):
        row = self._code_row_map.get(code)
        if row is None:
            return
        text, color = SIGN_MAP.get(sign, ("—", "#888888"))
        self._set_cell(row, 4, price, color="#dddddd", align=Qt.AlignmentFlag.AlignRight)
        self._set_cell(row, 5, text,  color=color,     align=Qt.AlignmentFlag.AlignCenter)

    # ── 더블클릭 → 차트 오픈 ─────────────────────────────────────────────

    def _on_row_double_clicked(self, row: int, _col: int):
        code_item = self._table.item(row, 1)
        name_item = self._table.item(row, 0)
        if code_item and name_item:
            self.stock_selected.emit(code_item.text(), name_item.text())

    def stop_loading(self):
        """위젯 제거 전 호출 — 진행 중인 가격 조회 스레드를 안전하게 중단"""
        if self._price_thread and self._price_thread.isRunning():
            self._retire_thread(self._price_thread)
            self._price_thread = None
        for thread in list(self._retired_threads):
            if thread.isRunning():
                thread.requestInterruption()

    def _retire_thread(self, thread: PriceLoaderThread):
        try:
            thread.price_loaded.disconnect(self._on_price_loaded)
        except TypeError:
            pass
        thread.requestInterruption()
        self._retired_threads.append(thread)
        thread.finished.connect(lambda t=thread: self._forget_thread(t))

    def _forget_thread(self, thread: PriceLoaderThread):
        if thread in self._retired_threads:
            self._retired_threads.remove(thread)
        thread.deleteLater()

    # ── 유틸 ──────────────────────────────────────────────────────────────

    def _set_cell(
        self,
        row: int,
        col: int,
        text: str,
        color: str | None = None,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignVCenter,
    ):
        item = QTableWidgetItem(text)
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        if color:
            item.setForeground(QColor(color))
        self._table.setItem(row, col, item)
