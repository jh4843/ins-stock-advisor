import sys
import traceback

from PyQt6.QtWidgets import QApplication

from src.api.auth_manager import AuthManager
from src.ui.main_window import MainWindow  # 이 줄만 남기고 아래 .py 라인은 삭제하세요
from src.utils.logger import logger


def main():
    app = QApplication(sys.argv)

    # [선택사항] 스타일시트 적용 (src/ui/styles.qss 파일이 있을 경우)
    try:
        with open("src/ui/styles.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        logger.warning("스타일시트 파일을 찾을 수 없습니다. 기본 테마로 실행합니다.")

    # 1. API 인증 확인
    try:
        auth = AuthManager()
        if not auth.get_access_token():
            logger.error("API 토큰 발급에 실패했습니다. .env 설정을 확인하세요.")
            return
    except Exception as e:
        logger.critical(f"인증 과정 중 치명적 오류 발생: {e}")
        return

    # 2. 메인 윈도우 실행
    try:
        window = MainWindow()
        window.show()
        logger.info("Inz-Stock-Advisor v1.0 가동 시작")
        sys.exit(app.exec())
    except Exception as e:
        # 실행 중 에러 발생 시 트레이스백을 출력해서 어디서 터졌는지 확인
        logger.error(f"프로그램 가동 중 에러 발생: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
