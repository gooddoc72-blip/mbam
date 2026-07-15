from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import random
from sqlalchemy.orm import Session
from mbam_nextgen.orchestrator import WorkflowOrchestrator, task_logger
from mbam_nextgen.backend.quota import consume_generation_quota
from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.backend.database import get_db

router = APIRouter()

class CommunicationRequest(BaseModel):
    login_mode: str # "manual" | "auto"
    naver_id: Optional[str] = None          # 단일 계정(레거시 호환)
    naver_ids: Optional[List[str]] = None   # 다중 계정 — 계정마다 순차 실행
    naver_pw: Optional[str] = None

    target_keyword: str
    limit: int = 10
    
    min_delay: int = 30
    max_delay: int = 120
    
    enable_neighbor: bool = False
    neighbor_message: Optional[str] = ""
    enable_like: bool = False
    enable_comment: bool = False
    comment_message: Optional[str] = ""

task_status_store = {}


def params_from_req(req: CommunicationRequest) -> dict:
    """실행 파라미터(계정 제외)만 뽑아 잡 payload/루프 공용 dict 로."""
    return {
        "target_keyword": req.target_keyword,
        "limit": min(req.limit, 10),
        "enable_like": req.enable_like,
        "enable_comment": req.enable_comment,
        "comment_message": req.comment_message,
        "enable_neighbor": req.enable_neighbor,
        "neighbor_message": req.neighbor_message,
        "min_delay": req.min_delay,
        "max_delay": req.max_delay,
    }


def resolve_engagement_accounts(db, user_id, req: CommunicationRequest):
    """실행할 계정 목록 구성 + 계정별 프록시(계정고정) 해소. (DB 필요 → 백엔드에서 1회 해소)
    반환: (accounts[{"naver_id","pw","proxy"}], skipped[naver_id])."""
    from mbam_nextgen.backend.database import NaverAccount
    from mbam_nextgen.backend.cipher_utils import decrypt_val
    from mbam_nextgen.services import proxy_pool

    ids = [i for i in (req.naver_ids or []) if i] or ([req.naver_id] if req.naver_id else [])
    multi = len(ids) > 1
    accounts, skipped = [], []
    if not ids:
        accounts.append({"naver_id": req.naver_id or "unknown_account", "pw": req.naver_pw})
    else:
        for nid in ids:
            acc = db.query(NaverAccount).filter(
                NaverAccount.user_id == user_id, NaverAccount.naver_id == nid).first() if user_id else None
            if multi:
                if not acc:  # 소유권 검증(IDOR 방지)
                    skipped.append(nid)
                    continue
                try:
                    pw = decrypt_val(acc.naver_pw) if acc.naver_pw else ""
                except Exception:
                    pw = acc.naver_pw or ""
                accounts.append({"naver_id": nid, "pw": pw})
            else:
                accounts.append({"naver_id": nid, "pw": req.naver_pw})
    # 프록시(계정별 고정) 해소 — URL 문자열로 심어 로컬·에이전트 동일 적용
    for a in accounts:
        try:
            pc = proxy_pool.resolve_proxy(db, user_id, account_id=a["naver_id"], task_kind="engagement")
            a["proxy"] = proxy_pool.to_url(pc) if pc else None
        except Exception:
            a["proxy"] = None
    return accounts, skipped


async def run_engagement_loop(accounts, params, log, stop_event=None, orchestrator=None):
    """계정별 순차 실행(공용) — DB 불필요. 로컬·에이전트 양쪽에서 호출. (총방문, 총성공) 반환."""
    orchestrator = orchestrator or WorkflowOrchestrator()
    safe_limit = min(int(params.get("limit", 10) or 10), 10)
    multi = len(accounts) > 1
    total_visited = total_ok = 0
    for ai, acc in enumerate(accounts):
        if stop_event is not None and stop_event.is_set():
            break
        aid = acc.get("naver_id") or "unknown_account"
        proxy = acc.get("proxy")
        if multi:
            log(f"[{ai+1}/{len(accounts)}] 계정 '{aid}' 시작" + (" · 프록시 적용" if proxy else ""))
        elif proxy:
            log("프록시 적용됨")

        result = await orchestrator.execute_engagement_workflow(
            account_id=aid,
            keyword=params.get("target_keyword"),
            account_pw=acc.get("pw"),
            limit=safe_limit,
            do_like=params.get("enable_like"),
            do_comment=params.get("enable_comment"),
            comment_msg=params.get("comment_message"),
            do_neighbor=params.get("enable_neighbor"),
            neighbor_msg=params.get("neighbor_message"),
            proxy=proxy,
            min_delay=params.get("min_delay", 30),
            max_delay=params.get("max_delay", 120),
            stop_event=stop_event,
        )

        if isinstance(result, dict) and result.get("error"):
            log(f"⚠️ 계정 '{aid}' 실패: {result.get('error')}")
        else:
            visited = result if isinstance(result, list) else []
            ok = sum(1 for r in visited if r.get("success"))
            total_visited += len(visited)
            total_ok += ok
            if multi:
                log(f"   ↳ 계정 '{aid}' 완료 (방문 {len(visited)}곳 / 성공 {ok}곳)")

        if ai < len(accounts) - 1 and not (stop_event is not None and stop_event.is_set()):
            lo = max(5, int(params.get("min_delay", 30) or 30))
            hi = max(lo + 5, int(params.get("max_delay", 120) or 120))
            wait = random.randint(lo, hi)
            log(f"⏳ 다음 계정까지 {wait}초 대기...")
            if stop_event is not None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=wait)
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(wait)
    return total_visited, total_ok


