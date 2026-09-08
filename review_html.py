# -*- coding: utf-8 -*-
"""
스마트폰 브라우저에서 전체 검수를 끝낼 수 있도록 만든 리뷰 대시보드.
- 세로 1열 레이아웃(모바일 우선), 버튼 큼직하게
- 본문/대체텍스트/해시태그/번역본 각각 "복사" 버튼 (원탭 클립보드 복사)
- 이미지는 "다운로드" 버튼으로 바로 저장 가능
- 체크박스로 업로드 대상 선택 (기기에 저장됨)
- GitHub Pages 등 HTTPS로 올리면 폰 브라우저에서 매일 그대로 열어서 쓰면 됨
"""

import os
import base64
from config import OUTPUT_DIR


def _img_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


CARD_TEMPLATE = """
<div class="card" data-country="{country}">
  <img id="img_{card_id}" src="data:image/png;base64,{img_b64}" />
  <div class="body">
    <span class="badge">{country} · {source}</span>
    <h3>{headline_display}</h3>

    <label class="select">
      <input type="checkbox" class="pick" data-id="{card_id}"> 업로드 대상으로 선택
    </label>

    <a class="btn download" download="{card_id}.png" href="data:image/png;base64,{img_b64}">⬇ 이미지 다운로드</a>

    <div class="field">
      <div class="field-label">본문 <button class="copy" data-copy="cap_{card_id}">복사</button></div>
      <p id="cap_{card_id}">{caption}</p>
    </div>
    <div class="field">
      <div class="field-label">대체텍스트 <button class="copy" data-copy="alt_{card_id}">복사</button></div>
      <p id="alt_{card_id}">{alt_text}</p>
    </div>
    <div class="field">
      <div class="field-label">해시태그 <button class="copy" data-copy="tag_{card_id}">복사</button></div>
      <p id="tag_{card_id}">{hashtag}</p>
    </div>
    {translation_block}
  </div>
</div>
"""

TRANSLATION_TEMPLATE = """
    <details class="translation">
      <summary>🇰🇷 번역본(비고) — 어투 확인용</summary>
      <div class="field">
        <div class="field-label"><button class="copy" data-copy="tr_{card_id}">복사</button></div>
        <p id="tr_{card_id}">{translation_ko}</p>
      </div>
    </details>
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>카드뉴스 리뷰 - {date}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Pretendard", sans-serif; background:#111; color:#eee;
         margin:0; padding:12px; font-size:16px; }}
  h1 {{ font-size: 18px; position: sticky; top:0; background:#111; padding:8px 0; margin:0 0 10px; z-index:5; }}
  .tabs {{ display:flex; gap:6px; margin-bottom:14px; position: sticky; top:38px; background:#111; z-index:5; padding-bottom:6px; }}
  .tabs button {{ flex:1; padding:10px 0; border-radius:20px; border:1px solid #555; background:#222; color:#eee; font-size:14px; }}
  .tabs button.active {{ background:#C5D805; color:#111; font-weight:bold; border-color:#C5D805; }}
  .grid {{ display:flex; flex-direction:column; gap:16px; max-width:520px; margin:0 auto; }}
  .card {{ background:#1c1c1c; border-radius:14px; overflow:hidden; border:1px solid #333; }}
  .card img {{ width:100%; display:block; }}
  .card .body {{ padding:14px; }}
  .badge {{ font-size:12px; color:#C5D805; }}
  h3 {{ font-size:17px; margin:6px 0 10px; line-height:1.35; }}
  .select {{ font-size:14px; display:flex; align-items:center; gap:8px; margin-bottom:10px; }}
  .select input {{ width:20px; height:20px; }}
  .btn {{ display:block; text-align:center; padding:12px; border-radius:10px; background:#2a2a2a;
         color:#eee; text-decoration:none; font-size:14px; margin-bottom:12px; border:1px solid #444; }}
  .field {{ margin-bottom:10px; }}
  .field-label {{ font-size:12px; color:#999; display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }}
  .field p {{ margin:0; font-size:14px; background:#242424; padding:10px; border-radius:8px; white-space:pre-wrap; }}
  button.copy {{ background:#333; color:#C5D805; border:1px solid #555; border-radius:14px; padding:4px 10px; font-size:12px; }}
  button.copy.copied {{ background:#C5D805; color:#111; }}
  details.translation summary {{ color:#8ecbff; font-size:14px; margin-top:4px; }}
  .hidden {{ display:none; }}
</style>
</head>
<body>
<h1>카드뉴스 리뷰 · {date}</h1>
<div class="tabs">
  <button onclick="filterCountry('ALL', this)" class="active">전체</button>
  <button onclick="filterCountry('KR', this)">한국</button>
  <button onclick="filterCountry('JP', this)">일본</button>
  <button onclick="filterCountry('US', this)">미국</button>
</div>
<div class="grid" id="grid">
{cards}
</div>
<script>
document.querySelectorAll('.pick').forEach(cb => {{
  const key = 'pick_' + cb.dataset.id;
  cb.checked = localStorage.getItem(key) === '1';
  cb.addEventListener('change', () => localStorage.setItem(key, cb.checked ? '1' : '0'));
}});

document.querySelectorAll('.copy').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const text = document.getElementById(btn.dataset.copy).innerText;
    navigator.clipboard.writeText(text).then(() => {{
      btn.classList.add('copied');
      btn.innerText = '복사됨';
      setTimeout(() => {{ btn.classList.remove('copied'); btn.innerText = '복사'; }}, 1200);
    }});
  }});
}});

function filterCountry(c, btn) {{
  document.querySelectorAll('.card').forEach(el => {{
    el.classList.toggle('hidden', c !== 'ALL' && el.dataset.country !== c);
  }});
  document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}}
</script>
</body>
</html>
"""


def build_dashboard(cards: list, date_str: str, out_path: str = None) -> str:
    """
    cards: [{
      "id": str, "country": "KR"/"JP"/"US", "source": str, "image_path": str,
      "headline_display": str, "caption": str, "alt_text": str, "hashtag": str,
      "translation_ko": str | None
    }, ...]
    """
    blocks = []
    for c in cards:
        translation_block = ""
        if c.get("translation_ko"):
            translation_block = TRANSLATION_TEMPLATE.format(
                card_id=c["id"], translation_ko=c["translation_ko"]
            )
        blocks.append(CARD_TEMPLATE.format(
            country=c["country"], source=c["source"], img_b64=_img_to_base64(c["image_path"]),
            headline_display=c["headline_display"], card_id=c["id"],
            caption=c["caption"], alt_text=c["alt_text"], hashtag=c["hashtag"],
            translation_block=translation_block,
        ))
    html = PAGE_TEMPLATE.format(date=date_str, cards="\n".join(blocks))
    out_path = out_path or os.path.join(OUTPUT_DIR, f"review_{date_str}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    # 모바일에서 GitHub Pages로 열 때 항상 최신 버전 링크가 고정되도록 index.html도 함께 저장
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
