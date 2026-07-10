import sys
import os
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import sys
import asyncio

if sys.platform == 'win32':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)

from mbam_nextgen.backend.routers import seo, settings, rank, content, place, auto_post, communication, multi_task, history, auth_router, schedule, shopping_router, admin_router, cafe_nurture, blogspot_router, coupang, manuscript_router, account_router, blog_schedule, agent_router
from mbam_nextgen.backend.database import engine, Base
from mbam_nextgen.backend.auth import get_current_user, verify_admin
from mbam_nextgen.backend.ai_context import setup_ai_context

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

try:
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified successfully.")
except Exception as e:
    print(f"[Warning] Failed to connect to database during startup: {e}")

# 기존 테이블 컬럼 추가(경량 마이그레이션) — create_all 은 신규 테이블만 만들고 컬럼은 안 붙임.
# 각 ALTER 를 독립 트랜잭션(engine.begin)으로 실행 → 이미 있으면(중복 컬럼) 예외 무시.
# VARCHAR 는 Postgres/SQLite 공통 문법이라 두 엔진 모두 동작.
try:
    from sqlalchemy import text as _sql_text
    _column_migrations = [
        "ALTER TABLE blog_schedules ADD COLUMN last_run_url VARCHAR",
        "ALTER TABLE blog_schedules ADD COLUMN last_run_title VARCHAR",
        "ALTER TABLE cafe_schedules ADD COLUMN last_run_date VARCHAR",
    ]
    for _mig in _column_migrations:
        try:
            with engine.begin() as _conn:
                _conn.execute(_sql_text(_mig))
        except Exception:
            pass  # 컬럼이 이미 존재하면 무시
except Exception as e:
    print(f"[Warning] Column migration skipped: {e}")

from contextlib import asynccontextmanager
from mbam_nextgen.services.scheduler_service import scheduler_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 설정 화면에서 저장한 API 키(DB 영속)를 os.environ 에 주입 — 재배포 후에도 유지
    try:
        from mbam_nextgen.backend.routers.settings import hydrate_env_from_db
        hydrate_env_from_db()
    except Exception as e:
        print(f"[startup] DB 설정 주입 실패: {e}")
    # [방법 B] 스케줄러 잡(콘텐츠 동기화·플레이스 소식·순위분석)은 전부 네이버 스크래핑이라
    # 클라우드(cloud 모드)에선 돌 수 없다(데이터센터 IP). 클라우드에서 켜면 startup이 막혀
    # 크래시 루프가 발생 → cloud 모드에선 스케줄러를 기동하지 않는다(스케줄 실행은 로컬/에이전트 몫).
    from mbam_nextgen.backend import jobs as jobsvc
    scheduler_on = not jobsvc.is_cloud_mode()
    cloud_batch = None
    blog_daily = None
    content_daily = None
    blogspot_daily = None
    cafe_daily = None
    if scheduler_on:
        scheduler_service.start()
    else:
        # cloud 모드: 스크래핑은 못 하지만 '적재'는 가능 — 새벽 5시(KST)에
        # 추적목록(플레이스/쇼핑)을 에이전트 작업 큐에 넣는 경량 스케줄러.
        from mbam_nextgen.services.cloud_batch import cloud_batch_scheduler
        cloud_batch = cloud_batch_scheduler
        cloud_batch.start()
        # 매일 자동발행(BlogSchedule)도 예약 시각마다 에이전트 잡으로 적재.
        from mbam_nextgen.services.blog_daily_scheduler import blog_daily_scheduler
        blog_daily = blog_daily_scheduler
        blog_daily.start()
        # 글감 자동수집(ContentSchedule) — 정부/공공 데이터는 서버에서 직접 수집 가능.
        from mbam_nextgen.services.content_daily_scheduler import content_daily_scheduler
        content_daily = content_daily_scheduler
        content_daily.start()
        # 블로그스팟 매일 자동발행 — Blogger API 라 클라우드에서 직접 발행(에이전트 불필요).
        from mbam_nextgen.services.blogspot_daily_scheduler import blogspot_daily_scheduler
        blogspot_daily = blogspot_daily_scheduler
        blogspot_daily.start()
        # 카페 예약 육성 — 네이버 스크래핑이라 클라우드는 잡 적재만, 실제 실행은 로컬 에이전트.
        from mbam_nextgen.services.cafe_daily_scheduler import cafe_daily_scheduler
        cafe_daily = cafe_daily_scheduler
        cafe_daily.start()
    yield
    if scheduler_on:
        scheduler_service.shutdown()
    if cloud_batch:
        cloud_batch.shutdown()
    if blog_daily:
        blog_daily.shutdown()
    if content_daily:
        content_daily.shutdown()
    if blogspot_daily:
        blogspot_daily.shutdown()
    if cafe_daily:
        cafe_daily.shutdown()

