import json
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.utils.logger import logger

CACHE_PATH = Path.home() / ".inz_stock_advisor" / "data" / "category_cache.json"
CACHE_TTL_HOURS = 24

KR_MAP_PATH  = Path("src/data/category_map.json")
US_LIST_PATH = Path("src/data/us_watchlist.json")
RULES_PATH   = Path("src/data/sector_rules.json")

MULTITHEME_ASSET_PATH = Path("assets/all_stocks_multitheme.csv")
MULTITHEME_USER_PATH  = Path.home() / ".inz_stock_advisor" / "data" / "all_stocks_multitheme.csv"
ALL_STOCKS_CSV_PATH   = Path.home() / ".inz_stock_advisor" / "data" / "all_stocks.csv"

# AV 무료 플랜: 분당 5회 → 12초 간격
_AV_RATE_LIMIT_SEC = 12


def load_categories(
    force_rebuild: bool = False,
    progress_cb=None,
) -> dict:
    """
    캐시가 유효하면 즉시 반환, 만료됐거나 force_rebuild=True 이면 rebuild.
    progress_cb(message: str) — 옵션. 진행 상황 텍스트를 UI에 전달.
    """
    if not force_rebuild and _is_cache_valid():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("카테고리 캐시 로드 완료")
            return data.get("categories", {})
        except Exception as e:
            logger.warning(f"캐시 읽기 실패, 재빌드: {e}")

    return _build(progress_cb)


def _get_multitheme_path() -> Path | None:
    """사용자 사본 반환; 없으면 번들 원본 복사 후 반환. 둘 다 없으면 None."""
    if MULTITHEME_USER_PATH.exists():
        return MULTITHEME_USER_PATH
    if MULTITHEME_ASSET_PATH.exists():
        MULTITHEME_USER_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MULTITHEME_ASSET_PATH, MULTITHEME_USER_PATH)
        logger.info(f"multitheme CSV 사본 생성: {MULTITHEME_USER_PATH}")
        return MULTITHEME_USER_PATH
    logger.warning("all_stocks_multitheme.csv 를 찾을 수 없습니다.")
    return None


