from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from src.utils.logger import logger


class SetupThread(QThread):
    progress = pyqtSignal(str)   # 상태 메시지
    done     = pyqtSignal(dict)  # 완성된 categories
    failed   = pyqtSignal(str)

    def __init__(self, force_rebuild: bool = False, parent=None):
        super().__init__(parent)
        self.force_rebuild = force_rebuild

    def run(self):
        try:
            from src.api.kis_api import KISApi
            from src.core import categorizer

            # 1. MST 마스터 파일
            csv_path = Path.home() / ".inz_stock_advisor" / "data" / "all_stocks.csv"
            if not csv_path.exists():
                self.progress.emit("KIS 전종목 마스터 파일 다운로드 중...")
                KISApi().download_all_symbols_to_csv()

            # 2. 카테고리 빌드
            cats = categorizer.load_categories(
                force_rebuild=self.force_rebuild,
                progress_cb=lambda msg: self.progress.emit(msg),
            )
            self.done.emit(cats)

        except Exception as e:
            logger.error(f"SetupThread 에러: {e}")
            self.failed.emit(str(e))


class LoadingWindow(QWidget):
    setup_complete = pyqtSignal(dict)  # categories를 MainWindow로 전달

    def __init__(self, force_rebuild: bool = False):
        super().__init__()
        self._thread: SetupThread | None = None
        self._init_ui()
        self._start(force_rebuild)

    def _init_ui(self):
        self.setWindowTitle("Inz-Stock-Advisor")
        self.setFixedSize(420, 140)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Inz-Stock-Advisor 초기화 중...")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #4a90e2;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("시작 중...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

    def _start(self, force_rebuild: bool):
        self._thread = SetupThread(force_rebuild=force_rebuild, parent=self)
        self._thread.progress.connect(self._on_progress)
        self._thread.done.connect(self._on_done)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()

    def _on_progress(self, msg: str):
        # 너무 긴 메시지는 잘라서 표시
        display = msg if len(msg) <= 50 else msg[:47] + "..."
        self.status_label.setText(display)

    def _on_done(self, cats: dict):
        self.setup_complete.emit(cats)
        self.close()

    def _on_failed(self, msg: str):
        self.status_label.setText(f"오류: {msg}")
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
