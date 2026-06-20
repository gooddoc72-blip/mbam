from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import datetime

from mbam_nextgen.backend.database import get_db
from mbam_nextgen.backend.models import SavedManuscript

router = APIRouter(prefix="/api/manuscripts", tags=["manuscripts"])

class ManuscriptCreate(BaseModel):
    title: str
    content: str
    keyword: Optional[str] = None
    account_id: Optional[str] = None

class ManuscriptResponse(BaseModel):
    id: int
    title: str
    content: str
    keyword: Optional[str] = None
    account_id: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

@router.post("", response_model=ManuscriptResponse)
@router.post("/", response_model=ManuscriptResponse)
def save_manuscript(manuscript: ManuscriptCreate, db: Session = Depends(get_db)):
    db_manuscript = SavedManuscript(
        title=manuscript.title,
        content=manuscript.content,
        keyword=manuscript.keyword,
        account_id=manuscript.account_id
    )
    db.add(db_manuscript)
    db.commit()
    db.refresh(db_manuscript)
    return db_manuscript

@router.get("", response_model=List[ManuscriptResponse])
@router.get("/", response_model=List[ManuscriptResponse])
def get_manuscripts(db: Session = Depends(get_db)):
    manuscripts = db.query(SavedManuscript).order_by(SavedManuscript.created_at.desc()).all()
    return manuscripts

@router.delete("/{manuscript_id}")
def delete_manuscript(manuscript_id: int, db: Session = Depends(get_db)):
    manuscript = db.query(SavedManuscript).filter(SavedManuscript.id == manuscript_id).first()
    if not manuscript:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    
    db.delete(manuscript)
    db.commit()
    return {"status": "success", "message": "Deleted successfully"}

from fastapi import UploadFile, File
import io

@router.post("/upload")
async def upload_manuscript(file: UploadFile = File(...)):
    filename = file.filename
    content = ""
    
    try:
        file_bytes = await file.read()
        
        if filename.endswith('.txt'):
            try:
                content = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                content = file_bytes.decode('cp949', errors='replace')
        
        elif filename.endswith('.docx'):
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            content = "\n".join([para.text for para in doc.paragraphs])
            
        else:
            raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식입니다. .txt와 .docx만 지원됩니다.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 파싱에 실패했습니다: {str(e)}")
        
    return {
        "success": True,
        "filename": filename,
        "content": content
    }
