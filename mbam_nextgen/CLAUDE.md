# MBAM NextGen — SEO 분석 버그 분석 및 수정 기록

---

# 📅 2026-07-03 완료 — 카페 권위 지수 v2 (등급/대표카페/스크랩) + 배포

## 배경
- 이전 세션의 미완 **2단계(카페 랭킹/활성도)** / **3단계(작성자 작성글수/가입일)** 를 재조사.
- ⚠ 중요 변화: 카페 추출이 Playwright DOM → **네이버 카페 article API JSON** 기반으로 이미 전환됨
  (`apis.naver.com/cafe-web/cafe-articleapi/v2.1/...`, [seo_analyzer.py:1230](services/seo_analyzer.py#L1230)).
  `fetch_cafe_author_info`(Playwright)는 사실상 레거시.

## 실측 조사 결론 (스코프 현실화)
| 원래 계획 | 실제 |
|---|---|
| 카페 랭킹 BIG/PREMIUM/RISING | ❌ 미존재 → ✅ **네이버 실제 등급 씨앗~숲(6단계) + 대표카페 마크** (카페 홈 HTML 공개) |
| 카페 일일 활성도 | ❌ 비공개 |
| 작성자 작성글수/가입일 | ❌ 멤버 프로필 API 전부 051(없음)·로그인 필요 → **불가 확정** |
| (신규 발견) | ✅ `scrapCount`(스크랩수) — article API 포함 |

## 구현 (전부 완료·라이브 검증)
| # | 위치 | 내용 |
|---|------|------|
| 1 | [seo_analyzer.py](services/seo_analyzer.py) `fetch_cafe_grade_info` 신규 | 카페 홈 HTML에서 `ico_rank rankNN`+`<em>등급명</em>` → `cafe_grade_name`/`cafe_grade_tier(1~6)`, `대표카페`/`popular_40x32` → `is_official_cafe` |
| 2 | 카페 분기 `cafe_author_info` | `scrap_count`(=scrapCount) 추가 + `fetch_cafe_grade_info` 호출 병합 |
| 3 | `_calculate_authority_scores` **v2** | Cafe = 회원수(0~55)+카페등급(0~30)+대표카페(0/15). Author 호응도에 스크랩(0~7) 추가(조회15/좋아요12/댓글11/스크랩7) |
| 4 | **버그 수정** level_tier | 아이콘 URL `/levelicon/1/13_120.gif` 에서 정규식이 테마id `1`을 잡던 것 → 파일명 `13_120`의 **13**(실제 등급) 추출로 수정 |
| 5 | [SeoResults.jsx](../mbam-web/components/SeoResults.jsx) / [cafe-analysis/page.js](../mbam-web/app/cafe-analysis/page.js) | 카페 카드에 🌳등급명 + ✔대표카페 칩, 호응도 4열(+🔖스크랩), 배지 tooltip·등급기준 문구 갱신 |

## 라이브 검증값 (샘플 2개, v2)
| | tier | Author | Cafe | 비고 |
|---|---|---|---|---|
| ungsangjang (성실멤버 t1, 조회912/좋20/댓11, 97K 숲, 대표X) | 1 | **33.7 / C** | **73.5 / A** | |
| mindy7857 (베나자고수 t13, 조회1159/좋1/댓2, 1.29M 숲, 대표O) | 13 | **54.9 / B** | **98.3 / S** | 대표카페 +15로 S 분리 |

## 남은 한계
- 작성자 가입일·작성글수, 카페 일일활성도는 **로그인/비공개 벽**으로 수집 불가 (재시도 무의미).
- 카페 좋아요수는 별도 route-like API로 수집(기존), 스크랩수는 article API 직접 포함.

---

## 프로젝트 구조

| 경로 | 역할 |
|------|------|
| `services/seo_analyzer.py` | 핵심 SEO 분석 엔진 (Playwright 스크래핑, 키워드 추출) |
| `services/soul.py` | AI 클라이언트 래퍼 (Gemini / Claude / OpenAI) |
| `backend/routers/seo.py` | FastAPI 라우터 (`/api/seo/analyze`, `/api/seo/search`) |
| `mbam-web/app/seo-analysis/page.js` | Next.js 프론트엔드 SEO 분석 페이지 |
| `mbam-web/components/SeoResults.jsx` | 분석 결과 테이블·키워드 렌더링 컴포넌트 |

---

## 분석 흐름

```
[프론트엔드]
  → GET /api/seo/search?keyword=...   (스마트블록 리스트 검색)
  → POST /api/seo/analyze { keyword, target_urls }   (선택 포스팅 분석)

[백엔드 analyze_keyword()]
  1. analyze_multiple_urls(target_urls)   → Playwright로 각 URL 스크래핑
  2. extract_keywords_with_ai(texts)      → Gemini AI 형태소 분석 (실패 시 fallback)
  3. 블로그별 top_keywords 계산          → count_phrase_occurrences()
  4. generate_winning_formula()           → AI 상위노출 공식 생성

[프론트엔드 SeoResults.jsx]
  → m.top_keywords.length > 0 ? 키워드 표시 : "키워드 추출 데이터가 없습니다..."
```

---

## 발견된 버그 및 원인 분석

### Bug 1 — 키워드 분석내역 전체 빈 배열 (최초 발견)

**증상:** 모든 포스팅의 "키워드 분석내역 리스트"에 "키워드 추출 데이터가 없습니다. 본문이 너무 짧거나 분석에 실패했을 수 있습니다." 표시.

**원인:** `extract_keywords_with_ai` (seo_analyzer.py:230)

```python
# 수정 전 — AI가 유효한 JSON이지만 빈 배열을 반환하면 예외 없이 [] 반환, fallback 미작동
return json.loads(json_str).get("top_keywords", [])
```

Gemini가 `{"top_keywords": []}` 또는 `{}` 같은 빈 결과를 응답하면 `json.loads().get()` 은 예외 없이 `[]` 를 반환하여 `except` 블록의 Python fallback이 실행되지 않음.

**수정 내용:**
```python
result = json.loads(json_str).get("top_keywords", [])
if not result:
    raise ValueError("AI가 빈 배열을 반환했습니다")  # → fallback 강제 가동
return result
```

---

### Bug 2 — 이미지수 0장 (SE3 블로그)

**증상:** 네이버 Smart Editor 3(SE3) 기반 블로그 포스팅의 이미지수가 0장으로 집계.

**원인 1:** `_setup_stealth_page`가 `"image"` 리소스를 전역 차단하여 SE3의 Intersection Observer 기반 lazy-load가 `<img>` 태그를 DOM에 삽입하지 못함.

**원인 2:** 스크롤 로직이 완전히 제거된 상태 — `domcontentloaded` 직후 HTML을 읽어 lazy-load 트리거 불가.

**원인 3:** `asyncio.Semaphore(10)` — 이미지 로딩을 허용한 상태에서 10개 병렬은 메모리 과부하 위험.

**수정 내용 (seo_analyzer.py):**
```python
# 1. block_images 파라미터 추가 (기본값 True → 검색 단계는 기존 유지)
async def _setup_stealth_page(self, context, block_images: bool = True):
    blocked = ["media", "font", "stylesheet"]
    if block_images:
        blocked.append("image")

# 2. analyze_multiple_urls에서만 이미지 허용
page = await self._setup_stealth_page(context, block_images=False)

# 3. 스크롤 복구 + 초기 iframe 대기 추가
await page.goto(post_url, timeout=10000, wait_until="domcontentloaded")
await page.wait_for_timeout(500)          # iframe 초기화 대기
frame = page.frame(name="mainFrame")
target_page = frame if frame else page
for _ in range(2):
    await target_page.evaluate("window.scrollBy(0, 4000)")
    await page.wait_for_timeout(500)      # lazy-load 트리거 대기

# 4. Semaphore 10 → 4로 감소, 미사용 ai_semaphore 제거
semaphore = asyncio.Semaphore(4)
```

---

### Bug 3 — 카페 포스팅 동일 데이터 반환 (153자, "다시 2회", 0장)

**증상:** 서로 다른 네이버 카페 URL 3개가 모두 153자, 띄어쓰기 25개, 키워드 "다시 2회", 이미지 0장으로 동일한 데이터를 반환.

**원인:** `analyze_multiple_urls`의 브라우저 컨텍스트가 **Android 모바일 UA** 고정:
```python
context = await browser.new_context(
    user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B)"  # Android UA
)
```
카페 URL(`cafe.naver.com/...`)에 Android UA로 접근하면 네이버가 "앱으로 보기" 모바일 인터스티셜 페이지로 유도. 서로 다른 카페 글 URL이 모두 동일한 인터스티셜에 걸려 같은 153자 반환.

> **참고:** 네이버 검색 VIEW탭에 노출된 카페 글은 로그인 불필요 (공개 글). 로그인 벽이 아니라 UA 불일치 문제.

블로그는 코드에서 데스크톱 URL로 명시 변환하지만 카페는 변환 없음:
```python
# 블로그 → 데스크톱 강제 변환 (정상)
post_url = f"https://blog.naver.com/{blog_id}/{log_no}"

# 카페 → URL 그대로 사용 (문제)
post_url = url   # Android UA + 데스크톱 카페 URL = 인터스티셜
```

**미수정 (수정 방향):**
```python
elif "cafe.naver.com" in url or "m.cafe.naver.com" in url:
    post_url = url.replace("m.cafe.naver.com", "cafe.naver.com")
    # + 카페 전용 데스크톱 UA 컨텍스트 분리 필요
```

---

### Bug 4 — 블로그 포스팅 키워드에 네이버 UI 단어 혼입 ("블로그", "보기", "본문", "폰트", "크기")

**증상:**
- 포스트 1 ("365 days of Summer Song"): "블로그 8회", "보기 4회"만 추출
- 포스트 3 (수구레국밥 블로그): "본문 4회", "폰트 3회", "크기 3회" 혼입

**원인 A — mainFrame iframe 로딩 미완료 (포스트 1):**

`page.wait_for_timeout(500)` 후 `page.frame("mainFrame")`은 iframe 객체를 반환하지만 iframe 내부 콘텐츠가 아직 로딩 중일 수 있음. `frame.content()` 호출 시 초기 빈 HTML 반환 → `.se-main-container` 미발견 → `soup.body` 폴백 → 외부 페이지 네이버 UI 전체 텍스트 수집.

```python
# 미수정 (수정 방향)
frame = page.frame(name="mainFrame")
if frame:
    await frame.wait_for_load_state("domcontentloaded")  # iframe 로딩 완료 대기 필요
```

**원인 B — Fallback 불용어 목록 부족 (포스트 3):**

`_fallback_extract_keywords`의 stopwords에 네이버 UI/에디터 전용 단어 미포함:
```python
# 현재 stopwords — 일반 한국어 불용어만 포함
stopwords = {"이것", "저것", "그것", "그리고", ...}

# 미포함 네이버 UI 단어 (추가 필요)
# "블로그", "보기", "본문", "폰트", "크기", "댓글", "이웃", "구독",
# "전체보기", "사진", "이동", "닫기", "카페", "게시글"
```

---

## 수정 완료 항목 요약

| # | 파일 | 수정 내용 | 상태 |
|---|------|-----------|------|
| 1 | seo_analyzer.py:80 | `_setup_stealth_page` `block_images` 파라미터 추가 | ✅ 완료 |
| 2 | seo_analyzer.py:233 | AI 빈 배열 반환 시 `ValueError` → fallback 강제 | ✅ 완료 |
| 3 | seo_analyzer.py:779 | `analyze_multiple_urls` 호출 `block_images=False` | ✅ 완료 |
| 4 | seo_analyzer.py:806 | 초기 500ms 대기 + 스크롤 2회 복구 (500ms 간격) | ✅ 완료 |
| 5 | seo_analyzer.py:775 | `Semaphore(10→4)`, 미사용 `ai_semaphore` 제거 | ✅ 완료 |

## 미수정 항목 (추가 작업 필요) — ✅ 2026-05-25 전부 완료

| # | 원인 | 수정 위치 | 상태 |
|---|------|-----------|------|
| A | 카페 Android UA 인터스티셜 | seo_analyzer.py:812-813 (`desktop_context` 분리) | ✅ |
| B | iframe 로딩 미완료 | seo_analyzer.py:857-861 (`frame.wait_for_load_state`) | ✅ |
| C | Fallback 불용어 부족 | seo_analyzer.py:248-260 (네이버 UI 단어 20+개 추가) | ✅ |
| D | 작성자 통계 미수집 | seo_analyzer.py:774-798 (`fetch_blog_stats_by_id` 신규) | ✅ |
| E | 카페 작성자 Naver ID 미추출 | seo_analyzer.py:843-849, 901-916 (`memberid` / `/members/` 정규식) | ✅ |
| F | `blog_info` 응답 누락 | seo_analyzer.py:374-376, 931 (analyze_keyword 응답에 포함) | ✅ |

---

# 📅 2026-05-26 세션 요약 (대화 흐름 + 결과물)

## 대화 흐름 — 사용자 요청 순서

1. **이전 개발내역 불러오기** — CLAUDE.md 로드
2. **샘플 카페 URL 2개 제공** (ungsangjang/828892, mindy7857/5182039) → DOM 분석 요청
   - `scratch/inspect_cafe_dom.py` 작성, `cafe_dom_dumps/` 에 HTML+summary.json 저장
   - 두 카페가 동일한 Vue 컴포넌트 (`data-v-e2e58648`) 사용 — 셀렉터 1세트 공용 확인
   - **중요 발견:** 신형 카페 SPA 는 `memberid=...` 가 아닌 `/ca-fe/cafes/{clubid}/members/{opaqueHash}` 사용 → CLAUDE.md 원안 정규식 매치 안 됨
3. **SEO 키워드 분석 원인 분석 요청** — "메인 = 검색어, 서브 = 메인 연관 키워드여야 하는데 단순 빈도만 분석되고 있다"
   - 5가지 근본 원인 파악 (§1 참조), 5단계 수정안 제시
4. **"카페글도 마찬가지로 분석 + 카페 ID 분석 개발 진행"** → 통합 구현
   - SEO 키워드 의미 연관 전환 (§1)
   - `fetch_cafe_author_info` 신설 + lazy 로드 대기 (§2)
   - 두 샘플 URL 로 12개 필드 모두 검증 완료
5. **"권위 지수 계산"** + UI 시안 요청 → A안(확장행 카드) + "여백 있는 분리형" 선택
   - `_calculate_authority_scores` v1 구현 (§3)
   - SeoResults.jsx 확장행에 3장 카드(작성자/카페/호응도) + GradeBadge 추가 (§4)
6. **"어느 메뉴에 추가했냐?"** → SEO 분석 메뉴 (`/seo-analysis`) 라고 응답
7. **"카페 분석 및 자동화 → 카페글 분석 메뉴에 만들어"** — 위치 정정 지시
   - `/cafe-analysis` 페이지에 탭 UI 신설 (URL 권위 분석 / 본문 해부 분석)
   - 신규 백엔드 엔드포인트 `/api/seo/analyze-cafe-urls` (§5)
   - SEO 분석의 카드는 그대로 유지 (검색 결과 분석 시에도 유용)
8. **"지금 Streamlit 아닌데"** — UI 스택 정정 지시
   - Next.js(mbam-web) 단일 스택 명시
   - `dashboard.py` 참조 제거, ⚠ 안내 추가
   - 영구 메모리 저장 (`mbam-nextgen-ui-stack.md`)

## 오늘 변경된 파일

### 백엔드 (`mbam_nextgen/`)
| 파일 | 변경 |
|------|------|
| [services/seo_analyzer.py](services/seo_analyzer.py) | `extract_keywords_with_ai` 검색어 인식 / `_fallback_extract_keywords` bigram+가중치 / `analyze_keyword` 통합 점수 / `_calculate_authority_scores` 신규 / `fetch_cafe_author_info` 신규 / `analyze_multiple_urls` 카페 분기 보완 |
| [backend/routers/seo.py](backend/routers/seo.py) | `POST /api/seo/analyze-cafe-urls` 엔드포인트 신규 (`CafeUrlsRequest` 모델 포함) |

### 프론트엔드 (`mbam-web/`)
| 파일 | 변경 |
|------|------|
| [components/SeoResults.jsx](../mbam-web/components/SeoResults.jsx) | 글감 테이블 확장행에 카페 3장 카드 + GradeBadge 컴포넌트 신규 |
| [app/cafe-analysis/page.js](../mbam-web/app/cafe-analysis/page.js) | 탭 UI 신설 (URL 권위 분석 기본, 본문 해부 분석 보존) + `CafeAuthorityCards` + 자체 GradeBadge |

### 검증 스크립트 (`mbam_nextgen/scratch/`)
| 파일 | 용도 |
|------|------|
| [scratch/inspect_cafe_dom.py](scratch/inspect_cafe_dom.py) | DOM 셀렉터 1회용 분석 (덤프 → `cafe_dom_dumps/`) |
| [scratch/test_cafe_author.py](scratch/test_cafe_author.py) | `analyze_multiple_urls` 통합 검증 (재실행 가능) |

## 미커밋 상태
- 모든 변경사항 **파일 저장만** 완료
- git 커밋 안 됨 → 다음 세션 시작 시 커밋 묶을지 결정 필요
- Next.js dev 서버 동작 중이면 HMR 자동 반영, 프로덕션은 빌드/배포 필요

---

# 📅 2026-05-26 완료 — SEO 키워드 분석 의미 연관 전환 + 카페 작성자/카페 권위 트랙

## 1. SEO 키워드 분석 — 단순 빈도 → 의미 연관 기반으로 재설계

### 근본 원인
- [seo_analyzer.py:205](services/seo_analyzer.py#L205) `extract_keywords_with_ai` 가 **검색어(메인 키워드)를 인자로 받지 않아** AI 가 주제 인식 없이 본문 최빈 명사만 반환했음
- [seo_analyzer.py:415](services/seo_analyzer.py#L415) `b['sub_kw'] = top_keywords[0]['keyword']` — 전역 1위 단어를 **모든 글에 동일 적용**
- `fetch_related_keywords` (자동완성) / `fetch_keyword_volumes` (검색량) 데이터를 수집만 하고 **키워드 랭킹에 미반영**
- 토큰 단위가 **단일 명사**라 검색 핵심인 복합 명사구(예: "중앙동 점심")가 누락
- `_fallback_extract_keywords` 도 동일 한계 + 네이버 UI 단어 stopwords 부족

### 수정 내용 (완료)
| # | 위치 | 변경 |
|---|------|------|
| 1 | [seo_analyzer.py:205-263](services/seo_analyzer.py#L205) `extract_keywords_with_ai` | `main_keyword`, `related_hints` 인자 추가. AI 프롬프트에 검색 의도 + 자동완성 연관어 + 복합 명사구 우선 + relevance 0~100 점수 출력 지시. 50점 미만 컷오프 |
| 2 | [seo_analyzer.py:265-321](services/seo_analyzer.py#L265) `_fallback_extract_keywords` | bigram 후보 추가, 메인 키워드 토큰/연관어 일치 시 점수 가중, 카페/네이버 UI stopwords 확장 |
| 3 | [seo_analyzer.py:457-461](services/seo_analyzer.py#L457) `analyze_keyword` 호출부 | `extract_keywords_with_ai(texts, main_keyword=keyword, related_hints=related)` 로 전달 |
| 4 | [seo_analyzer.py:464-481](services/seo_analyzer.py#L464) 통합 점수 계산 | `score = relevance×0.5 + log(volume)×0.3 + count×0.2`. 검색량 가중 합산 후 재정렬 |
| 5 | [seo_analyzer.py:483-509](services/seo_analyzer.py#L483) 블로그/카페별 sub_kw | 글마다 **상위 15개 sub_keywords 중 자기 본문에 가장 많이 나온 것**을 sub_kw 로 선정 → 글별 차별화 |

### 적용 범위
- 블로그·인플루언서·**카페 글 모두 동일 파이프라인**(`analyze_multiple_urls` → `texts` → `extract_keywords_with_ai`) → SEO 키워드 수정 자동 반영
- AI 실패 시 fallback 도 동일하게 검색어 인식 + bigram 추출

### 검증 방법
- 검색어 별로 결과 비교: 메인 검색어와 의미 연관 없는 단어("사진", "주소", "보기" 등)가 sub_keywords 에 포함되면 안 됨
- 블로그별 sub_kw 가 **글마다 다른 단어**로 표시되는지 확인 (이전: 모두 동일)
- AI 응답 형식이 `{"sub_keywords":[{"keyword":..,"relevance":..}]}` 로 바뀐 점에 유의 (구버전 `top_keywords` 호환 처리됨)

---

## 2. 카페 작성자 / 카페 권위 트랙 (`fetch_cafe_author_info`)

### 신규 메서드
- [seo_analyzer.py:843-905](services/seo_analyzer.py#L843) `fetch_cafe_author_info(target_page)` — 카페 iframe(cafe_main) 내부에서 JS evaluate 로 일괄 추출
- 좋아요/댓글은 lazy 모듈이라 `scrollIntoView({block:'center'}) + 900ms` 대기 후 추출

### 추출 필드 (검증 완료)
| 키 | 셀렉터 | 검증값(ungsangjang/mindy7857) |
|---|---|---|
| nickname | `.nick_box .nickname` | 교지컬에 반하다 / 인텔리2 |
| level_name | `em.nick_level` (icon 제거 후) | 새싹멤버 / 베나자고수 |
| level_tier | `i.LevelIcon` sprite `#N_M-usage` 의 N | 1 / 13 |
| is_popular | `em.popular_mark` 존재 | true / true |
| member_hash | `.ArticleWriterProfile a[href]` `/members/{hash}` | iSx…/Dn0… |
| view_count | `.article_info .count` | 772 / 439 |
| like_count | `.like_no em.u_cnt._count` (lazy) | 20 / 1 |
| comment_count | `.button_comment` | 11 / 2 |
| post_date | `.article_info .date` | 2026.03.24. 18:40 |
| cafe_name | `.cafe_info .cafe_name` | 부산 경남 맘스홀릭… |
| cafe_member | `.cafe_info .cafe_member em` | 96,062 / 1,268,205 |
| club_id | frame URL `/cafes/{N}/articles/` | 26334430 / 17373998 |

### `analyze_multiple_urls` 통합 변경
- **카페일 때 `fetch_blog_stats_by_id` 호출 차단** — 카페 hash 는 네이버 블로그 ID 가 아니므로 호출 시 항상 실패. `if blog_id and blog_id != "알수없음" and not is_cafe` 로 가드
- 응답 dict 에 `cafe_author_info` 필드 추가
- `text_type` / `source` / `type_color` 를 `is_cafe` 분기로 분리 (이전: 모두 "네이버 블로그" 하드코딩)
- 신형 카페 SPA 의 `/ca-fe/cafes/{clubid}/members/{hash}` 패턴이 더 이상 `memberid=` 가 아니므로, `cafe_author_info.member_hash` 를 그대로 `blog_id` 슬롯에 채워 UI 표시용으로 사용 (통계 호출은 위 가드로 차단)

### 미완 / 다음 단계
- [ ] **2단계** — 카페 메타에서 카페 랭킹(BIG/PREMIUM/RISING)/일일활성도 추가 수집 (회원수는 잡힘)
- [ ] **3단계** — 멤버 프로필 페이지(`/ca-fe/cafes/{clubid}/members/{hash}`) 직접 접근 시도 → 작성글수/가입일 (카페 공개 정책 의존)

> ⚠ 활성 UI 스택은 Next.js(mbam-web) 단일. `dashboard.py`(Streamlit)는 비활성/레거시이므로 신규 UI 작업 시 참고하지 말 것.

---

## 3. 카페 권위 지수 v1 — [seo_analyzer.py:786-857](services/seo_analyzer.py#L786) `_calculate_authority_scores`

### Author Authority (0~100, S/A/B/C/D 등급)
- **등급 점수 (0~40)** = `level_tier / 15 * 40` (linear cap)
- **인기멤버 보너스 (0 or 15)** = `is_popular ? 15 : 0`
- **글 호응도 (0~45)** = log scale 정규화 합
    - 조회: `log1p(view) / log(1001) * 15` (1000회 → 만점)
    - 좋아요: `log1p(like) / log(51) * 15` (50회 → 만점)
    - 댓글: `log1p(comment) / log(51) * 15` (50회 → 만점)

### Cafe Authority (0~100, S/A/B/C/D 등급)
- **회원수 (0~100)** = `log10(member) / log10(2,000,000) * 100` (200만명 → 만점)
- 랭킹/일일활성도는 미수집 → 회원수 단일 지표 (수집 후 재분배)

### 등급 컷오프
S ≥80 / A ≥65 / B ≥45 / C ≥25 / D <25

### v1 검증값 (샘플 2개)
| | Author | Cafe |
|---|---|---|
| ungsangjang (새싹멤버 tier 1, view 771/like 20/comment 11, 96K 멤버) | **53.2 / B** | **79.1 / A** |
| mindy7857 (베나자고수 tier 13, view 439/like 1/comment 2, 1.27M 멤버) | **69.7 / A** | **96.9 / S** |

→ 직관 검증 OK: "작은 카페의 활발한 새내기" vs "큰 카페의 잠잠한 고수" 가 분리됨.

### 자동 호출
`analyze_multiple_urls` 의 카페 분기에서 `cafe_author_info` 추출 직후 자동 호출되어 `author_score`/`author_grade`/`cafe_score`/`cafe_grade`/`score_breakdown` 필드 병합. UI 측은 별도 호출 없이 그대로 받음.

---

## 4. Next.js UI 노출 — [SeoResults.jsx](../mbam-web/components/SeoResults.jsx)

### 위치
글감 테이블 행 클릭 → 확장 영역 상단. 카페 글일 때만 `m.cafe_author_info?.nickname` 조건부 렌더.

### 구성 — 여백 있는 분리형 3장
1. **👤 작성자 카드** — 닉네임 / 인기멤버 뱃지 / 등급 + 티어 / 작성일 + `author_grade` 배지 (우상단)
2. **☕ 카페 카드** — 카페명 / 회원수 / club_id + `cafe_grade` 배지 (우상단)
3. **📊 글 호응도 카드** — 조회/좋아요/댓글 3분할 grid

### 등급 배지 컴포넌트
[SeoResults.jsx:3-26](../mbam-web/components/SeoResults.jsx#L3) `<GradeBadge>` — S=금/A=초록/B=파랑/C=주황/D=회색, hover title 에 점수 breakdown 표시.

### 배포 상태
파일 저장만 완료. Next.js dev 서버 동작 중이면 HMR 자동 반영, 프로덕션은 빌드/배포 필요.

### 검증 스크립트
- [scratch/inspect_cafe_dom.py](scratch/inspect_cafe_dom.py) — DOM 셀렉터 분석 (1회용, [scratch/cafe_dom_dumps/](scratch/cafe_dom_dumps/) 에 덤프)
- [scratch/test_cafe_author.py](scratch/test_cafe_author.py) — `analyze_multiple_urls` 통합 검증

---

## 5. 카페글 분석 메뉴 신설 — `/cafe-analysis` 탭 UI

### 위치 변경 배경
SEO 분석 메뉴의 SeoResults.jsx 카드는 **검색 결과로 카페가 섞여 들어올 때**의 표시용. 사용자는 "카페만 분석하는 전용 메뉴"가 필요했음 → **카페 분석 및 자동화 → 카페글 분석** (`/cafe-analysis`) 에 신설.

### 메뉴 구조
```
사이드바
└─ ☕ 카페 분석 및 자동화
   ├─ 🔍 카페글 분석 (/cafe-analysis)
   │   ├─ [Tab 1] 🔗 URL 권위 분석 (신규, 기본 활성)
   │   └─ [Tab 2] 📄 본문 해부 분석 (기존 보존)
   ├─ 카페글 자동화
   └─ 카페 댓글 자동화
```

### 신규 백엔드 엔드포인트 — `POST /api/seo/analyze-cafe-urls`
- 요청 body: `{ "urls": [str] }` (1~5개)
- 처리: `analyzer.analyze_multiple_urls(urls)` 호출 → `cafe_author_info` 자동 포함
- 응답: `{ "items": [{url, cafe_author_info, ...}], "errors": [{url, error}] }`
- **키워드 불필요** — 카페 작성자/카페 권위 측정에 집중 (키워드 기반 SEO 분석은 SEO 분석 메뉴에서)

### Next.js 페이지 — `/cafe-analysis/page.js`
- 탭 UI: `mode` state ('url' | 'content'), 기본 'url'
- URL 탭 입력: textarea(한 줄 = 한 URL, 최대 5), 검증 후 fetch
- URL 탭 결과: URL별 박스 + 3장 카드 (Author/Cafe/Engagement) + 등급 배지 + 글자/이미지 메타
- 실패 URL 은 별도 빨간 박스로 분리 표시
- 본문 탭: 기존 AI 해부 분석 로직 그대로 보존 (RCON/SCQA/D.I.A+/Chain)

### 컴포넌트 재사용 vs 인라인
- `GradeBadge`, `CafeAuthorityCards` 는 SeoResults.jsx 와 cafe-analysis/page.js 양쪽에 **각자 인라인** 정의
- 공유 컴포넌트로 분리하지 않음 (간단한 표시 로직이라 양쪽 변경 시 가독성 우선)
- 추후 변경 빈도가 잦아지면 `mbam-web/components/cafe/` 로 분리 고려

### 검증
- 두 샘플 URL 로 신규 엔드포인트 직접 호출: 2/2 성공, 0 errors
- ungsangjang B/A (53.2/79.1), mindy7857 A/S (69.7/96.9) — Section 3 결과와 일치

### 미완 / 다음 단계
- [ ] **2단계** (Cafe 권위 정밀화) — 카페 랭킹/일일활성도 수집
- [ ] **3단계** (Author 권위 정밀화) — 멤버 프로필 페이지에서 작성글수/가입일
- [ ] **git 커밋** — 오늘 변경 묶음

---

# 📅 2026-05-26 완료 (위 ↑) — 원본 분석 노트는 아래 보존

# 📅 2026-05-26 분석 예정 — 카페 인기글 작성자 카페 내 권위 지수 (Cafe Authority Score)

## 배경

블로그 작성자 분석(`blog_info` = 이웃수/방문자/총게시글/개설일)은 **네이버 통합 ID로 `m.blog.naver.com/{id}`** 에서 비로그인 수집 가능.

그러나 카페 글에서는 작성자의 "카페 내부 권위" — 즉 **해당 카페 안에서의 등급/활동량/호응도** — 가 SEO 노출 영향에 중요한데, 이는 블로그 통계로 측정 불가. 별도 트랙으로 카페 페이지에서 직접 수집해야 함.

## 비회원으로 카페 글에서 추출 가능한 작성자 데이터

| 항목 | 추출 위치 (DOM 후보) | 비고 |
|------|---------------------|------|
| **카페 멤버 등급** | `.tit_level`, `.member_grade`, `.grade_icon` | 매니저/스탭/정회원/준회원/새싹 — 카페별 등급명 상이 |
| **카페 닉네임** | `.nick_text`, `.member_nick` | 카페 내부 표시명 (Naver ID와 별개) |
| **글 조회수** | `.count_num`, `.no` (글 메타) | 글 자체 호응도 |
| **댓글수 / 좋아요수** | `.cmt_count`, `.like_count` | 글 자체 호응도 |
| **카페 회원수** | 카페 상단 `.member_num`, 메타 | 카페 자체 규모 |
| **카페 랭킹/등급** | 네이버 카페 랭킹 (BIG/PREMIUM/RISING) | 카페 자체 권위 |
| **작성자 글 수 (카페 내)** | `MemberView.nhn?clubid=XX&memberid=YY` 또는 호버 카드 | 카페별 공개 정책 따라 다름 |
| **가입일** | 멤버 프로필 페이지 | 활동 기간 산출 (일부 비공개) |

## 제안 지수 구조 — 2-트랙 분리 평가

```
[1] 작성자 권위 지수 (Author Authority, 0~100)
    = 등급 30% + 작성글수 20% + 활동기간 20% + 글 호응도(조회/댓글/좋아요) 30%

[2] 카페 권위 지수 (Cafe Authority, 0~100)
    = 회원수 40% + 카페 랭킹 30% + 일일활성도 30%
```

→ 두 지수를 분리하면 "큰 카페의 신입 작성자" vs "작은 카페의 매니저"를 다르게 평가 가능

## 구현 로드맵 — 3단계 분할

### 1단계 (확실히 가능)
카페 글 HTML에서 등급/닉네임/조회수/댓글수/좋아요 추출
→ 응답 dict에 `cafe_author_info` 필드 추가

### 2단계 (조건부 가능)
카페 메타에서 회원수/랭킹 수집
→ 응답 dict에 `cafe_info` 필드 추가

### 3단계 (가능시 시도)
멤버 프로필 페이지 접근 시도 → 작성글수/가입일
→ 카페 공개 설정에 따라 실패 가능, try/except + fallback 필요

## 작업 시작 시 첫 단계

1. **샘플 URL 2~3개 확보** — 네이버 검색 VIEW 탭에서 카페 글 3개 (대형/중형/소형 카페 각 1)
2. **샘플 HTML 저장** — Playwright로 fetch 후 DOM 구조 분석 (셀렉터 검증)
3. **공통/상이 셀렉터 분류** — 카페별로 다른 부분 파악 후 우선순위 정규식/셀렉터 fallback 체인 설계
4. **`fetch_cafe_author_info()` 메서드 신설** — `services/seo_analyzer.py` 내 `fetch_blog_stats_by_id` 옆에 추가
5. **`analyze_multiple_urls` 내 호출 분기** — `is_cafe == True` 일 때 `fetch_blog_stats_by_id` 대신 (또는 함께) `fetch_cafe_author_info` 호출

## 의존성 — 작업 시작 전 사용자 확인 필요

- [ ] 위 데이터 항목 중 우선순위 (시간 제한 시 무엇부터?)
- [ ] 점수 가중치 (위 30/20/20/30, 40/30/30 비율 검토)
- [ ] 샘플 카페 글 URL 2~3개

## 관련 파일

- [services/seo_analyzer.py](services/seo_analyzer.py) — `fetch_blog_stats_by_id` 옆에 신규 메서드 추가
- [mbam-web/components/SeoResults.jsx](../mbam-web/components/SeoResults.jsx) — `cafe_author_info` 표시 UI 신규 (Next.js 단일 UI 스택)
