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
from .base import Article, fetch_rss

GOOGLE_TRENDS_RSS_US = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"


def fetch_google_trends_us(limit: int = 20) -> list:
    articles = fetch_rss(GOOGLE_TRENDS_RSS_US, "Google Trends", "US", limit=limit)
    if not articles:
        raise RuntimeError("구글 트렌드 RSS에서 항목을 하나도 못 가져옴 (주소가 바뀌었거나 일시 차단 가능성)")
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
