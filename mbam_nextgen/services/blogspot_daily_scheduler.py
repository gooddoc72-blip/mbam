"""[클라우드 모드] 블로그스팟 매일 자동발행 스케줄러.

네이버와 달리 Blogger 는 공식 API 라 데이터센터 IP(Railway)에서 직접 발행된다(에이전트 불필요).
예약 시각이 되면 글감수집 캐시(네이버와 공유)에서 글감을 뽑아 관리자 'blogspot' 프롬프트로
HTML 원고를 생성하고 Blogger API 로 곧바로 발행한다.

- 분 단위 due 점검(하루 1회, last_run_date 로 중복 방지) + catch-up.
- 글감은 GovDataCollector 캐시 사용, last_index 로 매일 회전.
"""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mbam_nextgen.backend.database import SessionLocal, BlogspotSchedule, BlogspotAccount, BlogspotPostHistory

logger = logging.getLogger("BlogspotDailyScheduler")
KST = ZoneInfo("Asia/Seoul")

_running = False


def _topics(category: str) -> list:
    """글감수집 캐시에서 토픽 목록 로드: [{title, content}]."""
    try:
        from mbam_nextgen.services.gov_data import GovDataCollector
        return GovDataCollector().load_cache(category) or []
    except Exception:
        return []


async def publish_due_blogspot():
    """예약 시각이 지난(오늘 미실행) 블로그스팟 예약을 찾아 Blogger API 로 직접 발행."""
    global _running
    if _running:
        return
    now = datetime.now(KST)
    hhmm = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        due = (db.query(BlogspotSchedule)
               .filter(BlogspotSchedule.is_active == 1, BlogspotSchedule.schedule_time <= hhmm)
               .all())
        due = [s for s in due if s.schedule_time and s.last_run_date != today]
        if not due:
            return
    except Exception as e:
        logger.error(f"[BlogspotDaily] 예약 조회 실패: {e}")
        db.close()
        return

    _running = True
    try:
        from mbam_nextgen.services.blogspot_service import generate_blogspot_article, publish_to_blogger
        for s in due:
            acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == s.account_id).first()
            if not acc:
                s.last_run_date = today
                db.commit()
                continue
            items = _topics(s.content_category) if s.content_category else []
            if not items:
                logger.warning(f"[BlogspotDaily] '{s.content_category}' 글감 없음 — 발행 보류(글감수집 필요)")
                continue  # 글감 없으면 last_run_date 안 찍어 오늘 재시도
            qty = max(1, s.post_count_per_day or 1)
            start = (s.last_index or 0) % len(items)
            published = 0
            for i in range(qty):
                item = items[(start + i) % len(items)]
                title_seed = item.get("title", "정보")
                source = f"[작성 주제] {title_seed}\n[글감]\n{item.get('content', '')}"
                try:
                    article = await generate_blogspot_article(title_seed, source, s.ai_provider or "gemini")
                    result = await publish_to_blogger(acc, article["title"], article["html"])
                    if result.get("success"):
                        published += 1
                        s.last_run_url = result.get("url") or s.last_run_url
                        s.last_run_title = article["title"]
                        db.add(BlogspotPostHistory(
                            account_id=acc.id, keyword=title_seed, title=article["title"],
                            post_url=result.get("url", ""), status="success",
                        ))
                        logger.info(f"[BlogspotDaily] 발행 성공: {article['title']}")
                    else:
                        db.add(BlogspotPostHistory(
                            account_id=acc.id, keyword=title_seed, title=article["title"],
                            post_url="", status="failed",
                        ))
                        logger.warning(f"[BlogspotDaily] 발행 실패: {result.get('error')}")
                except Exception as e:
                    logger.error(f"[BlogspotDaily] 발행 예외: {e}")
                await asyncio.sleep(3)
            s.last_index = (start + qty) % len(items)
            s.last_run_date = today
            db.commit()
            logger.info(f"[BlogspotDaily] {acc.account_name} 완료: {published}/{qty}")
    except Exception as e:
        logger.error(f"[BlogspotDaily] 오류: {e}")
    finally:
        _running = False
        db.close()


class BlogspotDailyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        self.scheduler.add_job(
            publish_due_blogspot,
            CronTrigger(second=15, timezone="Asia/Seoul"),
            id="blogspot_daily_publish", replace_existing=True,
            misfire_grace_time=120, coalesce=True,
        )
        self.scheduler.start()
        logger.info("BlogspotDaily scheduler started — 매 분 KST 블로그스팟 예약 점검·발행.")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


blogspot_daily_scheduler = BlogspotDailyScheduler()
