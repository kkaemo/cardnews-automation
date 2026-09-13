# -*- coding: utf-8 -*-
"""
이미지 생성 - 전부 무료 (유료 API 없음)
1) Pollinations.ai `flux` 모델 (공식적으로 무료+무제한이라고 명시된 모델 - 기본값으로 두면
   혼잡한 다른 모델(lykon/dreamshaper-8-lcm 등)로 걸려 429가 자주 나서 명시적으로 지정)
2) Hugging Face 신규 라우터(router.huggingface.co) - 구 주소(api-inference.huggingface.co)는
   2025년에 완전히 폐쇄되어 DNS 자체가 안 됨 (410 Gone). 반드시 새 주소 사용.
   단, HF 무료 크레딧이 월 $0.10 수준으로 매우 작아져서 보조 수단 정도로만 기대할 것.
3) 로컬 그라데이션 배경 - 위 둘 다 실패해도 카드는 항상 만들어지도록 하는 최종 안전망.
"""

import io
import os
import time
import itertools
import random
import urllib.parse
import requests
from PIL import Image, ImageDraw
from config import IMG_WIDTH, IMG_HEIGHT

_hf_key_cycle = None


_announced = False


def generate_image(prompt: str) -> Image.Image:
    global _announced
    if not _announced:
        print("[imagegen] 모듈 버전: 2026-09-12-v9 (Pollinations flux 모델 + HF 신주소 + 로컬 폴백)")
        _announced = True
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
    # model=flux : Pollinations가 공식적으로 "무료+무제한"이라고 명시한 모델.
    # 지정 안 하면 혼잡한 다른 모델로 걸려 429/500이 자주 발생함.
    url = (f"https://image.pollinations.ai/prompt/{safe_prompt}"
           f"?width={IMG_WIDTH}&height={IMG_HEIGHT}&nologo=true&model=flux")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CardNewsBot/1.0)"}

    last_err = None
    for attempt, delay in enumerate([0, 3, 8]):
        if delay:
            time.sleep(delay)
        res = requests.get(url, timeout=60, headers=headers)
        content_type = res.headers.get("content-type", "")
        if res.status_code == 200 and content_type.startswith("image"):
            return Image.open(io.BytesIO(res.content)).convert("RGB")
        last_err = f"status={res.status_code}, content-type={content_type}, body={res.text[:200]}"
        print(f"[imagegen] Pollinations 응답이 이미지가 아님 ({last_err})")
    raise RuntimeError(f"Pollinations 재시도 후에도 실패 ({last_err})")


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
    model = "stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {key}"}
    # 2025년 구 주소(api-inference.huggingface.co)가 완전히 폐쇄되어 새 라우터 주소 사용
    res = requests.post(
        f"https://router.huggingface.co/hf-inference/models/{model}",
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
