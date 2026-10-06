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
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
            "title": getattr(r, "title", None),
            "latest_tongsearch_rank": r.latest_tongsearch_rank,
            "latest_cafetab_rank": r.latest_cafetab_rank,
            "last_checked_date": r.last_checked_date,
            "created_at": r.created_at.isoformat() if r.created_at else None,
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


async def _collect_rank_now(user_id: str, payload: dict):
    """설치형에서 순위를 이 PC가 직접 수집한다(백그라운드).

    ⚠ 예전에는 모드와 상관없이 잡 큐에만 넣었는데, 설치본은 로컬 에이전트(agent.py)를
      동봉하지도 실행하지도 않는다. 그래서 잡을 소비할 주체가 없어 순위가 영원히
      '미검사'로 남았다. 다른 라우터들처럼 로컬에서는 직접 실행한다.
    """
    from mbam_nextgen.services.cafe_rank_service import find_cafe_rank
    from ..database import SessionLocal
    try:
        res = await find_cafe_rank(payload.get("keyword", ""), payload.get("target_url", ""))
    except Exception as e:
        print(f"[cafe_rank] 수집 실패: {e}")
        return
    db = SessionLocal()
    try:
        _persist_cafe_rank(db, user_id, payload, res)   # 에이전트 결과와 같은 경로로 저장
        db.commit()
        print(f"[cafe_rank] 수집 완료 — 통합 {res.get('tongsearch_rank')} / 탭 {res.get('cafetab_rank')}")
    except Exception as e:
        db.rollback()
        print(f"[cafe_rank] 저장 실패: {e}")
    finally:
        db.close()


@router.post("/items/{item_id}/check", summary="지금 순위 수집")
def check_now(item_id: str, background: BackgroundTasks,
              db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # ⚠ 여기서 asyncio.create_task 를 쓰면 안 된다. 이 엔드포인트는 동기 함수라
    #   FastAPI 가 별도 스레드에서 실행하고, 그 스레드에는 이벤트 루프가 없어
    #   'RuntimeError: no running event loop' 로 500 이 난다(실제로 그랬다).
    #   BackgroundTasks 는 응답을 보낸 뒤 본래 이벤트 루프에서 코루틴을 실행해 준다.
    user_id = _uid(current_user)
    it = db.query(CafeRankItem).filter(CafeRankItem.id == item_id, CafeRankItem.user_id == user_id).first()
    if not it:
        raise HTTPException(status_code=404, detail="대상을 찾을 수 없습니다.")
    payload = {"keyword": it.keyword, "target_url": it.target_url, "tracked_id": it.id}

    # 클라우드에서는 집 IP가 필요해 로컬 에이전트에 위임하고, 설치형은 직접 수집한다.
    if jobsvc.is_cloud_mode():
        jobsvc.enqueue_job(db, user_id, "cafe_rank_check", payload, priority=5)
        return {"success": True, "message": "순위 수집을 시작했습니다. 에이전트가 실행되면 잠시 후 갱신됩니다."}

    background.add_task(_collect_rank_now, user_id, payload)
    return {"success": True, "message": "순위 수집을 시작했습니다. 30초쯤 뒤 [새로고침] 을 눌러주세요."}


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


# ─────────────── 카페 발행 → 순위추적 자동 등록 ───────────────
def register_cafe_rank_if_absent(db, user_id: str, keyword: str, target_url: str, name: str = None, title: str = None) -> bool:
    """카페/블로그 글 발행 성공 시, (키워드, URL)을 순위추적에 자동 등록(중복이면 건너뜀).
    순위추적은 URL(cafe.naver.com / blog.naver.com)로 블로그·카페를 구분한다.
    title = 발행 글 제목(키워드 아래 회색으로 표시). 중복이라도 title 비어있으면 채워준다."""
    keyword = (keyword or "").strip()
    target_url = (target_url or "").strip()
    title = (title or "").strip() or None
    if not user_id or not keyword or not target_url or not (
        "cafe.naver.com" in target_url or "blog.naver.com" in target_url):
        return False
    exists = (db.query(CafeRankItem)
              .filter(CafeRankItem.user_id == user_id, CafeRankItem.keyword == keyword,
                      CafeRankItem.target_url == target_url).first())
    if exists:
        if title and not exists.title:  # 기존 항목에 제목이 비어있으면 보충
            exists.title = title
        return False
    db.add(CafeRankItem(user_id=user_id, keyword=keyword, target_url=target_url, name=(name or None), title=title))
    return True


def _persist_auto_post(db, user_id, payload, result):
    """에이전트 auto_post(카페/블로그) 완료 시, track_rank 이면 발행 글을 순위추적에 자동 등록(클라우드)."""
    p = payload or {}
    if p.get("target_type") not in ("cafe", "blog") or not p.get("track_rank"):
        return
    url = (result or {}).get("result_url") or ""
    kw = p.get("target_keyword") or (result or {}).get("keyword") or ""
    title = (result or {}).get("title") or ""
    if url and kw:
        register_cafe_rank_if_absent(db, user_id, kw, url, title=title)


try:
    jobsvc.register_persister("auto_post", _persist_auto_post)
except Exception as _e:
    print(f"[cafe_rank] auto_post persister 등록 실패: {_e}")
