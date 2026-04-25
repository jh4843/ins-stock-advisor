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
        if "전체" in theme_name:
            market_code = "300" if "KOSPI" in theme_name else "400"
            symbols = self.api.fetch_all_symbols(market_code)
        else:
            symbols = self.category_map.get(theme_name, [])

        # [수정] 확보된 3개 종목이 무엇인지 로그로 출력
        logger.info(
            f">>> 스캔 대상 리스트 확보: {len(symbols)}개 종목 ({', '.join(symbols)})"
        )

        found_stocks = []
        for symbol in symbols:
            # 개별 종목 분석 시작 로그
            logger.debug(f"[{symbol}] 분석 시작...")

            raw_data = self.api.fetch_ohlcv(symbol, timeframe)
            if not raw_data or len(raw_data) < 20:
                logger.warning(
                    f"[{symbol}] 데이터 부족으로 스킵 (수신된 데이터: {len(raw_data) if raw_data else 0}개)"
                )
                continue

            df = pd.DataFrame(raw_data)
            df = df[["stck_clpr", "stck_oprc", "stck_hgpr", "stck_lwpr"]].copy()
            df.columns = ["close", "open", "high", "low"]
            df = df.astype(float).iloc[::-1].reset_index(drop=True)

            df = self.calculate_bollinger_bands(df)
            last = df.iloc[-1]
            bbl_cols = [c for c in df.columns if c.startswith("BBL_")]
            bbu_cols = [c for c in df.columns if c.startswith("BBU_")]

            if not bbl_cols or not bbu_cols:
                logger.warning(
                    f"[{symbol}] 볼린저밴드 지표 생성 실패 (컬럼 없음). 현재 컬럼: {df.columns.tolist()}"
                )
                continue

            # 찾은 첫 번째 컬럼에서 값을 가져옵니다.
            curr = last["close"]
            lower = last[bbl_cols[0]]
            upper = last[bbu_cols[0]]

            # NaN 체크 (지표 계산이 되었으나 값이 없는 경우)
            if pd.isna(lower) or pd.isna(upper):
                logger.debug(f"[{symbol}] 지표 값이 NaN입니다. 스킵합니다.")
                continue

            # 상세 값 로그 (app.log에서 확인 가능)
            logger.debug(
                f"[{symbol}] 결과 - 현재가: {curr}, 하단: {lower:.2f}, 상단: {upper:.2f}"
            )

            is_match = False
            if (condition == "하단 터치" or condition == "전체") and curr <= lower:
                is_match = True
            elif (condition == "상단 터치" or condition == "전체") and curr >= upper:
                is_match = True

            if is_match:
                logger.info(f"★ 조건 일치 종목 발견: {symbol} ★")
                found_stocks.append(
                    {"symbol": symbol, "price": curr, "status": "조건 일치"}
                )

        return found_stocks
