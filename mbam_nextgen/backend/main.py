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

# mbam_nextgen/data 는 git 에 없어 깨끗한 컨테이너(Railway)에는 처음에 없다.
# 여러 라우터·서비스가 import 시점에 data/ranking.db 를 열기 때문에, 라우터 import 보다 먼저 만든다.
# (라우터 import 순서가 바뀌자 schedule.py 가 폴더 생성 전에 열려 운영 백엔드가 기동 실패했었다)
os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"), exist_ok=True)

# ── 제품 프로파일 ──────────────────────────────────────────────────────────
# MBAM_PRODUCT=cafe 면 '네이버 카페 전용판', =blog 면 '블로그 자동화 전용판'이 된다.
# 그 제품에 필요 없는 라우터를 아예 마운트하지 않아, 프론트를 우회해 직접 호출해도 404 가 난다.
# (코드베이스는 하나로 유지 — 제품마다 포크하면 유지보수가 배로 늘어난다)
#
# ⚠ 이 판정은 반드시 라우터 import 보다 먼저 와야 한다.
#   예전에는 라우터를 전부 import 한 뒤 마운트만 골라서 했는데, 카페판이 쓰지도 않는
#   모듈(content 9.3초 · rank 2.5초 · shopping 2.4초 …)을 import 하느라
#   기동에 14초 이상을 그냥 버렸다. (실측)
PRODUCT = (os.getenv("MBAM_PRODUCT", "mbam") or "mbam").strip().lower()
IS_CAFE_EDITION = PRODUCT == "cafe"
IS_BLOG_EDITION = PRODUCT == "blog"

# 카페판이 쓰는 라우터 화이트리스트 — 카페 4개 화면(형태소분석/포스팅·육성/
# 이미지세탁소/순위추적) + 로그인·설정·계정관리·원고가 의존하는 것만.
_CAFE_ROUTERS = {
    "auth",          # 로그인
    "seo",           # 카페 형태소·권위 분석 (analyze-cafe-urls / analyze-cafe-post)
    "settings",      # 설정, 이미지 세탁소 라이브러리
    "auto_post",     # 카페 발행 + 이미지 캡션
    "cafe_nurture",  # 카페 육성·댓글·공감
    "cafe_rank",     # 카페/블로그 순위추적
    "proxy",         # 프록시 IP 등록
    "account",       # 네이버 계정 관리
    # "manuscript" (원고 관리)는 카페판에서 뺐다 — 원고 업로드가 '카페 포스팅 > 원고 업로드'
    # (/api/cafe-nurture/parse-manuscript) 로 합쳐졌고, 이 라우터를 쓰는 화면이 남아 있지 않다.
    "multi_task",    # 계정관리 화면
    "history",       # 작업 기록
    "schedule",      # 예약
    "agent",         # 로컬 에이전트 연동(폴더 선택 등)
    "admin",         # 관리자
    "sync",          # 계정 동기화(여러 PC 에서 같은 계정 쓰기)
    "image_wash",    # 이미지 세탁소(settings 가 관리자 전용이라 따로 뺀 경로)
}


# 블로그 전용판이 쓰는 라우터 화이트리스트 — 블로그 메뉴(진단/형태소분석/발행/
# 플레이스 블로그/소통·이웃/이미지세탁소/블로그스팟/티스토리) + 글감·원고·계정·순위추적.
# 제외한 것: rank(쇼핑·플레이스 순위), place(플레이스 진단), shopping, coupang.
#   - 플레이스 블로그(/place-blog)는 blog-posting 화면을 재사용하고 실제 호출은
#     auto_post·cafe-nurture 로 나가므로 place 라우터가 필요 없다.
_BLOG_ROUTERS = {
    "auth",           # 설치형 로컬 세션
    "seo",            # 블로그 진단 · 형태소 분석
    "settings",       # 설정, 이미지 세탁소 라이브러리
    "auto_post",      # 블로그 발행 + 이미지 캡션
    "cafe_nurture",   # 계정 목록·원고 파싱·맛집(플레이스) 수집 — 블로그 화면도 이걸 쓴다
    "cafe_rank",      # 블로그 순위추적(type=blog)
    "communication",  # 소통 & 이웃
    "blogspot",       # 구글 블로그스팟
    "blog_schedule",  # 매일 자동발행 · 1회 예약
    "tistory",        # 티스토리
    "content",        # 글감수집 (매일 자동발행이 글감 카테고리를 고른다)
    "manuscript",     # 원고관리
    "proxy",          # 프록시 IP
    "account",        # 네이버 계정 관리
    "multi_task",     # 계정관리 화면
    "history",        # 작업 기록
    "schedule",       # 예약
    "agent",          # 로컬 에이전트 연동(폴더 선택 등)
    "admin",          # 관리자
    "sync",           # 계정 동기화
    "image_wash",     # 이미지 세탁소
}

