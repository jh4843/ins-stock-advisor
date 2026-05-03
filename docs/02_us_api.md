# AlphaVantage 미국 종목 API

## 설정

```env
ALPHAVANTAGE_API_KEY=your_key_here
```

무료 플랜: **25 requests/day** → SQLite 캐시 필수

---

## OHLCV 엔드포인트

### 3분봉 (Intraday)
```
GET https://www.alphavantage.co/query
  ?function=TIME_SERIES_INTRADAY
  &symbol=AAPL
  &interval=3min
  &outputsize=compact       # 최근 100개 (full: 전체)
  &adjusted=true
  &apikey=YOUR_KEY
```

### 일봉 (Daily Adjusted)
```
GET https://www.alphavantage.co/query
  ?function=TIME_SERIES_DAILY_ADJUSTED
  &symbol=AAPL
  &outputsize=compact       # 최근 100일
  &apikey=YOUR_KEY
```

### 응답 컬럼 → 표준 컬럼 매핑

| AlphaVantage | 앱 내부 |
|---|---|
| `1. open` | `open` |
| `2. high` | `high` |
| `3. low` | `low` |
| `4. close` | `close` |
| `5. volume` | `volume` |

---

## 종목 메타데이터 (카테고리 자동 분류용)

```
GET https://www.alphavantage.co/query
  ?function=OVERVIEW
  &symbol=AAPL
  &apikey=YOUR_KEY
```

사용 필드: `Sector`, `Industry`, `Name`

→ Sector 값이 카테고리 키로 사용됨  
→ **캐시 TTL: 7일** (섹터 정보는 거의 변하지 않음)

---

## SQLite 캐시 전략

파일 경로: `~/.inz_stock_advisor/data/av_cache.db`

```sql
CREATE TABLE ohlcv_cache (
    symbol      TEXT,
    interval    TEXT,       -- '3min' | 'daily'
    fetched_at  DATETIME,
    data        TEXT        -- JSON blob
);

CREATE TABLE overview_cache (
    symbol      TEXT PRIMARY KEY,
    sector      TEXT,
    industry    TEXT,
    name        TEXT,
    fetched_at  DATETIME
);
```

캐시 히트 기준:
- OHLCV: `fetched_at > now - 3분` (3분봉), `now - 1일` (일봉)
- OVERVIEW: `fetched_at > now - 7일`

---

## 미국 관심 종목 목록

파일: `src/data/us_watchlist.json`

```json
{
  "watchlist": ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN",
                "META", "GOOGL", "AMD", "INTC", "PLTR"]
}
```

앱 로딩 시 이 목록 기준으로 OVERVIEW 조회 → 카테고리 배정.  
사용자가 UI에서 종목 추가 시 목록 업데이트.

---

## 미국 카테고리 (AlphaVantage Sector 기준)

| AlphaVantage Sector | 앱 카테고리 |
|---------------------|-----------|
| Technology | 기술/AI |
| Health Care | 바이오/헬스케어 |
| Energy | 에너지 |
| Financials | 금융 |
| Consumer Discretionary | 소비재 |
| Industrials | 산업재 |
| ETF / N/A | ETF |
