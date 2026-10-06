from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
from mbam_nextgen.services.seo_analyzer_v2 import SeoAnalyzerV2
from mbam_nextgen.infrastructure.database import DatabaseManager
from mbam_nextgen.backend.database import get_db
from mbam_nextgen.backend.models import AnalysisHistory
from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.backend.quota import check_quota, increment_quota, consume_generation_quota
import json
import asyncio

router = APIRouter()
analyzer = SeoAnalyzer()
analyzer_v2 = SeoAnalyzerV2()
db_manager = DatabaseManager()

from typing import List, Optional

class AnalyzeRequest(BaseModel):
    keyword: str
    target_urls: Optional[List[str]] = None

class KeywordRequest(BaseModel):
    keyword: str

class CafeUrlsRequest(BaseModel):
    urls: List[str]

class BlogIndexRequest(BaseModel):
    blog: str   # 블로그 ID 또는 URL


@router.post("/blog-index", summary="네이버 블로그 지수(추정) 진단 — 개설일/이웃/방문/활성도 기반 0~100 점수")
async def blog_index_endpoint(request: BlogIndexRequest,
                              current_user: dict = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """모바일 공개 엔드포인트를 스크래핑해 블로그 지수(추정)·등급·티어·레벨을 산출. (네이버 공식 지수 아님)
    [방법 B] cloud 모드면 job 적재 → 로컬 에이전트 실행."""
    from mbam_nextgen.services.blog_index import analyze_blog
    from mbam_nextgen.backend import jobs as jobsvc
    blog = (request.blog or "").strip()
    if not blog:
        raise HTTPException(status_code=400, detail="블로그 ID 또는 URL을 입력하세요.")
    if jobsvc.is_cloud_mode():
        return {"mode": "agent", "job_id": jobsvc.enqueue_job(db, current_user.get("sub"), "blog_index", {"blog": blog})}
    try:
        result = await analyze_blog(blog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="블로그 데이터를 가져오지 못했습니다. (아이디 확인 또는 비공개/차단)")
    return {"success": True, **result}


class BlogIndexSaveRequest(BaseModel):
    blog_id: str
    title: Optional[str] = None
    score: int
    grade: int
    tier: str
    level: int
    result: dict


@router.post("/blog-index/save", summary="블로그 지수 진단 결과 저장")
async def save_blog_index(req: BlogIndexSaveRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from mbam_nextgen.backend.models import BlogIndexRecord
    rec = BlogIndexRecord(
        user_id=current_user.get("sub"),
        blog_id=req.blog_id, title=req.title, score=req.score,
        grade=req.grade, tier=req.tier, level=req.level,
        result_data=json.dumps(req.result, ensure_ascii=False),
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return {"success": True, "id": rec.id}


@router.get("/blog-index/saved", summary="저장된 블로그 지수 진단 목록")
async def list_saved_blog_index(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from mbam_nextgen.backend.models import BlogIndexRecord
    uid = current_user.get("sub")
    rows = db.query(BlogIndexRecord).filter(BlogIndexRecord.user_id == uid).order_by(BlogIndexRecord.created_at.desc()).limit(100).all()
    return {"items": [{
        "id": r.id, "blog_id": r.blog_id, "title": r.title, "score": r.score,
        "grade": r.grade, "tier": r.tier, "level": r.level,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "result": json.loads(r.result_data) if r.result_data else None,
    } for r in rows]}


@router.delete("/blog-index/saved/{rec_id}", summary="저장된 블로그 지수 진단 삭제")
async def delete_saved_blog_index(rec_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from mbam_nextgen.backend.models import BlogIndexRecord
    uid = current_user.get("sub")
    r = db.query(BlogIndexRecord).filter(BlogIndexRecord.id == rec_id, BlogIndexRecord.user_id == uid).first()
    if not r:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    db.delete(r); db.commit()
    return {"success": True}


@router.post("/analyze-cafe-urls")
async def analyze_cafe_urls_endpoint(request: CafeUrlsRequest,
                                     current_user: dict = Depends(get_current_user),
                                     db: Session = Depends(get_db)):
    """카페 글 URL 권위 분석.

    키워드 불필요. 각 카페 URL 의 작성자/카페 권위 데이터(cafe_author_info)
    + 본문 통계를 일괄 추출한다. /api/seo/analyze 와 달리 키워드 기반 SEO
    분석은 수행하지 않는다 (카페글 분석 메뉴 전용).
    [방법 B] cloud 모드면 job 적재 → 로컬 에이전트 실행.
    """
    if not request.urls:
        raise HTTPException(status_code=400, detail="URL 을 1개 이상 제공해주세요.")
    if len(request.urls) > 5:
        raise HTTPException(status_code=400, detail="한 번에 최대 5개 URL 까지 분석 가능합니다.")

    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        return {"mode": "agent", "job_id": jobsvc.enqueue_job(db, current_user.get("sub"), "seo_cafe_urls", {"urls": request.urls})}

    try:
        results = await analyzer.analyze_multiple_urls(request.urls)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"분석 실패: {e}")

    items = []
    errors = []
    for url, detail in results.items():
        if "error" in detail:
            errors.append({"url": url, "error": detail["error"]})
        else:
            items.append({"url": url, **detail})

    return {"items": items, "errors": errors}


@router.post("/analyze")
async def analyze_keyword_endpoint(request: AnalyzeRequest,
                                   current_user: dict = Depends(get_current_user),
                                   db: Session = Depends(get_db),
                                   _q: dict = Depends(consume_generation_quota)):
    """
    네이버 키워드 SEO 정밀 분석 API
    - 키워드 검색 결과 상위 10개 추출
    - 각 포스팅 상세 크롤링 (이미지 수, 글자 수, 키워드 추출 등)
    - 상위노출 가이드라인(Winning Formula) 생성

    [방법 B] EXECUTION_MODE=cloud 이면 job 적재 → 로컬 에이전트가 집 IP로 실행.
    """
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        job_id = jobsvc.enqueue_job(db, current_user.get("sub"), "seo_analyze",
                                    {"keyword": request.keyword, "target_urls": request.target_urls})
        return {"mode": "agent", "job_id": job_id}
    try:
        # seo_analyzer의 병렬 비동기 함수 호출
        result = await analyzer.analyze_keyword(request.keyword, target_urls=request.target_urls)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # DB 저장 (히스토리)
        try:
            history_record = AnalysisHistory(
                keyword=request.keyword,
                result_data=json.dumps(result, ensure_ascii=False)
            )
            db.add(history_record)
            db.commit()
        except Exception as e:
            print(f"DB 저장 실패: {e}")
            db.rollback()
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"내부 오류: {str(e)}")

@router.post("/analyze-top3")
async def analyze_top3_seo(request: KeywordRequest, current_user: dict = Depends(check_quota), db: Session = Depends(get_db)):
    """
    신규: 상위 1~3위 블로그를 정밀 분석합니다.
    분석 완료 후 SaaS 운영 내역 DB에 결과를 저장하고 쿼터를 1 차감합니다.
    [방법 B] cloud 모드면 job 적재 → 로컬 에이전트 실행.
    """
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        return {"mode": "agent", "job_id": jobsvc.enqueue_job(db, current_user.get("sub"), "seo_top3", {"keyword": request.keyword})}
    try:
        result = await analyzer_v2.analyze(request.keyword)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "분석 실패"))
            
        # DB 저장(과금/운영 내역 로깅)
        stats = result["stats"]
        import json
        db_manager.log_analysis(
            keyword=request.keyword,
            total_words=stats["avg_words"],
            total_chars=stats["avg_chars_no_space"],
            total_images=stats["avg_img_count"],
            report_json=json.dumps(result["ai_report"], ensure_ascii=False)
        )
        
        # 쿼터 차감
        increment_quota(current_user["sub"], current_user.get("role", "advertiser"), db)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_keyword_endpoint(keyword: str,
                                  current_user: dict = Depends(get_current_user),
                                  db: Session = Depends(get_db)):
    """
    네이버 키워드 검색 결과 리스트 추출 (체크박스 UI용)

    [방법 B] EXECUTION_MODE=cloud 이면 직접 스크래핑하지 않고 job을 적재한다.
    → 사용자 로컬 에이전트가 집 IP로 실행 후 결과 반환(클라우드 IP 차단/502 회피).
    설치형(local)에서는 기존처럼 인프로세스 즉시 실행.
    """
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        job_id = jobsvc.enqueue_job(db, current_user.get("sub"), "seo_search", {"keyword": keyword})
        return {"mode": "agent", "job_id": job_id}
    try:
        result = await analyzer.search_smart_blocks(keyword)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("SEARCH ERROR:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"내부 오류: {str(e)}")

@router.get("/history")
async def get_history_endpoint(db: Session = Depends(get_db)):
    """
    최근 검색 기록(최대 20개)을 불러오는 API
    """
    records = db.query(AnalysisHistory).order_by(AnalysisHistory.id.desc()).limit(20).all()
    history = []
    for r in records:
        try:
            data = json.loads(r.result_data)
            history.append({
                "id": r.id,
                "keyword": r.keyword,
                "created_at": r.created_at.isoformat(),
                "data": data
            })
        except:
            pass
    return history


@router.delete("/history/{record_id}", summary="검색 기록 1건 삭제")
async def delete_history_endpoint(record_id: int, db: Session = Depends(get_db)):
    rec = db.query(AnalysisHistory).filter(AnalysisHistory.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    db.delete(rec)
    db.commit()
    return {"success": True}


@router.delete("/history", summary="검색 기록 전체 삭제")
async def clear_history_endpoint(db: Session = Depends(get_db)):
    deleted = db.query(AnalysisHistory).delete()
    db.commit()
    return {"success": True, "deleted": deleted}


class CafeAnalysisRequest(BaseModel):
    keyword: str = ""       # 비우면 글 제목을 키워드로 사용
    content: str = ""       # 직접 붙여넣기(선택, 단일)
    url: str = ""           # 단일 URL (하위호환)
    urls: List[str] = []    # 다중 URL (최대 10) — 서버가 각 본문 자동 추출 후 해부

# ── 형태소(어절) 빈도 집계 ──────────────────────────────────────────────
# 본문에서 실제로 몇 번 쓰였는지를 세는 부분이라 AI 를 부르지 않는다.
# (AI 는 지표 해석만 맡는다 — 횟수를 AI 에게 물으면 매번 다른 값이 나온다)
#
# 형태소 분석기(konlpy·kiwi 등)는 동봉 런타임에 없다. 넣으려면 2.5GB 전체 재빌드가
# 필요해서, 조사·어미를 규칙으로 떼어내는 방식으로 근사한다. 명사 위주 카페 글에서는
# 이 정도로도 '어떤 말이 몇 번 나왔나'는 충분히 잡힌다.
_MORPH_STOPWORDS = {
    "이것", "저것", "그것", "그리고", "그래서", "그러나", "그런데", "하지만", "때문",
    "있습니다", "합니다", "하는", "입니다", "있는", "너무", "진짜", "정말", "생각",
    "매우", "아주", "많이", "조금", "약간", "그냥", "오늘", "내일", "어제", "우리",
    "지금", "가장", "어떤", "이런", "저런", "그런", "다른", "모든", "어떻게", "여기",
    "저기", "거기", "이번", "다음", "하나", "경우", "정도", "사람", "시간", "부분",
    # 네이버 카페·블로그 UI 단어 — 본문 추출 때 섞여 들어온다
    "블로그", "카페", "보기", "본문", "댓글", "이웃", "구독", "전체보기", "카테고리",
    "네이버", "공감", "스크랩", "공유", "신고", "작성일", "목록", "더보기", "접기",
    "이미지", "동영상", "글자", "배경", "링크", "파일", "게시글", "작성자", "조회",
    "좋아요", "프로필", "멤버", "닉네임", "첨부", "수정", "삭제", "답글",
}
# 길이가 긴 것부터 떼어내야 '에서'가 '에'로 잘못 잘리지 않는다.
_JOSA = ("에서는", "에서도", "으로는", "이라고", "라고는", "에게는", "한테는",
         "에서", "으로", "에게", "한테", "까지", "부터", "보다", "처럼", "이라",
         "라는", "이나", "거나", "지만", "는데", "면서",
         "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "도", "만", "로")
# 서술어(동사·형용사 활용형)는 키워드가 아니므로 통째로 버린다.
# '다녀왔습니다', '훌륭했고', '찾아봤는데요' 같은 말이 빈도 상위에 끼면 목록이 쓸모없어진다.
# ※ '고'·'서' 로 끝나는 2글자(광고·참고·재고…)는 명사라서 건드리지 않는다.
_VERB_TAILS = ("니다", "는데요", "던데요", "군요", "네요", "세요", "어요", "아요",
               "예요", "에요", "드려요", "했고", "하며", "하면", "해서", "아서",
               "어서", "려고", "니까", "는지", "았다", "었다", "했다", "한다",
               "이다", "된다", "있다", "없다", "같다", "싶다")


def _count_words(text: str):
    """본문의 어절 빈도표(collections.Counter)와 전체 어절 수를 돌려준다."""
    import collections
    import re as _re
    counter = collections.Counter()
    if not text:
        return counter, 0
    tokens = _re.findall(r"[가-힣]{2,}|[A-Za-z]{3,}", text)
    for t in tokens:
        w = t
        if _re.match(r"^[가-힣]+$", w):
            if any(w.endswith(v) for v in _VERB_TAILS):   # 서술어는 버린다
                continue
            for j in _JOSA:                       # 조사 떼기 (떼고도 2글자 이상일 때만)
                if w.endswith(j) and len(w) - len(j) >= 2:
                    w = w[: -len(j)]
                    break
        if len(w) < 2 or w in _MORPH_STOPWORDS:
            continue
        counter[w] += 1
    return counter, sum(counter.values())


def _count_in_text(text: str, phrase: str) -> int:
    """본문에 그 말이 몇 번 나왔는지. 띄어쓰기 차이('교대역 맛집'/'교대역맛집')를 흡수한다."""
    import re as _re
    if not text or not phrase:
        return 0
    parts = [_re.escape(p) for p in phrase.split() if p]
    if not parts:
        return 0
    return len(_re.findall(r"\s*".join(parts), text))


async def _extract_morphemes(text: str, keyword: str = "", top: int = 30) -> list:
    """검색 키워드와 '의미가 이어지는' 말만 골라 빈도와 함께 돌려준다.

    그냥 많이 나온 순으로 보여주면 '같이·이날·직접·앉아' 같은 말이 위로 올라와
    쓸모가 없다(실제 화면에서 그랬다). 그래서 두 단계로 나눈다.

      1) 어떤 말이 몇 번 나왔는지는 여기서 직접 센다 — AI 에게 물으면 실행할 때마다
         숫자가 달라진다.
      2) 그중 무엇이 이 키워드와 연관된 말인지는 SEO 분석기의 키워드 추출기가 고른다.
         (검색 의도 + 네이버 자동완성 연관어를 함께 보고 relevance 를 매긴다)

    반환: [{word, count, ratio, relevance}] — relevance 높은 순
    """
    if not text:
        return []
    counter, total = _count_words(text)
    total = total or 1

    kw = (keyword or "").strip()
    if not kw:
        # 키워드가 없으면 연관도를 따질 기준이 없다 → 빈도순 그대로
        return [{"word": w, "count": c, "ratio": round(c * 100 / total, 2), "relevance": None}
                for w, c in counter.most_common(top)]

    # 네이버 자동완성 연관어를 힌트로 준다(실패해도 무시).
    hints = []
    try:
        hints = (await analyzer.fetch_related_keywords(kw)) or []
    except Exception as e:
        print(f"[SEO] 연관어 조회 실패(무시): {e}")

    try:
        # 글 하나만 보는 분석이라 기본 12초로는 매번 시간초과가 난다(실측). 넉넉히 준다.
        ranked = await analyzer.extract_keywords_with_ai([text], main_keyword=kw,
                                                        related_hints=hints, timeout=45.0)
    except Exception as e:
        print(f"[SEO] 연관 키워드 추출 실패: {e}")
        ranked = []

    # 추출기가 돌려준 말을 그대로 쓰면 안 된다. 폴백 경로는 조사·어미가 붙은 채로
    # 나온다('중식을', '친구들과', '다녀왔어요', '층에'). 이건 형태소 목록으로 쓸 수 없다.
    # 그래서 위에서 조사를 떼고 서술어를 버려 만든 counter 와 교차시킨다.
    #   - 한 단어  : counter 에 그대로 있어야 통과 (= 조사·어미가 안 붙은 형태)
    #   - 복합어   : 본문에 실제로 나오면 통과 ('교대역 맛집' 처럼 가장 쓸모 있는 항목)
    out = []
    seen = set()
    for item in ranked:
        w = (item.get("keyword") or "").strip()
        if not w or w in seen:
            continue
        seen.add(w)
        if " " in w:
            c = _count_in_text(text, w)          # 복합어는 본문에서 직접 센다
        else:
            c = counter.get(w, 0)                # 정리된 어절에 있는 것만
        if c <= 0:
            continue
        rel = item.get("relevance")
        # 폴백 경로는 근거가 없으면 전부 50 을 준다. 그 50 을 그대로 보여주면
        # '층에·있고·가까워요' 같은 말이 '연관어'로 둔갑한다 → 신호 있는 것만 남긴다.
        if isinstance(rel, (int, float)) and rel <= 50:
            continue
        out.append({"word": w, "count": c, "ratio": round(c * 100 / total, 2), "relevance": rel})

    # 연관도만으로 걸러 너무 적게 남으면, 키워드 낱말을 품은 말로 채운다.
    # (예: 키워드 '교대역맛집' → '교대역', '맛집' 이 들어간 말은 확실히 연관이다)
    if len(out) < 5:
        import re as _re2
        kw_tokens = [t for t in _re2.split(r"[\s·,/]+", kw) if len(t) >= 2]
        if len(kw_tokens) == 1 and len(kw_tokens[0]) >= 4:
            # 붙여 쓴 키워드('교대역맛집')는 낱말을 못 나누므로 앞뒤 조각도 후보로 본다
            w0 = kw_tokens[0]
            kw_tokens += [w0[:i] for i in range(2, len(w0)) if len(w0[i:]) >= 2]
            kw_tokens += [w0[i:] for i in range(1, len(w0) - 1) if len(w0[i:]) >= 2]
        added = {x["word"] for x in out}
        for w, c in counter.most_common():
            if len(out) >= top or w in added:
                continue          # seen 이 아니라 added 로 본다 —
                                  # 연관도 50 으로 걸러진 말도 여기서 다시 볼 수 있어야 한다
            if any(t in w or w in t for t in kw_tokens):
                added.add(w)
                out.append({"word": w, "count": c, "ratio": round(c * 100 / total, 2),
                            "relevance": None})

    # 연관도 우선, 같으면 많이 나온 순
    out.sort(key=lambda x: (-(x.get("relevance") or 0), -x["count"]))
    out = out[:top]
    if out:
        return out
    # 추출이 통째로 실패하면 최소한 빈도순이라도 보여준다(빈 화면보다 낫다).
    return [{"word": w, "count": c, "ratio": round(c * 100 / total, 2), "relevance": None}
            for w, c in counter.most_common(top)]


async def run_cafe_post_analysis(request: CafeAnalysisRequest):
    """네이버 카페/블로그 상위노출 글 4대 블랙박스 해부 (로컬 실행 본체).
    엔드포인트(local)·에이전트(cloud) 양쪽에서 공용 호출."""
    from mbam_nextgen.services.soul import SoulRewriter

    base_keyword = (request.keyword or "").strip()

    def _is_cafe(u: str, detail: dict = None) -> bool:
        if detail and "카페" in (detail.get("text_type") or ""):
            return True
        return "cafe.naver.com" in (u or "")

    async def _dissect(content: str, kw: str, is_cafe: bool = True):
        soul = SoulRewriter()
        if is_cafe:
            return await soul.analyze_cafe_cheat_keys(kw or "카페글 분석", content)
        return await soul.analyze_blog_seo_keys(kw or "블로그글 분석", content)

    # ── 다중 URL 모드 ──────────────────────────────────────────
    if request.urls:
        url_list = [u.strip() for u in request.urls if (u or "").strip().startswith("http")][:10]
        if not url_list:
            raise HTTPException(status_code=400, detail="유효한 카페 URL을 1개 이상 입력해주세요.")
        try:
            extracted = await analyzer.analyze_multiple_urls(url_list)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"본문 추출 실패: {e}")

        sem = asyncio.Semaphore(4)  # AI 동시 호출 제한(타임아웃 방지)

        async def _one(u: str):
            detail = extracted.get(u)
            if not detail or "error" in (detail or {}):
                return {"_error": {"url": u, "error": (detail or {}).get("error", "본문을 가져올 수 없습니다.")}}
            content = (detail.get("full_text") or detail.get("text_sample") or "").strip()
            if not content:
                return {"_error": {"url": u, "error": "본문이 비어 있습니다."}}
            kw = base_keyword or (detail.get("title") or "").strip()
            is_cafe = _is_cafe(u, detail)
            async with sem:
                try:
                    data = await _dissect(content, kw, is_cafe=is_cafe)
                except Exception as e:
                    return {"_error": {"url": u, "error": f"분석 오류: {e}"}}
            return {"url": u, "title": detail.get("title", ""), "used_keyword": kw,
                    "text_type": detail.get("text_type", "네이버 카페" if is_cafe else "네이버 블로그"),
                    "content_chars": len(content), "data": data,
                    "morphemes": await _extract_morphemes(content, kw)}

        results = await asyncio.gather(*[_one(u) for u in url_list])
        items = [r for r in results if "_error" not in r]
        errors = [r["_error"] for r in results if "_error" in r]
        return {"items": items, "errors": errors}

    # ── 단일 모드 (하위호환) ───────────────────────────────────
    content = (request.content or "").strip()
    url = (request.url or "").strip()
    keyword = base_keyword
    detail_single = None
    if url and not content:
        try:
            results = await analyzer.analyze_multiple_urls([url])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"본문 추출 실패: {e}")
        detail_single = results.get(url) or next(iter(results.values()), None)
        if not detail_single or "error" in (detail_single or {}):
            raise HTTPException(status_code=400, detail=(detail_single or {}).get("error", "본문을 가져올 수 없습니다."))
        content = (detail_single.get("full_text") or detail_single.get("text_sample") or "").strip()
        if not keyword:
            keyword = (detail_single.get("title") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="분석할 본문이 없습니다. URL 또는 본문을 입력해주세요.")
    is_cafe = _is_cafe(url, detail_single) if url else True
    try:
        result = await _dissect(content, keyword, is_cafe=is_cafe)
        return {"success": True, "data": result, "used_keyword": keyword or ("카페글 분석" if is_cafe else "블로그글 분석"),
                "text_type": (detail_single or {}).get("text_type", "네이버 카페" if is_cafe else "네이버 블로그"),
                "content_chars": len(content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"본문 해부 분석 오류: {str(e)}")


@router.post("/analyze-cafe-post")
async def analyze_cafe_post_endpoint(request: CafeAnalysisRequest,
                                     current_user: dict = Depends(get_current_user),
                                     db: Session = Depends(get_db)):
    """[방법 B] cloud 모드면 job 적재 → 로컬 에이전트가 집 IP로 본문 추출·해부."""
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        return {"mode": "agent", "job_id": jobsvc.enqueue_job(db, current_user.get("sub"), "seo_cafe_post", {
            "keyword": request.keyword, "content": request.content,
            "url": request.url, "urls": request.urls,
        })}
    return await run_cafe_post_analysis(request)
