# 카드뉴스 자동화 (KR/JP/US 통합)

`python3 main.py` **하나만 실행**하면 한국·일본·미국을 모두 처리해서
`output/review_YYYY-MM-DD.html` 대시보드 하나로 결과가 모입니다.
이 HTML을 브라우저로 열면:
- 국가별 탭으로 필터링
- 카드마다 체크박스로 "업로드할 것" 선택 (선택 상태 자동 저장)
- 본문/대체텍스트/해시태그 확인
- **미국·일본 카드는 "🇰🇷 번역본(비고)"를 펼쳐서 한국어 번역을 보고, 톤이 자연스럽게 나왔는지 확인 가능**

이후 실제 업로드는 이미지를 다운로드하고 본문/대체텍스트를 복사해서 사람이 직접 게시합니다(Graph API 앱 심사 전까지는 이 방식이 가장 현실적).

---

## 0. 📱 스마트폰만으로 전체 과정 운영하기 (최종 목표)

**한 번만(PC 또는 폰 브라우저로) 설정해두면, 그 다음부터는 매일 폰으로 3단계면 끝납니다.**

1. GitHub 앱(또는 모바일 브라우저)에서 **Actions 탭 → "카드뉴스 자동화" → Run workflow** 버튼 탭 (수동 실행. 스케줄대로면 매일 08:00 KST에 자동 실행되므로 이 단계도 생략 가능)
2. 몇 분 뒤 GitHub Pages 링크(예: `https://내계정.github.io/저장소명/`)를 폰 브라우저로 열기 → 오늘의 카드뉴스 전체가 세로 카드 형태로 뜸
3. 카드마다 **[이미지 다운로드]** 버튼으로 사진 저장, **[복사]** 버튼으로 본문/대체텍스트/해시태그를 원탭 복사 → 인스타그램 앱 열어서 붙여넣기+업로드. 체크박스로 "이건 올릴 것"만 표시해두면 다음에 봐도 유지됨

### 최초 1회 설정 (아래는 순서대로 한 번만)
1. **GitHub 계정 생성** (없다면) — 모바일 브라우저에서도 가능
2. **새 저장소(Repository) 생성** → 이 zip 압축을 풀어서 안의 파일들을 "Add file → Upload files"로 전부 업로드 (압축 해제는 폰 파일앱의 압축풀기 기능 사용)
   - 이 단계는 파일이 많아 **폰보다 PC/노트북에서 한 번에 끝내는 걸 강력 추천**합니다. (딱 1회만 하면 되고, 이후 운영은 100% 폰으로 가능)
