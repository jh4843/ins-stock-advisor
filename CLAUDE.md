# CLAUDE.md

## 프로젝트 핵심 컨텍스트

Python + PyQt6 데스크탑 앱. KIS API(한국 종목) + AlphaVantage(미국 종목) 연동.
요구사항 상세는 `docs/` 폴더 참고.

---

## KIS API 함정 모음

**응답 파싱**
- OHLCV 데이터는 `response["output2"]` — `output`(단수) 아님
- 성공 판별: `rt_cd == "0"` (HTTP 200이어도 API 거절일 수 있음)
- Rate limit: 요청마다 `time.sleep(0.2)` 필수, 안 하면 초당 초과 오류

**컬럼명이 엔드포인트마다 다름**
- 일봉 종가: `stck_clpr` / 3분봉 현재가: `stck_prpr`
- 일봉 거래량: `acml_vol` / 3분봉 거래량: `cntg_vol`
- `detail_window.py`의 `column_map` 분기 참고

**3분봉 주의**
- API(`FHKST03010230`)는 **1분봉**을 반환함 → `resample('3min')`으로 직접 변환
- 날짜(`stck_bsop_date`) + 시간(`stck_cntg_hour`) 합쳐서 datetime 인덱스 생성 후 리샘플링

**데이터 순서**
- KIS는 최신 → 과거 순으로 반환 → 차트 그리기 전 반드시 `iloc[::-1]` 뒤집기

**환경 URL**
- 모의투자: `https://openapivts.koreainvestment.com:9443` (`.env`의 `KIS_URL`)
- 실전투자: `https://openapi.koreainvestment.com:9443`

---

## MST 마스터파일 파싱

바이너리 CP949 인코딩. 현재 3필드만 추출 중 (`kis_api.py:56-59`).
- `byte[0:9]` → 종목코드 (마지막 6자리만 유효: `code[-6:]`)
- `byte[21:61]` → 종목명
- 업종코드는 byte 62 이후 — 아직 미구현 (카테고리 동적 분류 구현 시 필요)

---

## pandas_ta 볼린저밴드

컬럼명이 파라미터에 따라 동적 생성됨: `BBL_20_2.0`, `BBU_20_2.0`, `BBM_20_2.0`
→ 하드코딩 금지, `[c for c in df.columns if c.startswith("BBL_")]`로 탐색

---

## 카테고리 시스템 (변경 중)

현재: `src/data/category_map.json` 정적 관리  
목표: 앱 로딩 시 KIS 업종코드 + AlphaVantage Sector로 자동 빌드  
매핑 규칙: `src/data/sector_rules.json` (신규 생성 예정)  
캐시: `~/.inz_stock_advisor/data/category_cache.json` (TTL 24h)

---

## 파일 경로 규칙

| 용도 | 경로 |
|------|------|
| 전종목 CSV | `~/.inz_stock_advisor/data/all_stocks.csv` |
| 카테고리 캐시 | `~/.inz_stock_advisor/data/category_cache.json` |
| AlphaVantage 캐시 | `~/.inz_stock_advisor/data/av_cache.db` |
| 앱 로그 | `log/app.log` |

---

## AlphaVantage (미구현)

env var: `ALPHA_API_KEY` → `Config.ALPHA_API_KEY`로 접근  
무료 플랜 25 req/day → **캐시 없으면 당일 소진 위험**.  
모든 호출 전 SQLite 캐시 히트 확인 필수. `src/api/alphavantage_api.py` 신규 작성 예정.

---

## 건드리지 말 것

- `src/core/analyzer.py` — 빈 플레이스홀더, 아직 설계 전
- `AuthManager` — 싱글톤, 토큰 메모리 캐시. 인스턴스 여러 개 만들지 말 것
