import json

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.scanner import StockScanner
from src.ui.detail_window import DetailWindow
from src.utils.logger import logger


# 스캔을 수행할 백그라운드 스레드
class ScanWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, theme_name, timeframe, condition):  # 인자 추가
        super().__init__()
        self.theme_name = theme_name
        self.timeframe = timeframe
        self.condition = condition
        self.scanner = StockScanner()

    def run(self):
        try:
            # scanner.py의 함수가 3개의 인자를 받도록 수정되어야 합니다.
            results = self.scanner.scan_by_theme(
                self.theme_name, self.timeframe, self.condition
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()  # 여기서 아래 메서드를 호출합니다.
        self.load_categories()

    def init_ui(self):
        # 1. 창 기본 설정
        self.setWindowTitle("Inz-Stock-Advisor v1.0")
        self.resize(1000, 700)  # 인터페이스가 늘어났으므로 창 크기를 조금 키웁니다.

        # 2. 메인 위젯 및 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 3. 컨트롤바 (상단 검색 조건 설정)
        top_layout = QHBoxLayout()

        # 테마 선택
        self.category_combo = QComboBox()
        self.load_categories()

        # 타임프레임 선택 (3분봉, 일봉, 주봉, 월봉)
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["일봉", "3분봉", "주봉", "월봉"])

        # 지표 조건 선택 (상단/하단/전체)
        self.condition_combo = QComboBox()
        self.condition_combo.addItems(["전체", "하단 터치", "상단 터치"])

        self.scan_btn = QPushButton("종목 스캔 시작")

        # 컨트롤바 위젯 배치
        top_layout.addWidget(QLabel("테마:"))
        top_layout.addWidget(self.category_combo, 2)  # 테마 칸을 조금 더 넓게
        top_layout.addWidget(QLabel("단위:"))
        top_layout.addWidget(self.timeframe_combo, 1)
        top_layout.addWidget(QLabel("조건:"))
        top_layout.addWidget(self.condition_combo, 1)
        top_layout.addWidget(self.scan_btn)

        layout.addLayout(top_layout)

        # 4. 결과 테이블 생성
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(
            ["종목코드", "현재가", "상태 (볼린저밴드)"]
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.result_table)

        # 5. 상태바
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("준비 완료")

        # 6. 이벤트 연결
        self.scan_btn.clicked.connect(self.start_scan)
        self.result_table.itemDoubleClicked.connect(self.show_detail)

    def load_categories(self):
        """JSON 데이터와 전체 옵션을 콤보박스에 로드"""
        try:
            # 전체 스캔 옵션 상단에 추가
            self.category_combo.addItem("전체 (KOSPI)")
            self.category_combo.addItem("전체 (KOSDAQ)")

            with open("src/data/category_map.json", "r", encoding="utf-8") as f:
                categories = json.load(f)
                self.category_combo.addItems(categories.keys())
        except Exception as e:
            logger.error(f"카테고리 로드 실패: {e}")

    def start_scan(self):
        theme = self.category_combo.currentText()
        # UI에서 선택한 값을 파라미터로 매핑
        tf_map = {"일봉": "D", "3분봉": "3m", "주봉": "W", "월봉": "M"}
        timeframe = tf_map[self.timeframe_combo.currentText()]
        condition = self.condition_combo.currentText()

        self.scan_btn.setEnabled(False)
        self.statusBar().showMessage(f"[{theme} / {timeframe}] 스캔 중...")

        # Worker 스레드에 파라미터 전달
        self.worker = ScanWorker(theme, timeframe, condition)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.error.connect(self.on_scan_error)
        self.worker.start()

    def on_scan_finished(self, results):
        self.scan_btn.setEnabled(True)
        self.statusBar().showMessage(f"스캔 완료: {len(results)}개 종목 발견")

        self.result_table.setRowCount(len(results))
        for i, stock in enumerate(results):
            self.result_table.setItem(i, 0, QTableWidgetItem(stock["symbol"]))
            # 천단위 콤마 포맷팅
            price_item = QTableWidgetItem(f"{int(stock['price']):,}")
            price_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.result_table.setItem(i, 1, price_item)

            status_item = QTableWidgetItem(stock["status"])
            # 하단 터치는 파란색, 상단 터치는 빨간색 (가독성)
            if "하단" in stock["status"]:
                status_item.setForeground(Qt.GlobalColor.blue)
            else:
                status_item.setForeground(Qt.GlobalColor.red)
            self.result_table.setItem(i, 2, status_item)

    def on_scan_error(self, error_msg):
        self.scan_btn.setEnabled(True)
        self.statusBar().showMessage(f"에러 발생: {error_msg}")
        logger.error(error_msg)

    def show_detail(self, item):
        # 어떤 행이 클릭되었는지 확인하고 종목코드(0번 열) 가져오기
        row = item.row()
        symbol = self.result_table.item(row, 0).text()

        detail_win = DetailWindow(symbol, self)
        detail_win.exec()  # 모달 창으로 띄움
