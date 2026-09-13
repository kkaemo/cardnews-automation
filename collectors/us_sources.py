# -*- coding: utf-8 -*-
"""
미국 소스: 구글 트렌드 공개 RSS (기본, 키/가입 불필요)
- https://trends.google.com/trends/trendingsearches/daily/rss?geo=US
- 공식 "Daily Trends API" 상품 자체는 단종됐지만, 이 RSS 주소는 별개로 지금도 살아있음(2026-09 확인).
- 나중에 이 주소마저 막히면 collect_all()에서 fetch_reddit()로 교체 가능 (OAuth 앱 등록 필요,
  코드는 남겨뒀지만 기본값으로는 쓰지 않음 - 가입/토큰 설정 없이 쓰기 위한 선택).
"""

import os
import requests
import feedparser
from .base import Article

GOOGLE_TRENDS_RSS_US = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def fetch_google_trends_us(limit: int = 20) -> list:
    # feedparser가 자체적으로 요청을 보내면 기본 User-Agent 때문에 구글에게 차단당할 수 있어,
    # requests로 브라우저처럼 직접 가져온 뒤 그 내용을 feedparser에 넘김 (원인 진단 가능하게)
    res = requests.get(GOOGLE_TRENDS_RSS_US, headers=BROWSER_HEADERS, timeout=15)
    print(f"[US][Google Trends] HTTP 상태코드: {res.status_code}, 응답 길이: {len(res.content)} bytes")
    if res.status_code != 200:
        print(f"[US][Google Trends] 응답 본문 미리보기: {res.text[:300]}")
        raise RuntimeError(f"구글 트렌드 RSS 요청 실패 (status={res.status_code})")

    feed = feedparser.parse(res.content)
    if not feed.entries:
        print(f"[US][Google Trends] 응답 본문 미리보기(항목 0개): {res.text[:300]}")
        raise RuntimeError("구글 트렌드 RSS 응답은 받았지만 항목이 0개 (구조가 바뀌었을 가능성)")

    articles = []
    for i, entry in enumerate(feed.entries[:limit]):
        articles.append(Article(
            country="US", source="Google Trends",
            title=getattr(entry, "title", ""), url=getattr(entry, "link", ""),
            summary=getattr(entry, "summary", "")[:500],
            popularity=max(0.0, 1.0 - i / max(limit, 1)), collected_via="rss",
        ))
    return articles


# ── Reddit (선택사항 - 기본으로는 쓰지 않음, OAuth 앱 등록 필요) ──
def _reddit_oauth_token() -> str:
    client_id = os.environ["REDDIT_CLIENT_ID"]
    client_secret = os.environ["REDDIT_CLIENT_SECRET"]
    auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
    data = {"grant_type": "client_credentials"}
    headers = {"User-Agent": "CardNewsBot/1.0"}
    res = requests.post("https://www.reddit.com/api/v1/access_token",
                         auth=auth, data=data, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()["access_token"]


def fetch_reddit(subreddit: str, limit: int = 15) -> list:
    token = _reddit_oauth_token()
    headers = {"Authorization": f"bearer {token}", "User-Agent": "CardNewsBot/1.0"}
    res = requests.get(f"https://oauth.reddit.com/r/{subreddit}/hot", headers=headers,
                        params={"limit": limit}, timeout=10)
    res.raise_for_status()
    posts = res.json()["data"]["children"]
    articles = []
    max_score = max([p["data"]["score"] for p in posts], default=1) or 1
    for p in posts:
        d = p["data"]
        articles.append(Article(
            country="US", source=f"Reddit r/{subreddit}",
            title=d.get("title", ""), url="https://reddit.com" + d.get("permalink", ""),
            popularity=d.get("score", 0) / max_score, collected_via="api",
        ))
    return articles


def collect_all() -> list:
    # 기본: 구글 트렌드 RSS (가입/키 불필요)
    try:
        return fetch_google_trends_us()
    except Exception as e:
        print(f"[US][Google Trends] 수집 실패: {e}")
        return []
