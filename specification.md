# [설계 사양서] Inz-Stock-Advisor v1.2

**최종 수정일:** 2026-04-26  
**작성자:** 김재혁 (Software Developer)  
**버전:** v1.2 (Dashboard & Data Hub Edition)

---

## 1. 개요 (Introduction)

### 1.1 목적

한국투자증권(KIS) API를 활용하여 국내 주식 데이터를 수집하고, 볼린저밴드 등 기술적 지표를 기반으로 사용자의 매수/매도 의사결정을 보조하는 **데스크톱 대시보드 애플리케이션**이다.

### 1.2 v1.2 주요 개선 사항

- **인터페이스 혁신:** 단일 창 내에서 리스트와 상세 정보를 동시에 확인하는 `QSplitter` 기반 이중 패인(Dual-Pane) 구조 채택.
- **전종목 데이터 확보:** API를 통한 실시간 전종목 리스트 추출 및 CSV 저장 기능 추가 (분석용 오프라인 데이터 세트 구축).
- **멀티 타임프레임 확장:** 일봉 위주에서 벗어나 3분봉, 주봉, 월봉 시세 조회 및 지표 분석 지원.
- **사용자 정의 관리:** 카테고리별 종목 관리 및 동적 종목 추가 기능 강화.

---

## 2. UI/UX 디자인 (UI/UX Design)

### 2.1 메인 윈도우 구조 (Splitter Layout)

- **좌측 컨트롤 패널 (Control Pane):**
  - **Data Tools:** 전종목 리스트를 CSV로 내려받는 상단 버튼 (`all_stocks_YYYYMMDD.csv`).
  - **Timeframe Select:** 3분봉/일봉/주봉/월봉 선택 콤보박스.
  - **Category Select:** `category_map.json`에 정의된 테마별 그룹 필터링.
  - **Stock List:** 선택된 카테고리의 종목 코드를 나열하며, 클릭 시 우측 상세 패널 즉시 업데이트.
  - **Manage:** 종목 코드를 직접 입력하여 현재 카테고리에 실시간 추가 및 저장.
- **우측 상세 패널 (Detail Pane):**
  - **Info Header:** 종목명, 현재가, 전일대비(부호 포함), 현재 선택 주기를 가독성 있게 표시.
  - **Interactive Chart:** `pyqtgraph`를 활용하여 캔들/라인 및 볼린저밴드(상단, 중앙, 하단)를 실시간 렌더링.

---

## 3. 기능적 사양 (Functional Specifications)

### 3.1 데이터 수집 (API Integration)

- **전종목 마스터:** `inquire-search-stock` API를 통해 KOSPI/KOSDAQ 전종목 심볼 수집.
- **분봉 데이터:** 3분봉 선택 시 `inquire-time-itemchartprice` (FHKST03010200) 호출.
- **일/주/월 데이터:** `inquire-daily-itemchartprice` (FHKST03010100) 호출.
- **기본 정보:** `inquire-price` (FHKST01010100)를 통해 실시간 현재가 및 종목 한글명 수집.

### 3.2 데이터 처리 및 안정성

- **유연한 데이터 매핑:** API 응답 컬럼 개수 변동에 대응하기 위해 필요한 컬럼만 추출하는 동적 딕셔너리 매핑 적용.
- **에러 방지:** 데이터 부족(20건 미만) 시 분석 스킵 로직 및 지표 계산 시 `NaN` 처리 강화.
- **기술 지표:** 20일 이동평균선 기반 상하단 2.0σ 볼린저밴드 엔진 탑재.

---

## 4. 시스템 아키텍처 (System Architecture)

### 4.1 기술 스택

- **언어:** Python 3.13.2
- **GUI:** PyQt6
- **분석/차트:** Pandas, Pandas-ta, pyqtgraph
- **통신:** Requests (REST API)

### 4.2 프로젝트 구조

```text
ins-stock-advisor/
├── main.py                 # 앱 진입점 및 테마 적용
├── src/
│   ├── api/
│   │   ├── auth_manager.py  # OAuth2 토큰 관리
│   │   └── kis_api.py       # 시세 수집 및 전종목 CSV 추출 로직
│   ├── core/
│   │   └── scanner.py       # 기술적 지표 계산 엔진
│   ├── ui/
│   │   ├── main_window.py   # 메인 대시보드 (Splitter & 리스트 관리)
│   │   ├── detail_window.py # 우측 상세 정보 위젯 (QWidget)
│   │   └── components/
│   │       └── chart_view.py # 동적 지표 대응 차트 컴포넌트
│   ├── data/
│   │   └── category_map.json # 사용자 정의 테마 종목 저장소
│   └── utils/
│       ├── config.py        # 환경 설정 및 API 키 관리
│       └── logger.py        # 시스템 로그 관리
└── requirements.txt         # 의존성 목록

```

## 5. 향후 로드맵 (Future Roadmap)

1. 전종목 자동 스캔: 추출된 CSV 데이터를 루프 돌려 볼린저 하단 터치 종목을 한꺼번에 찾아내는 오프라인 엔진 개발.
2. 수급 지표 통합: 외국인/기관 매매동향(API 국내주식-037) 정보를 차트 패널에 추가 표시.
3. 실시간 알림: 특정 조건 충족 시 윈도우 시스템 알림(Toast Notification) 및 사운드 효과 구현.
