# 동적 카테고리 분류 시스템

## 기본 원칙

카테고리맵은 정적 파일이 아닌 **앱 로딩 시 자동 생성**된다.  
업종코드 → 카테고리 매핑 규칙만 별도 파일로 관리하며, 사용자가 편집 가능하다.

---

## 로딩 시퀀스

```
1. KR: category_map.json (수동 관리 목록) 로드
      └─ {"반도체": ["005930", ...]} → {"code", "name":"", "market":"KR"} 변환

2. US: us_watchlist.json 로드
      │
      ├─ AlphaVantage OVERVIEW 조회 (SQLite 캐시 우선, TTL 7일)
      └─ sector_rules.json "US" 섹터맵 → 카테고리 배정

3. 통합 category_cache.json 저장
      경로: ~/.inz_stock_advisor/data/category_cache.json
      TTL: 24시간 (만료 시 재빌드)

4. CategoryLoaderThread → UI 카테고리 드롭다운 갱신
```

> **KR 종목 업종코드 자동 분류는 미구현.**  
> 현재는 `category_map.json`을 수동 편집하거나 UI에서 직접 추가한다.  
> KIS MST 전체 파싱(byte 62+)을 통한 자동 분류는 추후 구현 예정.

---

## 매핑 규칙 파일

**파일**: `src/data/sector_rules.json`

```json
{
  "KR_keywords": {
    "반도체": ["반도체", "실리콘", "웨이퍼", "파운드리", ...],
    ...
  },
  "US": {
    "Technology":             "기술/AI",
    "Health Care":            "바이오/헬스케어",
    "Energy":                 "에너지",
    "Financials":             "금융",
    "Consumer Discretionary": "소비재",
    "Industrials":            "산업재",
    "Communication Services": "커뮤니케이션"
  }
}
```

- `KR_keywords`: 향후 종목명 키워드 기반 자동 분류용 (현재 미사용)
- `US`: AlphaVantage OVERVIEW `Sector` 값 → 앱 카테고리명 매핑  
- 사용자가 직접 편집해 카테고리명 변경 또는 신규 섹터 추가 가능

---

## 카테고리 캐시 포맷

**파일**: `~/.inz_stock_advisor/data/category_cache.json`

```json
{
  "built_at": "2025-05-03T09:00:00",
  "categories": {
    "반도체": [
      {"code": "005930", "name": "삼성전자", "market": "KR"},
      {"code": "000660", "name": "SK하이닉스", "market": "KR"}
    ],
    "기술/AI": [
      {"code": "NVDA", "name": "NVIDIA Corp", "market": "US"},
      {"code": "AMD",  "name": "Advanced Micro Devices", "market": "US"}
    ]
  }
}
```

---

## UI 동작

| 상황 | 동작 |
|------|------|
| 앱 시작 | 캐시 유효하면 즉시 로드, 만료 시 재빌드 |
| 카테고리 드롭다운 | 캐시의 키 목록으로 자동 구성 |
| "새로고침" 버튼 | TTL 무시하고 강제 재빌드 |
| 종목 수동 추가 | 선택 카테고리에 append 후 캐시 갱신 |
| sector_rules.json 수정 | 재시작 또는 새로고침 시 반영 |

---

## 미분류 처리

- 매핑 규칙에 없는 업종코드 → **"기타"** 카테고리로 분류
- UI에서 기타 카테고리 숨김 옵션 제공 (기본: 숨김)
