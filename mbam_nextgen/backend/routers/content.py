from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import os
import json
from mbam_nextgen.services.gov_data import GovDataCollector
from mbam_nextgen.services import golden_keyword
from mbam_nextgen.backend.database import SessionLocal, ContentSchedule
from mbam_nextgen.services.scheduler_service import scheduler_service

router = APIRouter()
collector = GovDataCollector()

class CategoryRequest(BaseModel):
    category: str

class ScheduleRequest(BaseModel):
    schedule_time: str
    interest_categories: list[str] = []

@router.get("/schedule")
async def get_schedule():
    db = SessionLocal()
    try:
        sch = db.query(ContentSchedule).first()
        if not sch:
            sch = ContentSchedule(schedule_time="09:00")
            db.add(sch)
            db.commit()
            db.refresh(sch)
        return {
            "schedule_time": sch.schedule_time,
            "interest_categories": sch.interest_categories.split(",") if sch.interest_categories else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/schedule")
async def update_schedule(req: ScheduleRequest):
    db = SessionLocal()
    try:
        sch = db.query(ContentSchedule).first()
        if not sch:
            sch = ContentSchedule(
                schedule_time=req.schedule_time,
                interest_categories=",".join(req.interest_categories)
            )
            db.add(sch)
        else:
            sch.schedule_time = req.schedule_time
            sch.interest_categories = ",".join(req.interest_categories)
        db.commit()
        
        # 스케줄러 즉시 반영
        scheduler_service.update_content_schedule(req.schedule_time)
        return {
            "message": "설정이 저장되었습니다.", 
            "schedule_time": req.schedule_time,
            "interest_categories": req.interest_categories
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/categories")
async def get_categories():
    """
    모든 카테고리 목록과 시스템 동기화 상태 반환
    """
    try:
        categories = list(collector.CATEGORIES.keys())
        
        # 시스템 동기화 상태 읽기
        sched_file = "mbam_nextgen/data/scheduler_state.json"
        full_sync_time = "기록 없음"
        if os.path.exists(sched_file):
            try:
                with open(sched_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    st_time = data.get("last_success", "")
                    if st_time:
                        full_sync_time = st_time # 프론트엔드에서 포맷팅
            except:
                pass

        return {
            "categories": categories,
            "full_sync_time": full_sync_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def get_category_list(category: str):
    """
    특정 카테고리의 저장된 항목 목록과 마지막 업데이트 시간을 반환
    """
    try:
        items = collector.load_cache(category) or collector.SAMPLE_DATA
        filtered_items = [i for i in items if i.get("category") == category]
        filtered_items.sort(key=lambda x: x.get("priority", 99))
        
        last_sync = collector.get_cache_time(category)
        
        return {
            "items": filtered_items,
            "last_sync": last_sync
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 카테고리별 실시간 수집 작업 상태 (in-memory)
# Gemini 리서치가 30~40초+ 걸려 동기 응답 시 dev 프록시(30s)·게이트웨이 타임아웃에 걸림.
# → 작업을 백그라운드로 띄우고 프론트는 /refresh/status 로 폴링한다.
# { category: {"status": "running"|"done"|"error", "count": int, "last_sync": str|None, "error": str|None} }
_refresh_jobs: dict[str, dict] = {}


async def _run_refresh(category: str):
    """백그라운드 수집 작업 — fetch_data(blocking 부분은 to_thread) 후 상태 갱신."""
    try:
        data = await collector.fetch_data(category)
        if data:
            collector.save_cache(category, data)
            _refresh_jobs[category] = {
                "status": "done",
                "count": len(data),
                "last_sync": collector.get_cache_time(category),
                "error": None,
            }
        else:
            _refresh_jobs[category] = {
                "status": "error",
                "count": 0,
                "last_sync": collector.get_cache_time(category),
                "error": "데이터 수집에 실패했습니다.",
            }
    except Exception as e:
        _refresh_jobs[category] = {
            "status": "error",
            "count": 0,
            "last_sync": collector.get_cache_time(category),
            "error": str(e),
        }


@router.post("/refresh")
async def refresh_category(request: CategoryRequest):
    """
    특정 카테고리 데이터 재수집을 '시작'만 하고 즉시 반환한다 (Gemini AI 또는 API).
    실제 완료 여부는 GET /refresh/status?category=... 로 폴링한다.
    """
    category = request.category
    job = _refresh_jobs.get(category)
    if job and job.get("status") == "running":
        # 이미 진행 중이면 중복 작업을 만들지 않고 현재 상태를 알린다.
        return {"status": "running", "message": "이미 수집이 진행 중입니다."}

    _refresh_jobs[category] = {"status": "running", "count": 0, "last_sync": None, "error": None}
    asyncio.create_task(_run_refresh(category))
    return {"status": "running", "message": "수집을 시작했습니다."}


@router.get("/refresh/status")
async def refresh_status(category: str):
    """실시간 수집 작업의 현재 상태 반환 (폴링용). 기록이 없으면 idle."""
    job = _refresh_jobs.get(category)
    if not job:
        return {"status": "idle"}
    return job


@router.get("/golden")
async def get_golden(category: str):
    """저장된 황금키워드 추천 결과 반환 (메뉴 이동/재접속 후 복원용). 없으면 빈 결과."""
    cached = golden_keyword.load_cache(category)
    if cached and cached.get("keywords"):
        return {**cached, "cached": True}
    return {"keywords": [], "seed": [], "candidate_count": 0, "cached": False}


@router.post("/golden")
async def golden_keywords(request: CategoryRequest):
    """
    수집된 글감을 시드로 황금키워드(검색량 高 / 문서수 低) 추천 후 결과를 캐시에 저장.
    각 키워드의 월검색량·경쟁도·블로그/카페 문서수·황금점수·추천채널 반환.
    """
    if not golden_keyword.has_keys():
        raise HTTPException(status_code=400, detail="네이버 검색광고/오픈API 키가 설정되지 않았습니다.")

    items = [i for i in (collector.load_cache(request.category) or []) if i.get("category") == request.category]
    if not items:
        raise HTTPException(status_code=400, detail="먼저 글감을 수집해주세요.")

    try:
        result = await golden_keyword.analyze(request.category, items, max_candidates=12)
        return golden_keyword.save_cache(request.category, result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
