import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.logger import logger

CACHE_PATH = Path.home() / ".inz_stock_advisor" / "data" / "category_cache.json"
CACHE_TTL_HOURS = 24

KR_MAP_PATH  = Path("src/data/category_map.json")
US_LIST_PATH = Path("src/data/us_watchlist.json")
RULES_PATH   = Path("src/data/sector_rules.json")

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
