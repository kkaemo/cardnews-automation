# -*- coding: utf-8 -*-
"""
통합 실행 진입점. 이 파일 하나만 실행하면 KR/JP/US 전체가 돈다.
    python3 main.py

흐름: 수집 -> 카테고리/인물판별 -> Top5 선정 -> LLM 콘텐츠생성(+번역) -> 이미지생성 -> 후처리 -> 리뷰 대시보드
스케줄 자동화: GitHub Actions에서 이 스크립트를 매일 08:00 KST(=전날 23:00 UTC)에 cron 실행 → 결과물을 Actions
아티팩트 또는 Google Drive 업로드로 보내는 방식이 가장 관리가 쉬움 (서버 상시 운영 불필요).
"""

# 코드 버전 마커: 로그 맨 위에 이 값이 찍히므로, GitHub에 올린 파일이 최신인지
# "느낌"이 아니라 로그로 바로 확인 가능함. 파일을 수정할 때마다 이 값을 바꿀 것.
CODE_VERSION = "2026-09-12-v9"

import os
import sys
import time
import uuid
import traceback
from datetime import datetime

from collectors import kr_sources, jp_sources, us_sources
from scorer import select_top_n
from llm import classify_batch, classify_and_check_person, generate_card_content
import imagegen
import postprocess
from review_html import build_dashboard
from config import OUTPUT_DIR

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 국가별로 LLM에 넘길 기사 수 상한 (무료 API 호출 한도 절약). 인기도 상위만 남김.
# 국가당 메인 소스 1개로 줄였으므로 후보 수도 최소화 -> 분류는 국가당 1번의 배치 호출로 끝남
MAX_ARTICLES_FOR_CLASSIFY = 12
CLASSIFY_BATCH_SIZE = 12     # 이 수만큼 묶어서 한 번의 LLM 호출로 분류 (국가당 배치 호출 1회)
LLM_CALL_INTERVAL_SEC = 3    # 호출 사이 최소 간격 (과부하 방지)


def process_country(country: str, raw_articles: list) -> tuple:
    """반환: (cards, stats) - stats는 이번 실행에서 어디까지 성공/실패했는지 요약"""
    stats = {"수집": len(raw_articles), "분류통과": 0, "카드생성": 0, "카드생성실패": 0}

    raw_articles = sorted(raw_articles, key=lambda a: a.popularity, reverse=True)[:MAX_ARTICLES_FOR_CLASSIFY]
    print(f"[{country}] 수집 {stats['수집']}건 → 상위 {len(raw_articles)}건을 분류 대상으로 축소")

    category_map = {}
    filtered = []
    for i in range(0, len(raw_articles), CLASSIFY_BATCH_SIZE):
        batch = raw_articles[i:i + CLASSIFY_BATCH_SIZE]
        try:
            results = classify_batch([a.title for a in batch], country)
        except Exception as e:
            print(f"[{country}] 배치 분류 실패({i}~{i+len(batch)}): {e}")
            results = []
        time.sleep(LLM_CALL_INTERVAL_SEC)

        # 배치 호출이 통째로 실패했으면 이 배치만 개별 호출로 재시도 (드문 경우 대비 안전망)
        if not results:
            for a in batch:
                try:
                    info = classify_and_check_person(a.title, country)
                except Exception as e:
                    print(f"[{country}] 분류 실패({a.title[:20]}...): {e}")
                    time.sleep(LLM_CALL_INTERVAL_SEC)
                    continue
                _apply_classification(a, info, category_map, filtered)
                time.sleep(LLM_CALL_INTERVAL_SEC)
            continue

        for a, info in zip(batch, results):
            _apply_classification(a, info, category_map, filtered)

    top5 = select_top_n(filtered, country, category_map=category_map)
    stats["분류통과"] = len(filtered)
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
            stats["카드생성"] += 1
        except Exception as e:
            print(f"[{country}] 카드 생성 실패({a.title[:20]}...): {e}")
            print("  ↳ 상세 traceback:")
            traceback.print_exc()
            stats["카드생성실패"] += 1
    return cards, stats


def _apply_classification(article, info: dict, category_map: dict, filtered: list):
    category_map[article.title] = info.get("category", "")
    # 인물 직접 묘사가 필요한데 상징적 대안도 없으면 제외
    if info.get("requires_real_person_depiction") and not info.get("symbolic_image_idea"):
        return
    article._image_hint = info.get("symbolic_image_idea", "")
    filtered.append(article)


def main():
    print(f"===== 카드뉴스 자동화 실행 시작 (코드버전: {CODE_VERSION}) =====")

    all_cards = []
    all_stats = {}

    print("== 한국 수집 ==")
    cards, stats = process_country("KR", kr_sources.collect_all())
    all_cards += cards
    all_stats["KR"] = stats

    print("== 일본 수집 ==")
    cards, stats = process_country("JP", jp_sources.collect_all())
    all_cards += cards
    all_stats["JP"] = stats

    print("== 미국 수집 ==")
    cards, stats = process_country("US", us_sources.collect_all())
    all_cards += cards
    all_stats["US"] = stats

    date_str = datetime.now().strftime("%Y-%m-%d")
    path = build_dashboard(all_cards, date_str)

    print("\n===== 최종 결과 요약 =====")
    for country, s in all_stats.items():
        print(f"  {country}: 수집 {s['수집']}건 → 분류통과 {s['분류통과']}건 → "
              f"카드생성 {s['카드생성']}건 (실패 {s['카드생성실패']}건)")
    print(f"총 카드 수: {len(all_cards)}건")
    print(f"리뷰 대시보드: {path}")

    if len(all_cards) == 0:
        print("\n[실패] 카드가 한 장도 생성되지 않았습니다. 위 요약을 참고해 원인을 확인하세요.")
        sys.exit(1)  # 카드 0개면 GitHub Actions에도 Failure(빨간 X)로 표시되도록 명시적 실패 처리

    print("브라우저로 열어서 카드별 체크박스로 업로드할 것만 선택하고, 비고(번역본)로 톤 확인 후 이미지 다운로드+본문 복사하면 됩니다.")


if __name__ == "__main__":
    main()
