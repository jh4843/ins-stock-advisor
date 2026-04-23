import os

from dotenv import load_dotenv

load_dotenv()

class Config:
    APP_KEY = os.getenv("KIS_APP_KEY")
    APP_SECRET = os.getenv("KIS_APP_SECRET")
    CANO = os.getenv("KIS_CANO")
    BASE_URL = os.getenv("KIS_URL")
    
    # API 요청 제한 (초당 호출 수) 방어용 설정
    API_DELAY = 0.05