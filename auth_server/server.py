from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime

DATABASE_URL = "sqlite:///./hwid_auth.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class HWIDRecord(Base):
    __tablename__ = "hwids"
    hwid = Column(String, primary_key=True, index=True)
    memo = Column(String, nullable=True) # 사용자 이름, 부서 등 메모
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Crawler Pro Auth Server")

class VerifyRequest(BaseModel):
    hwid: str

class RegisterRequest(BaseModel):
    hwid: str
    memo: str = ""

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/verify")
def verify_hwid(req: VerifyRequest, db: Session = Depends(get_db)):
    record = db.query(HWIDRecord).filter(HWIDRecord.hwid == req.hwid).first()
    if record and record.is_active:
        return {"authorized": True, "message": "승인된 기기입니다."}
    return {"authorized": False, "message": "등록되지 않았거나 차단된 기기입니다."}

@app.post("/register")
def register_hwid(req: RegisterRequest, db: Session = Depends(get_db)):
    record = db.query(HWIDRecord).filter(HWIDRecord.hwid == req.hwid).first()
    if record:
        return {"success": False, "message": "이미 등록된 기기입니다."}
    new_record = HWIDRecord(hwid=req.hwid, memo=req.memo, is_active=True)
    db.add(new_record)
    db.commit()
    return {"success": True, "message": "성공적으로 등록되었습니다."}

@app.get("/list")
def list_hwids(db: Session = Depends(get_db)):
    records = db.query(HWIDRecord).all()
    return [{"hwid": r.hwid, "memo": r.memo, "is_active": r.is_active, "created_at": r.created_at} for r in records]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
