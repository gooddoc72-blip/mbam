"""[클라우드 모드] 글감 자동 수집 스케줄러.

로컬 모드는 scheduler_service.run_content_sync_job 이 담당하지만, 클라우드(Railway)에선
scheduler_service 가 기동되지 않아 글감 자동수집이 전혀 안 됐다. 정부/공공 데이터 수집은
네이버 스크래핑이 아니라 데이터센터 IP에서도 가능하므로, 이 경량 스케줄러가 서버에서 직접
ContentSchedule.schedule_time 에 글감을 수집(캐시 저장)한다.

수집 대상은 '실제로 필요한 카테고리'만 — 활성 매일예약(BlogSchedule)이 쓰는 카테고리 +
글감수집 설정의 관심 카테고리. (전체 15개 일괄 수집은 앞쪽의 느린 크롤러 카테고리가 멈추면
뒤의 필요한 카테고리까지 도달을 못 해, 카테고리별 개별 수집 + 타임아웃으로 격리한다.)

- 매 분 KST 로 due(예약 시각이 지났고 오늘 아직 수집 안 함)를 점검 → catch-up 지원.
- 수집 성공(1개 이상) 후에만 last_run_time 을 찍어 하루 1회로 제한(전부 실패면 다음 분 재시도).
- _running 플래그로 중복 실행 방지.
"""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mbam_nextgen.backend.database import SessionLocal, ContentSchedule, BlogSchedule
from mbam_nextgen.backend import jobs as jobsvc

logger = logging.getLogger("ContentDailyScheduler")
KST = ZoneInfo("Asia/Seoul")

_running = False  # 수집이 1분 넘게 걸릴 수 있어 중복 실행 방지


async def collect_due_content():
    """예약 시각이 된 글감 자동수집을 서버에서 직접 실행(필요 카테고리만 개별 수집)."""
    global _running
    if not jobsvc.is_cloud_mode() or _running:
        return
    now_kst = datetime.now(KST)
    hhmm = now_kst.strftime("%H:%M")
    today = now_kst.strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        sch = db.query(ContentSchedule).first()
        if not sch or not sch.schedule_time or sch.schedule_time > hhmm:
            return
        if sch.last_run_time and sch.last_run_time.strftime("%Y-%m-%d") == today:
            return
        # 수집 대상: 활성 매일예약이 쓰는 카테고리 + 관심 카테고리(설정 화면)
        cats = set()
        for row in db.query(BlogSchedule.content_category).filter(BlogSchedule.is_active == 1).distinct():
            if row[0]:
                cats.add(row[0])
        if sch.interest_categories:
            cats.update(c.strip() for c in sch.interest_categories.split(",") if c.strip())
    except Exception as e:
        logger.error(f"[ContentDaily] 예약/대상 확인 실패: {e}")
        return
    finally:
        db.close()

    if not cats:
        return  # 수집할 카테고리 없음(활성 예약·관심 카테고리 모두 없음)

    _running = True
    ok = 0
    try:
        from mbam_nextgen.services.gov_data import GovDataCollector
        collector = GovDataCollector()
        logger.info(f"[ContentDaily] {hhmm} KST — 글감 자동수집 시작: {sorted(cats)}")
        for cat in cats:
            try:
                data = await asyncio.wait_for(collector.fetch_data(cat), timeout=180)
                if data:
                    collector.save_cache(cat, data)
                    ok += 1
                    logger.info(f"[ContentDaily] '{cat}' {len(data)}건 저장")
                else:
                    logger.warning(f"[ContentDaily] '{cat}' 수집 결과 없음")
            except Exception as e:
                logger.error(f"[ContentDaily] '{cat}' 수집 실패(건너뜀): {e}")
        # 하나라도 성공하면 오늘 완료로 마킹(전부 실패면 last_run_time 유지 → 다음 분 재시도)
        if ok > 0:
            db2 = SessionLocal()
            try:
                s2 = db2.query(ContentSchedule).first()
                if s2:
                    s2.last_run_time = now_kst.replace(tzinfo=None)  # KST 벽시계 naive 저장
                    db2.commit()
            finally:
                db2.close()
        logger.info(f"[ContentDaily] 완료 — 성공 {ok}/{len(cats)}")
    except Exception as e:
        logger.error(f"[ContentDaily] 글감 수집 오류: {e}")
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
