# [설계 사양서] Inz-Stock-Advisor v1.0

**작성일:** 2026-04-23  
**작성자:** 인즈팸 (Software Developer)  
**기술 스택:** Python 3.13.2, PyQt6, KIS API, Pandas

---

## 1. 개요 (Introduction)

### 1.1 목적

본 애플리케이션은 한국 증시(KOSPI, KOSDAQ) 종목 중 사용자가 설정한 기술적 지표(볼린저밴드) 및 특정 테마(분야) 조건에 부합하는 종목을 탐색하고, 상세 분석 데이터를 제공하는 **Windows 데스크톱 기반 의사결정 보조 도구**이다.

### 1.2 주요 기능

- **멀티 타임프레임 스캔:** 3분봉, 일봉, 주봉, 월봉 단위 데이터 분석.
- **기술적 지표 필터링:** 볼린저밴드 상단/하단 터치 종목 실시간 추출.
- **테마 기반 분류:** 사용자 정의 분야(반도체, 자동차, 로봇, 우주항공 등) 필터링.
- **종목 상세 분석:** 캔들 차트, 시가총액, 영업이익 등 기본적/기술적 데이터 통합 표시.

---

## 2. 시스템 아키텍처 (System Architecture)

애플리케이션은 유지보수와 확장을 위해 **계층형 아키텍처(Layered Architecture)**를 채택한다.

| 계층 (Layer)       | 구성 모듈           | 역할 설명                                               |
| :----------------- | :------------------ | :------------------------------------------------------ |
| **Presentation**   | `src/ui/`           | PyQt6 기반 GUI 렌더링, 차트 시각화, 사용자 이벤트 처리. |
| **Business Logic** | `src/core/`         | 볼린저밴드 연산, 테마 매핑, 종목 필터링 알고리즘.       |
| **Data Access**    | `src/api/`          | KIS API(REST/WebSocket) 통신, OAuth2 토큰 갱신 관리.    |
| **Persistence**    | `src/data/`, `.env` | 테마 매핑 JSON 파일, 사용자 설정 및 보안 키 관리.       |

---

## 3. 상세 요구사항 (Requirements)

### 3.1 종목 스캐너 (Scanner)

- **데이터 호출:** KIS API를 통해 전 종목 또는 특정 테마 리스트의 OHLCV 데이터를 수집한다.
- **지표 계산:** `pandas_ta` 라이브러리를 사용하여 볼린저밴드($20, 2$) 값을 산출한다.
- **조건 부합 판별:** 현재가 $P$가 $P \le Lower Band$ (하단 터치) 또는 $P \ge Upper Band$ (상단 터치) 조건을 충족하는지 검사한다.

### 3.2 테마 엔진 (Theme Engine)

- **분류 체계:** `category_map.json` 파일을 통해 업종별/테마별 종목 코드를 매핑한다.
- **필터링:** 사용자가 선택한 분야에 해당하는 종목군에 대해서만 스캔을 수행하여 효율성을 높인다.

### 3.3 상세 뷰어 (Detail Viewer)

- **시각화:** `pyqtgraph`를 활용하여 가격 캔들과 볼린저밴드 지표를 차트로 구현한다.
- **데이터 분석:** 시가총액, 최근 분기 영업이익 등 핵심 재무 지표를 요약 표시한다.

---

## 4. 데이터 모델 (Data Model)

### 4.1 테마 매핑 구조 (`category_map.json`)

```json
{
  "반도체": ["005930", "000660", "232290"],
  "로봇": ["043910", "404100", "383310"],
  "우주항공": ["047810", "272210"],
  "이차전지": ["006400", "373220"]
}
```

---

## 5. 보안 및 제약 사항 (Constraints)

- 인증 보안: App Key와 App Secret은 .env 파일에 저장하며, Git 저장소에 노출되지 않도록 처리한다.

- API 제한 관리: 한국투자증권 API의 초당 호출 제한(Rate Limit)을 준수하기 위해 QThread 내에서 호출 간격(Delay)을 제어한다.

- 배포 방식: PyInstaller 또는 Nuitka를 사용하여 단일 실행 파일(.exe)로 빌드한다.

---

## 6. Architecture

```
ins-stock-advisor/
├── .env                # API Key, Secret 등 민감 정보 (Git 제외)
├── .gitignore          # venv, __pycache__, .env, .exe 등 제외 설정
├── requirements.txt    # 의존성 라이브러리 목록
├── main.py             # 프로그램 진입점 (Entry Point)
│
├── src/                # 소스 코드 메인 폴더
│   ├── __init__.py
│   │
│   ├── api/            # 증권사 API 통신 모듈
│   │   ├── __init__.py
│   │   ├── auth_manager.py  # 토큰 발급 및 갱신
│   │   └── kis_api.py       # 시세 조회, 종목 정보 수집 API 래퍼
│   │
│   ├── ui/             # GUI 관련 (PyQt6)
│   │   ├── __init__.py
│   │   ├── main_window.py   # 메인 창 UI 및 이벤트 바인딩
│   │   ├── components/      # 커스텀 위젯 (차트 뷰, 종목 테이블 등)
│   │   └── styles.qss       # UI 디자인용 스타일시트
│   │
│   ├── core/           # 핵심 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── scanner.py       # 볼린저밴드 계산 및 종목 필터링 로직
│   │   └── analyzer.py      # 종목 상세 분석 (영업이익, 시총 계산 등)
│   │
│   ├── utils/          # 공통 유틸리티
│   │   ├── __init__.py
│   │   ├── logger.py        # 로그 기록 (디버깅용)
│   │   └── config.py        # 설정 파일 로드
│   │
│   └── data/           # 정적 데이터 관리
│       └── category_map.json # 반도체, 로봇 등 분야별 종목 매핑 데이터
│
├── assets/             # 아이콘, 로고 이미지 등 리소스
│
└── build_tools/        # 배포 관련 설정 (PyInstaller/Nuitka 스크립트)

```
