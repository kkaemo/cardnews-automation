# -*- coding: utf-8 -*-
"""
카드뉴스 자동화 통합 설정
- 국가 3개(KR/JP/US)를 이 파일 하나로 관리
- 소스 추가/제거는 SOURCES 딕셔너리만 수정하면 됨 (프로그램 하나로 통합 관리)
"""

import os

# ── 이미지 스펙 ──────────────────────────────────────────────
IMG_WIDTH = 1080
IMG_HEIGHT = 1440
GRADIENT_HEIGHT_RATIO = 0.5      # 하단 50%에 그라데이션
TITLE_LEFT_MARGIN_RATIO = 0.10   # 좌측 여백 10%
TITLE_MAX_LINES = 3
TITLE_MIN_LINES = 2
HIGHLIGHT_COLOR = "#C5D805"
BASE_TEXT_COLOR = "#F8F8FF"      # Ghost White
FONT_BOLD_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Pretendard-Bold.otf")

# ── 국가별 소스 정의 ─────────────────────────────────────────
# type: "rss" | "scrape" | "api" | "ocr_fallback"
SOURCES = {
    "KR": [
        {"name": "웰로", "type": "rss", "url": "https://weilo.co.kr/rss",
         "note": "실제 확인됨 - 뽐뿌/디시/엠팍/보배 등 커뮤니티 인기글 공식 RSS, 3시간마다 업데이트"},
        {"name": "나우히츠", "type": "scrape", "url": "https://nowhitz.com",
         "note": "실제 확인됨 - RSS는 없지만 서버 렌더링 HTML로 '실시간 검색어 순위' 제공, 실패 시 OCR 폴백"},
        {"name": "네이버뉴스", "type": "api", "url": "https://openapi.naver.com/v1/search/news.json",
         "note": "2020년 전체 랭킹 폐지 → 공식 오픈API(무료, 1일 25,000회)로 대체. developers.naver.com에서 발급"},
        {"name": "다음뉴스", "type": "scrape", "url": "https://news.daum.net/", "note": "URL 패턴 기반 스크래핑(클래스명 대신 v.daum.net/v/ 패턴 사용, 구조변경에 강함)"},
    ],
    "JP": [
        {"name": "Yahoo!ニュース", "type": "scrape", "url": "https://news.yahoo.co.jp/ranking/access/news",
         "note": "URL 패턴 기반 스크래핑(news.yahoo.co.jp/articles/ 패턴). 실패 시 OCR 폴백"},
        {"name": "NHK NEWS WEB", "type": "rss", "url": "https://www.nhk.or.jp/rss/news/cat0.xml", "note": "공식 RSS 제공"},
    ],
    "US": [
        {"name": "Google News Trends", "type": "rss", "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en", "note": "공식 RSS"},
        {"name": "BuzzFeed News", "type": "rss", "url": "https://www.buzzfeednews.com/rss.xml", "note": "공식 RSS(폐지 여부 확인 필요)"},
        {"name": "Vox", "type": "rss", "url": "https://www.vox.com/rss/index.xml", "note": "공식 RSS"},
        {"name": "Reddit r/news", "type": "api", "url": "https://oauth.reddit.com/r/news/hot", "note": "Reddit 공식 API(OAuth 필요)"},
        {"name": "Reddit r/worldnews", "type": "api", "url": "https://oauth.reddit.com/r/worldnews/hot", "note": "Reddit 공식 API(OAuth 필요)"},
    ],
}

# ── 선호 카테고리 가중치 (스코어링에 사용) ───────────────────
CATEGORY_WEIGHTS = {
    "경제": 1.3, "건강": 1.3, "날씨": 1.2, "문화": 1.2, "운동": 1.2,
    "스포츠": 1.2, "예술": 1.2, "정책/혜택/제도": 1.4,
    "연예": 1.0, "정치": 1.0,  # 인물 직접 묘사 불가 시에만 포함
}

TOP_N_PER_COUNTRY = 5

# ── 국가별 SNS 톤 가이드 (LLM 시스템 프롬프트에 삽입) ─────────
TONE_GUIDE = {
    "KR": "한국 인스타 카드뉴스 톤. 짧고 임팩트있게, 궁금증 유발형 헤드라인, 이모지 최소화, 반말/구어체 혼용 가능.",
    "JP": "日本のSNSでよく使われる自然な口語表現。「〜って知ってる?」「〜らしい」等の親近感のある文体。",
    "US": "Gen-Z Instagram tone, punchy hooks, casual conversational English, avoid stiff journalistic phrasing.",
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# ── 무료 LLM 프로바이더 폴백 순서 ──────────────────────────────
# 앞에서부터 시도하다가 한도초과/오류 나면 자동으로 다음으로 전환.
# 순서만 바꾸거나 항목을 빼면 됨 (예: ["gemini","groq"] 로 순서 변경 가능)
# 각 프로바이더의 키는 .env 에서 GROQ_API_KEYS / GEMINI_API_KEYS / HF_API_KEYS 로 설정
# (콤마로 여러 개 넣으면 같은 프로바이더 안에서도 키를 돌려씀)
PROVIDER_ORDER = ["groq", "gemini", "huggingface"]