async def run_communication_task(task_id: str, req: CommunicationRequest, stop_event: asyncio.Event, user_id: str = None):
    """로컬(설치형) 실행 — 백엔드 프로세스에서 직접 브라우저 자동화."""
    store = task_status_store[task_id]

    def log(msg: str):
        print(f"[{task_id}] {msg}")
        store["logs"].append(msg)

    task_logger.set(log)

    from mbam_nextgen.backend.database import SessionLocal
    db = SessionLocal()
    try:
        accounts, skipped = resolve_engagement_accounts(db, user_id, req)
    finally:
        try:
            db.close()
        except Exception:
            pass

    try:
        for nid in skipped:
            log(f"⏭ 건너뜀 — 내 계정이 아니거나 없는 계정: {nid}")
        if not accounts:
            log("⚠️ 실행할 계정이 없습니다.")
            store["status"] = "failed"
            return

        multi = len(accounts) > 1
        log(f"소통&이웃 다계정 워크플로우 시작 — 계정 {len(accounts)}개 순차 실행" if multi else "소통&이웃 워크플로우를 시작합니다...")

        total_visited, total_ok = await run_engagement_loop(accounts, params_from_req(req), log, stop_event)

        if stop_event.is_set():
            log(f"⏹ 중지됨 (총 방문 {total_visited}곳 / 성공 {total_ok}곳)")
        elif total_visited == 0:
            log("⚠️ 방문할 블로그를 찾지 못했습니다. (검색 결과 없음 또는 로그인 필요)")
        else:
            log(f"✅ 소통&이웃 순회 완료! (총 방문 {total_visited}곳 / 성공 {total_ok}곳)")

        store["status"] = "stopped" if stop_event.is_set() else "completed"

    except asyncio.CancelledError:
        log("⏹ 작업이 취소되었습니다.")
        store["status"] = "stopped"
        raise
    except Exception as e:
        log(f"오류 발생: {str(e)}")
        store["status"] = "failed"
    finally:
        store.pop("task", None)


@router.post("")
@router.post("/")
async def trigger_communication(req: CommunicationRequest, _q: dict = Depends(consume_generation_quota),
                                current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    import uuid

    if req.limit > 10:
        req.limit = 10 # 어뷰징 방지 하드 리밋

    user_id = current_user.get("sub")

    # [방법 B] 소통&이웃도 네이버 로그인+브라우저 자동화라 클라우드(데이터센터 IP·XServer 없음)에선 불가.
    # → 블로그/카페 발행과 동일하게 로컬 에이전트(집 PC)에 위임. 계정·비번·프록시는 여기(DB)서 해소해 payload 로 전달.
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        accounts, skipped = resolve_engagement_accounts(db, user_id, req)
        if not accounts:
            raise HTTPException(status_code=400, detail="실행할 계정이 없습니다. (자동 로그인 계정 선택 또는 계정관리 확인)")
        payload = params_from_req(req)
        payload["accounts"] = accounts
        job_id = jobsvc.enqueue_job(db, user_id, "engagement", payload)
        return {
            "success": True, "mode": "agent", "job_id": job_id, "skipped": skipped,
            "message": "내 PC 에이전트가 소통&이웃을 실행합니다. (로컬 에이전트 실행 필요)",
        }

    # 로컬(설치형) — 백엔드 프로세스에서 직접 실행
    task_id = str(uuid.uuid4())
    stop_event = asyncio.Event()
    task_status_store[task_id] = {
        "status": "running",
        "logs": ["소통&이웃 작업이 시작되었습니다."],
        "stop_event": stop_event,
    }
    task = asyncio.create_task(run_communication_task(task_id, req, stop_event, user_id=user_id))
    task_status_store[task_id]["task"] = task
    return {
        "success": True,
        "message": "소통 작업이 백그라운드에서 시작되었습니다.",
        "task_id": task_id
    }

@router.post("/stop/{task_id}")
async def stop_task(task_id: str):
    store = task_status_store.get(task_id)
    if not store:
        raise HTTPException(status_code=404, detail="Task not found")
    ev = store.get("stop_event")
    if ev:
        ev.set()  # 협조적 중지: 현재 동작 마무리 후 다음 단계에서 멈춤
    return {"success": True, "message": "중지를 요청했습니다. 진행 중인 단계가 끝나면 멈춥니다."}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    store = task_status_store.get(task_id)
    if not store:
        raise HTTPException(status_code=404, detail="Task not found")
    # 직렬화 불가 객체(stop_event/task) 제외하고 반환
    return {k: v for k, v in store.items() if k not in ("stop_event", "task")}
