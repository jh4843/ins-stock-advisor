import os

from dotenv import load_dotenv

from src.utils.paths import executable_dir, resource_path

load_dotenv(resource_path(".env"))
load_dotenv(executable_dir() / ".env", override=True)


class Config:
    APP_KEY = os.getenv("KIS_APP_KEY")
    APP_SECRET = os.getenv("KIS_APP_SECRET")
    CANO = os.getenv("KIS_CANO")
    BASE_URL = os.getenv("KIS_URL")

    ALPHA_API_KEY = os.getenv("ALPHA_API_KEY")

    # API 요청 제한 (초당 호출 수) 방어용 설정
    API_DELAY = 0.2
