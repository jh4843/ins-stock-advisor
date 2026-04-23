import json

import pandas as pd
import pandas_ta as ta

from src.api.kis_api import KISApi
from src.utils.logger import logger


class StockScanner:
    def __init__(self):
        self.api = KISApi()
        with open("src/data/category_map.json", "r", encoding="utf-8") as f:
            self.category_map = json.load(f)

    def calculate_bollinger_bands(
        self, df: pd.DataFrame, length: int = 20, std: int = 2
    ):
        """볼린저밴드 상단, 중앙, 하단 계산"""
        bb = ta.bbands(df["close"], length=length, std=std)
        df = pd.concat([df, bb], axis=1)
        return df

    def scan_stocks(self, theme_name: str, timeframe: str, condition: str):
        """사용자 정의 조건에 따른 종목 스캔"""
        # 종목 리스트 결정 로직 (기존과 동일)
        if "전체" in theme_name:
            market_code = "300" if "KOSPI" in theme_name else "400"
            symbols = self.api.fetch_all_symbols(market_code)
        else:
            symbols = self.category_map.get(theme_name, [])

        found_stocks = []
        for symbol in symbols:
            raw_data = self.api.fetch_ohlcv(symbol, timeframe)
            if len(raw_data) < 20:
                continue  # 데이터 부족 시 패스

            df = pd.DataFrame(raw_data)
            # KIS API 컬럼명 대응 (stck_clpr: 종가)
            df = df[["stck_clpr", "stck_oprc", "stck_hgpr", "stck_lwpr"]].copy()
            df.columns = ["close", "open", "high", "low"]
            df = df.astype(float).iloc[::-1].reset_index(drop=True)

            df = self.calculate_bollinger_bands(df)
            last = df.iloc[-1]
            curr_price, lower, upper = (
                last["close"],
                last["BBL_20_2.0"],
                last["BBU_20_2.0"],
            )

            # 조건 판별
            is_match = False
            status = ""
            if condition in ["전체", "하단 터치"] and curr_price <= lower:
                is_match, status = True, "하단 터치 (과매도)"
            elif condition in ["전체", "상단 터치"] and curr_price >= upper:
                is_match, status = True, "상단 터치 (돌파)"

            if is_match:
                found_stocks.append(
                    {"symbol": symbol, "price": curr_price, "status": status}
                )

        return found_stocks

    def scan_by_theme(self, theme_name: str, timeframe: str, condition: str):
        """
        사용자 정의 조건(테마, 타임프레임, 상/하단)에 따른 종목 스캔
        """
        # 1. 대상 종목 리스트 결정
        if theme_name == "전체 (KOSPI)":
            symbols = self.api.fetch_all_symbols("300")
        elif theme_name == "전체 (KOSDAQ)":
            symbols = self.api.fetch_all_symbols("400")
        else:
            symbols = self.category_map.get(theme_name, [])

        found_stocks = []
        total = len(symbols)
        logger.info(
            f"[{theme_name}] {timeframe} 단위 / {condition} 조건 스캔 시작... (총 {total}종목)"
        )

        for i, symbol in enumerate(symbols):
            # API 호출 제한 준수를 위해 주기적으로 진행 상황 기록
            if i % 10 == 0:
                logger.info(f"진행 상황: {i}/{total} ({int(i / total * 100)}%)")

            # 2. 지정된 타임프레임으로 데이터 호출
            raw_data = self.api.fetch_ohlcv(symbol, timeframe)
            if not raw_data or len(raw_data) < 20:  # 지표 계산을 위해 최소 20개 필요
                continue

            # 3. DataFrame 전처리
            df = pd.DataFrame(raw_data)
            # KIS API 응답 컬럼 매핑 (stck_clpr: 종가, stck_oprc: 시가 등)
            df = df[
                ["stck_clpr", "stck_oprc", "stck_hgpr", "stck_lwpr", "acml_vol"]
            ].copy()
            df.columns = ["close", "open", "high", "low", "volume"]
            df = df.astype(float)

            # ★ 중요: KIS 데이터는 최신순이므로 지표 계산을 위해 과거->현재 순으로 뒤집음
            df = df.iloc[::-1].reset_index(drop=True)

            # 4. 볼린저밴드 계산 ($20, 2$)
            df = self.calculate_bollinger_bands(df)

            # 최신 행 데이터 추출
            last_row = df.iloc[-1]
            curr_price = last_row["close"]
            lower_band = last_row["BBL_20_2.0"]
            upper_band = last_row["BBU_20_2.0"]

            # 5. 사용자 지정 조건에 따른 필터링
            is_match = False
            status = ""

            # 조건 판별식: P <= Lower Band 또는 P >= Upper Band
            # 조건 판별식: 너무 엄격하면 0개이므로 약간의 마진(0.5%)을 줍니다.
            if condition == "하단 터치" or condition == "전체":
                if curr_price <= lower_band * 1.005:  # 하단 근처 0.5% 이내 접근
                    is_match, status = True, "하단 근접/터치"

            if not is_match and (condition == "상단 터치" or condition == "전체"):
                if curr_price >= upper_band * 0.995:  # 상단 근처 0.5% 이내 접근
                    is_match, status = True, "상단 근접/터치"

            # 6. 결과 저장
            if is_match:
                logger.info(
                    f"발견: {symbol} | 가격: {int(curr_price):,} | 상태: {status}"
                )
                found_stocks.append(
                    {"symbol": symbol, "price": curr_price, "status": status}
                )

        return found_stocks
