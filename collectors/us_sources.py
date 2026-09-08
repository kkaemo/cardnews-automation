# -*- coding: utf-8 -*-
"""미국 소스: Google News/BuzzFeed/Vox(RSS) + Reddit(공식 API)"""

import os
import requests
from .base import Article, fetch_rss


def fetch_google_news_us() -> list:
    return fetch_rss("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en", "Google News Trends", "US")


def fetch_buzzfeed() -> list:
    return fetch_rss("https://www.buzzfeednews.com/rss.xml", "BuzzFeed News", "US")


def fetch_vox() -> list:
    return fetch_rss("https://www.vox.com/rss/index.xml", "Vox", "US")


def _reddit_oauth_token() -> str:
    """.env 또는 환경변수에 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET 필요 (무료 발급)."""
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
    articles = []
    for fn, label in [(fetch_google_news_us, "Google News"), (fetch_buzzfeed, "BuzzFeed"), (fetch_vox, "Vox")]:
        try:
            articles += fn()
        except Exception as e:
            print(f"[US][{label}] 수집 실패: {e}")
    for sub in ["news", "worldnews"]:
        try:
            articles += fetch_reddit(sub)
        except Exception as e:
            print(f"[US][Reddit r/{sub}] 수집 실패: {e}")
    return articles
