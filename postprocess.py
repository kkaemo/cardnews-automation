# -*- coding: utf-8 -*-
"""
카드뉴스 최종 합성
1) 배경 이미지를 1080x1440으로 리사이즈/크롭
2) 하단 50% 검정 그라데이션(최하단 진함 → 중앙으로 갈수록 옅어짐)
3) 좌측 정렬(10% 여백) 제목, 2~3줄 되도록 자동 크기 조정, 강조단어만 색 분리
4) 좌측 상단 로고 자리 확보 (로고 파일 있으면 합성, 없으면 스킵)
"""

from PIL import Image, ImageDraw, ImageFont
from config import (IMG_WIDTH, IMG_HEIGHT, GRADIENT_HEIGHT_RATIO,
                     TITLE_LEFT_MARGIN_RATIO, TITLE_MIN_LINES, TITLE_MAX_LINES,
                     HIGHLIGHT_COLOR, BASE_TEXT_COLOR, FONT_BOLD_PATH)


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
        # 최하단(alpha 최대) -> 그라데이션 시작점(alpha 0)으로 옅어짐
        progress = (y - top_y) / gradient_h  # 0(위쪽,옅음) ~ 1(아래쪽,진함)
        alpha = int(235 * (progress ** 1.3))
        draw.line([(0, y), (IMG_WIDTH, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img, overlay)


def _wrap_and_fit(draw, words, max_width, min_lines, max_lines, start_size=88, min_size=40):
    """폭 기준으로 줄바꿈했을 때 min~max 줄 수에 들어오도록 폰트 크기를 이진 감소시키며 탐색"""
    size = start_size
    while size >= min_size:
        font = ImageFont.truetype(FONT_BOLD_PATH, size)
        lines, current = [], []
        for w in words:
            trial = current + [w]
            width = draw.textlength(" ".join(trial), font=font)
            if width <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = [w]
        if current:
            lines.append(current)
        if min_lines <= len(lines) <= max_lines:
            return font, lines, size
        size -= 4
    # 못 찾으면 마지막 시도값 그대로 반환
    return font, lines, size


def _draw_title(img: Image.Image, headline: str, highlight_words: list) -> Image.Image:
    draw = ImageDraw.Draw(img)
    left_margin = int(IMG_WIDTH * TITLE_LEFT_MARGIN_RATIO)
    max_text_width = IMG_WIDTH - left_margin * 2
    words = headline.split()

    font, lines, size = _wrap_and_fit(draw, words, max_text_width, TITLE_MIN_LINES, TITLE_MAX_LINES)
    line_height = int(size * 1.35)
    total_h = line_height * len(lines)
    y = IMG_HEIGHT - total_h - int(IMG_HEIGHT * 0.06)  # 하단에서 여백 6%

    highlight_set = set(highlight_words or [])
    for line_words in lines:
        x = left_margin
        for w in line_words:
            clean = w.strip(",.!?~")
            color = HIGHLIGHT_COLOR if clean in highlight_set else BASE_TEXT_COLOR
            token = w + " "
            draw.text((x, y), token, font=font, fill=color)
            x += draw.textlength(token, font=font)
        y += line_height
    return img


def build_card(background_img: Image.Image, headline: str, highlight_words: list,
               logo_path: str = None) -> Image.Image:
    img = _fit_to_canvas(background_img)
    img = _apply_gradient(img)
    img = _draw_title(img, headline, highlight_words)

    if logo_path:
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((120, 120))
        img.paste(logo, (36, 36), logo)

    return img.convert("RGB")
