# -*- coding: utf-8 -*-
"""
통합 실행 진입점. 이 파일 하나만 실행하면 KR/JP/US 전체가 돈다.
    python3 main.py

흐름: 수집 -> 카테고리/인물판별 -> Top5 선정 -> LLM 콘텐츠생성(+번역) -> 이미지생성 -> 후처리 -> 리뷰 대시보드
스케줄 자동화: GitHub Actions에서 이 스크립트를 매일 08:00 KST(=전날 23:00 UTC)에 cron 실행 → 결과물을 Actions
아티팩트 또는 Google Drive 업로드로 보내는 방식이 가장 관리가 쉬움 (서버 상시 운영 불필요).
"""

import os
import time
import uuid
from datetime import datetime

from collectors import kr_sources, jp_sources, us_sources
from scorer import select_top_n
from llm import classify_and_check_person, generate_card_content
import imagegen
import postprocess
from review_html import build_dashboard
from config import OUTPUT_DIR

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 국가별로 LLM 분류에 넘길 기사 수 상한 (무료 API 과부하 방지). 이 안에서 인기도 상위만 남김.
MAX_ARTICLES_FOR_CLASSIFY = 25
LLM_CALL_INTERVAL_SEC = 1.5  # 호출 사이 최소 간격 (과부하 방지)


def process_country(country: str, raw_articles: list) -> list:
    # 소스가 많을 때(특히 한국) 전부 LLM에 태우면 무료 API가 금방 과부하되므로
    # 인기도(popularity) 상위 N개만 추려서 분류에 태움
    raw_articles = sorted(raw_articles, key=lambda a: a.popularity, reverse=True)[:MAX_ARTICLES_FOR_CLASSIFY]
    print(f"[{country}] 수집 {len(raw_articles)}건 → 분류 대상으로 축소")

    category_map = {}
    filtered = []
    for a in raw_articles:
        try:
            info = classify_and_check_person(a.title, country)
        except Exception as e:
            print(f"[{country}] 분류 실패({a.title[:20]}...): {e}")
            time.sleep(LLM_CALL_INTERVAL_SEC)
            continue
        category_map[a.title] = info["category"]
        # 인물 직접 묘사가 필요한데 상징적 대안도 없으면 제외
        if info["requires_real_person_depiction"] and not info.get("symbolic_image_idea"):
            time.sleep(LLM_CALL_INTERVAL_SEC)
            continue
        a._image_hint = info.get("symbolic_image_idea", "")
        filtered.append(a)
        time.sleep(LLM_CALL_INTERVAL_SEC)

    top5 = select_top_n(filtered, country, category_map=category_map)
    print(f"[{country}] 분류 통과 {len(filtered)}건 → Top{len(top5)} 선정")

    cards = []
    for a in top5:
        try:
            content = generate_card_content(a.title, a.summary or a._image_hint, country)
            time.sleep(LLM_CALL_INTERVAL_SEC)
            prompt = content["image_prompt"]
            bg = imagegen.generate_image(prompt)
            final_img = postprocess.build_card(
                bg, content["headline"], content.get("headline_highlight_words", [])
            )
            card_id = str(uuid.uuid4())[:8]
            img_path = os.path.join(OUTPUT_DIR, f"{country}_{card_id}.png")
            final_img.save(img_path)

            cards.append({
                "id": card_id, "country": country, "source": a.source, "image_path": img_path,
                "headline_display": content["headline"].replace("\n", "<br>"),
                "caption": content["caption"], "alt_text": content["alt_text"],
                "hashtag": content["hashtag"],
                "translation_ko": content.get("translation_ko"),
            })
        except Exception as e:
            print(f"[{country}] 카드 생성 실패({a.title[:20]}...): {e}")
    return cards


def main():
    all_cards = []

    print("== 한국 수집 ==")
    all_cards += process_country("KR", kr_sources.collect_all())

    print("== 일본 수집 ==")
    all_cards += process_country("JP", jp_sources.collect_all())

    print("== 미국 수집 ==")
    all_cards += process_country("US", us_sources.collect_all())

    date_str = datetime.now().strftime("%Y-%m-%d")
    path = build_dashboard(all_cards, date_str)
    print(f"\n완료! 리뷰 대시보드: {path}")
    print("브라우저로 열어서 카드별 체크박스로 업로드할 것만 선택하고, 비고(번역본)로 톤 확인 후 이미지 다운로드+본문 복사하면 됩니다.")


if __name__ == "__main__":
    main()
