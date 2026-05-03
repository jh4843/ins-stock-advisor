# INS STOCK ADVISOR

## 패키지 설치

pip install -r requirements.txt

## 가상환경 셍상

### 1. 가상환경 생성 (이름은 보통 .venv로 합니다)

python -m venv .venv

### 2. 가상환경 활성화 (Windows 기준)

.venv\Scripts\activate

### 3. 그 다음 패키지 설치

pip install -r requirements.txt

```
ins-stock-advisor
├─ LICENSE
├─ main.py
├─ README.md
├─ requirements.txt
├─ specification.md
└─ src
   ├─ api
   │  ├─ auth_manager.py
   │  ├─ kis_api.py
   │  └─ __init__.py
   ├─ assets
   ├─ build_tools
   ├─ core
   │  ├─ analyzer.py
   │  ├─ scanner.py
   │  └─ __init__.py
   ├─ data
   │  └─ category_map.json
   ├─ ui
   │  ├─ components
   │  ├─ main_window.py
   │  ├─ styles.qss
   │  └─ __init__.py
   ├─ utils
   │  ├─ config.py
   │  ├─ logger.py
   │  └─ __init__.py
   └─ __init__.py

```

### 4. 실행

python main.py
