# -*- coding: utf-8 -*-
"""
일본 소스 수집기 (2026-09 기준)
- NHK: 공식 RSS 그대로 사용 (가장 안정적)
- Yahoo!ニュース: news.yahoo.co.jp/ranking/access/news 는 살아있으나 클래스명이 자주 바뀜
  → 기사 링크는 항상 news.yahoo.co.jp/articles/{id} 형태이므로 URL 패턴으로 추출 (구조변경에 강함)
  실패 시 화면 캡쳐 + OCR로 폴백
"""

import re
import requests
from bs4 import BeautifulSoup
from .base import Article, fetch_rss
from .kr_sources import fetch_by_ocr  # OCR 로직 재사용

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CardNewsBot/1.0)"}
YAHOO_ARTICLE_RE = re.compile(r"^https://news\.yahoo\.co\.jp/articles/[a-zA-Z0-9]+")


def fetch_nhk() -> list:
    return fetch_rss("https://www.nhk.or.jp/rss/news/cat0.xml", "NHK NEWS WEB", "JP")


def fetch_yahoo_japan_ranking(limit: int = 15) -> list:
    url = "https://news.yahoo.co.jp/ranking/access/news"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        articles = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if YAHOO_ARTICLE_RE.match(href) and href not in seen:
                title = a.get_text(strip=True)
                if len(title) < 6:
                    continue
                seen.add(href)
                articles.append(Article(
                    country="JP", source="Yahoo!ニュース", title=title, url=href,
                    popularity=max(0.0, 1.0 - len(articles) / max(limit, 1)), collected_via="scrape",
                ))
            if len(articles) >= limit:
                break
        if not articles:
            raise ValueError("기사 링크를 찾지 못함 → OCR 폴백")
        return articles
    except Exception:
        return fetch_by_ocr("Yahoo!ニュース", url, limit)


def collect_all() -> list:
    articles = []
    try:
        articles += fetch_nhk()
    except Exception as e:
        print(f"[JP][NHK] 수집 실패: {e}")
    try:
        articles += fetch_yahoo_japan_ranking()
    except Exception as e:
        print(f"[JP][Yahoo] 수집 실패: {e}")
    return articles
