"""[방법 B] 로컬 에이전트 ↔ 클라우드 연동 라우터.

  GET  /api/agent/next-job        : 내 작업 1건 선점(claim) — 로컬 에이전트가 폴링
  POST /api/agent/job-result      : 실행 결과 반환
  GET  /api/agent/jobs/{job_id}   : 작업 상태/결과 조회 — 웹 프론트가 폴링

모든 엔드포인트는 로그인 유저(JWT) 기준. 에이전트는 사용자 계정으로 로그인해 토큰을 얻는다.
"""
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mbam_nextgen.backend.database import get_db
from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.backend import jobs as jobsvc

router = APIRouter(prefix="/api/agent", tags=["Local Agent"])


@router.get("/next-job", summary="로컬 에이전트: 내 작업 선점")
async def next_job(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db),
                   agent_id: Optional[str] = None):
    user_id = current_user.get("sub")
    job = jobsvc.claim_next_job(db, user_id, agent_id=agent_id)
    if not job:
        return {"job": None}
    import json
    try:
        payload = json.loads(job.payload) if job.payload else {}
    except Exception:
        payload = {}
    return {"job": {"job_id": job.id, "job_type": job.job_type, "payload": payload}}


class JobResult(BaseModel):
    job_id: str
    status: str = "done"          # "done" | "error"
    result: Optional[dict] = None
    error: Optional[str] = None


@router.post("/job-result", summary="로컬 에이전트: 작업 결과 반환")
async def job_result(body: JobResult, current_user: dict = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    user_id = current_user.get("sub")
    ok = jobsvc.complete_job(db, body.job_id, user_id, body.status,
                             result=body.result, error=body.error)
    return {"success": ok}


@router.get("/jobs/{job_id}", summary="웹 프론트: 작업 상태/결과 폴링")
async def job_status(job_id: str, current_user: dict = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    user_id = current_user.get("sub")
    info = jobsvc.get_job(db, job_id, user_id)
    if not info:
        return {"status": "not_found"}
    return info


class TaskLog(BaseModel):
    task_id: str
    line: Optional[str] = None
    status: Optional[str] = None   # "running" | "completed" | "failed"


@router.post("/task-log", summary="로컬 에이전트: 실행 로그·상태를 클라우드로 중계")
async def task_log(body: TaskLog, current_user: dict = Depends(get_current_user)):
    """에이전트가 위임받은 작업(카페 댓글 등)의 진행 로그·최종 상태를 task_status_store 에 반영.
    웹 프론트는 기존 /api/cafe-nurture/status/{task_id} 폴링으로 그대로 로그를 본다."""
    from mbam_nextgen.backend.routers.auto_post import task_status_store
    entry = task_status_store.setdefault(body.task_id, {"status": "running", "logs": []})
    if body.line:
        entry["logs"].append(body.line)
    if body.status:
        entry["status"] = body.status
    return {"ok": True}
