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
