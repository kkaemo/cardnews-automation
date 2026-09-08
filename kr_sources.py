# -*- coding: utf-8 -*-
"""
한국 소스 수집기 (2026-09 기준 실제 구조 반영)

- 네이버: 2020년 10월 사이트 전체 '많이 본 뉴스' 랭킹이 공식 폐지되어 더 이상 스크래핑 대상이 없음.
  → 네이버 공식 오픈API(개발자센터 발급, 무료, 1일 25,000회)로 대체.
    발급: https://developers.naver.com/apps/#/register (검색 API 사용 설정)
- 다음: news.daum.net(메인)에 '이 시각 주요뉴스' + '실시간 트렌드'가 살아있음.
  다음 CSS 클래스명은 자주 바뀌므로, 클래스가 아니라 실제 기사/검색 링크의 URL 패턴으로
  잡는 방식을 씀 (v.daum.net/v/... , search.daum.net/search?...DA=TRW...) → 구조 변경에 훨씬 강함.
- 웰로/나우히츠: 검색으로도 정확한 서비스를 특정하지 못했음. URL만 config.py에 채워 넣으면
  바로 동작하도록 범용 스크래�atch+OCR 폴백 함수로 구현해둠 (URL 확인되면 바로 사용 가능).
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from .base import Article, fetch_rss

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CardNewsBot/1.0)"}


# ── 네이버: 공식 오픈API (뉴스 검색) ──────────────────────────
# 트렌딩 랭킹 자체는 폐지되어 없으므로, 선호 카테고리 키워드로 최신순 검색해
# "지금 올라온 기사 후보군"을 모으고, 이후 LLM 스코어링(scorer.py)에서 Top5를 가린다.
NAVER_SEED_QUERIES = ["경제", "건강", "날씨", "문화", "스포츠", "정책 혜택", "생활 꿀팁"]


def fetch_naver_news(limit_per_query: int = 8) -> list:
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET 없음 (developers.naver.com 무료 발급)")

    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    articles = []
    for q in NAVER_SEED_QUERIES:
        res = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers=headers,
            params={"query": q, "display": limit_per_query, "sort": "date"},
            timeout=10,
        )
        res.raise_for_status()
        items = res.json().get("items", [])
        for i, it in enumerate(items):
            title = re.sub("<.*?>", "", it.get("title", ""))  # <b> 태그 제거
            desc = re.sub("<.*?>", "", it.get("description", ""))
            articles.append(Article(
                country="KR", source="네이버뉴스", title=title, url=it.get("link", ""),
                summary=desc, popularity=max(0.0, 1.0 - i / max(limit_per_query, 1)),
                category_hint=q, collected_via="api",
            ))
    return articles


# ── 다음: URL 패턴 기반 스크래핑 (클래스명 대신 실제 링크 패턴 사용) ──
DAUM_ARTICLE_RE = re.compile(r"^https://v\.daum\.net/v/\d+")
DAUM_TREND_RE = re.compile(r"^https://search\.daum\.net/search\?.*DA=TRW")


def fetch_daum_news(limit: int = 15) -> list:
    url = "https://news.daum.net/"
    res = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    articles = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if DAUM_ARTICLE_RE.match(href) and href not in seen:
            title = a.get_text(strip=True)
            if len(title) < 8:   # 썸네일 등 텍스트 없는 링크 제외
                continue
            seen.add(href)
            articles.append(Article(
                country="KR", source="다음뉴스", title=title, url=href,
                popularity=max(0.0, 1.0 - len(articles) / max(limit, 1)), collected_via="scrape",
            ))
        if len(articles) >= limit:
            break

    # 실시간 트렌드 키워드도 보조 신호로 수집 (인기도 가중치만 살짝 부여, 기사 본문은 아님)
    trend_keywords = []
    for a in soup.find_all("a", href=True):
        if DAUM_TREND_RE.match(a["href"]):
            kw = a.get_text(strip=True)
            if kw:
                trend_keywords.append(kw)
    for art in articles:
        if any(kw and kw in art.title for kw in trend_keywords):
            art.popularity = min(1.0, art.popularity + 0.15)

    return articles


# ── 웰로/나우히츠: URL 미확정 → 범용 스크래핑+OCR 폴백 함수 ─────
# ── 웰로: 공식 RSS 제공 (커뮤니티 트렌드 인사이트, 3시간마다 업데이트) ──
def fetch_weilo(limit: int = 20) -> list:
    """
    weilo.co.kr/rss 실제 확인 결과 - 뽐뿌/디시/엠팍/보배 등 커뮤니티 인기글을
    3시간마다 집계하는 공식 RSS를 제공함. 가장 안정적인 방식이라 스크래핑 없이 그대로 사용.
    title이 "[디시] 제목" 형식이라 앞의 [커뮤니티명]을 source로 분리해서 기록.
    """
    articles = fetch_rss("https://weilo.co.kr/rss", "웰로", "KR", limit=limit)
    tag_re = re.compile(r"^\[(.+?)\]\s*(.*)")
    for a in articles:
        m = tag_re.match(a.title)
        if m:
            a.source = f"웰로·{m.group(1)}"
            a.title = m.group(2)
    return articles


# ── 나우히츠: RSS 없음, 서버 렌더링 HTML 확인됨 → 스크래핑, 실패 시 OCR 폴백 ──
def fetch_nowhitz(limit: int = 12) -> list:
    """
    nowhitz.com 실제 확인 결과 - RSS는 없지만 '실시간 검색어 순위' 섹션이 서버에서
    완성된 HTML로 내려옴 (headless 브라우저 없이도 requests로 읽힘).
    각 항목 하단의 원문 출처(SOURCE 링크, 예: yna.co.kr)를 기사 URL로 사용.
    사이트 개편으로 이 셀렉터가 깨지면 자동으로 OCR 폴백.
    """
    url = "https://nowhitz.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        articles = []
        # '실시간 검색어 순위' 항목들은 순번(01,02..) 뒤에 제목이 오고, 그 다음 SOURCE 링크가 붙는 구조
        candidates = soup.find_all(["li", "div", "article"])
        for el in candidates:
            text = el.get_text(" ", strip=True)
            if not text or "WHY!" not in text:
                continue
            # 첫 줄(순번+제목) 추출: 'WHY!' 이전 텍스트를 제목 후보로
            title_part = text.split("WHY!")[0].strip()
            title_part = re.sub(r"^\d{1,2}\s*", "", title_part).strip()
            if len(title_part) < 6 or len(title_part) > 60:
                continue
            source_link = el.find("a", href=True, string=re.compile("SOURCE"))
            link = source_link["href"] if source_link else url
            articles.append(Article(
                country="KR", source="나우히츠", title=title_part, url=link,
                popularity=max(0.0, 1.0 - len(articles) / max(limit, 1)), collected_via="scrape",
            ))
            if len(articles) >= limit:
                break
        if not articles:
            raise ValueError("항목을 찾지 못함 → OCR 폴백")
        return articles
    except Exception:
        return fetch_by_ocr("나우히츠", url, limit)


def fetch_generic_ranking_or_ocr(name: str, url: str, list_selector: str = None, limit: int = 10) -> list:
    """
    list_selector를 알면 1차로 CSS 선택자 스크래핑을 시도하고,
    실패(또는 selector 미지정)하면 화면 캡쳐 → OCR로 폴백한다.
    config.py에서 이 소스의 실제 url을 채운 뒤 사용하면 됨.
    """
    if not url:
        print(f"[KR][{name}] URL 미설정 — config.py에 실제 서비스 URL을 채워주세요. 건너뜁니다.")
        return []
    try:
        if not list_selector:
            raise ValueError("셀렉터 미지정 → OCR 폴백")
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(list_selector)
        if not items:
            raise ValueError("셀렉터로 항목을 찾지 못함 → OCR 폴백")
        articles = []
        for i, el in enumerate(items[:limit]):
            articles.append(Article(
                country="KR", source=name, title=el.get_text(strip=True), url=url,
                popularity=max(0.0, 1.0 - i / max(limit, 1)), collected_via="scrape",
            ))
        return articles
    except Exception:
        return fetch_by_ocr(name, url, limit)


def fetch_by_ocr(name: str, url: str, limit: int = 10) -> list:
    """Playwright로 화면 캡쳐 → pytesseract OCR로 사람이 보는 것처럼 제목 텍스트 추출."""
    from playwright.sync_api import sync_playwright
    import pytesseract
    from PIL import Image
    import io

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 2000})
        page.goto(url, timeout=15000)
        page.wait_for_timeout(2000)
        screenshot_bytes = page.screenshot(full_page=True)
        browser.close()

    img = Image.open(io.BytesIO(screenshot_bytes))
    text = pytesseract.image_to_string(img, lang="kor+eng")
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 8]

    return [
        Article(country="KR", source=f"{name}(OCR)", title=line, url=url,
                popularity=max(0.0, 1.0 - i / max(limit, 1)), collected_via="ocr")
        for i, line in enumerate(lines[:limit])
    ]


def collect_all() -> list:
    all_articles = []

    try:
        all_articles += fetch_naver_news()
    except Exception as e:
        print(f"[KR][네이버뉴스] 수집 실패: {e}")

    try:
        all_articles += fetch_daum_news()
    except Exception as e:
        print(f"[KR][다음뉴스] 수집 실패: {e}")

    try:
        all_articles += fetch_weilo()
    except Exception as e:
        print(f"[KR][웰로] 수집 실패: {e}")

    try:
        all_articles += fetch_nowhitz()
    except Exception as e:
        print(f"[KR][나우히츠] 수집 실패: {e}")

    return all_articles
