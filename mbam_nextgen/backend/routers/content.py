from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import os
import json
from mbam_nextgen.services.gov_data import GovDataCollector
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

@router.post("/refresh")
async def refresh_category(request: CategoryRequest):
    """
    특정 카테고리의 데이터를 실시간으로 재수집 (Gemini AI 또는 API)
    """
    try:
        data = await collector.fetch_data(request.category)
        if data:
            collector.save_cache(request.category, data)
            return {"message": "수집 완료", "count": len(data), "last_sync": collector.get_cache_time(request.category)}
        else:
            raise HTTPException(status_code=500, detail="데이터 수집에 실패했습니다.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
