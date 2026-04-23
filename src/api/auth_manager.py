import json

import requests

from src.utils.config import Config
from src.utils.logger import logger


class AuthManager:
    _instance = None
    _token = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthManager, cls).__new__(cls)
        return cls._instance

    def get_access_token(self):
        """KIS API 접근 토큰 발급"""
        if self._token:
            return self._token

        url = f"{Config.BASE_URL}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": Config.APP_KEY,
            "appsecret": Config.APP_SECRET,
        }

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body))

            if res.status_code != 200:
                logger.error(f"KIS API 서버 응답: {res.text}")
            res.raise_for_status()

            res.raise_for_status()
            self._token = res.json().get("access_token")
            logger.info("KIS API Access Token 발급 성공")
            return self._token
        except Exception as e:
            logger.error(f"Access Token 발급 실패: {e}")
            return None
