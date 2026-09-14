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
TITLE_LEFT_MARGIN_RATIO = 0.05   # 좌측 여백 5% (기존 10%에서 절반으로 축소, 우측도 동일)
TITLE_MAX_LINES = 3
TITLE_MIN_LINES = 2
BASE_TEXT_COLOR = "#F8F8FF"      # Ghost White - 이제 강조색 없이 전부 이 색 하나로 통일

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
# 국가별 폰트: 프리텐다드는 일본어 한자(漢字) 글리프가 없어 일본 카드 제목이 깨지는 문제가 있었음
# → 일본은 한자 커버리지가 넓은 Noto Sans JP 사용. 한국/미국은 프리텐다드 그대로.
FONT_PATHS = {
    "KR": os.path.join(FONTS_DIR, "Pretendard-Bold.otf"),
    "US": os.path.join(FONTS_DIR, "Pretendard-Bold.otf"),
    "JP": os.path.join(FONTS_DIR, "NotoSansJP-Bold.otf"),
}
# Noto Sans JP는 가변폰트(Variable Font)라서 굵기(Weight)를 명시적으로 지정해야 Bold로 보임
FONT_VARIATION = {
    os.path.join(FONTS_DIR, "NotoSansJP-Bold.otf"): 700,
}
FONT_BOLD_PATH = FONT_PATHS["KR"]  # 하위 호환용 (기존에 이 이름을 참조하는 코드 대비)

# ── 국가별 소스 정의 (요청 수 절감을 위해 국가당 메인 소스 1개로 축소) ──
# type: "rss" | "scrape" | "api" | "ocr_fallback"
SOURCES = {
    "KR": [
        {"name": "웰로", "type": "rss", "url": "https://weilo.co.kr/rss",
         "note": "커뮤니티 인기글 공식 RSS, 3시간마다 업데이트. 한국 메인 소스로 단일화"},
    ],
    "JP": [
        {"name": "Yahoo!ニュース", "type": "scrape", "url": "https://news.yahoo.co.jp/ranking/access/news",
         "note": "URL 패턴 기반 스크래핑. 일본 메인 소스로 단일화. 실패 시 OCR 폴백"},
    ],
    "US": [
        {"name": "Google Trends", "type": "rss", "url": "https://trends.google.com/trending/rss?geo=US",
         "note": "미국 메인 소스. 키/가입 불필요한 공개 RSS. (레딧은 OAuth 앱 등록이 필요해 기본에서 제외, 코드는 남겨둠)"},
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
# 반말 금지, 이모지 사용 금지(폰트가 컬러 이모지를 지원하지 않아 카드 이미지에서 깨짐), 매거진 톤
TONE_GUIDE = {
    "KR": "정돈된 매거진 톤. 반말 금지(합쇼체/해요체 등 격식 있는 문장으로 작성). 이모지 사용 금지. 궁금증을 유발하되 신뢰감 있는 문장.",
    "JP": "整った雑誌のような文体。タメ口(カジュアルすぎる口語)は禁止、丁寧語で作成。絵文字は使用しない。",
    "US": "Clean, editorial magazine tone (like a digital lifestyle magazine). No emoji. No slang-heavy Gen-Z tone. Professional but engaging.",
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# ── 무료 LLM 프로바이더 폴백 순서 ──────────────────────────────
# Groq는 로그인 문제로 제외. 제미나이 실패 시 HuggingFace로 전환.
# 각 프로바이더의 키는 GitHub Secrets에서 GEMINI_API_KEYS / HF_API_KEYS 로 설정
# (콤마로 여러 개 넣으면 같은 프로바이더 안에서도 키를 돌려씀)
PROVIDER_ORDER = ["gemini", "huggingface"]
