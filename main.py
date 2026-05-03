import sys
import traceback

from PyQt6.QtWidgets import QApplication

from src.api.auth_manager import AuthManager
from src.ui.loading_window import LoadingWindow
from src.ui.main_window import MainWindow
from src.utils.logger import logger

_main_window: MainWindow | None = None


def _on_setup_complete(app: QApplication, cats: dict):
    global _main_window
    _main_window = MainWindow(initial_categories=cats)
    _main_window.show()
    logger.info(f"Inz-Stock-Advisor v2.0 가동 시작 (카테고리 {len(cats)}개)")


def main():
    app = QApplication(sys.argv)

    try:
        with open("src/ui/styles.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        logger.warning("스타일시트 없음 — 기본 테마로 실행")

    # 1. KIS 인증
    try:
        if not AuthManager().get_access_token():
            logger.error("KIS API 토큰 발급 실패 — .env 확인")
            return
    except Exception as e:
        logger.critical(f"인증 오류: {e}")
        return

    # 2. 로딩 화면 → 완료 시 MainWindow 오픈
    try:
        loader = LoadingWindow()
        loader.setup_complete.connect(lambda cats: _on_setup_complete(app, cats))
        loader.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"실행 오류: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
