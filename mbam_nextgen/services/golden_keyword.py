"""
황금키워드 분석 서비스.

글감수집으로 모인 항목(키워드/제목)을 시드로,
  1) 네이버 검색광고 keywordstool 로 연관키워드 + 월간검색량 + 경쟁도(compIdx) 확장
  2) 글감 토큰 기반 연관도 필터 (검색광고 API의 과도한 광역 확장 차단)
  3) 네이버 오픈API 블로그/카페 문서수(포화도) 조회
  4) 황금점수 = 검색량 / 문서수 (검색량 높고 문서 적을수록 ↑) 계산 후 채널별 추천

모든 외부 호출은 라이브로 검증됨 (2026-06-22).
"""
import os
import re
import json
import time
import hmac
import hashlib
import base64
import asyncio

import httpx
from collections import Counter
from dotenv import load_dotenv

from mbam_nextgen.services.soul import SoulRewriter

# 뉴스 제목 명사 추출용 (선택적)
import os as _os
if (_os.environ.get("EXECUTION_MODE", "local") or "").strip().lower() == "cloud":
    _kiwi = None  # [슬림] 클라우드는 분석을 에이전트에 위임 → Kiwi 미로드(OOM 방지)
else:
    try:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    except Exception:
        _kiwi = None

load_dotenv("mbam_nextgen/.env")

# 키는 호출 시점에 읽는다 — 관리자(/admin)에서 저장한 키가 서버 재시작 없이 바로 반영되도록.
def _cid(): return os.getenv("NAVER_CUSTOMER_ID")
def _lic(): return os.getenv("NAVER_ACCESS_LICENSE")
def _sk(): return os.getenv("NAVER_SECRET_KEY")
def _oid(): return os.getenv("NAVER_CLIENT_ID")
def _osec(): return os.getenv("NAVER_CLIENT_SECRET")

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")
# 카테고리 공통어/조사성 단어 — 시드 토큰에서 제외 (관련도 필터가 너무 헐거워지는 것 방지)
_STOP = {
    "지원", "안내", "정보", "신청", "사업", "제도", "혜택", "방법", "대상", "공고",
    "최신", "확대", "주요", "내용", "기준", "관련", "추진", "운영", "실시", "연도",
    "2024", "2025", "2026", "정부", "국가", "전국",
    # 시드로 부적합한 약한 토큰 (연도/증감 표현 등) — keywordstool 확장 노이즈 유발
    "2023년", "2024년", "2025년", "2026년", "2027년",
    "상향", "인상", "신설", "조정", "강화", "개편", "지급", "대상자",
}

# 상업성/제품판매 키워드 블랙리스트 — 후보가 이 토큰을 '포함'하면 제외.
# 보수적으로 명백한 판매·렌탈·통신가입 유도성 단어만 (예: '국민행복카드'의 '카드'는 막지 않음).
_COMMERCIAL = {
    "정수기", "렌탈", "렌트", "사은품", "최저가", "위약금", "약정", "비교견적", "견적",
    "인터넷가입", "인터넷설치", "인터넷요금", "현금사은품", "가입사은품", "설치비", "할부",
    "공기청정기", "안마의자", "비데", "매트리스", "상조",
}

# 뉴스 카테고리 — 글감 keywords 가 출처/형식 메타단어라, 제목에서 주제어를 직접 추출하고
# 검색량(화제성) 우선으로 정렬한다 (일반 카테고리의 keywordstool 확장과 다른 경로).
NEWS_CATEGORIES = {"네이버 뉴스 (많이 본 뉴스)"}