# 제품 → 허용 라우터. 없는 제품(mbam 풀버전)은 전부 마운트한다.
_PRODUCT_ROUTERS = {"cafe": _CAFE_ROUTERS, "blog": _BLOG_ROUTERS}
_ALLOWED_ROUTERS = _PRODUCT_ROUTERS.get(PRODUCT)


def _enabled(name: str) -> bool:
    """이 제품에서 해당 라우터를 마운트할지."""
    return True if _ALLOWED_ROUTERS is None else (name in _ALLOWED_ROUTERS)


# 어느 제품에서도 쓰는 라우터
from mbam_nextgen.backend.routers import (
    seo, settings, auto_post, multi_task, history, auth_router, schedule,
    admin_router, cafe_nurture, manuscript_router, account_router,
    agent_router, cafe_rank_router, proxy_router, sync_router, image_wash_router,
)
# 제품마다 마운트 여부가 갈리는 라우터 — 마운트도 안 할 걸 import 할 이유가 없다.
# (아래 include_router 들은 전부 같은 _enabled() 가드 안에서만 이 이름들을 쓴다)
# 하나씩 따로 거는 이유: 카페판은 content·rank·shopping 을, 블로그판은 rank·place·
# shopping·coupang 을 빼는데, 빼는 목록이 서로 달라 한 덩어리로 묶을 수 없다.
if _enabled("rank"):
    from mbam_nextgen.backend.routers import rank
if _enabled("content"):
    from mbam_nextgen.backend.routers import content
if _enabled("place"):
    from mbam_nextgen.backend.routers import place
if _enabled("communication"):
    from mbam_nextgen.backend.routers import communication
if _enabled("shopping"):
    from mbam_nextgen.backend.routers import shopping_router
if _enabled("blogspot"):
    from mbam_nextgen.backend.routers import blogspot_router
if _enabled("coupang"):
    from mbam_nextgen.backend.routers import coupang
if _enabled("blog_schedule"):
    from mbam_nextgen.backend.routers import blog_schedule
if _enabled("tistory"):
    from mbam_nextgen.backend.routers import tistory_router
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
        "ALTER TABLE cafe_rank_items ADD COLUMN title VARCHAR",
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
    tistory_daily = None
    billing_sched = None
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
        # 티스토리 매일 자동발행 — 브라우저 자동화라 잡 적재만, 실제 발행은 로컬 에이전트.
        from mbam_nextgen.services.tistory_daily_scheduler import tistory_daily_scheduler
        tistory_daily = tistory_daily_scheduler
        tistory_daily.start()
        # 웹 회원 정기결제 — 토스 키가 없으면 주기마다 아무것도 안 하고 넘어간다.
        from mbam_nextgen.services.billing_scheduler import billing_scheduler
        billing_sched = billing_scheduler
        billing_sched.start()
    yield
    if billing_sched:
        billing_sched.shutdown()
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
    if tistory_daily:
        tistory_daily.shutdown()

app = FastAPI(
    title="SEO Analysis Platform API",
    description="FastAPI Backend for high-performance SEO crawling and AI analysis",
    version="1.0.0",
    lifespan=lifespan
)

_PRODUCT_LABEL = {"cafe": " (네이버 카페 전용판)", "blog": " (블로그 자동화 전용판)"}
print(f"[startup] 제품 프로파일: {PRODUCT}" + _PRODUCT_LABEL.get(PRODUCT, ""))

# 헬스체크 — 배포/재기동 확인용 (started_at 이 바뀌면 새 컨테이너)
from datetime import datetime as _dt
_STARTED_AT = _dt.utcnow().isoformat() + "Z"


@app.get("/api/health", tags=["Health"])
async def health():
    return {"status": "ok", "started_at": _STARTED_AT, "product": PRODUCT}


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
if _enabled("auth"):
    app.include_router(auth_router.router, prefix="/api/auth", tags=["Authentication"])

