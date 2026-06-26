import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

# Always use project root for db to prevent appearing/disappearing bug
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = f"sqlite:///{os.path.join(PROJECT_ROOT, 'seo_history.db').replace('\\\\', '/')}"

DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DB_PATH)
if DATABASE_URL == "sqlite:///./mbam_local.db" or DATABASE_URL == "sqlite:///./seo_history.db":
    DATABASE_URL = DEFAULT_DB_PATH

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Advertiser(Base):
    __tablename__ = "advertisers"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=True)
    social_provider = Column(String, nullable=True)
    social_id = Column(String, nullable=True)
    business_name = Column(String)
    status = Column(String, default="active")
    plan_type = Column(String, default="trial")
    trial_ends_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    max_usage = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

class Agency(Base):
    __tablename__ = "agencies"

    id = Column(String, primary_key=True, index=True)
    login_id = Column(String, unique=True, index=True)
    password = Column(String)
    agency_name = Column(String)
    manager_name = Column(String)
    status = Column(String, default="active")
    plan_type = Column(String, default="trial")
    trial_ends_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    max_usage = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

class Distributor(Base):
    __tablename__ = "distributors"

    id = Column(String, primary_key=True, index=True)
    login_id = Column(String, unique=True, index=True)
    password = Column(String)
    business_name = Column(String)
    representative = Column(String)
    status = Column(String, default="active")
    plan_type = Column(String, default="trial")
    trial_ends_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    max_usage = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

class DeviceSession(Base):
    __tablename__ = "device_sessions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True) # ID of Advertiser, Agency, or Distributor
    hwid = Column(String, index=True)
    last_login = Column(DateTime, default=datetime.utcnow)

class NaverAccount(Base):
    __tablename__ = "naver_accounts"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True) # ID of Advertiser, Agency, or Distributor
    naver_id = Column(String, index=True)
    naver_pw = Column(String) # 암호화되어 저장됨
    blog_addr = Column(String, nullable=True)  # 로그인ID와 다른 실제 블로그 주소(예: bonetacasa)
    status = Column(String, default="active") # active, blocked, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class JoinedCafe(Base):
    __tablename__ = "joined_cafes"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("naver_accounts.id", ondelete="CASCADE"))
    cafe_url = Column(String)
    board_name = Column(String)
    nickname = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CafeSchedule(Base):
    __tablename__ = "cafe_schedules"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True)
    account_id = Column(String, ForeignKey("naver_accounts.id", ondelete="CASCADE"))
    cafe_id = Column(String, ForeignKey("joined_cafes.id", ondelete="CASCADE"))
    schedule_time = Column(String) # e.g. "14:00"
    content_category = Column(String, nullable=True) # e.g. "소상공인 24"
    content_item_id = Column(String, nullable=True)
    content_item_title = Column(String, nullable=True)
    post_count_per_day = Column(Integer, default=1) # 1일 작성/방문 횟수
    post_qty_per_time = Column(Integer, default=1) # 1회당 작성 수량
    # 게시글 부스트(조회수/좋아요): 대상 글 URL이 있으면 방문+좋아요, 없으면 방문(육성)만
    target_post_url = Column(String, nullable=True)
    do_view = Column(Integer, default=1)   # 조회수 올리기(방문)
    do_like = Column(Integer, default=1)   # 좋아요 누르기
    visit_interval_min = Column(Integer, default=30)  # 방문 간 텀(분)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class BlogSchedule(Base):
    """블로그 매일 자동발행 예약: 글감수집 카테고리에서 매일 같은 시각에 글감을 뽑아 자동 포스팅."""
    __tablename__ = "blog_schedules"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True)
    account_id = Column(String, ForeignKey("naver_accounts.id", ondelete="CASCADE"))
    schedule_time = Column(String)  # "HH:MM" — 매일 발행 시각
    content_category = Column(String, nullable=True)  # 글감수집 카테고리
    post_count_per_day = Column(Integer, default=1)   # 1일 발행 개수
    ai_provider = Column(String, default="claude")
    distribution_mode = Column(String, default="normal")  # normal | quick
    generate_card_news = Column(Integer, default=1)   # 첨부 이미지 없을 때 AI 카드뉴스 5장 자동 생성
    is_active = Column(Integer, default=1)
    last_run_date = Column(String, nullable=True)  # "YYYY-MM-DD" — 하루 1회 중복 방지
    last_index = Column(Integer, default=0)         # 글감 회전 인덱스(매일 다른 글감)
    created_at = Column(DateTime, default=datetime.utcnow)

