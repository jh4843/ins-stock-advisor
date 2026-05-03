from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src.api.kis_api import KISApi
from src.core import categorizer
from src.ui.category_edit_dialog import CategoryEditDialog
from src.ui.detail_window import DetailWindow
from src.utils.logger import logger


class RefreshThread(QThread):
    """카테고리 새로고침 전용 스레드 (강제 재빌드)"""
    loaded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            cats = categorizer.load_categories(
                force_rebuild=True,
                progress_cb=lambda msg: logger.info(msg),
            )
            self.loaded.emit(cats)
        except Exception as e:
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self, initial_categories: dict):
        super().__init__()
        self.api = KISApi()
        self.categories: dict[str, list] = initial_categories
        self.stock_name_map: dict[str, str] = {}
        self.all_stocks_df: pd.DataFrame = pd.DataFrame()
        self._refresh_thread: RefreshThread | None = None

        self._load_stock_master()
        self._init_ui()
        self._populate_categories(initial_categories)

    # ── 마스터 데이터 ──────────────────────────────────────────────────────

    def _load_stock_master(self):
        csv_path = Path.home() / ".inz_stock_advisor" / "data" / "all_stocks.csv"
        try:
            if csv_path.exists():
                df = pd.read_csv(csv_path, dtype={"종목코드": str})
                self.all_stocks_df  = df
                self.stock_name_map = dict(zip(df["종목코드"], df["종목명"]))
                logger.info(f"마스터 데이터 로드: {len(self.stock_name_map):,}개")
        except Exception as e:
            logger.error(f"마스터 데이터 로드 실패: {e}")

    def _build_theme_map(self) -> dict[str, str]:
        """categories dict를 역순 순회해 {종목코드: 테마명} 반환"""
        result: dict[str, str] = {}
        for theme, stocks in self.categories.items():
            for entry in stocks:
                code = entry["code"] if isinstance(entry, dict) else entry
                result[code] = theme
        return result

    # ── UI 초기화 ──────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle("Inz-Stock-Advisor v2.0")
        self.resize(1400, 900)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.fetch_all_btn = QPushButton("📂 전종목 리스트 추출 (CSV)")
        self.fetch_all_btn.clicked.connect(self._on_download_csv)
        self.fetch_all_btn.setStyleSheet(
            "height: 40px; font-weight: bold; background-color: #34495e; color: white;"
        )

        self.all_stocks_btn = QPushButton("📋 전체 종목 보기")
        self.all_stocks_btn.clicked.connect(self._on_show_all_stocks)
        self.all_stocks_btn.setStyleSheet(
            "height: 34px; background-color: #1a5276; color: #7fb3d3;"
        )

        self.edit_theme_btn = QPushButton("📝 테마 편집")
        self.edit_theme_btn.clicked.connect(self._open_category_editor)
        self.edit_theme_btn.setStyleSheet(
            "height: 34px; background-color: #1a6b3c; color: white;"
        )

        self.refresh_btn = QPushButton("🔄 카테고리 새로고침")
        self.refresh_btn.clicked.connect(self._on_refresh_categories)
        self.refresh_btn.setStyleSheet(
            "height: 34px; background-color: #2c3e50; color: #aaa;"
        )

        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["일봉", "3분봉", "주봉", "월봉"])
        self.timeframe_combo.currentIndexChanged.connect(self._refresh_current_chart)

        self.category_combo = QComboBox()
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)

        self.stock_list = QListWidget()
        self.stock_list.itemClicked.connect(self._on_stock_clicked)

        self.add_stock_btn = QPushButton("+ 종목 추가")
        self.add_stock_btn.clicked.connect(self._add_custom_stock)

        left_layout.addWidget(self.fetch_all_btn)
        left_layout.addWidget(self.all_stocks_btn)
        left_layout.addWidget(self.edit_theme_btn)
        left_layout.addWidget(self.refresh_btn)
        left_layout.addWidget(QLabel("⏰ 차트 주기:"))
        left_layout.addWidget(self.timeframe_combo)
        left_layout.addWidget(QLabel("📂 카테고리:"))
        left_layout.addWidget(self.category_combo)
        left_layout.addWidget(QLabel("📋 종목 목록:"))
        left_layout.addWidget(self.stock_list)
        left_layout.addWidget(self.add_stock_btn)

        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_container)
        placeholder = QLabel("왼쪽 목록에서 종목을 선택하거나 전체 종목을 탐색하세요.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_layout.addWidget(placeholder)

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.detail_container)
        self.splitter.setStretchFactor(1, 4)

        layout.addWidget(self.splitter)
        self.setStatusBar(QStatusBar())

    # ── 전체 종목 뷰 ───────────────────────────────────────────────────────

    def _on_show_all_stocks(self):
        if self.all_stocks_df.empty:
            self.statusBar().showMessage("마스터 데이터가 없습니다. CSV를 먼저 다운로드하세요.", 4000)
            return

        from src.ui.all_stocks_view import AllStocksView

        self._clear_detail()
        view = AllStocksView(
            all_stocks_df=self.all_stocks_df,
            code_to_theme=self._build_theme_map(),
        )
        view.stock_selected.connect(self._open_chart_from_table)
        self.detail_layout.addWidget(view)

    def _open_chart_from_table(self, code: str, name: str):
        tf = self.timeframe_combo.currentText()
        self._clear_detail()
        self.detail_layout.addWidget(
            DetailWindow(code, name, tf, back_callback=self._restore_all_stocks_view)
        )

    def _restore_all_stocks_view(self):
        self._clear_detail()
        self._on_show_all_stocks()

    # ── 카테고리 ───────────────────────────────────────────────────────────

    def _populate_categories(self, cats: dict):
        self.categories = cats
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItems(cats.keys())
        self.category_combo.blockSignals(False)
        self._on_category_changed()

    def _on_category_changed(self):
        category = self.category_combo.currentText()
        self.stock_list.clear()
        for entry in self.categories.get(category, []):
            code   = entry["code"]
            market = entry.get("market", "KR")
            name   = self.stock_name_map.get(code) or entry.get("name") or code
            self.stock_list.addItem(f"[{market}] {name} ({code})")

    def _on_refresh_categories(self):
        if self._refresh_thread and self._refresh_thread.isRunning():
            return
        self.refresh_btn.setEnabled(False)
        self.statusBar().showMessage("카테고리 재빌드 중...")
        self._refresh_thread = RefreshThread(parent=self)
        self._refresh_thread.loaded.connect(self._on_refresh_done)
        self._refresh_thread.failed.connect(self._on_refresh_failed)
        self._refresh_thread.start()

    def _on_refresh_done(self, cats: dict):
        self._populate_categories(cats)
        self.refresh_btn.setEnabled(True)
        self.statusBar().showMessage(f"카테고리 새로고침 완료 ({len(cats)}개)", 3000)

    def _on_refresh_failed(self, msg: str):
        self.refresh_btn.setEnabled(True)
        self.statusBar().showMessage(f"새로고침 실패: {msg}", 5000)

    # ── 종목 선택 ──────────────────────────────────────────────────────────

    def _on_stock_clicked(self, item):
        text = item.text()                          # "[KR] 삼성전자 (005930)"
        code = text.split("(")[-1].rstrip(")")
        name = text.split("] ", 1)[-1].rsplit("(", 1)[0].strip()
        tf   = self.timeframe_combo.currentText()

        self._clear_detail()
        self.detail_layout.addWidget(DetailWindow(code, name, tf))

    def _refresh_current_chart(self):
        current = self.stock_list.currentItem()
        if current:
            self._on_stock_clicked(current)

    def _clear_detail(self):
        for i in reversed(range(self.detail_layout.count())):
            w = self.detail_layout.itemAt(i).widget()
            if w:
                if hasattr(w, "stop_loading"):
                    w.stop_loading()
                w.deleteLater()

    # ── 종목 추가 ──────────────────────────────────────────────────────────

    def _add_custom_stock(self):
        category = self.category_combo.currentText()
        if not category:
            return

        code, ok = QInputDialog.getText(
            self, "종목 추가", "종목 코드 입력 (예: 005930 또는 AAPL):"
        )
        if not ok or not code:
            return

        code   = code.strip().upper()
        market = "US" if not code.isdigit() else "KR"

        if market == "KR":
            name = self.stock_name_map.get(code, "")
        else:
            from src.api.alphavantage_api import AlphaVantageApi
            overview = AlphaVantageApi().fetch_overview(code)
            name = overview.get("name", code) if overview else code

        try:
            self.categories = categorizer.add_stock(self.categories, category, code, name, market)
            self._on_category_changed()
        except Exception as e:
            QMessageBox.warning(self, "오류", f"종목 추가 실패: {e}")

    # ── 테마 편집 ──────────────────────────────────────────────────────────

    def _open_category_editor(self):
        dlg = CategoryEditDialog(parent=self)
        dlg.themes_updated.connect(self._on_refresh_categories)
        dlg.exec()

    # ── CSV 다운로드 ───────────────────────────────────────────────────────

    def _on_download_csv(self):
        self.statusBar().showMessage("전체 종목 수집 중...")
        file_name = self.api.download_all_symbols_to_csv()
        if file_name:
            self._load_stock_master()
            self._on_category_changed()
            QMessageBox.information(self, "완료", f"전종목 리스트 저장:\n{file_name}")
        self.statusBar().showMessage("준비 완료", 3000)
