"""[방법 B] 클라우드 ↔ 로컬 에이전트 작업 큐 헬퍼.

핵심 아이디어:
  - 클라우드(Railway)는 네이버를 직접 못 긁으므로(데이터센터 IP 차단), 작업을 DB에 적재만 한다.
  - 사용자 PC의 로컬 에이전트가 폴링으로 claim → 집 IP로 Playwright 실행 → 결과 반환.
  - 설치형(EXECUTION_MODE=local)은 큐를 쓰지 않고 인프로세스로 즉시 실행(기존 동작 유지).

EXECUTION_MODE:
  - "local"  (기본) : 설치형 — 트리거 시 인프로세스 즉시 실행
  - "cloud"          : 웹 배포 — 트리거 시 job을 queued로 적재하고 에이전트가 처리
"""
import os
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from mbam_nextgen.backend.database import AgentJob


# ── DB 동기화(영속화) 훅 ──────────────────────────────────────────────
# 추적/히스토리 계열 job은 에이전트가 집 IP로 스크래핑한 결과를 반환하고,
# 여기 등록된 영속화 함수가 그 결과를 클라우드 DB(Postgres)에 기록한다.
# → 웹의 관심목록/일자별 히스토리 탭이 클라우드에서 그대로 조회 가능.
#   fn 시그니처: (db, user_id: str, payload: dict, result: dict) -> None
PERSISTERS = {}


def register_persister(job_type: str, fn):
    PERSISTERS[job_type] = fn


def execution_mode() -> str:
    return (os.environ.get("EXECUTION_MODE", "local") or "local").strip().lower()


def is_cloud_mode() -> bool:
    return execution_mode() == "cloud"


def enqueue_job(db: Session, user_id: str, job_type: str, payload: dict, priority: int = 5) -> str:
    """작업을 queued 상태로 적재하고 job_id 반환.
    priority: 낮을수록 먼저 처리 — 실시간(사용자 클릭) 5, 새벽 일괄배치 9.
    배치가 큐를 채워도 실시간 요청이 항상 먼저 실행되게 한다."""
    job = AgentJob(
        id=str(uuid.uuid4()),
        user_id=user_id,
        job_type=job_type,
        payload=json.dumps(payload or {}, ensure_ascii=False),
        priority=priority,
        status="queued",
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    return job.id


def claim_next_job(db: Session, user_id: str, agent_id: str = None) -> Optional[AgentJob]:
    """해당 유저의 가장 오래된 queued 작업 1건을 running 으로 선점(claim)해 반환.
    단일 유저-단일 에이전트를 전제로 단순 트랜잭션 사용(다중 에이전트 경합은 P4에서 SKIP LOCKED 고려)."""
    job = (
        db.query(AgentJob)
        .filter(AgentJob.user_id == user_id, AgentJob.status == "queued")
        .order_by(AgentJob.priority.asc(), AgentJob.created_at.asc())
        .first()
    )
    if not job:
        return None
    job.status = "running"
    job.agent_id = agent_id
    job.claimed_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job


def complete_job(db: Session, job_id: str, user_id: str, status: str,
                 result: dict = None, error: str = None) -> bool:
    """에이전트가 결과 반환. status: 'done' | 'error'."""
    job = (
        db.query(AgentJob)
        .filter(AgentJob.id == job_id, AgentJob.user_id == user_id)
        .first()
    )
    if not job:
        return False
    job.status = status if status in ("done", "error") else "error"
    if result is not None:
        job.result = json.dumps(result, ensure_ascii=False)
    if error:
        job.error = str(error)[:2000]
    job.finished_at = datetime.utcnow()

    # DB 동기화: 완료된 결과를 클라우드 DB에 영속화(등록된 job_type만)
    if job.status == "done" and result is not None and job.job_type in PERSISTERS:
        try:
            payload = json.loads(job.payload) if job.payload else {}
        except Exception:
            payload = {}
        try:
            PERSISTERS[job.job_type](db, user_id, payload, result)
        except Exception as e:
            print(f"[jobs] 영속화 실패({job.job_type}): {e}")

    db.commit()
    return True


def get_job(db: Session, job_id: str, user_id: str) -> Optional[dict]:
    """프론트 폴링용 — 작업 상태/결과 조회(소유자 스코프)."""
    job = (
        db.query(AgentJob)
        .filter(AgentJob.id == job_id, AgentJob.user_id == user_id)
        .first()
    )
    if not job:
        return None
    out = {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
    if job.status == "done" and job.result:
        try:
            out["result"] = json.loads(job.result)
        except Exception:
            out["result"] = None
    if job.status == "error":
        out["error"] = job.error
    return out
