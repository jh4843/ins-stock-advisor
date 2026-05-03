# ins-stock-advisor 개요

## 목적
한국(KIS API) + 미국(AlphaVantage) 종목을 카테고리별로 분류하고, 볼린저밴드 터치 종목을 실시간으로 탐지하는 데스크탑 주식 분석 도구.

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.13+ |
| GUI | PyQt6 |
| 차트 | pyqtgraph |
| 분석 | pandas, pandas_ta |
| 한국 API | 한국투자증권 KIS OpenAPI |
| 미국 API | AlphaVantage |
| 로컬 캐시 | SQLite (`src/core/cache.py`) |

---

## 폴더 구조

```
ins-stock-advisor/
├── main.py
├── requirements.txt
├── .env                          # API 키 설정
├── src/
│   ├── api/
│   │   ├── auth_manager.py       # KIS OAuth2 토큰 관리
│   │   ├── kis_api.py            # KIS API 래퍼
│   │   └── alphavantage_api.py   # AlphaVantage API 래퍼 (신규)
│   ├── core/
│   │   ├── cache.py              # SQLite 캐시 (OHLCV + Overview)
│   │   ├── categorizer.py        # 동적 카테고리 빌더
│   │   └── scanner.py            # 볼린저밴드 스캔 엔진 (KR+US)
│   ├── data/
│   │   ├── category_map.json     # KR 수동 카테고리 (사용자 편집)
│   │   ├── us_watchlist.json     # US 관심 종목 목록
│   │   └── sector_rules.json     # 섹터 → 카테고리 매핑 규칙
│   └── ui/
│       ├── main_window.py        # 메인 UI (QThread 백그라운드 로딩)
│       ├── detail_window.py      # 종목 차트 (KR/US 분기)
│       └── components/
│           └── chart_view.py
└── docs/                         # 요구사항 문서
```

---

## 앱 로딩 시퀀스

```
앱 시작
  │
  ├─ 1. KIS OAuth2 토큰 발급
  │
  ├─ 2. KIS MST → all_stocks.csv (없을 때만)
  │
  ├─ 3. CategoryLoaderThread (백그라운드)
  │       ├─ 캐시 유효 (24h) → category_cache.json 즉시 로드
  │       └─ 캐시 만료 → rebuild
  │               ├─ KR: category_map.json 로드
  │               └─ US: us_watchlist.json + AV OVERVIEW (SQLite 캐시 우선)
  │
  └─ 4. 카테고리 드롭다운 표시
```

---

## 환경변수 (.env)

```
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_CANO=
KIS_URL=https://openapi.koreainvestment.com:9443

ALPHA_API_KEY=
```
