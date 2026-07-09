"""[클라우드 모드] 글감 자동 수집 스케줄러.

로컬 모드는 scheduler_service.run_content_sync_job 이 담당하지만, 클라우드(Railway)에선
scheduler_service 가 기동되지 않아 글감 자동수집이 전혀 안 됐다. 정부/공공 데이터 수집은
네이버 스크래핑이 아니라 데이터센터 IP에서도 가능하므로, 이 경량 스케줄러가 서버에서 직접
ContentSchedule.schedule_time 에 전체 카테고리 글감을 수집(캐시 저장)한다.

- 매 분 KST 로 due(예약 시각이 지났고 오늘 아직 수집 안 함)를 점검 → catch-up 지원.
- 수집이 수 분 걸릴 수 있어 _running 플래그로 중복 실행 방지, last_run_time 을 착수 시 먼저 찍어
  (비용이 큰) 재수집이 하루 1회로 제한되게 한다.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mbam_nextgen.backend.database import SessionLocal, ContentSchedule
from mbam_nextgen.backend import jobs as jobsvc

logger = logging.getLogger("ContentDailyScheduler")
KST = ZoneInfo("Asia/Seoul")

_running = False  # 수집이 1분 넘게 걸릴 수 있어 중복 실행 방지


async def collect_due_content():
    """예약 시각이 된 글감 자동수집을 서버에서 직접 실행(전체 카테고리)."""
    global _running
    if not jobsvc.is_cloud_mode() or _running:
        return
    now_kst = datetime.now(KST)
    now_naive = now_kst.replace(tzinfo=None)  # KST 벽시계 기준 naive 로 저장(컬럼 tz 처리 차이 회피)
    hhmm = now_kst.strftime("%H:%M")
    today = now_kst.strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        sch = db.query(ContentSchedule).first()
        if not sch or not sch.schedule_time:
            return
        # catch-up: 예약 시각이 지났고("HH:MM" 제로패딩 문자열 비교) 오늘 아직 수집 안 함
        if sch.schedule_time > hhmm:
            return
        if sch.last_run_time and sch.last_run_time.strftime("%Y-%m-%d") == today:
            return
        # 착수 마킹(중복/재수집 방지) 후 수집 — 실패해도 오늘은 재시도 안 함(Gemini 비용 보호)
        _running = True
        sch.last_run_time = now_naive
        db.commit()
    except Exception as e:
        logger.error(f"[ContentDaily] 예약 확인 실패: {e}")
        _running = False
        return
    finally:
        db.close()

    if not _running:
        return
    try:
        from mbam_nextgen.services.gov_data import GovDataCollector
        logger.info(f"[ContentDaily] {hhmm} KST — 전체 카테고리 글감 자동 수집 시작")
        await GovDataCollector().fetch_all_categories_batch()
        logger.info("[ContentDaily] 글감 자동 수집 완료")
    except Exception as e:
        logger.error(f"[ContentDaily] 글감 수집 실패: {e}")
    finally:
        _running = False


class ContentDailyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.add_job(
            collect_due_content,
            CronTrigger(second=10, timezone="Asia/Seoul"),
            id="content_daily_collect", replace_existing=True,
            misfire_grace_time=120, coalesce=True,
        )
        self.scheduler.start()
        logger.info("ContentDaily scheduler started — 매 분 KST 글감 자동수집 예약 점검.")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


content_daily_scheduler = ContentDailyScheduler()