# 뉴스 메타/형식 단어 + 언론사명 — 주제어가 아니므로 제외
_NEWS_STOP = {
    # 형식/메타
    "속보", "단독", "인기뉴스", "뉴스", "종합", "영상", "포토", "사진", "기자", "오늘", "어제",
    "공식", "논란", "파문", "충격", "경악", "공개", "발표", "이유", "상황", "모습", "현장", "관련",
    # 언론사
    "YTN", "연합뉴스", "연합", "서울신문", "뉴시스", "한겨레", "조선일보", "중앙일보", "동아일보",
    "경향신문", "국민일보", "머니투데이", "이데일리", "헤럴드경제", "뉴스1", "KBS", "MBC", "SBS",
    "JTBC", "채널A", "TV조선", "MBN",
    # 일반 빈출 명사 (검색량은 높지만 콘텐츠 주제로는 무의미) — 화제성 정렬 오염 방지
    "한국", "사망", "형제", "자매", "초등", "중등", "고등", "산소", "남성", "여성", "사람", "정도",
    "발생", "사고", "사건", "피해", "주장", "발언", "의혹", "혐의", "조사", "결정", "가능", "이상",
    "지난", "최근", "이번", "당시", "이후", "전국", "국내", "세계", "지역", "사회", "경제", "정치",
}


def extract_news_topics(items: list) -> list:
    """뉴스 글감 제목에서 주제어(명사 + 인접 명사 bigram) 추출. 메타단어/언론사명 제외."""
    seen, out = set(), []

    def add(w):
        if w and len(w) > 1 and w not in seen and w not in _NEWS_STOP:
            seen.add(w)
            out.append(w)

    for it in items:
        title = it.get("title") or ""
        if _kiwi:
            nouns = [
                t.form for t in _kiwi.tokenize(title)
                if t.tag in ("NNG", "NNP", "SL") and len(t.form) > 1 and t.form not in _NEWS_STOP
            ]
        else:
            # Kiwi 미설치 폴백: 괄호/기호 제거 후 공백 분리
            cleaned = re.sub(r"[\[\]\(\)\"'“”‘’.,…·]", " ", title)
            nouns = [w for w in cleaned.split() if len(w) > 1 and w not in _NEWS_STOP]
        for n in nouns:
            add(n)
        # 인접 명사 bigram (호르무즈+해협 → 호르무즈해협) — 개체명 포착용
        for a, b in zip(nouns, nouns[1:]):
            bg = a + b
            if len(bg) <= 12:
                add(bg)
    return out


async def _volumes_map(client: httpx.AsyncClient, keywords: list) -> dict:
    """주어진 키워드들의 월검색량/경쟁도를 keywordstool 로 조회 (5개씩 청크). {정규화키워드: row}."""
    vmap = {}
    for i in range(0, len(keywords), 5):
        chunk = keywords[i:i + 5]
        rows = await _keywordstool(client, chunk)
        for r in rows:
            k = (r.get("keyword") or "").replace(" ", "")
            if k and k not in vmap:
                vmap[k] = r
    return vmap


def has_keys() -> bool:
    return all([_cid(), _lic(), _sk(), _oid(), _osec()])


# --- 결과 캐시 (글감 캐시와 동일 디렉터리, 카테고리별 파일) ---------------------
_DATA_PATH = "mbam_nextgen/data"
os.makedirs(_DATA_PATH, exist_ok=True)


def _cache_path(category: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9가-힣]", "_", category)
    return os.path.join(_DATA_PATH, f"golden_{safe}.json")


def _db_write_golden(category: str, out: dict):
    """DB 영속(재배포에도 유지). 실패해도 파일 저장은 계속된다."""
    try:
        from mbam_nextgen.backend.database import SessionLocal, GoldenCache
    except Exception:
        return
    db = SessionLocal()
    try:
        payload = json.dumps(out, ensure_ascii=False)
        row = db.query(GoldenCache).filter(GoldenCache.category == category).first()
        if row:
            row.payload = payload
            row.updated = out.get("updated", "")
        else:
            db.add(GoldenCache(category=category, payload=payload, updated=out.get("updated", "")))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _db_read_golden(category: str):
    try:
        from mbam_nextgen.backend.database import SessionLocal, GoldenCache
    except Exception:
        return None
    db = SessionLocal()
    try:
        row = db.query(GoldenCache).filter(GoldenCache.category == category).first()
        return json.loads(row.payload) if row and row.payload else None
    except Exception:
        return None
    finally:
        db.close()


