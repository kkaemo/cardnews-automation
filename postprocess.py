# -*- coding: utf-8 -*-
"""
카드뉴스 최종 합성
1) 배경 이미지를 1080x1440으로 리사이즈/크롭
2) 하단 50% 검정 그라데이션(최하단 진함 → 중앙으로 갈수록 옅어짐)
3) 좌우 대칭 여백(5%) 제목, 2~3줄 자동 크기 조정, 전부 고스트화이트 단일색(강조 없음)
   - 국가별로 다른 폰트 사용(일본은 한자 커버리지가 있는 Noto Sans JP)
   - 이모지는 각 폰트가 컬러 이모지를 지원하지 않아 깨진 네모로 나오므로 자동 제거
   - 일본어처럼 띄어쓰기가 없는 언어는 단어 단위 대신 글자 단위로 줄바꿈
4) 좌측 상단 로고 자리 확보 (로고 파일 있으면 합성, 없으면 스킵)
"""

import re
from PIL import Image, ImageDraw, ImageFont
from config import (IMG_WIDTH, IMG_HEIGHT, GRADIENT_HEIGHT_RATIO,
                     TITLE_LEFT_MARGIN_RATIO, TITLE_MIN_LINES, TITLE_MAX_LINES,
                     BASE_TEXT_COLOR, FONT_PATHS, FONT_VARIATION)

# 대부분의 이모지/픽토그램이 속한 유니코드 대역. 컬러 이모지 폰트가 아니면 깨진 박스로 나오므로 제거.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\uFE0F"
    "]+", flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


def _load_font(country: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_PATHS.get(country, FONT_PATHS["KR"])
    font = ImageFont.truetype(path, size)
    weight = FONT_VARIATION.get(path)
    if weight:
        try:
            font.set_variation_by_axes([weight])
        except Exception:
            pass  # 가변폰트가 아니거나 축 이름이 다르면 기본값으로 진행
    return font


def _fit_to_canvas(img: Image.Image) -> Image.Image:
    target_ratio = IMG_WIDTH / IMG_HEIGHT
    w, h = img.size
    ratio = w / h
    if ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    return img.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)


def _apply_gradient(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    gradient_h = int(IMG_HEIGHT * GRADIENT_HEIGHT_RATIO)
    overlay = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    top_y = IMG_HEIGHT - gradient_h
    for y in range(top_y, IMG_HEIGHT):
        progress = (y - top_y) / gradient_h
        alpha = int(235 * (progress ** 1.3))
        draw.line([(0, y), (IMG_WIDTH, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img, overlay)


def _split_tokens(headline: str) -> tuple:
    """
    줄바꿈 단위를 정한다.
    - 공백이 충분히 있으면(한/영) 단어 단위로 분리
    - 공백이 거의 없으면(일본어처럼 띄어쓰기가 없는 문장) 글자 단위로 분리
    반환: (tokens, join_str) - join_str은 토큰을 이어붙일 때 쓸 구분자("" 또는 " ")
    """
    clean = headline.replace("\n", " ")
    words = clean.split()
    # 평균 단어 길이가 비정상적으로 길면(=사실상 공백이 없으면) 글자 단위로 전환
    if not words:
        return list(clean), ""
    avg_len = sum(len(w) for w in words) / len(words)
    if avg_len >= 6:  # 일반적인 한/영 단어보다 훨씬 길면 공백 없는 언어로 판단
        return [ch for ch in clean if ch != " "], ""
    return words, " "


def _wrap_and_fit(draw, tokens, join_str, font_loader, max_width, min_lines, max_lines,
                   start_size=88, min_size=36):
    size = start_size
    font = font_loader(start_size)
    while size >= min_size:
        font = font_loader(size)
        lines, current = [], []
        for t in tokens:
            trial = current + [t]
            width = draw.textlength(join_str.join(trial), font=font)
            if width <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = [t]
        if current:
            lines.append(current)
        if min_lines <= len(lines) <= max_lines:
            return font, lines, size
        size -= 4
    return font, lines, size


def _draw_title(img: Image.Image, headline: str, country: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    headline = _strip_emoji(headline)
    left_margin = int(IMG_WIDTH * TITLE_LEFT_MARGIN_RATIO)
    max_text_width = IMG_WIDTH - left_margin * 2

    tokens, join_str = _split_tokens(headline)
    font_loader = lambda size: _load_font(country, size)
    font, lines, size = _wrap_and_fit(draw, tokens, join_str, font_loader,
                                       max_text_width, TITLE_MIN_LINES, TITLE_MAX_LINES)
    line_height = int(size * 1.35)
    total_h = line_height * len(lines)
    y = IMG_HEIGHT - total_h - int(IMG_HEIGHT * 0.06)

    for line_tokens in lines:
        text = join_str.join(line_tokens)
        draw.text((left_margin, y), text, font=font, fill=BASE_TEXT_COLOR)
        y += line_height
    return img


def build_card(background_img: Image.Image, headline: str, country: str = "KR",
               logo_path: str = None) -> Image.Image:
    img = _fit_to_canvas(background_img)
    img = _apply_gradient(img)
    img = _draw_title(img, headline, country)

    if logo_path:
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((120, 120))
        img.paste(logo, (36, 36), logo)

    return img.convert("RGB")
