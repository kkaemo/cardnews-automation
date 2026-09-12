# -*- coding: utf-8 -*-
"""
이미지 생성 - 전부 무료 (유료 API 없음)
1) Pollinations.ai (기본, 완전 무료, 키 불필요)
2) Hugging Face Inference API - Stable Diffusion (무료 티어, 이미 있는 HF_API_KEYS 재사용)
3) 로컬 그라데이션 배경 - 위 둘 다 실패해도 카드는 항상 만들어지도록 하는 최종 안전망
"""

import io
import os
import itertools
import random
import urllib.parse
import requests
from PIL import Image, ImageDraw
from config import IMG_WIDTH, IMG_HEIGHT

_hf_key_cycle = None


def generate_image(prompt: str) -> Image.Image:
    for fn, label in [(_generate_via_pollinations, "Pollinations"),
                       (_generate_via_huggingface, "HuggingFace(무료)")]:
        try:
            return fn(prompt)
        except Exception as e:
            print(f"[imagegen] {label} 실패({e}) → 다음 방법으로 전환")
    print("[imagegen] 모든 무료 이미지 생성 방법 실패 → 로컬 그라데이션 배경으로 대체")
    return _generate_fallback_background()


def _generate_via_pollinations(prompt: str) -> Image.Image:
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={IMG_WIDTH}&height={IMG_HEIGHT}&nologo=true"
    res = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0 (compatible; CardNewsBot/1.0)"})
    content_type = res.headers.get("content-type", "")
    if res.status_code != 200 or not content_type.startswith("image"):
        print(f"[imagegen] Pollinations 응답이 이미지가 아님 (status={res.status_code}, content-type={content_type}): {res.text[:200]}")
        raise RuntimeError("Pollinations가 이미지가 아닌 응답을 반환")
    return Image.open(io.BytesIO(res.content)).convert("RGB")


def _next_hf_key():
    global _hf_key_cycle
    raw = os.environ.get("HF_API_KEYS", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        return None
    if _hf_key_cycle is None:
        _hf_key_cycle = itertools.cycle(keys)
    return next(_hf_key_cycle)


def _generate_via_huggingface(prompt: str) -> Image.Image:
    key = _next_hf_key()
    if not key:
        raise RuntimeError("HF_API_KEYS 없음")
    model = "stabilityai/stable-diffusion-xl-base-1.0"  # 무료 추론 API로 제공되는 모델
    headers = {"Authorization": f"Bearer {key}"}
    res = requests.post(
        f"https://api-inference.huggingface.co/models/{model}",
        headers=headers, json={"inputs": prompt}, timeout=90,
    )
    content_type = res.headers.get("content-type", "")
    if res.status_code != 200 or not content_type.startswith("image"):
        print(f"[imagegen] HuggingFace 응답이 이미지가 아님 (status={res.status_code}, content-type={content_type}): {res.text[:200]}")
        raise RuntimeError("HuggingFace가 이미지가 아닌 응답을 반환")
    return Image.open(io.BytesIO(res.content)).convert("RGB")


def _generate_fallback_background() -> Image.Image:
    """이미지 생성이 전부 안 될 때 쓰는 대체 배경 - 랜덤 색상 그라데이션"""
    palette = [
        ((30, 60, 90), (10, 20, 40)),
        ((70, 40, 90), (20, 10, 30)),
        ((30, 80, 60), (10, 30, 20)),
        ((90, 60, 30), (30, 20, 10)),
    ]
    c1, c2 = random.choice(palette)
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(IMG_HEIGHT):
        t = y / IMG_HEIGHT
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (IMG_WIDTH, y)], fill=(r, g, b))
    return img