def save_cache(category: str, result: dict) -> dict:
    """분석 결과를 DB(영속)+파일에 저장(메뉴 이동/재접속·재배포 후에도 유지)."""
    from datetime import datetime
    out = {**result, "updated": datetime.now().isoformat()}
    _db_write_golden(category, out)
    try:
        with open(_cache_path(category), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Golden] 캐시 저장 실패: {e}")
    return out


def load_cache(category: str):
    # DB 우선(재배포에도 유지) → 파일 폴백
    blob = _db_read_golden(category)
    if blob is not None:
        return blob
    path = _cache_path(category)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _sign(ts: str, method: str, uri: str) -> str:
    msg = f"{ts}.{method}.{uri}"
    return base64.b64encode(
        hmac.new(_sk().encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")


def _num(c) -> int:
    """'< 10' 같은 문자열·콤마 포함 값을 정수로 안전 변환."""
    if isinstance(c, str) and "<" in c:
        return 10
    try:
        return int(str(c).replace(",", "")) if c else 0
    except (ValueError, TypeError):
        return 0


def _tokens(text: str) -> list:
    return [t for t in _TOKEN_RE.findall(text or "") if len(t) > 1]


def build_seed(items: list) -> tuple:
    """글감 항목들에서 keywordstool 힌트(상위 5) + 연관도 허용 토큰(상위 15)을 추출."""
    counter = Counter()
    for it in items:
        for k in (it.get("keywords") or []):
            for t in _tokens(k):
                if t not in _STOP:
                    counter[t] += 2  # AI가 뽑은 키워드 토큰은 가중
        for t in _tokens(it.get("title")):
            if t not in _STOP:
                counter[t] += 1
    hint_words = [t for t, _ in counter.most_common(5)]
    allow_tokens = [t for t, _ in counter.most_common(15)]
    return hint_words, allow_tokens


async def _keywordstool(client: httpx.AsyncClient, hint_words: list) -> list:
    ts = str(int(time.time() * 1000))
    uri = "/keywordstool"
    headers = {
        "X-Timestamp": ts,
        "X-API-KEY": _lic(),
        "X-Customer": str(_cid()),
        "X-Signature": _sign(ts, "GET", uri),
    }
    params = {"hintKeywords": ",".join(w.replace(" ", "") for w in hint_words[:5]), "showDetail": 1}
    try:
        r = await client.get("https://api.naver.com" + uri, params=params, headers=headers, timeout=10.0)
        if r.status_code != 200:
            return []
        out = []
        for it in r.json().get("keywordList", []):
            vol = _num(it.get("monthlyPcQcCnt")) + _num(it.get("monthlyMobileQcCnt"))
            out.append({"keyword": it.get("relKeyword"), "volume": vol, "comp": it.get("compIdx")})
        return out
    except Exception as e:
        print(f"[Golden] keywordstool 실패: {e}")
        return []


async def _doc_count(client: httpx.AsyncClient, kind: str, kw: str, _retry: bool = True):
    """
    kind: 'blog' | 'cafearticle' → 해당 채널 문서 총수(total).
    반환: int(성공) | None(측정 실패). 429(레이트리밋)는 1회 재시도.
    None 은 '문서 0건'과 구분하기 위함 — 실패를 0으로 처리하면 황금점수가 거짓이 됨.
    """
    url = f"https://openapi.naver.com/v1/search/{kind}.json"
    headers = {"X-Naver-Client-Id": _oid(), "X-Naver-Client-Secret": _osec()}
    try:
        r = await client.get(url, params={"query": kw, "display": 1}, headers=headers, timeout=5.0)
        if r.status_code == 200:
            return int(r.json().get("total", 0) or 0)
        if r.status_code == 429 and _retry:
            await asyncio.sleep(1.2)
            return await _doc_count(client, kind, kw, _retry=False)
    except Exception:
        pass
    return None


async def _paced_doc_counts(client: httpx.AsyncClient, specs: list, batch: int = 8, pause: float = 1.2) -> list:
    """
    네이버 오픈API 검색은 약 초당 10건 제한 → 배치(기본 8) 단위로 끊고 사이에 pause 초 대기.
    specs: [(kind, keyword), ...] 순서 그대로 결과 리스트 반환.
    """
    out = []
    for i in range(0, len(specs), batch):
        chunk = specs[i:i + batch]
        res = await asyncio.gather(*[_doc_count(client, kind, kw) for kind, kw in chunk])
        out.extend(res)
        if i + batch < len(specs):
            await asyncio.sleep(pause)
    return out


async def _ai_relevance_filter(category: str, items: list, candidates: list) -> list:
    """
    글감 맥락(카테고리+제목/요약) 대비 후보 키워드의 의미 연관성을 AI 1회 호출로 일괄 판정.
    관련 키워드만 추려 반환. 실패/타임아웃 시 입력(candidates)을 그대로 반환 (기능 보존).
    """
    if not candidates:
        return candidates

    # 맥락: 글감 제목/요약 일부
    ctx_lines = []
    for it in items[:8]:
        title = (it.get("title") or "").strip()
        summary = (it.get("summary") or "").strip()
        if title:
            ctx_lines.append(f"- {title}" + (f" / {summary}" if summary else ""))
    context = "\n".join(ctx_lines) if ctx_lines else category

    kw_list = [c["keyword"] for c in candidates]
    prompt = f"""다음은 '{category}' 카테고리의 실제 글감 주제 목록입니다.
{context}

아래 키워드 후보 중에서, 위 글감 주제와 **직접적으로 의미가 연관된** 키워드만 골라주세요.
제품 판매/렌탈/통신가입/광고성/주제와 무관한 키워드는 반드시 제외하세요.

키워드 후보:
{json.dumps(kw_list, ensure_ascii=False)}

응답은 선택된 키워드만 담은 순수 JSON 배열이어야 합니다. 키워드는 입력 그대로 쓰세요.
예: ["키워드1", "키워드2"]"""

    try:
        soul = SoulRewriter()
        text = await asyncio.wait_for(soul.generate_content(prompt), timeout=15.0)
        s = re.sub(r"```json\s*|```", "", text or "").strip()
        start, end = s.find("["), s.rfind("]") + 1
        if start == -1 or end <= start:
            return candidates
        keep = set(json.loads(s[start:end]))
        filtered = [c for c in candidates if c["keyword"] in keep]
        return filtered if filtered else candidates  # AI가 전부 거르면 폴백
    except Exception as e:
        print(f"[Golden] AI 연관도 필터 실패(폴백): {e}")
        return candidates


async def analyze(category: str, items: list, max_candidates: int = 20, use_ai: bool = True) -> dict:
    """
    글감 항목 리스트 → 황금키워드 추천 결과.
    반환: {"keywords": [...추천 정렬...], "seed": [...], "candidate_count": int}
    """
    if not has_keys():
        raise RuntimeError("네이버 API 키(검색광고/오픈API)가 설정되지 않았습니다.")
    if not items:
        return {"keywords": [], "seed": [], "candidate_count": 0}

    is_news = category in NEWS_CATEGORIES

    # api.naver.com keywordstool 은 308 리다이렉트를 반환하므로 follow_redirects 필수
    async with httpx.AsyncClient(follow_redirects=True) as client:

        if is_news:
            # === 뉴스 경로: 제목 주제어 추출 → 검색량 조회 → 화제성(검색량) 우선 ===
            topics = extract_news_topics(items)
            seed_out = topics[:5]
            candidate_count = len(topics)
            # 검색량 조회 (상위 후보 일부만; keywordstool 호출 절약)
            vmap = await _volumes_map(client, topics[:30])
            scored = []
            for t in topics:
                row = vmap.get(t.replace(" ", ""))
                if row and row.get("volume", 0) > 0:
                    scored.append({"keyword": t, "volume": row["volume"], "comp": row.get("comp")})
            scored.sort(key=lambda x: -x["volume"])
            top = scored[:max_candidates]
        else:
            # === 일반 경로: keywordstool 확장 → 토큰/블랙리스트/AI 필터 → 황금점수 ===
            hint_words, allow_tokens = build_seed(items)
            if not hint_words:
                return {"keywords": [], "seed": [], "candidate_count": 0}
            seed_out = hint_words

            raw = await _keywordstool(client, hint_words)
            seen = {}
            for c in raw:
                k = (c.get("keyword") or "").strip()
                if k and k not in seen:
                    seen[k] = c
            cands = list(seen.values())
            candidate_count = len(cands)

            # 1) 토큰 연관도 필터(cheap): 후보(공백 제거)가 시드 허용 토큰을 최소 1개 포함
            relevant = [c for c in cands if any(tok in c["keyword"].replace(" ", "") for tok in allow_tokens)]
            if not relevant:
                relevant = cands  # 폴백: 필터가 모두 거르면 원본 사용

            # 2) 상업성 블랙리스트 제거(cheap)
            despammed = [c for c in relevant if not any(b in c["keyword"].replace(" ", "") for b in _COMMERCIAL)]
            relevant = despammed or relevant

            # 3) 검색량 내림차순 → AI 필터용 풀
            relevant.sort(key=lambda x: -x["volume"])
            pool = relevant[: max(max_candidates * 2, 24)]

            # 4) AI 연관도 필터(1회 호출, 실패 시 폴백) — 문서수 조회 전에 걸러 호출 절약
            if use_ai:
                pool = await _ai_relevance_filter(category, items, pool)

            top = pool[:max_candidates]

        # === 공통: 블로그/카페 문서수 조회 ===
        specs = []
        for c in top:
            specs.append(("blog", c["keyword"]))
            specs.append(("cafearticle", c["keyword"]))
        counts = await _paced_doc_counts(client, specs)

    def gold_score(volume, docs):
        # docs None=측정실패, 0=신뢰불가 → 점수 산출 불가(None)
        if not docs:
            return None
        return round(volume / docs * 100000, 1)

    results = []
    for i, c in enumerate(top):
        blog_docs = counts[i * 2]
        cafe_docs = counts[i * 2 + 1]
        blog_gold = gold_score(c["volume"], blog_docs)
        cafe_gold = gold_score(c["volume"], cafe_docs)

        # 추천 채널 = 황금점수가 더 높은 쪽 (둘 다 측정되면 비교, 한쪽만 되면 그쪽)
        if blog_gold is not None and (cafe_gold is None or blog_gold >= cafe_gold):
            channel, gold = "블로그", blog_gold
        elif cafe_gold is not None:
            channel, gold = "카페", cafe_gold
        else:
            channel, gold = None, None  # 양쪽 모두 측정 실패

        results.append({
            "keyword": c["keyword"],
            "volume": c["volume"],
            "comp": c["comp"],
            "blog_docs": blog_docs,
            "cafe_docs": cafe_docs,
            "blog_gold": blog_gold,
            "cafe_gold": cafe_gold,
            "channel": channel,
            "gold": gold,
        })

    if is_news:
        # 뉴스: 화제성(검색량) 우선 정렬
        results.sort(key=lambda x: -(x["volume"] or 0))
    else:
        # 일반: 황금점수 내림차순 (측정 실패=None 은 맨 뒤로)
        results.sort(key=lambda x: (x["gold"] is None, -(x["gold"] or 0)))
    return {"keywords": results, "seed": seed_out, "candidate_count": candidate_count, "is_news": is_news}
