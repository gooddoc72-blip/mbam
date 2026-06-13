from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
from mbam_nextgen.services.seo_analyzer_v2 import SeoAnalyzerV2
from mbam_nextgen.infrastructure.database import DatabaseManager
from mbam_nextgen.backend.database import get_db
from mbam_nextgen.backend.models import AnalysisHistory
from mbam_nextgen.backend.quota import check_quota, increment_quota
import json

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
async def analyze_keyword_endpoint(request: AnalyzeRequest, db: Session = Depends(get_db)):
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
        increment_quota(current_user["sub"], db)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_keyword_endpoint(keyword: str):
    """
    네이버 키워드 검색 결과 리스트 추출 (체크박스 UI용)
    """
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

class CafeAnalysisRequest(BaseModel):
    keyword: str
    content: str

@router.post("/analyze-cafe-post")
async def analyze_cafe_post_endpoint(request: CafeAnalysisRequest):
    """
    네이버 카페 상위노출 글의 4대 블랙박스 로직 + 작성자 영향력을 분석하는 API
    """
    from mbam_nextgen.services.soul import SoulRewriter
    soul_rewriter = SoulRewriter()
    
    try:
        result = await soul_rewriter.analyze_cafe_cheat_keys(request.keyword, request.content)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카페글 분석 오류: {str(e)}")
