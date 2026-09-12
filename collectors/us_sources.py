# -*- coding: utf-8 -*-
"""미국 소스: Reddit(공식 API) 단일 소스로 단일화 (요청 수 절감)"""

import os
import requests
from .base import Article


def _reddit_oauth_token() -> str:
    """GitHub Secrets 또는 .env에 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET 필요 (무료 발급)."""
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
    # 요청 수 절감을 위해 미국은 Reddit(r/news, r/worldnews) 단일 소스만 사용
    articles = []
    for sub in ["news", "worldnews"]:
        try:
            articles += fetch_reddit(sub)
        except Exception as e:
            print(f"[US][Reddit r/{sub}] 수집 실패: {e}")
    return articles
