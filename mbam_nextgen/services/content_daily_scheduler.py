"""[클라우드 모드] 글감 자동 수집 스케줄러.

로컬 모드는 scheduler_service.run_content_sync_job 이 담당하지만, 클라우드(Railway)에선
scheduler_service 가 기동되지 않아 글감 자동수집이 전혀 안 됐다. 정부/공공 데이터 수집은
네이버 스크래핑이 아니라 데이터센터 IP에서도 가능하므로, 이 경량 스케줄러가 서버에서 직접
ContentSchedule.schedule_time 에 글감을 수집(캐시 저장)한다.

설계 포인트:
- 수집 대상 = '실제로 필요한 카테고리'만: 활성 매일예약(BlogSchedule) 카테고리 + 관심 카테고리.
  (전체 15개 일괄 수집은 앞쪽 크롤러 카테고리가 멈추면 뒤까지 도달 못 함 → 카테고리별 개별 수집.)
- '캐시가 비어 있으면 수집' 방식(load_cache 기준). Railway 는 재배포 때 파일시스템(캐시)이
  초기화되므로, DB 플래그(last_run_time) 대신 실제 캐시 유무로 판단해야 재배포 후에도 자가 복구된다.
- 같은 날 이미 시도(성공/빈결과)한 카테고리는 프로세스 메모리에 기록해 반복 호출(비용)을 막는다.
- 예약 시각(schedule_time) 이 지난 뒤에만 수집. catch-up: 시각을 놓쳐도 이후 분에 보충.
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

_running = False                       # 수집이 1분 넘게 걸릴 수 있어 중복 실행 방지
_attempted = {"date": None, "cats": set()}  # 같은 날 재시도(빈결과 반복) 방지


async def collect_due_content():
    """예약 시각이 된 뒤, 캐시가 비어있는 '필요 카테고리'만 서버에서 개별 수집."""
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

    # 날짜 바뀌면 '오늘 시도' 기록 초기화
    if _attempted["date"] != today:
        _attempted["date"] = today
        _attempted["cats"] = set()

    _running = True
    try:
        from mbam_nextgen.services.gov_data import GovDataCollector
        collector = GovDataCollector()
        for cat in cats:
            if cat in _attempted["cats"]:
                continue                       # 오늘 이미 시도함
            if collector.load_cache(cat):
                continue                       # 이미 캐시 있음(오늘 수집됨)
            _attempted["cats"].add(cat)        # 시도 마킹(빈결과 반복 호출 방지)
            try:
                logger.info(f"[ContentDaily] {hhmm} KST — '{cat}' 글감 자동수집 시작")
                data = await asyncio.wait_for(collector.fetch_data(cat), timeout=180)
                if data:
                    collector.save_cache(cat, data)
                    logger.info(f"[ContentDaily] '{cat}' {len(data)}건 저장")
                else:
                    logger.warning(f"[ContentDaily] '{cat}' 수집 결과 없음")
            except Exception as e:
                logger.error(f"[ContentDaily] '{cat}' 수집 실패(건너뜀): {e}")
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
