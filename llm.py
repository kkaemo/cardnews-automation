# -*- coding: utf-8 -*-
"""
멀티 프로바이더 LLM 모듈
- 여러 무료 API를 등록해두고, 한도 초과(429)/오류 시 자동으로 다음 프로바이더로 전환
- 프로바이더별로 키를 여러 개(콤마 구분) 넣으면 같은 프로바이더 내에서도 키 로테이션
- 키가 없는 프로바이더는 자동으로 건너뜀

지원: Groq(Llama), Gemini(Google), Hugging Face Inference
우선순위와 프로바이더 추가/삭제는 config.py의 PROVIDER_ORDER 만 수정하면 됨.
"""

import os
import json
import itertools
import requests
from config import TONE_GUIDE, PROVIDER_ORDER

_key_cycles = {}


def _get_keys(env_var: str) -> list:
    raw = os.environ.get(env_var, "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def _next_key(provider: str, env_var: str):
    keys = _get_keys(env_var)
    if not keys:
        return None
    if provider not in _key_cycles:
        _key_cycles[provider] = itertools.cycle(keys)
    return next(_key_cycles[provider])


class QuotaExceeded(Exception):
    pass


def _call_groq(system_prompt: str, user_prompt: str) -> str:
    key = _next_key("groq", "GROQ_API_KEYS")
    if not key:
        raise RuntimeError("GROQ_API_KEYS 없음")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-70b-versatile",
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
        "temperature": 0.7,
    }
    res = requests.post("https://api.groq.com/openai/v1/chat/completions",
                         headers=headers, json=payload, timeout=30)
    if res.status_code == 429:
        raise QuotaExceeded("groq")
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    key = _next_key("gemini", "GEMINI_API_KEYS")
    if not key:
        raise RuntimeError("GEMINI_API_KEYS 없음")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"temperature": 0.7},
    }
    res = requests.post(url, json=payload, timeout=30)
    if res.status_code == 429:
        raise QuotaExceeded("gemini")
    res.raise_for_status()
    return res.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call_huggingface(system_prompt: str, user_prompt: str) -> str:
    key = _next_key("hf", "HF_API_KEYS")
    if not key:
        raise RuntimeError("HF_API_KEYS 없음")
    model = "meta-llama/Meta-Llama-3-8B-Instruct"
    headers = {"Authorization": f"Bearer {key}"}
    prompt = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"
    res = requests.post(f"https://api-inference.huggingface.co/models/{model}",
                         headers=headers, json={"inputs": prompt, "parameters": {"temperature": 0.7}},
                         timeout=60)
    if res.status_code == 429:
        raise QuotaExceeded("huggingface")
    res.raise_for_status()
    data = res.json()
    return data[0]["generated_text"].split("<|assistant|>")[-1].strip()


PROVIDER_FUNCS = {
    "groq": _call_groq,
    "gemini": _call_gemini,
    "huggingface": _call_huggingface,
}


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """PROVIDER_ORDER 순서대로 시도. 한도초과/오류 나면 다음 프로바이더로 자동 전환."""
    last_error = None
    for provider in PROVIDER_ORDER:
        fn = PROVIDER_FUNCS.get(provider)
        if not fn:
            continue
        try:
            return fn(system_prompt, user_prompt)
        except Exception as e:
            print(f"[LLM] {provider} 실패({e}) → 다음 프로바이더로 전환")
            last_error = e
            continue
    raise RuntimeError(f"모든 LLM 프로바이더 실패. 마지막 오류: {last_error}")


def _extract_json(raw: str) -> dict:
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def classify_and_check_person(article_title: str, country: str) -> dict:
    system = "너는 뉴스 카테고리 분류 및 이미지 표현 가능성 판별 도우미다. 반드시 JSON만 출력."
    user = f"""
기사 제목: {article_title}

아래 JSON 형식으로만 답하라:
{{
  "category": "경제|건강|날씨|문화|운동|스포츠|예술|정책/혜택/제도|연예|정치|기타",
  "requires_real_person_depiction": true or false,
  "symbolic_image_idea": "인물 없이 상징적으로 표현할 아이디어 한 문장 (해당 없으면 빈 문자열)"
}}
"""
    return _extract_json(call_llm(system, user))


def generate_card_content(article_title: str, article_summary: str, country: str) -> dict:
    tone = TONE_GUIDE.get(country, "")
    need_translation = country != "KR"
    system = f"""너는 {country} 인스타그램 카드뉴스 에디터다. 톤 가이드: {tone}
반드시 JSON만 출력하고 다른 설명은 절대 붙이지 마라."""
    translation_field = '"translation_ko": "본문 전체를 한국어로 그대로 번역 (톤 확인용, 의역 아닌 직역에 가깝게)",' if need_translation else ""
    user = f"""
기사 제목: {article_title}
기사 요약: {article_summary}

아래 JSON 스키마로 작성하라 (언어는 {country}에서 실제 쓰는 언어로, translation_ko 항목만 한국어):
{{
  "headline": "2~3줄로 자연스럽게 줄바꿈 가능한 헤드라인",
  "headline_highlight_words": ["강조할 단어1", "강조할 단어2"],
  "image_prompt": "인물 얼굴을 특정하지 않는 이미지 생성 프롬프트 (영어로 작성)",
  "caption": "게시글 본문 (해당 국가 SNS 자연스러운 어투)",
  "alt_text": "대체텍스트",
  "hashtag": "#해시태그1개",
  {translation_field}
  "_end": true
}}
"""
    return _extract_json(call_llm(system, user))