def sync_themes_from_multitheme(progress_cb=None) -> None:
    """
    all_stocks.csv + all_stocks_multitheme.csv 를 비교해 category_map.json 재생성.
    미분류 종목은 '기타'로 처리. 완료 후 캐시 삭제.
    """
    def notify(msg: str):
        logger.info(msg)
        if progress_cb:
            progress_cb(msg)

    if not ALL_STOCKS_CSV_PATH.exists():
        logger.info("all_stocks.csv 없음 — sync_themes 건너뜀")
        return

    mt_path = _get_multitheme_path()
    if mt_path is None:
        return

    notify("all_stocks_multitheme.csv 로드 중...")
    try:
        all_df = pd.read_csv(ALL_STOCKS_CSV_PATH, dtype={"종목코드": str})
        mt_df  = pd.read_csv(mt_path, dtype={"종목코드": str})
    except Exception as e:
        logger.error(f"CSV 로드 실패: {e}")
        return

    # {code: theme} 맵 (multitheme CSV 기준)
    theme_map: dict[str, str] = dict(zip(mt_df["종목코드"].str.strip(), mt_df["테마"].str.strip()))

    # all_stocks.csv의 모든 코드에 테마 할당
    kr_map: dict[str, list[str]] = {}
    for code in all_df["종목코드"]:
        code = str(code).strip()
        theme = theme_map.get(code, "기타")
        kr_map.setdefault(theme, [])
        if code not in kr_map[theme]:
            kr_map[theme].append(code)

    # "기타"는 맨 뒤로 정렬
    ordered: dict[str, list[str]] = {k: v for k, v in sorted(kr_map.items()) if k != "기타"}
    if "기타" in kr_map:
        ordered["기타"] = kr_map["기타"]

    try:
        with open(KR_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(ordered, f, ensure_ascii=False, indent=2)
        notify(f"category_map.json 재생성 완료: {len(ordered)}개 테마")
    except Exception as e:
        logger.error(f"category_map.json 저장 실패: {e}")
        return

    # 캐시 삭제 → 다음 load_categories() 에서 _build() 강제 실행
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()


def update_stock_themes(changes: dict[str, str]) -> None:
    """
    changes = {code: new_theme} 를 multitheme CSV(사용자 사본)에 반영.
    완료 후 sync_themes_from_multitheme() 호출.
    """
    if not changes:
        return

    mt_path = _get_multitheme_path()
    if mt_path is None:
        return

    try:
        mt_df = pd.read_csv(mt_path, dtype={"종목코드": str})
    except Exception as e:
        logger.error(f"multitheme CSV 로드 실패: {e}")
        return

    mt_df["종목코드"] = mt_df["종목코드"].str.strip()

    for code, theme in changes.items():
        mask = mt_df["종목코드"] == code
        if mask.any():
            mt_df.loc[mask, "테마"] = theme
        else:
            new_row = {"종목코드": code, "종목명": code, "시장코드": "KOSPI", "테마": theme}
            if ALL_STOCKS_CSV_PATH.exists():
                try:
                    all_df = pd.read_csv(ALL_STOCKS_CSV_PATH, dtype={"종목코드": str})
                    row = all_df[all_df["종목코드"].str.strip() == code]
                    if not row.empty:
                        new_row["종목명"]  = row.iloc[0]["종목명"]
                        new_row["시장코드"] = row.iloc[0]["시장코드"]
                except Exception:
                    pass
            mt_df = pd.concat([mt_df, pd.DataFrame([new_row])], ignore_index=True)

    try:
        mt_df.to_csv(mt_path, index=False, encoding="utf-8-sig")
        logger.info(f"multitheme CSV 저장 완료: {len(changes)}건 변경")
    except Exception as e:
        logger.error(f"multitheme CSV 저장 실패: {e}")
        return

    sync_themes_from_multitheme()


def _build(progress_cb=None) -> dict:
    def notify(msg: str):
        logger.info(msg)
        if progress_cb:
            progress_cb(msg)

    categories: dict[str, list] = {}

    # ── 1. KR: category_map.json ───────────────────────────────────────────
    notify("KR 종목 카테고리 로드 중...")
    try:
        with open(KR_MAP_PATH, "r", encoding="utf-8") as f:
            kr_map = json.load(f)
        for cat, codes in kr_map.items():
            categories.setdefault(cat, [])
            for code in codes:
                if not any(e["code"] == code for e in categories[cat]):
                    categories[cat].append({"code": code, "name": "", "market": "KR"})
        notify(f"KR 카테고리 로드 완료: {list(kr_map.keys())}")
    except Exception as e:
        logger.error(f"category_map.json 로드 실패: {e}")

    # ── 2. US: known sectors 우선, 나머지만 AV OVERVIEW 호출 ───────────────
    notify("US 종목 카테고리 빌드 중...")
    try:
        from src.api.alphavantage_api import AlphaVantageApi

        with open(US_LIST_PATH, "r", encoding="utf-8") as f:
            watchlist: list[str] = json.load(f).get("watchlist", [])

        with open(RULES_PATH, "r", encoding="utf-8") as f:
            rules = json.load(f)

        us_sector_map: dict  = rules.get("US", {})
        us_known: dict       = rules.get("us_known_sectors", {})

        av = AlphaVantageApi()
        last_api_call = 0.0

        for i, symbol in enumerate(watchlist):
            notify(f"US 종목 분류 중... ({i+1}/{len(watchlist)}) {symbol}")

            # ① SQLite 캐시 확인
            overview = av.cache.get_overview(symbol)

            # ② 하드코딩된 known 목록 확인
            if not overview and symbol in us_known:
                known = us_known[symbol]
                av.cache.set_overview(symbol, known["sector"], "", known["name"])
                overview = {"sector": known["sector"], "name": known["name"]}

            # ③ 그래도 없으면 AV API 호출 (rate limit 적용)
            if not overview:
                elapsed = time.time() - last_api_call
                if elapsed < _AV_RATE_LIMIT_SEC:
                    wait = _AV_RATE_LIMIT_SEC - elapsed
                    notify(f"AV API 한도 대기 중... ({wait:.0f}초)")
                    time.sleep(wait)
                overview = av.fetch_overview(symbol)
                last_api_call = time.time()

            av_sector = overview.get("sector", "") if overview else ""
            cat  = us_sector_map.get(av_sector, "US 기타")
            name = overview.get("name", symbol) if overview else symbol

            categories.setdefault(cat, [])
            if not any(e["code"] == symbol for e in categories[cat]):
                categories[cat].append({"code": symbol, "name": name, "market": "US"})

        notify(f"US 카테고리 빌드 완료: {len(watchlist)}개 종목")
    except Exception as e:
        logger.error(f"US 카테고리 빌드 실패: {e}")

    _save_cache(categories)
    return categories


def add_stock(categories: dict, category: str, code: str, name: str, market: str) -> dict:
    """종목 추가 후 원본 파일과 캐시를 갱신한다."""
    categories.setdefault(category, [])
    if any(e["code"] == code for e in categories[category]):
        return categories

    categories[category].append({"code": code, "name": name, "market": market})

    if market == "KR":
        _update_kr_map(category, code)
    else:
        _update_us_watchlist(code)

    _save_cache(categories)
    return categories


# ── 내부 헬퍼 ──────────────────────────────────────────────────────────────

def _is_cache_valid() -> bool:
    if not CACHE_PATH.exists():
        return False
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        built_at = datetime.fromisoformat(data.get("built_at", "2000-01-01"))
        return datetime.now() - built_at < timedelta(hours=CACHE_TTL_HOURS)
    except Exception:
        return False


def _save_cache(categories: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"built_at": datetime.now().isoformat(), "categories": categories},
            f, ensure_ascii=False, indent=2,
        )


def _update_kr_map(category: str, code: str):
    try:
        with open(KR_MAP_PATH, "r", encoding="utf-8") as f:
            kr_map = json.load(f)
        kr_map.setdefault(category, [])
        if code not in kr_map[category]:
            kr_map[category].append(code)
        with open(KR_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump(kr_map, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"category_map.json 업데이트 실패: {e}")


def _update_us_watchlist(symbol: str):
    try:
        with open(US_LIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if symbol not in data["watchlist"]:
            data["watchlist"].append(symbol)
        with open(US_LIST_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"us_watchlist.json 업데이트 실패: {e}")