class CafeManuscript(Base):
    """카페 일괄 발행용 저장 원고: 계정별로 (원고 + 타겟 카페/게시판)을 각각 저장 → 일괄 발행."""
    __tablename__ = "cafe_manuscripts"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True)
    account_id = Column(String)   # 발행 네이버 아이디
    cafe_url = Column(String)     # 타겟 카페 URL
    board_name = Column(String)   # 게시판 이름
    title = Column(String)
    content = Column(Text)
    status = Column(String, default="saved")  # saved | posted
    created_at = Column(DateTime, default=datetime.utcnow)

class ContentSchedule(Base):
    __tablename__ = "content_schedules"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    schedule_time = Column(String, default="09:00") # "HH:MM" format
    interest_categories = Column(String, default="") # Comma-separated list of categories
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PlaceNewsSchedule(Base):
    __tablename__ = "place_news_schedules"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    place_url = Column(String, index=True) # e.g. https://m.place.naver.com/restaurant/1234/home
    place_name = Column(String)
    interval_weeks = Column(Integer, default=1) # 1 or 2
    is_active = Column(Integer, default=1)
    last_run_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class PlaceNewsHistory(Base):
    __tablename__ = "place_news_history"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    schedule_id = Column(String, ForeignKey("place_news_schedules.id", ondelete="CASCADE"))
    generated_text = Column(String)
    clip_path = Column(String)
    status = Column(String, default="pending") # pending, published
    created_at = Column(DateTime, default=datetime.utcnow)

class ShoppingTrackedItem(Base):
    __tablename__ = "shopping_tracked_items"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    mid = Column(String, index=True)
    keyword = Column(String, index=True)
    name = Column(String)
    latest_places = Column(Text, nullable=True)
    latest_report = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ShoppingHistory(Base):
    __tablename__ = "shopping_history"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tracked_id = Column(String, ForeignKey("shopping_tracked_items.id", ondelete="CASCADE"))
    date_str = Column(String, index=True) # YYYY-MM-DD
    rank = Column(Integer)
    page = Column(Integer)
    visitor_reviews = Column(Integer, default=0) # 구매평수 (Shopping 리뷰수)
    blog_reviews = Column(Integer, default=0) # 안쓰지만 통일을 위해 0
    saves = Column(Integer, default=0) # 찜수
    purchases = Column(Integer, default=0) # 구매수
    n1 = Column(Integer, default=0)
    n2 = Column(Integer, default=0)
    n3 = Column(Integer, default=0)
    n4 = Column(Integer, default=100)
    n5 = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class BlogspotAccount(Base):
    __tablename__ = "blogspot_accounts"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    account_name = Column(String) # 구분용 이름 (예: 메인 블로그)
    blog_id = Column(String) # Blogger API Blog ID
    access_token = Column(String)
    refresh_token = Column(String)
    client_id = Column(String)
    client_secret = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class BlogspotPostHistory(Base):
    __tablename__ = "blogspot_post_history"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("blogspot_accounts.id", ondelete="CASCADE"))
    keyword = Column(String) # 발급/생성 타겟 키워드
    title = Column(String)
    post_url = Column(String)
    status = Column(String, default="success") # success, failed
    created_at = Column(DateTime, default=datetime.utcnow)

class BlogspotKeywordTracker(Base):
    __tablename__ = "blogspot_keyword_tracker"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("blogspot_accounts.id", ondelete="CASCADE"))
    keyword = Column(String, index=True)
    current_rank = Column(Integer, default=0)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CoupangTrackedItem(Base):
    __tablename__ = "coupang_tracked_items"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String, index=True) # 쿠팡 상품번호 (productId)
    keyword = Column(String, index=True)
    name = Column(String)
    latest_places = Column(Text, nullable=True)
    latest_report = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class CoupangHistory(Base):
    __tablename__ = "coupang_history"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tracked_id = Column(String, ForeignKey("coupang_tracked_items.id", ondelete="CASCADE"))
    date_str = Column(String, index=True) # YYYY-MM-DD
    rank = Column(Integer)
    page = Column(Integer)
    reviews = Column(Integer, default=0) # 상품평 수
    rating = Column(String, default="0.0") # 별점
    price = Column(Integer, default=0) # 판매가격
    is_rocket = Column(Integer, default=0) # 로켓배송 여부 (1: True, 0: False)
    n1 = Column(Integer, default=0) # 검색 적합도 임의 배점
    n5 = Column(Integer, default=0) # 총점 임의 배점
    created_at = Column(DateTime, default=datetime.utcnow)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
