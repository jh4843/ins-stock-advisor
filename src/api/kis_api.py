import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from src.api.auth_manager import AuthManager
from src.utils.config import Config
from src.utils.logger import logger


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

    def download_all_symbols_to_csv(self):
        """한국투자증권 공식 마스터파일(mst)을 다운로드하여 전종목 리스트 추출"""
        logger.info("마스터 파일 다운로드 시작...")

        base_url = "https://new.real.download.dws.co.kr/common/master/"
        markets = [("kospi_code", "KOSPI"), ("kosdaq_code", "KOSDAQ")]
        all_data = []

        try:
            for file_name, market_name in markets:
                # ... (기존 마스터 파일 다운로드 및 파싱 로직 동일) ...
                logger.info(f"{market_name} 수집 중...")
                zip_url = f"{base_url}{file_name}.mst.zip"
                zip_path = f"{file_name}.zip"
                mst_path = f"{file_name}.mst"

                import os
                import urllib.request
                import zipfile

                urllib.request.urlretrieve(zip_url, zip_path)

                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall()

                with open(mst_path, "rb") as f:
                    for line in f:
                        try:
                            code = line[0:9].decode("cp949").strip()
                            if len(code) >= 6:
                                code = code[-6:]
                            name = line[21:61].decode("cp949").strip()

                            if code and name:
                                all_data.append(
                                    {
                                        "종목코드": code,
                                        "종목명": name,
                                        "시장코드": market_name,
                                    }
                                )
                        except Exception:
                            continue

                if os.path.exists(zip_path):
                    os.remove(zip_path)
                if os.path.exists(mst_path):
                    os.remove(mst_path)

            # 5. DataFrame 변환 및 특정 사용자 폴더에 CSV 고정 저장
            if all_data:
                df = pd.DataFrame(all_data)
                df = df[df["종목코드"].str.isnumeric()]

                # 사용자 홈 디렉터리 하위에 앱 폴더 생성
                user_data_dir = Path.home() / ".inz_stock_advisor" / "data"
                user_data_dir.mkdir(parents=True, exist_ok=True)

                file_path = user_data_dir / "all_stocks.csv"
                df.to_csv(file_path, index=False, encoding="utf-8-sig")

                logger.info(f"총 {len(df)}개 종목 마스터 데이터 저장 완료: {file_path}")
                return str(file_path)

            return None

        except Exception as e:
            logger.error(f"마스터 파일 수집 실패: {e}")
            return None

    def fetch_ohlcv(self, symbol: str, timeframe: str = "D"):
        """주기별 시세 조회 (D:일, W:주, M:월, 3m:3분봉)"""
        try:
            today = datetime.now()

            if timeframe == "3m":
                # 주식일별분봉조회 (최대 120개의 1분봉 데이터를 수집)
                url = f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
                params = {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": symbol,
                    "FID_INPUT_DATE_1": today.strftime("%Y%m%d"),
                    "FID_INPUT_HOUR_1": "235959",  # 가장 최근 시간부터 역순으로 조회
                    "FID_PW_DATA_INCU_YN": "Y",
                }
                tr_id = "FHKST03010230"
            else:
                # 국내주식기간별시세 (일/주/월)
                start_date = (today - timedelta(days=365)).strftime("%Y%m%d")
                end_date = today.strftime("%Y%m%d")

                url = f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
                params = {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": symbol,
                    "FID_INPUT_DATE_1": start_date,
                    "FID_INPUT_DATE_2": end_date,
                    "FID_PERIOD_DIV_CODE": timeframe,
                    "FID_ORG_ADJ_PRC": "1",
                }
                tr_id = "FHKST03010100"

            res = requests.get(url, headers=self.get_headers(tr_id), params=params)
            time.sleep(Config.API_DELAY)

            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") != "0":
                    logger.error(f"[{symbol}] KIS API 거절 응답: {data.get('msg1')}")
                return data.get("output2", [])
            return []

        except Exception as e:
            logger.error(f"[{symbol}] fetch_ohlcv 에러: {e}")
            return []

    def fetch_stock_fundamental(self, symbol: str):
        """종목 현재가 및 기본 정보 조회"""
        url = f"{Config.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}
        try:
            res = requests.get(
                url, headers=self.get_headers("FHKST01010100"), params=params
            )
            if res.status_code == 200:
                return res.json().get("output", {})
        except Exception as e:
            logger.error(f"[{symbol}] 기본정보 조회 에러: {e}")
        return {}
        return {}
