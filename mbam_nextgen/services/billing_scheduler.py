# -*- coding: utf-8 -*-
"""[클라우드 모드] 정기결제 스케줄러 — 10분마다 결제일이 된 구독을 자동 결제한다.

결제 로직은 services/billing.py 의 charge_due 에 있다. 여기는 주기 실행만 맡는다.
토스 키가 없으면(결제 미설정) 아무것도 하지 않는다.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from mbam_nextgen.backend.database import SessionLocal
from mbam_nextgen.services import billing

logger = logging.getLogger("BillingScheduler")

_running = False   # 결제 API 가 느릴 때 다음 주기와 겹치지 않게


async def run_billing_cycle():
    global _running
    if _running or not billing.enabled():
        return
    _running = True
    db = SessionLocal()
    try:
        await billing.charge_due(db)
    except Exception as e:
        logger.error(f"[Billing] 정기결제 처리 실패: {e}")
    finally:
        db.close()
        _running = False


class BillingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.add_job(run_billing_cycle, IntervalTrigger(minutes=10),
                               id="billing_cycle", replace_existing=True, max_instances=1)
        self.scheduler.start()
        logger.info("[Billing] 정기결제 스케줄러 시작 (10분 주기)")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)


billing_scheduler = BillingScheduler()
