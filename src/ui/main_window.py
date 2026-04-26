import json
from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt
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
from src.ui.detail_window import DetailWindow
from src.utils.logger import logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = KISApi()
        self.categories = {}
        self.stock_name_map = {}
        self.load_stock_master()
        self.init_ui()
        self.load_categories()

    def load_stock_master(self):
        """저장된 전종목 CSV가 있다면 로드, 없으면 최초 1회 다운로드"""
        user_data_dir = Path.home() / ".inz_stock_advisor" / "data"
        csv_path = user_data_dir / "all_stocks.csv"

        # 프로그램 처음 시작 시 파일이 없으면 자동 다운로드
        if not csv_path.exists():
            logger.info("마스터 데이터가 없습니다. 최초 종목 다운로드를 진행합니다...")
            self.api.download_all_symbols_to_csv()

        try:
            if csv_path.exists():
                df = pd.read_csv(csv_path, dtype={"종목코드": str})
                self.stock_name_map = dict(zip(df["종목코드"], df["종목명"]))
                logger.info(f"마스터 데이터 로드 완료: {csv_path}")
        except Exception as e:
            logger.error(f"마스터 데이터 로드 실패: {e}")

    def init_ui(self):
        self.setWindowTitle("Inz-Stock-Advisor v1.2")
        self.resize(1400, 900)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.fetch_all_btn = QPushButton("📂 전종목 리스트 추출 (CSV)")
        self.fetch_all_btn.clicked.connect(self.on_download_csv)
        self.fetch_all_btn.setStyleSheet(
            "height: 45px; font-weight: bold; background-color: #34495e; color: white;"
        )

        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["일봉", "3분봉", "주봉", "월봉"])
        self.timeframe_combo.currentIndexChanged.connect(self.refresh_current_chart)

        self.category_combo = QComboBox()
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)

        self.stock_list = QListWidget()
        self.stock_list.itemClicked.connect(self.on_stock_clicked)

        self.add_stock_btn = QPushButton("+ 종목 추가 (코드)")
        self.add_stock_btn.clicked.connect(self.add_custom_stock)

        left_layout.addWidget(self.fetch_all_btn)
        left_layout.addWidget(QLabel("⏰ 차트 주기:"))
        left_layout.addWidget(self.timeframe_combo)
        left_layout.addWidget(QLabel("📂 카테고리:"))
        left_layout.addWidget(self.category_combo)
        left_layout.addWidget(QLabel("📋 종목 목록:"))
        left_layout.addWidget(self.stock_list)
        left_layout.addWidget(self.add_stock_btn)

        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.placeholder = QLabel("왼쪽 목록에서 종목을 선택하세요.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_layout.addWidget(self.placeholder)

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.detail_container)
        self.splitter.setStretchFactor(1, 4)

        layout.addWidget(self.splitter)
        self.setStatusBar(QStatusBar())

    def load_categories(self):
        try:
            with open("src/data/category_map.json", "r", encoding="utf-8") as f:
                self.categories = json.load(f)
                self.category_combo.clear()
                self.category_combo.addItems(self.categories.keys())
        except Exception as e:
            logger.error(f"카테고리 로드 실패: {e}")

    def on_category_changed(self):
        category = self.category_combo.currentText()
        self.stock_list.clear()
        if category in self.categories:
            for code in self.categories[category]:
                # 맵에 이름이 없으면 기본적으로 "알 수 없음" 으로 표시
                name = self.stock_name_map.get(code, "알 수 없음")
                self.stock_list.addItem(f"{name} ({code})")

    def on_download_csv(self):
        self.statusBar().showMessage("전체 종목 수집 중...")
        file_name = self.api.download_all_symbols_to_csv()
        if file_name:
            QMessageBox.information(
                self, "완료", f"전종목 리스트가 저장되었습니다:\n{file_name}"
            )
            # CSV 다운로드 완료 시 즉시 마스터 데이터를 다시 읽고 리스트를 새로고침
            self.load_stock_master()
            self.on_category_changed()
        self.statusBar().showMessage("준비 완료")

    def on_stock_clicked(self, item):
        display_text = item.text()  # 예: 삼성전자 (005930)

        # 괄호 안의 코드와 괄호 밖의 종목명을 분리
        symbol = display_text.split("(")[-1].replace(")", "").strip()
        stock_name = display_text.rsplit("(", 1)[0].strip()

        timeframe_text = self.timeframe_combo.currentText()

        for i in reversed(range(self.detail_layout.count())):
            w = self.detail_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        # DetailWindow에 종목명(stock_name)도 함께 전달
        detail_view = DetailWindow(symbol, stock_name, timeframe_text)
        self.detail_layout.addWidget(detail_view)

    def refresh_current_chart(self):
        current_item = self.stock_list.currentItem()
        if current_item:
            self.on_stock_clicked(current_item)

    def add_custom_stock(self):
        category = self.category_combo.currentText()
        if not category:
            return

        code, ok = QInputDialog.getText(
            self, "종목 추가", "추가할 종목 코드를 입력하세요:"
        )
        if ok and code:
            if code not in self.categories.get(category, []):
                self.categories[category].append(code)
                try:
                    with open("src/data/category_map.json", "w", encoding="utf-8") as f:
                        json.dump(self.categories, f, ensure_ascii=False, indent=2)
                    self.on_category_changed()
                except Exception as e:
                    logger.error(f"카테고리 파일 저장 중 에러 발생: {e}")
            else:
                QMessageBox.warning(self, "경고", "이미 추가된 종목입니다.")
            if code not in self.categories.get(category, []):
                self.categories[category].append(code)
                try:
                    with open("src/data/category_map.json", "w", encoding="utf-8") as f:
                        json.dump(self.categories, f, ensure_ascii=False, indent=2)
                    self.on_category_changed()
                except Exception as e:
                    logger.error(f"카테고리 파일 저장 중 에러 발생: {e}")
            else:
                QMessageBox.warning(self, "경고", "이미 추가된 종목입니다.")
