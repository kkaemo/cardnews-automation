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
import time
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"temperature": 0.7},
    }
    # 무료 티어가 일시적으로 과부하(503)/한도초과(429)일 때는 잠깐 쉬었다가 재시도
    # (429는 분당 한도가 대부분이라 20초 정도 쉬면 풀리는 경우가 많음)
    delays = [1, 3, 6, 20]
    last_res = None
    for attempt, delay in enumerate([0] + delays):
        if delay:
            time.sleep(delay)
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code in (429, 503):
            last_res = res
            continue
        if res.status_code != 200:
            print(f"[LLM][gemini] 응답 코드 {res.status_code}: {res.text[:300]}")
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    if last_res.status_code == 429:
        raise QuotaExceeded("gemini")
    print(f"[LLM][gemini] {len(delays)}번 재시도 후에도 실패 지속 (마지막 응답 {last_res.status_code})")
    last_res.raise_for_status()


def _call_huggingface(system_prompt: str, user_prompt: str) -> str:
    key = _next_key("hf", "HF_API_KEYS")
    if not key:
        raise RuntimeError("HF_API_KEYS 없음")
    # 2025년 구 주소(api-inference.huggingface.co)가 완전히 폐쇄(410 Gone)되어 새 라우터 사용.
    # 모델은 HF 라우터에서 실제로 여러 업체(provider)가 서빙 확인된 openai/gpt-oss-120b 사용.
    # :fastest 접미사는 HF 라우터가 그 모델을 서빙하는 여러 업체 중 가장 빠른 곳으로 자동 연결.
    # 주의: HF 토큰에 "Make calls to Inference Providers" 권한이 켜져 있어야 동작함
    # (huggingface.co/settings/tokens 에서 토큰 생성/수정 시 확인).
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "openai/gpt-oss-120b:fastest",
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
        "temperature": 0.7,
    }
    res = requests.post("https://router.huggingface.co/v1/chat/completions",
                         headers=headers, json=payload, timeout=60)
    if res.status_code == 429:
        raise QuotaExceeded("huggingface")
    if res.status_code != 200:
        print(f"[LLM][huggingface] 응답 코드 {res.status_code}: {res.text[:300]}")
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


PROVIDER_FUNCS = {
    "groq": _call_groq,
    "gemini": _call_gemini,
    "huggingface": _call_huggingface,
}


_llm_announced = False


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """PROVIDER_ORDER 순서대로 시도. 한도초과/오류 나면 다음 프로바이더로 자동 전환."""
    global _llm_announced
    if not _llm_announced:
        print("[LLM] 모듈 버전: 2026-09-12-v9 (HF 모델: openai/gpt-oss-120b:fastest)")
        _llm_announced = True
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


def classify_batch(titles: list, country: str) -> list:
    """
    여러 기사 제목을 한 번의 LLM 호출로 묶어서 분류 (무료 API 호출 횟수 절감용).
    titles 순서와 동일한 순서의 dict 리스트를 반환. 실패하거나 개수가 안 맞으면
    호출한 쪽에서 개별 classify_and_check_person으로 재시도할 수 있도록 빈 리스트를 반환.
    """
    system = "너는 뉴스 카테고리 분류 및 이미지 표현 가능성 판별 도우미다. 반드시 JSON 배열만 출력."
    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
    user = f"""
아래는 기사 제목 목록이다. 각 항목마다 순서대로 분류하라.

{numbered}

반드시 아래처럼 정확히 {len(titles)}개짜리 JSON 배열로만 답하라 (순서를 titles와 동일하게 유지):
[
  {{"category": "경제|건강|날씨|문화|운동|스포츠|예술|정책/혜택/제도|연예|정치|기타",
   "requires_real_person_depiction": true or false,
   "symbolic_image_idea": "인물 없이 상징적으로 표현할 아이디어 한 문장 (해당 없으면 빈 문자열)"}},
  ...
]
"""
    result = _extract_json(call_llm(system, user))
    if isinstance(result, list) and len(result) == len(titles):
        return result
    print(f"[LLM] 배치 분류 결과 개수 불일치({len(result) if isinstance(result, list) else '비정상'}) — 이 배치는 건너뜀")
    return []


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
