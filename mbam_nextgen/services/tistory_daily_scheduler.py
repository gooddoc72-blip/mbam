"""[클라우드 모드] 티스토리 매일 자동발행 스케줄러.

티스토리는 공식 API가 없어 브라우저 자동화로만 발행되고, 데이터센터 IP 차단 때문에
클라우드에선 직접 못 돈다. 그래서 예약 시각이 되면 '에이전트 잡'으로 적재만 하고,
로컬 에이전트(집 IP·영구 프로필 로그인)가 claim 해 실제 발행한다.

- 분 단위 due 점검(하루 1회, last_run_date) + catch-up.
- 글감은 글감수집 캐시(네이버와 공유)에서 뽑아 payload 에 실어 보낸다(에이전트엔 캐시 없음).
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mbam_nextgen.backend.database import SessionLocal, TistorySchedule, TistoryAccount
from mbam_nextgen.backend import jobs as jobsvc

logger = logging.getLogger("TistoryDailyScheduler")
KST = ZoneInfo("Asia/Seoul")


def enqueue_due_tistory():
    if not jobsvc.is_cloud_mode():
        return
    now = datetime.now(KST)
    hhmm = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")
    db = SessionLocal()
    try:
        due = (db.query(TistorySchedule)
               .filter(TistorySchedule.is_active == 1, TistorySchedule.schedule_time <= hhmm)
               .all())
        due = [s for s in due if s.schedule_time and s.last_run_date != today]
        if not due:
            return

        from mbam_nextgen.services.gov_data import GovDataCollector
        collector = GovDataCollector()
        total = 0
        for s in due:
            acc = db.query(TistoryAccount).filter(TistoryAccount.id == s.account_id).first()
            if not acc:
                s.last_run_date = today
                continue
            try:
                items = collector.load_cache(s.content_category) or [] if s.content_category else []
            except Exception:
                items = []
            if not items:
                logger.warning(f"[TistoryDaily] '{s.content_category}' 글감 없음 — 발행 보류(글감수집 필요)")
                continue  # 글감 없으면 last_run_date 안 찍어 오늘 재시도
            qty = max(1, s.post_count_per_day or 1)
            start = (s.last_index or 0) % len(items)
            for i in range(qty):
                item = items[(start + i) % len(items)]
                title = item.get("title", "정보 제공")
                payload = {
                    "schedule_id": s.id,
                    "account_id": acc.id,
                    "blog_name": acc.blog_name,
                    "keyword": title,
                    "title": title,
                    "content": item.get("content", ""),
                    "ai_provider": s.ai_provider or "gemini",
                }
                jobsvc.enqueue_job(db, s.user_id, "tistory_post", payload, priority=7)
                total += 1
            s.last_index = (start + qty) % len(items)
            s.last_run_date = today
        db.commit()
        if total:
            logger.info(f"[TistoryDaily] {hhmm} KST — 티스토리 발행 잡 {total}건 적재")
    except Exception as e:
        logger.error(f"[TistoryDaily] 적재 실패: {e}")
    finally:
        db.close()


class TistoryDailyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.add_job(
            enqueue_due_tistory,
            CronTrigger(second=25, timezone="Asia/Seoul"),
            id="tistory_daily_enqueue", replace_existing=True,
            misfire_grace_time=120, coalesce=True,
        )
        self.scheduler.start()
        logger.info("TistoryDaily scheduler started — 매 분 KST 티스토리 예약 점검·적재.")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


tistory_daily_scheduler = TistoryDailyScheduler()
