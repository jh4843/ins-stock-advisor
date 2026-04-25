import logging
import os
import sys


def setup_logger():
    # 1. log 폴더 경로 설정 및 자동 생성
    log_dir = "log"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger("InzStockAdvisor")
    logger.setLevel(logging.DEBUG)  # 상세 분석을 위해 DEBUG 레벨 유지

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 2. 콘솔(Terminal) 출력용 핸들러
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # 3. 파일(File) 저장용 핸들러 (log/app.log)
    file_path = os.path.join(log_dir, "app.log")
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