# 라우터 연결 (인증 필수 라우터)
if _enabled("seo"):
    app.include_router(seo.router, prefix="/api/seo", tags=["SEO Analysis"], dependencies=[Depends(setup_ai_context)])
if _enabled("settings"):
    app.include_router(settings.router, prefix="/api/settings", tags=["Settings"], dependencies=[Depends(verify_admin)])
if _enabled("rank"):
    app.include_router(rank.router, prefix="/api/seo/rank", tags=["Ranking Tracker"], dependencies=[Depends(get_current_user)])
if _enabled("content"):
    app.include_router(content.router, prefix="/api/content", tags=["Content Collect"], dependencies=[Depends(setup_ai_context)])
if _enabled("place"):
    app.include_router(place.router, prefix="/api/place", tags=["Place SEO"], dependencies=[Depends(setup_ai_context)])
if _enabled("auto_post"):
    app.include_router(auto_post.router, prefix="/api/auto_post", tags=["Blog & Cafe Auto Post"], dependencies=[Depends(setup_ai_context)])
if _enabled("communication"):
    app.include_router(communication.router, prefix="/api/communication", tags=["Neighbor & Communication"], dependencies=[Depends(setup_ai_context)])
if _enabled("multi_task"):
    app.include_router(multi_task.router, prefix="/api/multi_task", tags=["multi_task"], dependencies=[Depends(setup_ai_context)])
if _enabled("history"):
    app.include_router(history.router, prefix="/api/history", tags=["SaaS History"], dependencies=[Depends(get_current_user)])
if _enabled("schedule"):
    app.include_router(schedule.router, dependencies=[Depends(get_current_user)])
if _enabled("shopping"):
    app.include_router(shopping_router.router, dependencies=[Depends(get_current_user)])
if _enabled("admin"):
    app.include_router(admin_router.router)
if _enabled("billing"):
    # 웹 회원 정기결제 — 설치형(카페·블로그 전용판)은 기기 승인 기간으로 관리하므로 마운트 안 함
    from mbam_nextgen.backend.routers import billing_router
    app.include_router(billing_router.router, prefix="/api/billing", tags=["Billing"])
if _enabled("blogspot"):
    app.include_router(blogspot_router.router, dependencies=[Depends(setup_ai_context)])
if _enabled("tistory"):
    app.include_router(tistory_router.router, dependencies=[Depends(setup_ai_context)])
if _enabled("cafe_rank"):
    app.include_router(cafe_rank_router.router, dependencies=[Depends(get_current_user)])
if _enabled("proxy"):
    app.include_router(proxy_router.router, dependencies=[Depends(get_current_user)])
if _enabled("cafe_nurture"):
    # ⚠ setup_ai_context 여야 한다(get_current_user 만 걸면 안 된다).
    #   이 라우터는 AI 댓글을 만든다(미리보기 + 댓글 작업). setup_ai_context 가
    #   [설정 > AI API 키] 에 저장한 키를 AI 모듈로 넘겨주는데, 이게 빠져 있으면
    #   키를 제대로 넣어도 무시되고 .env 환경변수만 찾는다.
    #   개발 PC 는 .env 가 있어 동작했지만, 고객 PC 는 .env 가 없어
    #   'API 키를 확인하세요' 만 반복됐다. (setup_ai_context 는 내부에서 인증도 한다)
    app.include_router(cafe_nurture.router, dependencies=[Depends(setup_ai_context)])
if _enabled("blog_schedule"):
    app.include_router(blog_schedule.router, dependencies=[Depends(get_current_user)])
if _enabled("coupang"):
    app.include_router(coupang.router, prefix="/api/coupang", tags=["Coupang"], dependencies=[Depends(get_current_user)])
if _enabled("manuscript"):
    app.include_router(manuscript_router.router, dependencies=[Depends(setup_ai_context)])
if _enabled("account"):
    app.include_router(account_router.router, dependencies=[Depends(get_current_user)])
if _enabled("agent"):
    app.include_router(agent_router.router, tags=["Local Agent"])
if _enabled("sync"):
    app.include_router(sync_router.router, dependencies=[Depends(get_current_user)])
if _enabled("image_wash"):
    # settings 라우터는 관리자 전용이라 일반 고객이 이미지 세탁소를 쓸 수 없었다.
    # 같은 처리 함수를 '로그인만 요구하는' 경로로도 열어준다.
    app.include_router(image_wash_router.router, dependencies=[Depends(get_current_user)])
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
