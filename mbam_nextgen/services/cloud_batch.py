"""[방법 B] 클라우드 모드 전용 — 새벽 5시(KST) 추적목록 일괄 '적재' 스케줄러.

클라우드(Railway)는 네이버를 직접 못 긁으므로(데이터센터 IP 차단) 여기서는
실행하지 않고, 추적목록을 에이전트 작업 큐(AgentJob)에 적재만 한다.
사용자 PC의 로컬 에이전트가 폴링으로 claim → 집 IP로 실행 → 결과는
jobs.PERSISTERS 훅(place_analyze / shopping_analyze)이 클라우드 DB에 영속화.
새벽에 에이전트 PC가 꺼져 있어도 잡이 큐에 남아, 켜지는 즉시 처리된다(자연 보충).
"""
import os
import json
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mbam_nextgen.backend.database import SessionLocal, PlaceTracked, ShoppingTrackedItem, AgentJob
from mbam_nextgen.backend import jobs as jobsvc

logger = logging.getLogger("CloudBatch")

BATCH_HOUR, BATCH_MINUTE = 5, 0  # KST


def _pending_keys(db, job_type: str) -> set:
    """이미 대기/실행 중인 같은 유형 잡의 (keyword, mid) 집합 — 에이전트가 며칠
    꺼져 있던 경우 같은 잡이 매일 쌓이는 것을 방지."""
    keys = set()
    rows = (db.query(AgentJob)
            .filter(AgentJob.job_type == job_type, AgentJob.status.in_(("queued", "running")))
            .all())
    for j in rows:
        try:
            p = json.loads(j.payload or "{}")
        except Exception:
            continue
        keys.add((p.get("keyword"), p.get("target_mid") or p.get("mid")))
    return keys


def _shopping_owner(db) -> Optional[str]:
    """쇼핑 추적목록은 전역 테이블(user_id 없음)이라, 잡을 받아 갈 계정을 정한다.
    BATCH_SHOPPING_USER 환경변수(이메일) 우선, 없으면 최근 에이전트 활동 계정."""
    uid = (os.environ.get("BATCH_SHOPPING_USER") or "").strip()
    if uid:
        return uid
    j = (db.query(AgentJob).filter(AgentJob.agent_id.isnot(None))
         .order_by(AgentJob.created_at.desc()).first())
    return j.user_id if j else None


def enqueue_daily_batch():
    db = SessionLocal()
    try:
        # 1) 플레이스: 유저별 추적목록 → place_analyze 잡
        pend = _pending_keys(db, "place_analyze")
        n_place = 0
        for r in db.query(PlaceTracked).all():
            if (r.keyword, r.mid) in pend:
                continue
            jobsvc.enqueue_job(db, r.user_id, "place_analyze", {
                "keyword": r.keyword, "target_mid": r.mid,
                "compare_days": 1, "force_refresh": True,
            })
            pend.add((r.keyword, r.mid))
            n_place += 1

        # 2) 쇼핑: 전역 추적목록 → shopping_analyze 잡 (에이전트 운영 계정 큐로)
        n_shop = 0
        items = db.query(ShoppingTrackedItem).all()
        if items:
            owner = _shopping_owner(db)
            if not owner:
                logger.warning("쇼핑 일괄수집을 받을 에이전트 계정을 찾지 못해 스킵 "
                               "(BATCH_SHOPPING_USER 환경변수로 지정 가능)")
            else:
                pend = _pending_keys(db, "shopping_analyze")
                for it in items:
                    if (it.keyword, it.mid) in pend:
                        continue
                    jobsvc.enqueue_job(db, owner, "shopping_analyze", {
                        "keyword": it.keyword, "target_mid": it.mid, "tracked_id": it.id,
                    })
                    pend.add((it.keyword, it.mid))
                    n_shop += 1
        logger.info(f"[CloudBatch] 일괄 적재 완료 — 플레이스 {n_place}건, 쇼핑 {n_shop}건")
    except Exception as e:
        logger.error(f"[CloudBatch] 일괄 적재 실패: {e}")
    finally:
        db.close()


class CloudBatchScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.add_job(
            enqueue_daily_batch,
            CronTrigger(hour=BATCH_HOUR, minute=BATCH_MINUTE, timezone="Asia/Seoul"),
            id="cloud_daily_enqueue", replace_existing=True,
            misfire_grace_time=3600, coalesce=True,
        )
        self.scheduler.start()
        logger.info(f"CloudBatch scheduler started — 매일 {BATCH_HOUR:02d}:{BATCH_MINUTE:02d} KST 추적목록 큐 적재.")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


cloud_batch_scheduler = CloudBatchScheduler()
