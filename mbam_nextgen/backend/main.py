from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
import sys
import asyncio

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)

from mbam_nextgen.backend.routers import seo, settings, rank, content, place, auto_post, communication, multi_task, history, auth_router, schedule, shopping_router, admin_router, cafe_nurture, blogspot_router
from mbam_nextgen.backend.database import engine, Base
from mbam_nextgen.backend.auth import get_current_user

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

try:
    Base.metadata.create_all(bind=engine)
    print("Database tables created/verified successfully.")
except Exception as e:
    print(f"[Warning] Failed to connect to database during startup: {e}")

from contextlib import asynccontextmanager
from mbam_nextgen.services.scheduler_service import scheduler_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 스케줄러 가동
    scheduler_service.start()
    yield
    # 종료 시 스케줄러 중지
    scheduler_service.shutdown()

app = FastAPI(
    title="SEO Analysis Platform API",
    description="FastAPI Backend for high-performance SEO crawling and AI analysis",
    version="1.0.0",
    lifespan=lifespan
)

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
app.include_router(seo.router, prefix="/api/seo", tags=["SEO Analysis"], dependencies=[Depends(get_current_user)])
# 설정 라우터는 API 키/시크릿을 읽고 .env를 덮어쓰므로 관리자 전용
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"], dependencies=[Depends(admin_router.verify_admin)])
app.include_router(rank.router, prefix="/api/seo/rank", tags=["Ranking Tracker"], dependencies=[Depends(get_current_user)])
app.include_router(content.router, prefix="/api/content", tags=["Content Collect"], dependencies=[Depends(get_current_user)])
app.include_router(place.router, prefix="/api/place", tags=["Place SEO"], dependencies=[Depends(get_current_user)])
app.include_router(auto_post.router, prefix="/api/auto_post", tags=["Blog & Cafe Auto Post"], dependencies=[Depends(get_current_user)])
app.include_router(communication.router, prefix="/api/communication", tags=["Neighbor & Communication"], dependencies=[Depends(get_current_user)])
app.include_router(multi_task.router, prefix="/api/multi_task", tags=["multi_task"], dependencies=[Depends(get_current_user)])
app.include_router(history.router, prefix="/api/history", tags=["SaaS History"], dependencies=[Depends(get_current_user)])
app.include_router(schedule.router, dependencies=[Depends(get_current_user)])
app.include_router(shopping_router.router, dependencies=[Depends(get_current_user)])
app.include_router(admin_router.router)
app.include_router(blogspot_router.router, dependencies=[Depends(get_current_user)])
app.include_router(cafe_nurture.router, dependencies=[Depends(get_current_user)])

# 설치형 배포 시 Next.js 정적 파일 서빙 로직
from fastapi.staticfiles import StaticFiles
frontend_out = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "mbam-web", "out")
if os.path.exists(frontend_out):
    app.mount("/", StaticFiles(directory=frontend_out, html=True), name="static")
else:
    @app.get("/")
    async def root():
        return {"message": "Welcome to SEO Analysis Platform Backend API"}
