from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import random
from mbam_nextgen.orchestrator import WorkflowOrchestrator, task_logger
from mbam_nextgen.backend.quota import consume_generation_quota
from mbam_nextgen.backend.auth import get_current_user

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

async def run_communication_task(task_id: str, req: CommunicationRequest, stop_event: asyncio.Event, user_id: str = None):
    store = task_status_store[task_id]

    def log(msg: str):
        print(f"[{task_id}] {msg}")
        store["logs"].append(msg)

    task_logger.set(log)

    from mbam_nextgen.backend.database import SessionLocal, NaverAccount
    from mbam_nextgen.backend.cipher_utils import decrypt_val
    from mbam_nextgen.services import proxy_pool

    db = SessionLocal()
    try:
        orchestrator = WorkflowOrchestrator()
        safe_limit = min(req.limit, 10)

        # 실행할 계정 목록 구성 — 다계정(naver_ids) 우선, 없으면 단일(naver_id)
        ids = [i for i in (req.naver_ids or []) if i] or ([req.naver_id] if req.naver_id else [])
        accounts = []  # [{"naver_id","pw"}]
        multi = len(ids) > 1
        if not ids:
            # 수동 로그인 등 계정 미선택 — 기존 단일 동작 유지
            accounts.append({"naver_id": req.naver_id or "unknown_account", "pw": req.naver_pw})
        else:
            for nid in ids:
                acc = db.query(NaverAccount).filter(
                    NaverAccount.user_id == user_id, NaverAccount.naver_id == nid).first() if user_id else None
                if multi:
                    # 다계정은 소유권 검증 필수(IDOR 방지), 비번은 DB에서 복호화
                    if not acc:
                        log(f"⏭ 건너뜀 — 내 계정이 아니거나 없는 계정: {nid}")
                        continue
                    pw = ""
                    try:
                        pw = decrypt_val(acc.naver_pw) if acc.naver_pw else ""
                    except Exception:
                        pw = acc.naver_pw or ""
                    accounts.append({"naver_id": nid, "pw": pw})
                else:
                    accounts.append({"naver_id": nid, "pw": req.naver_pw})

        if not accounts:
            log("⚠️ 실행할 계정이 없습니다.")
            store["status"] = "failed"
            return

        if multi:
            log(f"소통&이웃 다계정 워크플로우 시작 — 계정 {len(accounts)}개 순차 실행")
        else:
            log("소통&이웃 워크플로우를 시작합니다...")

        total_visited = total_ok = 0
        for ai, acc in enumerate(accounts):
            if stop_event.is_set():
                break
            aid = acc["naver_id"] or "unknown_account"
            # 프록시 해소(하이브리드: 소통이웃=계정별 고정 IP)
            proxy_cfg = None
            try:
                proxy_cfg = proxy_pool.resolve_proxy(db, user_id, account_id=aid, task_kind="engagement")
            except Exception as e:
                log(f"프록시 해소 실패(무시): {e}")
            if multi:
                log(f"[{ai+1}/{len(accounts)}] 계정 '{aid}' 시작" + (" · 프록시 적용" if proxy_cfg else ""))
            elif proxy_cfg:
                log("프록시 적용됨")

            result = await orchestrator.execute_engagement_workflow(
                account_id=aid,
                keyword=req.target_keyword,
                account_pw=acc["pw"],
                limit=safe_limit,
                do_like=req.enable_like,
                do_comment=req.enable_comment,
                comment_msg=req.comment_message,
                do_neighbor=req.enable_neighbor,
                neighbor_msg=req.neighbor_message,
                proxy=proxy_cfg,
                min_delay=req.min_delay,
                max_delay=req.max_delay,
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

            # 계정 간 대기(마지막 계정 제외) — 봇 탐지 완화
            if ai < len(accounts) - 1 and not stop_event.is_set():
                wait = random.randint(max(5, req.min_delay), max(req.min_delay + 5, req.max_delay))
                log(f"⏳ 다음 계정까지 {wait}초 대기...")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=wait)
                except asyncio.TimeoutError:
                    pass

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
        try:
            db.close()
        except Exception:
            pass
        store.pop("task", None)


@router.post("")
@router.post("/")
async def trigger_communication(req: CommunicationRequest, _q: dict = Depends(consume_generation_quota), current_user: dict = Depends(get_current_user)):
    import uuid

    if req.limit > 10:
        req.limit = 10 # 어뷰징 방지 하드 리밋

    user_id = current_user.get("sub")
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