3. 저장소 **Settings → Secrets and variables → Actions**에서 아래 키들을 등록 (Settings 진입은 폰 브라우저로도 가능):
   - `GEMINI_API_KEYS` = 제공해주신 제미나이 키 (샘플로 `.env`에 이미 넣어뒀습니다)
   - `GROQ_API_KEYS`, `HF_API_KEYS`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` (있는 만큼만 등록, 없으면 비워둬도 등록된 것만 자동으로 사용됨)
4. 저장소 **Settings → Pages**에서 Source를 "GitHub Actions"로 설정 (한 번만)
5. 이후부터는 위 "0-1~0-3" 3단계만 반복하면 됩니다.

> ⚠️ 저장소를 **Public(공개)**으로 만들면 누구나 코드를 볼 수 있습니다. API 키는 Secrets에만 넣고 `.env` 파일 자체는 절대 저장소에 커밋하지 마세요(`.gitignore`에 이미 제외 처리되어 있습니다). 보내주신 제미나이 키가 외부에 노출된 적이 있다면 Google AI Studio에서 재발급(rotate)하시는 걸 권장드립니다.

## 1. 무료 LLM API 여러 개 등록 (한도 초과 시 자동 전환)

`config.py`의 `PROVIDER_ORDER = ["groq", "gemini", "huggingface"]` 순서대로 시도하다가,
호출한 프로바이더가 **429(한도초과)나 오류**를 내면 자동으로 다음 프로바이더로 넘어갑니다.
같은 프로바이더 안에서도 키를 콤마로 여러 개 넣으면(`GEMINI_API_KEYS=키1,키2`) 그 안에서도 로테이션합니다.

| 프로바이더 | 발급처 | 환경변수 |
|---|---|---|
| Groq (Llama) | https://console.groq.com | `GROQ_API_KEYS` |
| Gemini (Google) | https://aistudio.google.com/apikey | `GEMINI_API_KEYS` ← **샘플키 반영 완료** |
| Hugging Face | https://huggingface.co/settings/tokens | `HF_API_KEYS` |

순서를 바꾸거나 프로바이더를 더 추가하고 싶으면 `config.py`의 `PROVIDER_ORDER`와 `llm.py`에
같은 패턴으로 `_call_새프로바이더()` 함수만 추가하면 됩니다.

## 2. PC에서 직접 실행하고 싶을 때

```bash
pip install -r requirements.txt
playwright install chromium   # OCR 폴백 쓸 경우에만
cp .env.example .env          # 키 입력 후 (또는 이미 채워진 .env 그대로 사용)
export $(cat .env | xargs)
python3 main.py
```

## 3. 왜 이 방식이 "관리가 가장 쉬운" 구조인가
- **국가 3개, 소스 9개를 전부 `config.py` 한 파일**에서 관리 (추가/삭제/URL 변경 시 여기만 수정)
- **실행 진입점이 `main.py` 하나** — 국가별로 따로 스크립트를 돌릴 필요 없음
- **결과물도 대시보드 HTML 하나**로 모여서 세 나라를 각각 확인할 필요 없고, 폰 브라우저로 바로 열림 (GitHub Pages)
- **LLM 프로바이더가 여러 개** 등록되어 있어 하나가 한도초과여도 자동 전환
- LLM/이미지 생성 provider를 바꾸고 싶으면 `llm.py`, `imagegen.py`만 교체하면 나머지 코드는 그대로 동작
- 서버를 상시로 켜둘 필요 없이 `.github/workflows/daily.yml`이 매일 08:00 KST에 자동 실행되고, 결과가 GitHub Pages로 자동 배포됨 (설정은 위 "0. 최초 1회 설정" 참고)

## 3-1. 실제 사이트 구조 확인 결과 (반영 완료)
- **웰로(weilo.co.kr)**: 실제 확인 결과 `weilo.co.kr/rss`에 **공식 RSS**가 있었습니다. 뽐뿌·디시·엠팍·보배 등 커뮤니티 인기글을 3시간마다 집계해서 제공 — 스크래핑 없이 RSS로 바로 연동, 가장 안정적인 소스입니다. 제목이 `[디시] 제목`처럼 커뮤니티 태그가 붙어 있어서 자동으로 분리해 기록하도록 구현했습니다.
- **나우히츠(nowhitz.com)**: RSS는 없지만, `실시간 검색어 순위` 섹션이 서버에서 완성된 HTML로 내려오는 것을 확인했습니다(자바스크립트 렌더링 불필요). 순위별 제목과 원문 출처(SOURCE 링크)를 스크래핑하도록 구현했고, 사이트 개편으로 깨지면 자동 OCR 폴백됩니다.
- **네이버**: 2020년 10월 사이트 전체 '많이 본 뉴스' 랭킹이 공식 폐지되어 더 이상 스크래핑 대상이 없습니다. 대신 **네이버 공식 오픈API**(뉴스 검색, 무료 1일 25,000회)로 대체했습니다. `developers.naver.com`에서 앱 등록 후 `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`만 넣으면 됩니다.
- **다음**: `news.daum.net`에 '이 시각 주요뉴스'와 '실시간 트렌드'가 실제로 살아있는 것을 확인했습니다. CSS 클래스명 대신 **실제 기사 링크의 URL 패턴**(`v.daum.net/v/...`)으로 잡도록 구현했습니다.
- **야후재팬**: `news.yahoo.co.jp/ranking/access/news`가 살아있는 것을 확인했습니다. 마찬가지로 클래스명 대신 기사 URL 패턴(`news.yahoo.co.jp/articles/...`)으로 추출, 실패 시 OCR 폴백.

한국 소스 4개(웰로/나우히츠/네이버/다음) 모두 실제 URL과 방식이 확정되어 `collectors/kr_sources.py`에 반영 완료됐습니다.

## 4. 현재 상태 / 실제 서비스 전 확인 필요한 부분
- **나우히츠 스크래핑 셀렉터**: 실제 페이지 구조를 텍스트로는 확인했지만 정확한 HTML class는 못 봤습니다. `collectors/kr_sources.py`의 `fetch_nowhitz()`는 텍스트 패턴(`WHY!`, `SOURCE` 링크) 기반이라 왠만하면 동작하지만, 첫 실행 시 결과가 이상하면 셀렉터를 실제 HTML 보고 조정해드릴게요.
- **BuzzFeed News RSS**: 서비스 축소 이력이 있어 RSS가 살아있는지 최신 확인 필요.
- 이 개발 환경(샌드박스)은 뉴스/SNS 사이트로의 네트워크 접근이 막혀 있어 **실제 수집·LLM·이미지생성 API 호출은 테스트하지 못했고, 이미지 후처리(그라데이션+텍스트) 로직만 실제로 동작 검증**했습니다 (`output/test_card_KR.png` 참고). 나머지는 본인 PC나 GitHub Actions에서 키를 넣고 실행하면 됩니다.

## 5. 폴더 구조
```
config.py                 국가/소스/이미지 스펙/LLM 프로바이더 순서 전체 설정
collectors/                국가별 수집기 (kr_sources, jp_sources, us_sources)
scorer.py                  Top5 선정 로직
llm.py                     멀티 프로바이더 콘텐츠 생성 + 번역(비고)
imagegen.py                Pollinations.ai 이미지 생성
postprocess.py             그라데이션 + 제목 합성 (테스트 완료)
review_html.py             모바일 최적화 리뷰 대시보드 생성 (테스트 완료)
main.py                    전체 실행 진입점
fonts/Pretendard-Bold.otf
.github/workflows/daily.yml  자동 스케줄 + Pages 배포
.env                        키 보관용 (제미나이 샘플키 반영, 절대 커밋 금지)
output/                     생성 결과물 (index.html이 항상 최신본)
```
