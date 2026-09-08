# -*- coding: utf-8 -*-
"""
통합 실행 진입점. 이 파일 하나만 실행하면 KR/JP/US 전체가 돈다.
    python3 main.py

흐름: 수집 -> 카테고리/인물판별 -> Top5 선정 -> LLM 콘텐츠생성(+번역) -> 이미지생성 -> 후처리 -> 리뷰 대시보드
스케줄 자동화: GitHub Actions에서 이 스크립트를 매일 08:00 KST(=전날 23:00 UTC)에 cron 실행 → 결과물을 Actions
아티팩트 또는 Google Drive 업로드로 보내는 방식이 가장 관리가 쉬움 (서버 상시 운영 불필요).
"""

import os
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


def process_country(country: str, raw_articles: list) -> list:
    category_map = {}
    filtered = []
    for a in raw_articles:
        try:
            info = classify_and_check_person(a.title, country)
        except Exception as e:
            print(f"[{country}] 분류 실패({a.title[:20]}...): {e}")
            continue
        category_map[a.title] = info["category"]
        # 인물 직접 묘사가 필요한데 상징적 대안도 없으면 제외
        if info["requires_real_person_depiction"] and not info.get("symbolic_image_idea"):
            continue
        a._image_hint = info.get("symbolic_image_idea", "")
        filtered.append(a)

    top5 = select_top_n(filtered, country, category_map=category_map)

    cards = []
    for a in top5:
        try:
            content = generate_card_content(a.title, a.summary or a._image_hint, country)
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
