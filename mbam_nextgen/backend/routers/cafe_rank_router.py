"""카페 글 통합검색 순위 추적 라우터.

(키워드, 카페 글 URL)을 등록해두면, 로컬 에이전트(집 IP)가 네이버 검색을 스크래핑해
- 통합검색 카페/VIEW 블록 내 순위(tongsearch_rank)
- 카페탭 전체 순위(cafetab_rank)
를 수집하고, persister 가 CafeRankHistory 에 일자별로 기록한다. 클라우드 새벽 배치(cloud_batch)가
매일 자동 수집 잡을 적재하고, 사용자가 '지금 수집'으로 즉시 실행할 수도 있다.
"""
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mbam_nextgen.backend.database import get_db, CafeRankItem, CafeRankHistory
from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.backend import jobs as jobsvc

router = APIRouter(prefix="/api/cafe-rank", tags=["Cafe Rank Tracker"])
KST = ZoneInfo("Asia/Seoul")


def _uid(cu):
    return cu.get("sub")


class CafeRankCreate(BaseModel):
    keyword: str
    target_url: str
    name: Optional[str] = None


@router.get("/items", summary="카페 순위 추적 목록(+최근 순위·히스토리)")
def list_items(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    rows = db.query(CafeRankItem).filter(CafeRankItem.user_id == _uid(current_user)).order_by(CafeRankItem.created_at.desc()).all()
    out = []
    for r in rows:
        hist = (db.query(CafeRankHistory)
                .filter(CafeRankHistory.tracked_id == r.id)
                .order_by(CafeRankHistory.date_str.desc()).limit(14).all())
        out.append({
            "id": r.id, "keyword": r.keyword, "target_url": r.target_url, "name": r.name,
            "latest_tongsearch_rank": r.latest_tongsearch_rank,
            "latest_cafetab_rank": r.latest_cafetab_rank,
            "last_checked_date": r.last_checked_date,
            "history": [{"date": h.date_str, "tongsearch_rank": h.tongsearch_rank, "cafetab_rank": h.cafetab_rank} for h in reversed(hist)],
        })
    return {"success": True, "items": out}


@router.post("/items", summary="카페 순위 추적 대상 추가")
def add_item(req: CafeRankCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not (req.keyword or "").strip() or not (req.target_url or "").strip():
        raise HTTPException(status_code=400, detail="키워드와 카페 글 URL을 입력하세요.")
    item = CafeRankItem(user_id=_uid(current_user), keyword=req.keyword.strip(),
                        target_url=req.target_url.strip(), name=(req.name or "").strip() or None)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"success": True, "id": item.id}


@router.delete("/items/{item_id}", summary="카페 순위 추적 대상 삭제")
def delete_item(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    it = db.query(CafeRankItem).filter(CafeRankItem.id == item_id, CafeRankItem.user_id == _uid(current_user)).first()
    if it:
        db.delete(it)
        db.commit()
    return {"success": True}


@router.post("/items/{item_id}/check", summary="지금 순위 수집(에이전트 실행)")
def check_now(item_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = _uid(current_user)
    it = db.query(CafeRankItem).filter(CafeRankItem.id == item_id, CafeRankItem.user_id == user_id).first()
    if not it:
        raise HTTPException(status_code=404, detail="대상을 찾을 수 없습니다.")
    jobsvc.enqueue_job(db, user_id, "cafe_rank_check", {
        "keyword": it.keyword, "target_url": it.target_url, "tracked_id": it.id,
    }, priority=5)
    return {"success": True, "message": "순위 수집을 시작했습니다. 에이전트가 실행되면 잠시 후 갱신됩니다."}


# ─────────────── 결과 영속화(persister) ───────────────
def _persist_cafe_rank(db, user_id, payload, result):
    tid = (payload or {}).get("tracked_id")
    if not tid:
        return
    it = db.query(CafeRankItem).filter(CafeRankItem.id == tid).first()
    if not it:
        return
    ts = (result or {}).get("tongsearch_rank")
    ct = (result or {}).get("cafetab_rank")
    today = datetime.now(KST).strftime("%Y-%m-%d")
    it.latest_tongsearch_rank = ts
    it.latest_cafetab_rank = ct
    it.last_checked_date = today
    # 같은 날 재수집이면 갱신, 아니면 추가
    row = (db.query(CafeRankHistory)
           .filter(CafeRankHistory.tracked_id == tid, CafeRankHistory.date_str == today).first())
    if row:
        row.tongsearch_rank = ts
        row.cafetab_rank = ct
    else:
        db.add(CafeRankHistory(tracked_id=tid, date_str=today, tongsearch_rank=ts, cafetab_rank=ct))


try:
    jobsvc.register_persister("cafe_rank_check", _persist_cafe_rank)
except Exception as _e:
    print(f"[cafe_rank] persister 등록 실패: {_e}")
