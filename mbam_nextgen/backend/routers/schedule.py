from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3
import os
from mbam_nextgen.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/api/schedule", tags=["Schedule"])
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ranking.db")

def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS scheduler_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            hour INTEGER NOT NULL,
            minute INTEGER NOT NULL
        )
    ''')
    # Default to 10:00 if not exists
    c.execute("INSERT OR IGNORE INTO scheduler_config (id, hour, minute) VALUES (1, 10, 0)")
    conn.commit()
    conn.close()

init_db()

class ScheduleTimeRequest(BaseModel):
    hour: int
    minute: int

@router.get("/time")
def get_schedule_time():
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT hour, minute FROM scheduler_config WHERE id=1")
        row = c.fetchone()
        conn.close()
        
        if row:
            return {"success": True, "hour": row[0], "minute": row[1]}
        return {"success": True, "hour": 10, "minute": 0}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/time")
def update_schedule_time(req: ScheduleTimeRequest):
    try:
        if req.hour < 0 or req.hour > 23 or req.minute < 0 or req.minute > 59:
            raise ValueError("Invalid time format")

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("UPDATE scheduler_config SET hour=?, minute=? WHERE id=1", (req.hour, req.minute))
        conn.commit()
        conn.close()
        
        # 스케줄러 동적 업데이트
        scheduler_service.update_schedule(req.hour, req.minute)
        
        return {"success": True, "message": f"스케줄러가 매일 {req.hour:02d}:{req.minute:02d} 작동으로 변경되었습니다."}
    except Exception as e:
        return {"success": False, "error": str(e)}
