import time

import requests

from src.api.auth_manager import AuthManager
from src.utils.config import Config


class KISApi:
    def __init__(self):
        self.auth = AuthManager()

    def get_headers(self, tr_id: str):
        """기본 헤더 생성"""
        return {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.auth.get_access_token()}",
            "appkey": Config.APP_KEY,
            "appsecret": Config.APP_SECRET,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def fetch_all_symbols(self, market_code: str = "300"):
        """
        시장별 전종목 리스트 조회
        market_code: 300(KOSPI), 400(KOSDAQ)
        """
        url = (
            f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-search-stock"
        )
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": market_code,  # 시장 분류 코드
        }
        # 실제 운영시에는 마스터 파일을 로컬에 저장해두고 쓰는 것이 빠르지만,
        # 실시간성을 위해 API 방식을 예시로 듭니다.
        response = requests.get(
            url, headers=self.get_headers("FHKST01010100"), params=params
        )
        time.sleep(Config.API_DELAY)

        if response.status_code == 200:
            # 종목코드 리스트만 추출해서 반환
            return [item["pdno"] for item in response.json().get("output", [])]
        return []

    def fetch_ohlcv(self, symbol: str, timeframe: str = "D"):
        """타임프레임별 데이터 호출 및 구조 검증"""
        if timeframe == "3m":
            url = f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_ETC_CLS_CODE": "",
                "FID_PW_DATA_INCU_YN": "N",
            }
            tr_id = "FHKST03010200"
        else:
            url = f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_PERIOD_DIV_CODE": timeframe,
                "FID_ORG_ADJ_PRC": "0",
            }
            tr_id = "FHKST03010100"

        res = requests.get(url, headers=self.get_headers(tr_id), params=params)

        if res.status_code == 200:
            data = res.json().get("output2", [])
            # 데이터가 너무 적으면 지표 계산이 안 됨 (최소 20개)
            if len(data) < 20:
                logger.warning(f"{symbol}: 데이터 부족 ({len(data)}개)")
                return []
            return data
        else:
            logger.error(f"API 호출 실패: {res.text}")
            return []

    def fetch_stock_fundamental(self, symbol: str):
        """종목 기본적 분석 데이터(시가총액, PER, EPS 등) 조회"""
        url = f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}
        # 트랜잭션 ID: FHKST01010100 (주식현재가 시세)
        response = requests.get(
            url, headers=self.get_headers("FHKST01010100"), params=params
        )
        time.sleep(Config.API_DELAY)

        if response.status_code == 200:
            return response.json().get("output", {})
        return {}

    def fetch_financial_statement(self, symbol: str):
        """주요 재무지표(영업이익 등) 조회"""
        url = f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-invest"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}
        # 트랜잭션 ID: FHKST01010200 (주식현재가 투자지표)
        response = requests.get(
            url, headers=self.get_headers("FHKST01010200"), params=params
        )
        time.sleep(Config.API_DELAY)

        if response.status_code == 200:
            return response.json().get("output", {})
        return {}
