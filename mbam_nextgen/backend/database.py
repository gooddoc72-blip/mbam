import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./seo_history.db")

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
    post_count_per_day = Column(Integer, default=1) # 1일 작성 횟수
    post_qty_per_time = Column(Integer, default=1) # 1회당 작성 수량
    is_active = Column(Integer, default=1)
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
    price = Column(Integer, default=0) # 판매가격
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
