# 한국투자증권 KIS API

## 인증

- 방식: OAuth2 Client Credentials
- 토큰 유효시간: 24시간 → 만료 전 자동 갱신
- 구현: `src/api/auth_manager.py` (싱글톤)

---

## MST 마스터 파일 파싱 (확장 필요)

현재 byte 0~61만 파싱 중. **업종코드 포함 전체 파싱으로 확장 필요.**

### 파싱 대상 필드

| 필드 | 바이트 범위 | 설명 |
|------|------------|------|
| 종목코드 | 0–8 | 6자리 종목 코드 |
| 종목명 | 21–60 | 한글 종목명 |
| 업종구분코드 | 업종 영역 | KIS 업종 분류 코드 |
| 시장구분 | — | KOSPI / KOSDAQ |

### 데이터 저장 경로
```
~/.inz_stock_advisor/data/all_stocks.csv
  컬럼: 종목코드, 종목명, 시장코드, 업종코드
```

### 참고
- KIS 공식 MST 파서: https://github.com/koreainvestment/open-trading-api
- KOSPI / KOSDAQ 각각 별도 파일 다운로드

---

## OHLCV 엔드포인트

### 3분봉
```
GET /uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice
tr_id: FHKST03010230
params: fid_input_iscd, fid_input_hour_1, fid_pw_data_incu_yn=Y
```
- 응답: 최대 30개 → 반복 호출로 충분한 데이터 확보
- 1분봉 → 3분봉 리샘플링: `resample('3T')` (ohlc + volume sum)

### 일봉
```
GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
tr_id: FHKST03010100
params: fid_input_iscd, fid_period_div_code=D, fid_org_adj_prc=0
```
- 조회 기간: 최근 1년 (365일)

### 현재가 / 기본 정보
```
GET /uapi/domestic-stock/v1/quotations/inquire-price
tr_id: FHKST01010100
```

---

## Rate Limit

- 요청 간격: **0.2초** (`API_DELAY = 0.2`)
- 스캔 중 대량 호출 시 큐 기반 순차 처리 권장

---

## 수급 데이터 (선택 기능)

```
GET /uapi/domestic-stock/v1/quotations/inquire-investor
tr_id: FHKST01010900
```
- 외국인/기관 순매수 수량 → 차트 오버레이용
