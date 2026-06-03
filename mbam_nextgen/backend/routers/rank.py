from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import asyncio
from typing import List, Optional
import re

from mbam_nextgen.infrastructure.db_ranking import RankingDB
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

router = APIRouter()
db = RankingDB()
analyzer = SeoAnalyzer()

class AddKeywordRequest(BaseModel):
    blog_id: str
    keyword: str

class KeywordIdRequest(BaseModel):
    keyword_id: int

@router.get("/keywords")
async def get_tracked_keywords():
    """
    현재 추적 중인 모든 키워드와 최신 순위 이력을 반환합니다.
    """
    try:
        keywords = db.get_keywords()
        table_data = []
        for kw_id, blog_id, kw in keywords:
            history = db.get_history(kw_id, days=1)
            current_rank = "-"
            check_date = "-"
            
            if history:
                rank_val = history[0][1]
                check_date = history[0][0]
                current_rank = f"{rank_val}위" if rank_val > 0 else "75위 권외"
                
            table_data.append({
                "id": kw_id,
                "blog_id": blog_id,
                "keyword": kw,
                "rank": current_rank,
                "date": check_date,
                "rank_val": history[0][1] if history else -1
            })
        return {"data": table_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add")
async def add_keyword(request: AddKeywordRequest):
    """
    블로그 ID와 키워드를 DB에 추가하고 최초 실시간 순위를 가져옵니다.
    """
    clean_blog_id = request.blog_id.strip()
    if "blog.naver.com/" in clean_blog_id:
        match = re.search(r'blog\.naver\.com/([^/]+)', clean_blog_id)
        if match:
            clean_blog_id = match.group(1)

    added = db.add_keyword(clean_blog_id, request.keyword)
    if not added:
        raise HTTPException(status_code=400, detail="이미 등록된 키워드입니다.")

    try:
        # 최초 실시간 조회
        res = await analyzer.track_my_ranking(clean_blog_id, request.keyword)
        rank = res.get("rank", -1)
        
        # 방금 넣은 키워드의 ID 다시 조회
        kws = db.get_keywords(clean_blog_id)
        k_id = None
        for item in kws:
            if item[2] == request.keyword:
                k_id = item[0]
                break
                
        if k_id is not None:
            db.add_history(k_id, rank)
            
        return {"message": "등록 및 조회 성공", "rank": rank, "id": k_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"순위 조회 중 오류 발생: {str(e)}")

@router.post("/refresh")
async def refresh_keyword(request: KeywordIdRequest):
    """
    특정 키워드의 순위를 다시 조회하여 DB를 업데이트합니다.
    """
    try:
        keywords = db.get_keywords()
        target = next((item for item in keywords if item[0] == request.keyword_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다.")
            
        blog_id, keyword = target[1], target[2]
        res = await analyzer.track_my_ranking(blog_id, keyword)
        rank = res.get("rank", -1)
        
        db.add_history(request.keyword_id, rank)
        
        return {"message": "갱신 성공", "rank": rank}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete")
async def delete_keyword(request: KeywordIdRequest):
    """
    추적 중인 키워드를 삭제합니다.
    """
    try:
        db.remove_keyword(request.keyword_id)
        return {"message": "삭제 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
