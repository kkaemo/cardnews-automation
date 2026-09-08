# -*- coding: utf-8 -*-
"""무료 이미지 생성: Pollinations.ai (API 키 불필요)"""

import io
import urllib.parse
import requests
from PIL import Image
from config import IMG_WIDTH, IMG_HEIGHT


def generate_image(prompt: str) -> Image.Image:
    safe_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={IMG_WIDTH}&height={IMG_HEIGHT}&nologo=true"
    res = requests.get(url, timeout=60)
    res.raise_for_status()
    return Image.open(io.BytesIO(res.content)).convert("RGB")
