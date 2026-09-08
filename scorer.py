# -*- coding: utf-8 -*-
"""수집된 기사들 중 국가별 Top N 선정"""

from config import CATEGORY_WEIGHTS, TOP_N_PER_COUNTRY


def score_article(article, category: str = "") -> float:
    weight = CATEGORY_WEIGHTS.get(category, 1.0)
    return article.popularity * weight


def select_top_n(articles: list, country: str, top_n: int = TOP_N_PER_COUNTRY,
                  category_map: dict = None) -> list:
    """
    category_map: {article.title: category} 형태로 LLM이 사전 분류한 결과를 넘기면 가중치 반영.
    없으면 popularity 순으로만 정렬.
    """
    category_map = category_map or {}
    country_articles = [a for a in articles if a.country == country]
    for a in country_articles:
        cat = category_map.get(a.title, "")
        a.category_hint = cat
    ranked = sorted(country_articles, key=lambda a: score_article(a, a.category_hint), reverse=True)

    # 중복 제목(유사) 제거 - 간단한 부분일치 기준
    unique = []
    seen_titles = []
    for a in ranked:
        if any(a.title[:12] == t[:12] for t in seen_titles):
            continue
        unique.append(a)
        seen_titles.append(a.title)
        if len(unique) >= top_n:
            break
    return unique
