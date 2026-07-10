"""[클라우드 모드] 카페 예약 육성 스케줄러.

로컬은 scheduler_service.run_cafe_nurture_job(cron)이 담당하지만, 클라우드(Railway)에선
scheduler_service 가 기동되지 않아 카페 예약 육성이 전혀 안 됐다(그리고 네이버 스크래핑이라
데이터센터 IP·무화면에서 직접 실행도 불가). 이 스케줄러는 예약 시각이 되면 각 카페 예약을
'에이전트 잡'으로 적재만 하고, 상시 켜둔 로컬 에이전트(집 IP·화면)가 claim 해 실제 실행한다.

- 분 단위 due 점검(하루 1회, last_run_date 로 중복 방지) + catch-up.
- run_cafe_nurture_job 의 3케이스를 그대로 'action' 으로 해소해 payload 에 담는다:
    boost(게시글 부스트) / visit(방문 육성) / post(콘텐츠 카테고리 자동 포스팅).
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mbam_nextgen.backend.database import SessionLocal, CafeSchedule, NaverAccount, JoinedCafe
from mbam_nextgen.backend.cipher_utils import decrypt_val
from mbam_nextgen.backend import jobs as jobsvc

logger = logging.getLogger("CafeDailyScheduler")
KST = ZoneInfo("Asia/Seoul")


def enqueue_due_cafe_nurture():
    """지금 시각(KST)에 실행 예정인 카페 예약을 찾아 에이전트 잡으로 적재."""
    if not jobsvc.is_cloud_mode():
        return
    now = datetime.now(KST)
    hhmm = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")
    db = SessionLocal()
    try:
        # catch-up: 정확한 1분이 아니라 '시각이 지났고 오늘 아직 안 돈' 예약을 적재.
        due = (db.query(CafeSchedule)
               .filter(CafeSchedule.is_active == 1, CafeSchedule.schedule_time <= hhmm)
               .all())
        due = [s for s in due if s.schedule_time and s.last_run_date != today]
        if not due:
            return

        total = 0
        for s in due:
            acc = db.query(NaverAccount).filter(NaverAccount.id == s.account_id).first()
            cafe = db.query(JoinedCafe).filter(JoinedCafe.id == s.cafe_id).first()
            if not acc or not cafe:
                s.last_run_date = today
                continue

            pw = acc.naver_pw or ""
            try:
                if acc.naver_pw:
                    pw = decrypt_val(acc.naver_pw)
            except Exception:
                pw = acc.naver_pw or ""

            visits = max(1, s.post_count_per_day or 1)
            interval = int(s.visit_interval_min or 30)
            target = s.target_post_url

            payload = {
                "naver_id": acc.naver_id,
                "naver_pw": pw,
                "cafe_url": cafe.cafe_url,
                "board_name": cafe.board_name,
                "visits": visits,
                "visit_interval_min": interval,
            }

            if target:
                payload.update({"action": "boost", "post_url": target,
                                "do_view": bool(s.do_view), "do_like": bool(s.do_like)})
            elif not s.content_category:
                payload.update({"action": "visit", "post_url": cafe.cafe_url})
            else:
                # 콘텐츠 카테고리 자동 포스팅 — 글감을 클라우드 캐시에서 뽑아 payload 에 실어 보냄
                # (에이전트 PC엔 클라우드 캐시가 없으므로 여기서 해소해야 한다)
                try:
                    from mbam_nextgen.services.gov_data import GovDataCollector
                    items = GovDataCollector().load_cache(s.content_category) or []
                except Exception:
                    items = []
                if not items:
                    logger.warning(f"[CafeDaily] '{s.content_category}' 글감 없음 — 발행 보류(글감수집 필요)")
                    continue  # 글감 없으면 last_run_date 안 찍어 오늘 재시도
                qty = max(1, s.post_qty_per_time or 1)
                selected = items[:qty]
                payload.update({
                    "action": "post",
                    "items": [{"title": it.get("title", "정보 제공"), "content": it.get("content", "")} for it in selected],
                })

            jobsvc.enqueue_job(db, s.user_id, "cafe_nurture_run", payload, priority=6)
            s.last_run_date = today
            total += 1
        db.commit()
        if total:
            logger.info(f"[CafeDaily] {hhmm} KST — 카페 예약 육성 잡 {total}건 적재")
    except Exception as e:
        logger.error(f"[CafeDaily] 적재 실패: {e}")
    finally:
        db.close()


class CafeDailyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.add_job(
            enqueue_due_cafe_nurture,
            CronTrigger(second=20, timezone="Asia/Seoul"),
            id="cafe_daily_enqueue", replace_existing=True,
            misfire_grace_time=120, coalesce=True,
        )
        self.scheduler.start()
        logger.info("CafeDaily scheduler started — 매 분 KST 카페 예약 육성 점검·적재.")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


cafe_daily_scheduler = CafeDailyScheduler()
