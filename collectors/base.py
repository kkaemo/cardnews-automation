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
