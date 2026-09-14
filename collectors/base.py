# -*- coding: utf-8 -*-
"""모든 수집기가 공통으로 반환해야 하는 데이터 형식"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Article:
    country: str          # "KR" | "JP" | "US"
    source: str            # 소스명 (예: "네이버뉴스")
    title: str
    url: str
    summary: str = ""
    popularity: float = 0.0   # 조회수/업보트/랭킹 등을 0~1로 정규화한 값
    category_hint: str = ""   # 대략적 카테고리 (LLM이 재판별 가능)
    collected_via: str = "rss"  # "rss" | "scrape" | "api" | "ocr"


def fetch_article_body(url: str, max_chars: int = 1500) -> str:
    """
    기사 URL에서 본문 텍스트를 최대한 긁어온다 (JP/US처럼 요약이 빈약한 소스의 보강용).
    사이트마다 구조가 달라 완벽하지 않을 수 있음 - 실패하거나 내용이 너무 짧으면 빈 문자열 반환.
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; CardNewsBot/1.0)"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = " ".join(p for p in paragraphs if len(p) > 20)  # 너무 짧은(메뉴/카피라이트성) 문단 제외
        return text[:max_chars]
    except Exception as e:
        print(f"[본문보강] {url[:50]}... 실패: {e}")
        return ""


def fetch_rss(url: str, source_name: str, country: str, limit: int = 15) -> list:
    """RSS 피드 공통 파서. feedparser 필요 (requirements.txt 참고)."""
    import feedparser
    feed = feedparser.parse(url)
    articles = []
    for i, entry in enumerate(feed.entries[:limit]):
        articles.append(Article(
            country=country,
            source=source_name,
            title=getattr(entry, "title", ""),
            url=getattr(entry, "link", ""),
            summary=getattr(entry, "summary", "")[:500],
            popularity=max(0.0, 1.0 - i / max(limit, 1)),  # 피드 순서 기반 임시 점수
            collected_via="rss",
        ))
    return articles
