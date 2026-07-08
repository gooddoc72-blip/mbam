"""[방법 B] 클라우드 모드 전용 — 매일 자동발행(BlogSchedule)을 에이전트 작업 큐로 적재.

클라우드(Railway)는 네이버 발행(브라우저 자동화)을 직접 못 하므로, 각 예약의 발행 시각이
되면 오늘 수집 글감 중 '인기순(황금점수)'으로 골라 `blog_daily_post` 잡을 적재만 한다.
상시 켜둔 로컬 에이전트가 폴링으로 claim → 집 IP로 생성+발행한다.

- 분 단위로 due 예약을 점검(하루 1회, last_run_date로 중복 방지).
- 같은 (유저·카테고리·시각) 그룹은 계정마다 '다른 글감'을 배분.
"""
import logging
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from mbam_nextgen.backend.database import SessionLocal, BlogSchedule, NaverAccount
from mbam_nextgen.backend.cipher_utils import decrypt_val
from mbam_nextgen.backend import jobs as jobsvc

logger = logging.getLogger("BlogDailyScheduler")
KST = ZoneInfo("Asia/Seoul")


def _ordered_topics(category: str) -> list:
    """오늘 수집 글감을 '인기순(황금점수)'으로 정렬한 토픽 목록.
    반환: [{keyword, title, content}] — 황금키워드 캐시가 있으면 그 순서 우선, 없으면 수집 순서."""
    from mbam_nextgen.services.gov_data import GovDataCollector
    from mbam_nextgen.services import golden_keyword
    items = []
    try:
        items = GovDataCollector().load_cache(category) or []
    except Exception:
        items = []
    golden = {}
    try:
        golden = golden_keyword.load_cache(category) or {}
    except Exception:
        golden = {}
    gk = [k.get("keyword") for k in (golden.get("keywords") or []) if k.get("keyword")]

    def _norm(s):
        return (s or "").replace(" ", "")

    topics, used = [], set()

    def _find_item(kw):
        nk = _norm(kw)
        if not nk:
            return None
        for idx, it in enumerate(items):
            if idx in used:
                continue
            hay = _norm(it.get("title", "")) + _norm(it.get("content", ""))[:400]
            if nk in hay:
                return idx
        return None

    # 1) 인기순(황금점수) 키워드부터 — 매칭되는 수집 글감을 참고자료로 붙임
    for kw in gk:
        idx = _find_item(kw)
        if idx is not None:
            used.add(idx)
            it = items[idx]
            topics.append({"keyword": kw, "title": it.get("title") or kw, "content": it.get("content", "")})
        else:
            topics.append({"keyword": kw, "title": kw, "content": ""})
    # 2) 매칭 안 된 나머지 수집 글감(폴백)
    for idx, it in enumerate(items):
        if idx not in used:
            topics.append({"keyword": it.get("title", ""), "title": it.get("title", ""), "content": it.get("content", "")})
    return topics


def enqueue_due_blog_posts():
    """지금 시각(KST)에 발행 예정인 예약을 찾아 에이전트 잡으로 적재."""
    if not jobsvc.is_cloud_mode():
        return
    now = datetime.now(KST)
    hhmm = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")
    db = SessionLocal()
    try:
        due = (db.query(BlogSchedule)
               .filter(BlogSchedule.is_active == 1, BlogSchedule.schedule_time == hhmm)
               .all())
        due = [s for s in due if s.last_run_date != today]
        if not due:
            return

        # (유저, 카테고리)별로 묶어 계정마다 다른 글감 배분
        groups = defaultdict(list)
        for s in due:
            groups[(s.user_id, s.content_category)].append(s)

        total = 0
        for (uid, cat), schs in groups.items():
            topics = _ordered_topics(cat)
            if not topics:
                logger.warning(f"[BlogDaily] '{cat}' 글감이 없어 발행 보류 (글감수집 먼저 필요) — 유저 {uid}")
                # 글감 없으면 오늘 재시도되게 last_run_date는 찍지 않음
                continue
            ti = 0
            for s in schs:
                acc = db.query(NaverAccount).filter(NaverAccount.id == s.account_id).first()
                if not acc:
                    s.last_run_date = today
                    continue
                pw = ""
                try:
                    pw = decrypt_val(acc.naver_pw) if acc.naver_pw else ""
                except Exception:
                    pw = acc.naver_pw or ""
                qty = max(1, s.post_count_per_day or 1)
                for _ in range(qty):
                    topic = topics[ti % len(topics)]
                    ti += 1
                    source = f"[작성 주제] {topic['title']}\n[글감]\n{topic.get('content', '')}"
                    payload = {
                        "naver_id": acc.naver_id,
                        "naver_pw": pw,
                        "blog_addr": acc.blog_addr or None,
                        "keyword": topic.get("keyword") or topic.get("title") or "정보",
                        "source_data": source,
                        "ai_provider": s.ai_provider or "claude",
                        "distribution_mode": s.distribution_mode or "normal",
                        "generate_card_news": bool(s.generate_card_news),
                    }
                    jobsvc.enqueue_job(db, uid, "blog_daily_post", payload, priority=7)
                    total += 1
                s.last_run_date = today
            db.commit()
        if total:
            logger.info(f"[BlogDaily] {hhmm} KST — 매일 자동발행 잡 {total}건 적재")
    except Exception as e:
        logger.error(f"[BlogDaily] 적재 실패: {e}")
    finally:
        db.close()


class BlogDailyScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        # 매 분 정각에 due 예약 점검 (schedule_time 이 'HH:MM' 분 단위라 분 해상도로 충분)
        self.scheduler.add_job(
            enqueue_due_blog_posts,
            CronTrigger(second=5, timezone="Asia/Seoul"),
            id="blog_daily_enqueue", replace_existing=True,
            misfire_grace_time=120, coalesce=True,
        )
        self.scheduler.start()
        logger.info("BlogDaily scheduler started — 매 분 KST 매일 자동발행 예약 점검·적재.")

    def shutdown(self):
        try:
            self.scheduler.shutdown()
        except Exception:
            pass


blog_daily_scheduler = BlogDailyScheduler()
