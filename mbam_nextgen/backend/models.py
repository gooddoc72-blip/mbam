from sqlalchemy import Column, Integer, String, Text, DateTime
from mbam_nextgen.backend.database import Base
import datetime

class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # 분석 결과를 JSON 형태의 문자열로 저장
    result_data = Column(Text)

class SavedManuscript(Base):
    __tablename__ = "saved_manuscripts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    keyword = Column(String, index=True, nullable=True)
    account_id = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserAIKey(Base):
    __tablename__ = "user_ai_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)  # 로그인 사용자 식별자(sub)
    claude_key = Column(String, nullable=True)
    gemini_key = Column(String, nullable=True)
    openai_key = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class BlogIndexRecord(Base):
    __tablename__ = "blog_index_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)
    blog_id = Column(String, index=True)
    title = Column(String, nullable=True)
    score = Column(Integer)
    grade = Column(Integer)
    tier = Column(String)
    level = Column(Integer)
    result_data = Column(Text)  # 전체 결과(stats+index) JSON 문자열
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
