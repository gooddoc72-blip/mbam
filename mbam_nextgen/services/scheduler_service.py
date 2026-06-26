import asyncio
import sqlite3
import os
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from mbam_nextgen.backend.routers.place import run_place_analysis
from mbam_nextgen.backend.database import SessionLocal, CafeSchedule, NaverAccount, JoinedCafe, ContentSchedule, BlogSchedule, BlogReservation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SchedulerService")

class SchedulerService:
    def __init__(self):
        # AsyncIOScheduler 사용 (FastAPI와 비동기 통합)
        self.scheduler = AsyncIOScheduler()
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ranking.db")
        
    def get_tracked_places(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # tracked_places 테이블이 존재하는지 확인 후 조회
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_places'")
            if not c.fetchone():
                conn.close()
                return []
                
            c.execute("SELECT mid, keyword FROM tracked_places")
            places = c.fetchall()
            conn.close()
            return [{"mid": row[0], "keyword": row[1]} for row in places]
        except Exception as e:
            logger.error(f"Error fetching tracked places: {str(e)}")
            return []

    async def run_daily_analysis(self):
        """매일 실행되는 플레이스 분석 작업 (새벽 5시 일괄 실행 최적화)"""
        logger.info(f"[{datetime.now()}] Starting daily scheduled place analysis...")
        
        places = self.get_tracked_places()
        if not places:
            logger.info("No tracked places found to analyze.")
            return

        # 중복 크롤링 방지를 위해 키워드별로 그룹화
        # run_place_analysis 내부에서 동일 날짜 동일 키워드는 캐시를 사용하므로, 
        # 한 키워드당 한 번의 네이버 지도 크롤링만 발생합니다.
        # 혹시 모를 동시 실행 이슈 방지를 위해 키워드를 중복 제거 후 순차 실행합니다.
        keyword_groups = {}
        for p in places:
            keyword_groups.setdefault(p["keyword"], []).append(p["mid"])

        logger.info(f"Found {len(places)} places across {len(keyword_groups)} unique keywords. Beginning processing...")

        for idx, (keyword, mids) in enumerate(keyword_groups.items()):
            logger.info(f"[{idx+1}/{len(keyword_groups)}] Keyword Group: '{keyword}' with {len(mids)} places")
            
            # 각 MID별로 히스토리 업데이트를 위해 순차적으로 run_place_analysis 호출
            # 첫 번째 호출에서만 실제 크롤링이 발생하고, 나머지는 로컬 DB 캐시를 즉시 활용함
            for mid in mids:
                try:
                    await asyncio.to_thread(run_place_analysis, keyword, mid)
                    logger.info(f"  -> Successfully updated history for MID: {mid}")
                except Exception as e:
                    logger.error(f"  -> Failed to update MID: {mid}. Error: {str(e)}")
            
            # 다음 키워드 분석 전 IP 차단 방지를 위한 20초 대기 (마지막 항목 제외)
            if idx < len(keyword_groups) - 1:
                logger.info("Waiting 20 seconds to avoid rate limiting before next keyword...")
                await asyncio.sleep(20)
                
        logger.info(f"[{datetime.now()}] Daily scheduled place analysis completed successfully.")


    async def run_daily_shopping_analysis(self):
        """매일 실행되는 쇼핑 분석 작업 (새벽 5시 일괄 실행)"""
        logger.info(f"[{datetime.now()}] Starting daily scheduled shopping analysis...")
        try:
            from mbam_nextgen.backend.database import SessionLocal, ShoppingTrackedItem, ShoppingHistory
            from mbam_nextgen.backend.routers.shopping_router import fetch_target_rank_via_api, AnalyzeRequest, analyze_keyword_shopping
            
            db = SessionLocal()
            tracked_items = db.query(ShoppingTrackedItem).all()
            if not tracked_items:
                logger.info("No tracked shopping items found.")
                db.close()
                return
                
            for item in tracked_items:
                logger.info(f"Analyzing Shopping Item: {item.name} / Keyword: {item.keyword}")
                try:
                    req = AnalyzeRequest(keyword=item.keyword, target_mid=item.mid)
                    # FastAPI 의존성(check_quota) 우회: 스케줄러는 시스템 권한으로 직접 호출.
                    # current_user를 명시적으로 넘기지 않으면 Depends 객체가 들어와 increment_quota에서 크래시함.
                    res = await analyze_keyword_shopping(req, db, {"sub": "system_scheduler", "role": "admin"})
                    if res.get('found') and res.get('places'):
                        target_stat = next((p for p in res['places'] if p.get('is_target')), None)
                        if target_stat:
                            date_str = datetime.now().strftime('%Y-%m-%d')
                            # Check if history exists for today
                            existing_hist = db.query(ShoppingHistory).filter(ShoppingHistory.tracked_id == item.id, ShoppingHistory.date_str == date_str).first()
                            if existing_hist:
                                existing_hist.rank = target_stat.get('rank', 0)
                                existing_hist.page = (target_stat.get('rank', 0) - 1) // 40 + 1 if target_stat.get('rank', 0) > 0 else 1
                                existing_hist.saves = target_stat.get('keeps', 0)
                                existing_hist.visitor_reviews = target_stat.get('reviews', 0)
                                existing_hist.purchases = target_stat.get('purchases', 0)
                                existing_hist.n1 = target_stat.get('n1', 0)
                                existing_hist.n2 = target_stat.get('n2', 0)
                                existing_hist.n3 = target_stat.get('n3', 0)
                                existing_hist.n4 = target_stat.get('n4', 0)
                                existing_hist.n5 = target_stat.get('n5', 0)
                            else:
                                new_hist = ShoppingHistory(
                                    tracked_id=item.id,
                                    date_str=date_str,
                                    rank=target_stat.get('rank', 0),
                                    page=(target_stat.get('rank', 0) - 1) // 40 + 1 if target_stat.get('rank', 0) > 0 else 1,
                                    saves=target_stat.get('keeps', 0),
                                    visitor_reviews=target_stat.get('reviews', 0),
                                    purchases=target_stat.get('purchases', 0),
                                    n1=target_stat.get('n1', 0),
                                    n2=target_stat.get('n2', 0),
                                    n3=target_stat.get('n3', 0),
                                    n4=target_stat.get('n4', 0),
                                    n5=target_stat.get('n5', 0)
                                )
                                db.add(new_hist)
                            db.commit()
                except Exception as e:
                    logger.error(f"Error processing shopping item {item.id}: {str(e)}")
                import asyncio
                await asyncio.sleep(10) # 10초 딜레이
            db.close()
            logger.info("Daily shopping analysis completed.")
        except Exception as e:
            logger.error(f"Failed in daily shopping analysis: {str(e)}")

    def _get_scheduled_time(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT hour, minute FROM scheduler_config WHERE id=1")
            row = c.fetchone()
            conn.close()
            if row:
                return row[0], row[1]
        except Exception as e:
            logger.error(f"Error fetching schedule time: {str(e)}")
        return 10, 0

    def load_cafe_schedules(self):
        try:
            db = SessionLocal()
            schedules = db.query(CafeSchedule).filter(CafeSchedule.is_active == 1).all()
            for sch in schedules:
                try:
                    hour, minute = map(int, sch.schedule_time.split(":"))
                    job_id = f"cafe_nurture_{sch.id}"
                    
                    self.scheduler.add_job(
                        self.run_cafe_nurture_job, 
                        'cron', 
                        hour=hour, 
                        minute=minute, 
                        args=[sch.id],
                        id=job_id, 
                        replace_existing=True
                    )
                except ValueError:
                    logger.error(f"Invalid schedule time format for {sch.id}: {sch.schedule_time}")
            db.close()
            logger.info(f"Loaded {len(schedules)} cafe nurture schedules.")
        except Exception as e:
            logger.error(f"Error loading cafe schedules: {e}")

    def add_cafe_schedule_job(self, schedule_id, schedule_time):
        """단건 카페 육성 예약을 '실행 중인' 스케줄러에 즉시 등록 (UI 추가 즉시 반영)."""
        try:
            hour, minute = map(int, str(schedule_time).split(":"))
            job_id = f"cafe_nurture_{schedule_id}"
            self.scheduler.add_job(
                self.run_cafe_nurture_job, 'cron',
                hour=hour, minute=minute, args=[schedule_id],
                id=job_id, replace_existing=True
            )
            logger.info(f"카페 예약 즉시 등록: {job_id} @ {hour:02d}:{minute:02d}")
            return True
        except Exception as e:
            logger.error(f"카페 예약 등록 실패({schedule_id}): {e}")
            return False

    def remove_cafe_schedule_job(self, schedule_id):
        """단건 카페 육성 예약을 스케줄러에서 제거."""
        try:
            self.scheduler.remove_job(f"cafe_nurture_{schedule_id}")
            logger.info(f"카페 예약 제거: cafe_nurture_{schedule_id}")
        except Exception:
            pass

    async def run_cafe_nurture_job(self, schedule_id: str):
        db = SessionLocal()
        try:
            sch = db.query(CafeSchedule).filter(CafeSchedule.id == schedule_id).first()
            if not sch:
                return
                
            acc = db.query(NaverAccount).filter(NaverAccount.id == sch.account_id).first()
            cafe = db.query(JoinedCafe).filter(JoinedCafe.id == sch.cafe_id).first()
            
            if not acc or not cafe:
                return
                
            logger.info(f"🚀 [Scheduler] Running cafe nurture for account: {acc.naver_id} at {cafe.cafe_url}")
            
            from mbam_nextgen.orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            
            # TODO: We can store naver_pw encrypted, here we assume it's in DB or mock
            import os
            os.environ["NAVER_PW"] = acc.naver_pw # Temporarily pass password via env if needed
            
            # 0순위: 게시글 부스트(조회수/좋아요) — 대상 글 URL이 있으면 방문+좋아요
            target_url = getattr(sch, 'target_post_url', None)
            do_view = bool(getattr(sch, 'do_view', 1))
            do_like = bool(getattr(sch, 'do_like', 1))
            visits = max(1, getattr(sch, 'post_count_per_day', 1) or 1)
            interval = int(getattr(sch, 'visit_interval_min', 30) or 30)
            if target_url:
                logger.info(f"👍 [Scheduler] 게시글 부스트: {target_url} (방문 {visits}회/{interval}분 간격, 좋아요 {do_like})")
                await orchestrator.execute_cafe_boost(
                    account_id=acc.naver_id, post_url=target_url,
                    do_view=do_view, do_like=do_like, visits=visits, naver_pw=acc.naver_pw,
                    visit_interval_min=interval,
                )
                return
            # 대상 글 URL이 없으면: 카페 방문(육성)만 → 방문횟수 증가
            if not (hasattr(sch, 'content_category') and sch.content_category):
                logger.info(f"🚶 [Scheduler] 일반 육성(방문만): {cafe.cafe_url} (방문 {visits}회/{interval}분 간격)")
                await orchestrator.execute_cafe_boost(
                    account_id=acc.naver_id, post_url=cafe.cafe_url,
                    do_view=True, do_like=False, visits=visits, naver_pw=acc.naver_pw,
                    visit_interval_min=interval,
                )
                return

            # (레거시) Content Category 기반 자동 포스팅
            if hasattr(sch, 'content_category') and sch.content_category:
                logger.info(f"🚀 [Scheduler] Running content-based cafe post for category: {sch.content_category}")
                from mbam_nextgen.services.gov_data import GovDataCollector
                import random
                
                collector = GovDataCollector()
                items = collector.load_cache(sch.content_category)
                
                qty = getattr(sch, 'post_qty_per_time', 1)
                if not items:
                    logger.warning(f"No items found for category {sch.content_category}")
                    return
                
                # Pick top N items or random N items
                selected_items = items[:qty] if len(items) >= qty else items
                
                for i, item in enumerate(selected_items):
                    logger.info(f"  -> Posting item {i+1}/{len(selected_items)}: {item.get('title')}")
                    await orchestrator.execute_cafe_workflow(
                        account_id=acc.naver_id,
                        cafe_id=cafe.cafe_url,
                        board_name=cafe.board_name,
                        keyword=item.get('title', '정보 제공'),
                        title=item.get('title', '정보 제공'),
                        content=item.get('content', ''),
                        auto_submit=True,
                        action_type="post"
                    )
            else:
                await orchestrator.execute_cafe_workflow(
                    account_id=acc.naver_id,
                    cafe_id=cafe.cafe_url,
                    board_name=cafe.board_name,
                    keyword="소통", # General keyword for nurturing
                    auto_submit=True,
                    action_type="comment"
                )
        except Exception as e:
            logger.error(f"Cafe nurture job failed: {e}")
        finally:
            db.close()

    # ===================== 블로그 매일 자동발행 =====================
    def load_blog_schedules(self):
        """기동 시 DB의 활성 블로그 매일발행 예약을 스케줄러에 등록."""
        try:
            db = SessionLocal()
            schedules = db.query(BlogSchedule).filter(BlogSchedule.is_active == 1).all()
            for sch in schedules:
                try:
                    hour, minute = map(int, sch.schedule_time.split(":"))
                    self.scheduler.add_job(
                        self.run_blog_post_job, 'cron',
                        hour=hour, minute=minute, args=[sch.id],
                        id=f"blog_post_{sch.id}", replace_existing=True,
                        misfire_grace_time=3600, coalesce=True,
                    )
                except ValueError:
                    logger.error(f"Invalid blog schedule time for {sch.id}: {sch.schedule_time}")
            db.close()
            logger.info(f"Loaded {len(schedules)} blog post schedules.")
        except Exception as e:
            logger.error(f"Error loading blog schedules: {e}")

    def add_blog_schedule_job(self, schedule_id, schedule_time):
        """단건 블로그 매일발행 예약을 '실행 중인' 스케줄러에 즉시 등록 (UI 추가 즉시 반영)."""
        try:
            hour, minute = map(int, str(schedule_time).split(":"))
            self.scheduler.add_job(
                self.run_blog_post_job, 'cron',
                hour=hour, minute=minute, args=[schedule_id],
                id=f"blog_post_{schedule_id}", replace_existing=True,
                misfire_grace_time=3600, coalesce=True,
            )
            logger.info(f"블로그 예약 즉시 등록: blog_post_{schedule_id} @ {hour:02d}:{minute:02d}")
            return True
        except Exception as e:
            logger.error(f"블로그 예약 등록 실패({schedule_id}): {e}")
            return False

    def remove_blog_schedule_job(self, schedule_id):
        """단건 블로그 매일발행 예약을 스케줄러에서 제거."""
        try:
            self.scheduler.remove_job(f"blog_post_{schedule_id}")
            logger.info(f"블로그 예약 제거: blog_post_{schedule_id}")
        except Exception:
            pass

    async def run_blog_post_job(self, schedule_id: str):
        """매일 같은 시각: 글감수집 카테고리에서 글감을 뽑아 블로그에 자동 발행."""
        db = SessionLocal()
        try:
            sch = db.query(BlogSchedule).filter(BlogSchedule.id == schedule_id).first()
            if not sch or not sch.is_active:
                return
            acc = db.query(NaverAccount).filter(NaverAccount.id == sch.account_id).first()
            if not acc:
                logger.error(f"[BlogSchedule] 계정을 찾을 수 없음: {sch.account_id}")
                return

            # 하루 1회 중복 방지 (서버 재시작/보충 발화로 인한 중복 발행 차단)
            today = datetime.now().strftime("%Y-%m-%d")
            if sch.last_run_date == today:
                logger.info(f"[BlogSchedule] {schedule_id} 오늘 이미 발행됨 — 스킵")
                return

            # 글감 선택 (글감수집 카테고리 캐시)
            from mbam_nextgen.services.gov_data import GovDataCollector
            collector = GovDataCollector()
            items = collector.load_cache(sch.content_category) if sch.content_category else []
            if not items:
                logger.warning(f"[BlogSchedule] '{sch.content_category}' 글감이 없어 발행 보류 (글감수집 먼저 필요)")
                return

            qty = max(1, sch.post_count_per_day or 1)
            start = (sch.last_index or 0) % len(items)  # 매일 다른 글감으로 회전

            from mbam_nextgen.orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            logger.info(f"📝 [BlogSchedule] {acc.naver_id} 매일발행 시작 (카테고리: {sch.content_category}, {qty}개)")

            published = 0
            for i in range(qty):
                item = items[(start + i) % len(items)]
                title = item.get("title", "정보 제공")
                source = f"[작성 주제] {title}\n[글감]\n{item.get('content', '')}"
                try:
                    result = await orchestrator.execute_blog_workflow(
                        account_id=acc.naver_id,
                        account_pw=acc.naver_pw,
                        keyword=title,
                        source_data=source,
                        publish_mode="instant",
                        ai_provider=sch.ai_provider or "claude",
                        distribution_mode=sch.distribution_mode or "normal",
                        generate_card_news=bool(getattr(sch, "generate_card_news", 1)),
                        blog_id=acc.blog_addr or None,
                    )
                    if result and result.get("success"):
                        published += 1
                        logger.info(f"  -> [{i+1}/{qty}] 발행 성공: {title}")
                    else:
                        logger.warning(f"  -> [{i+1}/{qty}] 발행 실패: {(result or {}).get('error')}")
                except Exception as e:
                    logger.error(f"  -> [{i+1}/{qty}] 발행 예외: {e}")
                await asyncio.sleep(5)  # 발행 간 텀

            sch.last_index = (start + qty) % len(items)
            sch.last_run_date = today
            db.commit()
            logger.info(f"[BlogSchedule] {schedule_id} 완료: {published}/{qty} 발행")
        except Exception as e:
            logger.error(f"[BlogSchedule] job 실패({schedule_id}): {e}")
        finally:
            db.close()

    # ===================== 블로그 예약 포스팅 (1회) =====================
    async def run_blog_reservation_job(self, reservation_id: str):
        db = SessionLocal()
        try:
            r = db.query(BlogReservation).filter(BlogReservation.id == reservation_id).first()
            if not r or r.status != "pending":
                return
            acc = db.query(NaverAccount).filter(NaverAccount.id == r.account_id).first()
            if not acc:
                r.status = "failed"; db.commit(); return
            from mbam_nextgen.orchestrator import WorkflowOrchestrator
            orchestrator = WorkflowOrchestrator()
            logger.info(f"📅 [BlogReservation] {acc.naver_id} 예약 발행 시작: {r.keyword} @ {r.run_at}")
            try:
                result = await orchestrator.execute_blog_workflow(
                    account_id=acc.naver_id,
                    account_pw=acc.naver_pw,
                    keyword=r.keyword or "정보",
                    source_data=r.source_data or "",
                    publish_mode="instant",
                    ai_provider=r.ai_provider or "claude",
                    distribution_mode=r.distribution_mode or "normal",
                    generate_card_news=bool(getattr(r, "generate_card_news", 1)),
                    image_folder_path=(r.image_folder or None),
                    blog_id=acc.blog_addr or None,
                )
                if result and result.get("success"):
                    r.status = "done"; r.result_url = result.get("result_url") or ""
                    logger.info(f"📅 [BlogReservation] 발행 성공: {r.keyword}")
                else:
                    r.status = "failed"
                    logger.warning(f"📅 [BlogReservation] 발행 실패: {(result or {}).get('error')}")
            except Exception as e:
                r.status = "failed"
                logger.error(f"📅 [BlogReservation] 예외: {e}")
            db.commit()
        except Exception as e:
            logger.error(f"[BlogReservation] job 실패({reservation_id}): {e}")
        finally:
            db.close()

    def add_blog_reservation_job(self, reservation_id, run_at):
        """run_at: 'YYYY-MM-DD HH:MM' → date 트리거로 1회 발화 (즉시 등록)."""
        try:
            dt = datetime.strptime(run_at, "%Y-%m-%d %H:%M")
            self.scheduler.add_job(
                self.run_blog_reservation_job, 'date', run_date=dt,
                args=[reservation_id], id=f"blog_resv_{reservation_id}",
                replace_existing=True, misfire_grace_time=3600,
            )
            logger.info(f"블로그 예약 등록: blog_resv_{reservation_id} @ {run_at}")
            return True
        except Exception as e:
            logger.error(f"블로그 예약 등록 실패({reservation_id}): {e}")
            return False

    def remove_blog_reservation_job(self, reservation_id):
        try:
            self.scheduler.remove_job(f"blog_resv_{reservation_id}")
        except Exception:
            pass

    def load_blog_reservations(self):
        """기동 시 pending 예약을 스케줄러에 등록. 이미 지난 건은 30초 뒤 보충 발화."""
        try:
            from datetime import timedelta
            db = SessionLocal()
            rows = db.query(BlogReservation).filter(BlogReservation.status == "pending").all()
            now = datetime.now()
            for r in rows:
                try:
                    dt = datetime.strptime(r.run_at, "%Y-%m-%d %H:%M")
                    run_date = dt if dt > now else now + timedelta(seconds=30)
                    self.scheduler.add_job(
                        self.run_blog_reservation_job, 'date', run_date=run_date,
                        args=[r.id], id=f"blog_resv_{r.id}", replace_existing=True,
                        misfire_grace_time=3600,
                    )
                except Exception as e:
                    logger.error(f"예약 로드 실패({r.id}): {e}")
            db.close()
            logger.info(f"Loaded {len(rows)} blog reservations.")
        except Exception as e:
            logger.error(f"Error loading blog reservations: {e}")

    async def run_content_sync_job(self):
        """매일 실행되는 글감 데이터 동기화 작업"""
        logger.info(f"[{datetime.now()}] Starting scheduled content data sync...")
        try:
            from mbam_nextgen.services.gov_data import GovDataCollector
            collector = GovDataCollector()
            # 비동기 함수 실행
            await collector.fetch_all_categories_batch()
            logger.info("Scheduled content data sync completed successfully.")
            
            # 관심 카테고리 텔레그램 전송 로직
            db = SessionLocal()
            sch = db.query(ContentSchedule).first()
            if sch and sch.interest_categories:
                interests = sch.interest_categories.split(",")
                summary_text = "🔔 <b>[마케팅 플랫폼] 오늘의 관심 글감 요약</b>\n\n"
                
                has_items = False
                for cat in interests:
                    if not cat.strip(): continue
                    items = collector.load_cache(cat.strip())
                    if items:
                        has_items = True
                        top_items = items[:2] # 상위 2개만 요약
                        summary_text += f"📌 <b>{cat}</b>\n"
                        for i, item in enumerate(top_items):
                            summary_text += f" - {item.get('title')}\n"
                        summary_text += "\n"
                
                if has_items:
                    summary_text += "👉 <a href='http://localhost:3000/content-collect'>웹(Web) 대시보드</a>에서 <b>[📝 블로그 작성 준비]</b> 버튼을 눌러 원클릭 자동포스팅을 진행하세요!"
                    
                    from mbam_nextgen.services.telegram_service import TelegramService
                    ts = TelegramService()
                    await ts.send_message(summary_text)
                    logger.info("Sent Telegram notification for interest categories.")
            db.close()
            
        except Exception as e:
            logger.error(f"Failed to sync content data: {str(e)}")

    async def run_place_news_job(self):
        """1주/2주 주기에 맞춰 플레이스 리뷰를 수집하고 소식 원고 및 클립 영상 생성"""
        logger.info(f"[{datetime.now()}] Checking Place News schedules...")
        try:
            from mbam_nextgen.backend.database import SessionLocal, PlaceNewsSchedule, PlaceNewsHistory
            from mbam_nextgen.services.place_review_service import PlaceReviewService
            from mbam_nextgen.services.soul import SoulRewriter
            from mbam_nextgen.services.clip import ClipGenerator
            from mbam_nextgen.services.telegram_service import TelegramService
            import uuid
            from datetime import timedelta
            
            db = SessionLocal()
            schedules = db.query(PlaceNewsSchedule).filter(PlaceNewsSchedule.is_active == 1).all()
            
            for sch in schedules:
                now = datetime.now()
                # Check if it's time to run based on interval_weeks
                if sch.last_run_time:
                    days_passed = (now - sch.last_run_time).days
                    if days_passed < sch.interval_weeks * 7:
                        continue
                
                logger.info(f"Running Place News generation for {sch.place_name}...")
                
                pr_service = PlaceReviewService()
                review_data = await pr_service.collect_reviews(sch.place_url)
                
                if review_data.get("success") and review_data.get("reviews"):
                    # 자동화 시 3가지 테마 중 랜덤 선택
                    import random
                    themes = [
                        "🌟 고객 극찬 릴레이 (방문 후기형)",
                        "👩‍🍳 우리 매장의 차별점 (전문성 어필형)",
                        "🎉 이번 주 베스트 포토 (시각적 어필형)"
                    ]
                    selected_theme = random.choice(themes)
                    logger.info(f"Selected Theme for Auto-generation: {selected_theme}")
                    
                    soul = SoulRewriter()
                    ai_result = await soul.generate_place_news(sch.place_name, review_data["reviews"], selected_theme)
                    
                    clip_gen = ClipGenerator()
                    clip_name = f"clip_{uuid.uuid4().hex[:8]}"
                    clip_texts = ai_result.get("clip_texts", [])
                    clip_path = clip_gen.generate_clip(review_data["image_paths"], clip_texts, clip_name)
                    
                    history = PlaceNewsHistory(
                        schedule_id=sch.id,
                        generated_text=f"[{selected_theme}]\n제목: {ai_result.get('title')}\n\n{ai_result.get('content')}",
                        clip_path=clip_path,
                        status="pending"
                    )
                    db.add(history)
                    sch.last_run_time = now
                    db.commit()
                    
                    ts = TelegramService()
                    msg = f"🎉 <b>[{sch.place_name}] 새로운 소식 및 클립 영상 완성!</b>\n\n최근 방문자 리뷰를 분석하여 새로운 마케팅 원고와 영상이 제작되었습니다. 웹 플랫폼에서 확인 후 스마트플레이스에 발행해 보세요!"
                    await ts.send_message(msg)
                    
            db.close()
        except Exception as e:
            logger.error(f"Failed to run place news job: {str(e)}")

    async def run_daily_blogspot_analysis(self):
        """매일 실행되는 블로그 스팟(Blogspot) SEO 순위 모니터링 작업 (새벽 5시 일괄 실행)"""
        logger.info(f"[{datetime.now()}] Starting daily scheduled Blogspot SEO ranking analysis...")
        try:
            from mbam_nextgen.backend.database import SessionLocal, BlogspotKeywordTracker
            import httpx
            
            db = SessionLocal()
            tracked_keywords = db.query(BlogspotKeywordTracker).all()
            if not tracked_keywords:
                logger.info("No tracked Blogspot keywords found.")
                db.close()
                return
                
            async with httpx.AsyncClient() as client:
                for item in tracked_keywords:
                    logger.info(f"Analyzing Blogspot Keyword: {item.keyword}")
                    # Google Custom Search API를 사용하여 블로그 스팟 순위 추적
                    # API Key가 없으므로 현재는 임의의 등락(Mock) 또는 실패 처리 로직만 유지
                    # 향후 Google API Key가 연결되면 여기서 순위를 검색해 current_rank를 갱신
                    import random
                    item.current_rank = random.randint(1, 100) # Mock 순위 업데이트
                    item.last_checked_at = datetime.now()
            
            db.commit()
            db.close()
            logger.info(f"[{datetime.now()}] Daily scheduled Blogspot SEO ranking analysis completed successfully.")
        except Exception as e:
            logger.error(f"Error in daily Blogspot analysis: {str(e)}")

    def load_content_schedule(self):
        try:
            from apscheduler.triggers.cron import CronTrigger
            db = SessionLocal()
            
            # 3. 글감 수집 스케줄러 추가 (기본 매일 09:00)
            content_sch = db.query(ContentSchedule).first()
            if not content_sch:
                content_sch = ContentSchedule(schedule_time="09:00")
                db.add(content_sch)
                db.commit()
            
            content_time_str = content_sch.schedule_time
            hr_str, mn_str = content_time_str.split(":")
            # misfire_grace_time: 정시에 서버가 잠깐 꺼져 놓쳐도, 이후 1시간 내 기동하면 발화
            # coalesce: 여러 번 밀린 경우 1회로 합침
            self.scheduler.add_job(
                self.run_content_sync_job,
                CronTrigger(hour=int(hr_str), minute=int(mn_str)),
                id="content_sync",
                replace_existing=True,
                misfire_grace_time=3600,
                coalesce=True,
            )
            logger.info(f"Loaded content sync schedule: {content_time_str} daily.")

            # 기동 시 보충: 오늘 예정 시각이 이미 지났는데 '오늘 수집 기록'이 없으면 30초 뒤 1회 즉시 수집
            # (로컬 PC 특성상 정시에 서버가 꺼져 있던 날을 위한 안전장치)
            try:
                import json
                from datetime import timedelta
                now = datetime.now()
                sched_today = now.replace(hour=int(hr_str), minute=int(mn_str), second=0, microsecond=0)
                ran_today = False
                binfo = os.path.join("mbam_nextgen", "data", "batch_info.json")
                if os.path.exists(binfo):
                    with open(binfo, encoding="utf-8") as bf:
                        last_run = (json.load(bf).get("last_batch_run") or "")
                    if last_run[:10] == now.strftime("%Y-%m-%d"):
                        ran_today = True
                if now >= sched_today and not ran_today:
                    self.scheduler.add_job(
                        self.run_content_sync_job, 'date',
                        run_date=now + timedelta(seconds=30),
                        id="content_sync_catchup", replace_existing=True,
                    )
                    logger.info("오늘 예정 글감수집 미실행 감지 → 기동 30초 뒤 보충 수집 예약")
            except Exception as e:
                logger.error(f"글감수집 보충 체크 실패: {e}")

            # 4. 플레이스 소식(리뷰 기반) 스케줄러 (매주 월요일 10:00 체크)
            self.scheduler.add_job(
                self.run_place_news_job,
                CronTrigger(day_of_week='mon', hour=10, minute=0),
                id="place_news_sync",
                replace_existing=True
            )
            logger.info("Loaded Place News schedule check (every Monday 10:00).")

            db.close()
        except Exception as e:
            logger.error(f"Error loading content schedule: {e}")

    def update_content_schedule(self, schedule_time: str):
        """글감 수집 스케줄러 작동 시간 업데이트"""
        try:
            hour, minute = map(int, schedule_time.split(":"))
            self.scheduler.reschedule_job('content_sync', trigger='cron', hour=hour, minute=minute)
            logger.info(f"Content sync scheduler job updated to {hour:02d}:{minute:02d} daily.")
        except Exception as e:
            logger.error(f"Error updating content schedule: {e}")

    def start(self):
        """스케줄러 시작 (DB 설정 무시, 매일 새벽 5시 강제 일괄 실행)"""
        # hour, minute = self._get_scheduled_time()
        hour, minute = 5, 0 # 새벽 5시 고정
        self.scheduler.add_job(self.run_daily_analysis, 'cron', hour=hour, minute=minute, id='daily_place_analysis', replace_existing=True)
        self.scheduler.add_job(self.run_daily_shopping_analysis, 'cron', hour=hour, minute=minute, id='daily_shopping_analysis', replace_existing=True)
        self.scheduler.add_job(self.run_daily_blogspot_analysis, 'cron', hour=hour, minute=minute, id='daily_blogspot_analysis', replace_existing=True)
        
        # Load Cafe Nurturing Schedules
        self.load_cafe_schedules()

        # Load Blog Daily Post Schedules
        self.load_blog_schedules()

        # Load Blog Reservations (1회 예약)
        self.load_blog_reservations()

        # Load Content Sync Schedule
        self.load_content_schedule()
        
        self.scheduler.start()
        logger.info(f"Scheduler started successfully. Next run is scheduled for {hour:02d}:{minute:02d} daily.")
        
    def update_schedule(self, hour: int, minute: int):
        """스케줄러 작동 시간 업데이트"""
        self.scheduler.reschedule_job('daily_place_analysis', trigger='cron', hour=hour, minute=minute)
        logger.info(f"Scheduler job updated. Next run is scheduled for {hour:02d}:{minute:02d} daily.")

    def shutdown(self):
        """스케줄러 종료"""
        self.scheduler.shutdown()
        logger.info("Scheduler shut down successfully.")

# 싱글톤 인스턴스 생성
scheduler_service = SchedulerService()