app = FastAPI(
    title="SEO Analysis Platform API",
    description="FastAPI Backend for high-performance SEO crawling and AI analysis",
    version="1.0.0",
    lifespan=lifespan
)

# 헬스체크 — 배포/재기동 확인용 (started_at 이 바뀌면 새 컨테이너)
from datetime import datetime as _dt
_STARTED_AT = _dt.utcnow().isoformat() + "Z"


@app.get("/api/health", tags=["Health"])
async def health():
    return {"status": "ok", "started_at": _STARTED_AT}


# CORS Middleware (SaaS 보안 강화: 특정 프론트엔드 도메인만 허용)
origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001")
allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 연결 (인증 미적용 라우터)
app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])

# 라우터 연결 (인증 필수 라우터)
app.include_router(seo.router, prefix="/api/seo", tags=["SEO Analysis"], dependencies=[Depends(setup_ai_context)])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"], dependencies=[Depends(verify_admin)])
app.include_router(rank.router, prefix="/api/seo/rank", tags=["Ranking Tracker"], dependencies=[Depends(get_current_user)])
app.include_router(content.router, prefix="/api/content", tags=["Content Collect"], dependencies=[Depends(setup_ai_context)])
app.include_router(place.router, prefix="/api/place", tags=["Place SEO"], dependencies=[Depends(setup_ai_context)])
app.include_router(auto_post.router, prefix="/api/auto_post", tags=["Blog & Cafe Auto Post"], dependencies=[Depends(setup_ai_context)])
app.include_router(communication.router, prefix="/api/communication", tags=["Neighbor & Communication"], dependencies=[Depends(setup_ai_context)])
app.include_router(multi_task.router, prefix="/api/multi_task", tags=["multi_task"], dependencies=[Depends(setup_ai_context)])
app.include_router(history.router, prefix="/api/history", tags=["SaaS History"], dependencies=[Depends(get_current_user)])
app.include_router(schedule.router, dependencies=[Depends(get_current_user)])
app.include_router(shopping_router.router, dependencies=[Depends(get_current_user)])
app.include_router(admin_router.router)
app.include_router(blogspot_router.router, dependencies=[Depends(setup_ai_context)])
app.include_router(cafe_nurture.router, dependencies=[Depends(get_current_user)])
app.include_router(blog_schedule.router, dependencies=[Depends(get_current_user)])
app.include_router(coupang.router, prefix="/api/coupang", tags=["Coupang"], dependencies=[Depends(get_current_user)])
app.include_router(manuscript_router.router, dependencies=[Depends(setup_ai_context)])
app.include_router(account_router.router, dependencies=[Depends(get_current_user)])
app.include_router(agent_router.router, tags=["Local Agent"])
# 수집된 사진 서빙
from fastapi.staticfiles import StaticFiles
images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp_clips", "images")
os.makedirs(images_dir, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=images_dir), name="images")

# 설치형 배포 시 Next.js 정적 파일 서빙 로직
from fastapi.staticfiles import StaticFiles
frontend_out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "mbam-web", "out")
if os.path.exists(frontend_out):
    app.mount("/", StaticFiles(directory=frontend_out, html=True), name="static")
else:
    @app.get("/")
    async def root():
        return {"message": "Welcome to SEO Analysis Platform Backend API"}
