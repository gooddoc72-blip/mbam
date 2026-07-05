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
async def blog_index_endpoint(request: BlogIndexRequest):
    """모바일 공개 엔드포인트를 스크래핑해 블로그 지수(추정)·등급·티어·레벨을 산출. (네이버 공식 지수 아님)"""
    from mbam_nextgen.services.blog_index import analyze_blog
    blog = (request.blog or "").strip()
    if not blog:
        raise HTTPException(status_code=400, detail="블로그 ID 또는 URL을 입력하세요.")
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
async def analyze_cafe_urls_endpoint(request: CafeUrlsRequest):
    """카페 글 URL 권위 분석.

    키워드 불필요. 각 카페 URL 의 작성자/카페 권위 데이터(cafe_author_info)
    + 본문 통계를 일괄 추출한다. /api/seo/analyze 와 달리 키워드 기반 SEO
    분석은 수행하지 않는다 (카페글 분석 메뉴 전용).
    """
    if not request.urls:
        raise HTTPException(status_code=400, detail="URL 을 1개 이상 제공해주세요.")
    if len(request.urls) > 5:
        raise HTTPException(status_code=400, detail="한 번에 최대 5개 URL 까지 분석 가능합니다.")

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
async def analyze_keyword_endpoint(request: AnalyzeRequest, db: Session = Depends(get_db), _q: dict = Depends(consume_generation_quota)):
    """
    네이버 키워드 SEO 정밀 분석 API
    - 키워드 검색 결과 상위 10개 추출
    - 각 포스팅 상세 크롤링 (이미지 수, 글자 수, 키워드 추출 등)
    - 상위노출 가이드라인(Winning Formula) 생성
    """
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
    """
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

@router.post("/analyze-cafe-post")
async def analyze_cafe_post_endpoint(request: CafeAnalysisRequest):
    """
    네이버 카페 상위노출 글의 4대 블랙박스 로직 + 작성자 영향력 분석.
    - urls[](최대 10): 각 URL 본문을 자동 추출해 동시 해부 → {items, errors}
    - url / content(단일, 하위호환): {success, data}
    """
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
                    "content_chars": len(content), "data": data}

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
