import pandas as pd
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.core import categorizer
from src.utils.logger import logger


class CategoryEditDialog(QDialog):
    themes_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("종목 테마 편집")
        self.resize(820, 600)

        # {code: new_theme} — 이 세션에서 변경된 항목만 추적
        self._changes: dict[str, str] = {}

        self._df: pd.DataFrame | None = None
        self._filtered_rows: list[int] = []  # 현재 표시 중인 원본 df 인덱스

        self._init_ui()
        self._load_data()

    # ── UI 초기화 ──────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # 검색
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 검색:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("종목코드 또는 종목명 입력...")
        self.search_edit.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["종목코드", "종목명", "시장코드", "테마"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        # 테마 변경 행
        change_row = QHBoxLayout()
        change_row.addWidget(QLabel("선택 종목 테마 변경:"))
        self.theme_combo = QComboBox()
        self.theme_combo.setEditable(True)
        self.theme_combo.setMinimumWidth(180)
        change_row.addWidget(self.theme_combo)
        apply_btn = QPushButton("변경")
        apply_btn.setFixedWidth(60)
        apply_btn.clicked.connect(self._on_apply_theme)
        change_row.addWidget(apply_btn)
        change_row.addStretch()
        self.change_count_label = QLabel("변경: 0건")
        self.change_count_label.setStyleSheet("color: #aaa;")
        change_row.addWidget(self.change_count_label)
        layout.addLayout(change_row)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("저장 & 닫기")
        save_btn.setStyleSheet("background-color: #2980b9; color: white; padding: 6px 16px;")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    # ── 데이터 로드 ────────────────────────────────────────────────────────

    def _load_data(self):
        mt_path = categorizer._get_multitheme_path()
        if mt_path is None:
            QMessageBox.warning(self, "오류", "all_stocks_multitheme.csv 를 찾을 수 없습니다.")
            return

        try:
            self._df = pd.read_csv(mt_path, dtype={"종목코드": str})
            self._df["종목코드"] = self._df["종목코드"].str.strip()
        except Exception as e:
            logger.error(f"multitheme CSV 로드 실패: {e}")
            QMessageBox.warning(self, "오류", f"CSV 로드 실패: {e}")
            return

        # 테마 콤보 목록 구성 (고유 테마, "기타" 맨 뒤)
        themes = sorted(
            {
                theme
                for value in self._df["테마"].dropna()
                for theme in categorizer._split_themes(value)
            }
        )
        if "기타" in themes:
            themes.remove("기타")
            themes.append("기타")
        self.theme_combo.addItems(themes)

        self._apply_filter("")

    # ── 필터 / 표시 ────────────────────────────────────────────────────────

    def _on_search(self, text: str):
        self._apply_filter(text.strip())

    def _apply_filter(self, text: str):
        if self._df is None:
            return

        df = self._df
        if text:
            mask = (
                df["종목코드"].str.contains(text, case=False, na=False)
                | df["종목명"].str.contains(text, case=False, na=False)
            )
            indices = df[mask].index.tolist()
        else:
            indices = df.index.tolist()

        self._filtered_rows = indices
        self._populate_table(indices)

    def _populate_table(self, indices: list[int]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(indices))

        for row, idx in enumerate(indices):
            rec = self._df.iloc[idx]
            code  = str(rec["종목코드"])
            name  = str(rec["종목명"])
            mkt   = str(rec["시장코드"])
            theme = self._changes.get(code, str(rec["테마"]))

            code_item  = QTableWidgetItem(code)
            name_item  = QTableWidgetItem(name)
            mkt_item   = QTableWidgetItem(mkt)
            theme_item = QTableWidgetItem(theme)

            # 변경된 항목은 강조
            if code in self._changes:
                for item in (code_item, name_item, mkt_item, theme_item):
                    item.setForeground(Qt.GlobalColor.cyan)

            self.table.setItem(row, 0, code_item)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, mkt_item)
            self.table.setItem(row, 3, theme_item)

        self.table.setSortingEnabled(True)

    # ── 선택 / 변경 ────────────────────────────────────────────────────────

    def _on_selection_changed(self):
        rows = self.table.selectedItems()
        if not rows:
            return
        # 선택된 행의 현재 테마를 콤보박스에 반영
        row = self.table.currentRow()
        if row < 0:
            return
        theme_item = self.table.item(row, 3)
        if theme_item:
            idx = self.theme_combo.findText(theme_item.text())
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
            else:
                self.theme_combo.setCurrentText(theme_item.text())

    def _on_apply_theme(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "알림", "테마를 변경할 종목을 선택하세요.")
            return

        new_theme = self.theme_combo.currentText().strip()
        if not new_theme:
            return

        changed_rows = set(item.row() for item in selected)
        for row in changed_rows:
            code_item = self.table.item(row, 0)
            if code_item is None:
                continue
            code = code_item.text()
            self._changes[code] = new_theme

            theme_item = self.table.item(row, 3)
            if theme_item:
                theme_item.setText(new_theme)

            # 강조 표시
            for col in range(4):
                it = self.table.item(row, col)
                if it:
                    it.setForeground(Qt.GlobalColor.cyan)

        self.change_count_label.setText(f"변경: {len(self._changes)}건")

    # ── 저장 ──────────────────────────────────────────────────────────────

    def _on_save(self):
        if not self._changes:
            self.accept()
            return

        try:
            categorizer.update_stock_themes(self._changes)
            self.themes_updated.emit()
            self.accept()
        except Exception as e:
            logger.error(f"테마 저장 실패: {e}")
            QMessageBox.warning(self, "오류", f"저장 실패: {e}")
