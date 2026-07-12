# -*- coding: utf-8 -*-
"""[방법 B] 로컬 에이전트 (사용자 PC 상주)

웹(클라우드)에 로그인 → 내 작업을 폴링으로 받아 → 집 IP로 Playwright 실행 → 결과 반환.
클라우드는 네이버를 직접 못 긁으므로(데이터센터 IP 차단), 실제 실행은 이 에이전트가 담당한다.

설정(우선순위: 환경변수 > agent_config.json):
  AGENT_CLOUD_URL   예: https://www.marketlabs.kr  (기본: http://127.0.0.1:8000)
  AGENT_EMAIL       marketlabs 계정 이메일/아이디
  AGENT_PASSWORD    비밀번호
  AGENT_POLL_SEC    폴링 간격(초, 기본 3)

실행:  python agent.py     (PYTHONPATH=프로젝트 루트 필요 — 런처가 자동 설정)
"""
import os
import sys
import json
import asyncio
import platform

import httpx

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 설치형(에이전트 전용) 패키지에서는 Chromium 이 runtime\ms-playwright 에 동봉된다.
# agent_startup.vbs 가 런처 없이 agent.py 를 직접 실행하므로, 여기서 브라우저 경로를
# 잡아줘야 Playwright(블로그·발행)가 동봉 Chromium 을 찾는다. (개발 환경엔 폴더가 없어 무시)
_bundled_browsers = os.path.join(APP_DIR, "runtime", "ms-playwright")
if os.path.isdir(_bundled_browsers):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _bundled_browsers)


def _load_config() -> dict:
    cfg = {
        # 설치형(구독/웹) 기본값 = 운영 서버. 개발 시 AGENT_CLOUD_URL 로 override.
        "cloud_url": "https://clever-transformation-production.up.railway.app",
        "email": "",
        "password": "",
        "poll_sec": 3,
    }
    cfg_path = os.path.join(APP_DIR, "agent_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items() if v not in (None, "")})
        except Exception:
            pass
    # 환경변수 우선
    cfg["cloud_url"] = os.environ.get("AGENT_CLOUD_URL", cfg["cloud_url"]).rstrip("/")
    cfg["email"] = os.environ.get("AGENT_EMAIL", cfg["email"])
    cfg["password"] = os.environ.get("AGENT_PASSWORD", cfg["password"])
    cfg["poll_sec"] = int(os.environ.get("AGENT_POLL_SEC", cfg["poll_sec"]))
    return cfg


def _agent_id() -> str:
    """이 PC 식별자. 라이선스 HWID가 있으면 재사용, 없으면 호스트명."""
    try:
        from licensing.hwid import get_hwid  # 설치형에 존재
        return get_hwid()
    except Exception:
        return platform.node() or "agent"


# ── 작업 핸들러 레지스트리 ────────────────────────────────────────────────
#   job_type -> async fn(payload: dict) -> dict(result)
#   여기에 추가하면 새 작업 유형이 바로 에이전트에서 실행된다(P2/P3 확장 지점).
async def _handle_seo_search(payload: dict) -> dict:
    from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
    keyword = payload.get("keyword", "")
    result = await SeoAnalyzer().search_smart_blocks(keyword)
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(result["error"])
    return result


async def _handle_seo_analyze(payload: dict) -> dict:
    from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
    result = await SeoAnalyzer().analyze_keyword(
        payload.get("keyword", ""), target_urls=payload.get("target_urls")
    )
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(result["error"])
    return result


async def _handle_place_analyze(payload: dict) -> dict:
    from mbam_nextgen.backend.routers.place import run_place_analysis
    return await asyncio.to_thread(
        run_place_analysis,
        payload.get("keyword", ""), payload.get("target_mid", ""),
        int(payload.get("compare_days", 1) or 1), bool(payload.get("force_refresh", True)),
    )


async def _handle_place_fetch_mid(payload: dict) -> dict:
    from mbam_nextgen.backend.routers.place import fetch_place_by_mid_cli
    res = await asyncio.to_thread(fetch_place_by_mid_cli, payload.get("mid", ""))
    if isinstance(res, dict) and res.get("error"):
        raise RuntimeError(res["error"])
    res["success"] = True
    return res


async def _handle_place_fetch_reviews(payload: dict) -> dict:
    from mbam_nextgen.services.place_review_service import PlaceReviewService
    data = await PlaceReviewService().collect_reviews(payload.get("place_url", ""))
    if not data.get("success"):
        raise RuntimeError(data.get("error", "리뷰 수집 실패"))
    if not data.get("reviews"):
        raise RuntimeError("최근 리뷰를 찾을 수 없습니다.")
    return {"success": True, "reviews": data.get("reviews", []), "image_paths": data.get("image_paths", [])}


async def _handle_blog_index(payload: dict) -> dict:
    from mbam_nextgen.services.blog_index import analyze_blog
    result = await analyze_blog(payload.get("blog", ""))
    if not result:
        raise RuntimeError("블로그 데이터를 가져오지 못했습니다. (아이디 확인 또는 비공개/차단)")
    return {"success": True, **result}


async def _handle_seo_cafe_urls(payload: dict) -> dict:
    from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
    results = await SeoAnalyzer().analyze_multiple_urls(payload.get("urls", []))
    items, errors = [], []
    for url, detail in results.items():
        if "error" in detail:
            errors.append({"url": url, "error": detail["error"]})
        else:
            items.append({"url": url, **detail})
    return {"items": items, "errors": errors}


async def _handle_seo_top3(payload: dict) -> dict:
    from mbam_nextgen.services.seo_analyzer_v2 import SeoAnalyzerV2
    result = await SeoAnalyzerV2().analyze(payload.get("keyword", ""))
    if isinstance(result, dict) and not result.get("success", True) and result.get("error"):
        raise RuntimeError(result["error"])
    return result


async def _handle_seo_cafe_post(payload: dict) -> dict:
    from mbam_nextgen.backend.routers.seo import run_cafe_post_analysis, CafeAnalysisRequest
    req = CafeAnalysisRequest(
        keyword=payload.get("keyword", "") or "",
        content=payload.get("content", "") or "",
        url=payload.get("url", "") or "",
        urls=payload.get("urls", []) or [],
    )
    return await run_cafe_post_analysis(req)


async def _handle_auto_post(payload: dict) -> dict:
    # 발행(블로그/카페): 사용자 PC에서 네이버 로그인+글쓰기 브라우저 자동화 실행
    import uuid as _uuid
    from mbam_nextgen.backend.routers.auto_post import run_automation_task, task_status_store, AutoPostRequest
    req = AutoPostRequest(**payload)
    tid = _uuid.uuid4().hex
    await run_automation_task(tid, req)   # 워크플로우 실행 + 로컬 task_status_store에 상태 기록
    st = task_status_store.get(tid, {})
    if st.get("status") == "failed":
        logs = st.get("logs", [])
        raise RuntimeError("발행 실패: " + (" / ".join(str(l) for l in logs[-2:]) if logs else "원인 미상"))
    out = {"success": True, "logs": [str(l) for l in st.get("logs", [])[-6:]]}
    # 카페 발행 결과(URL·키워드) 전달 → 클라우드 persister(auto_post)가 순위추적 자동 등록에 사용
    res = st.get("result") or {}
    if isinstance(res, dict):
        out.update({k: res[k] for k in ("result_url", "keyword") if res.get(k)})
    return out


async def _handle_blog_daily_post(payload: dict) -> dict:
    # 매일 자동발행: 클라우드가 예약 시각에 적재한 잡을 집 IP에서 생성+발행.
    # 로컬 스케줄러(run_blog_post_job)와 동일하게 execute_blog_workflow 로 글감→원고→발행.
    from mbam_nextgen.orchestrator import WorkflowOrchestrator
    result = await WorkflowOrchestrator().execute_blog_workflow(
        account_id=payload.get("naver_id", ""),
        account_pw=payload.get("naver_pw", ""),
        keyword=payload.get("keyword", "정보"),
        source_data=payload.get("source_data", ""),
        publish_mode="instant",
        ai_provider=payload.get("ai_provider", "claude"),
        distribution_mode=payload.get("distribution_mode", "normal"),
        generate_card_news=bool(payload.get("generate_card_news", True)),
        prompt_category=payload.get("prompt_category"),
        custom_prompt=payload.get("custom_prompt"),
        blog_id=payload.get("blog_addr") or None,
    )
    if not (result and result.get("success")):
        raise RuntimeError("발행 실패: " + str((result or {}).get("error", "원인 미상")))
    return {
        "success": True,
        "result_url": result.get("result_url", ""),
        "title": result.get("title", "") or payload.get("keyword", ""),
    }


async def _handle_place_news_publish(payload: dict) -> dict:
    # 플레이스 소식 발행: 소유주 계정(기기 인증 프로필)으로 스마트플레이스 새소식 등록
    from mbam_nextgen.services.smartplace_news import publish_smartplace_news
    res = await publish_smartplace_news(
        payload.get("naver_id", ""), payload.get("title", ""),
        payload.get("content", ""), payload.get("clip_path") or None,
    )
    if not res.get("success"):
        raise RuntimeError(res.get("error", "스마트플레이스 발행 실패"))
    return res


async def _handle_shopping_analyze(payload: dict) -> dict:
    # 쇼핑 순위 분석: 사용자 PC(집 IP)에서 Playwright 스크레이핑 실행.
    # 결과는 클라우드의 persist_shopping_history 훅이 ShoppingHistory 에 기록한다.
    from mbam_nextgen.backend.database import SessionLocal
    from mbam_nextgen.backend.routers.shopping_router import analyze_keyword_shopping, AnalyzeRequest
    req = AnalyzeRequest(
        keyword=payload.get("keyword", ""),
        target_mid=payload.get("target_mid", "") or "",
        store_name=payload.get("store_name", "") or "",
        product_name=payload.get("product_name", "") or "",
    )
    db = SessionLocal()
    try:
        # role=admin → increment_quota 는 no-op (시스템 배치는 쿼터 미차감)
        res = await analyze_keyword_shopping(req, db, {"sub": "agent_batch", "role": "admin"})
    finally:
        db.close()
    if not isinstance(res, dict):
        raise RuntimeError("쇼핑 분석 결과 형식 오류")
    if not res.get("found"):
        raise RuntimeError(res.get("message") or "타겟 상품을 찾지 못했습니다.")
    return res


async def _handle_register_account(payload: dict) -> dict:
    # 기기 인증: 사용자 PC에서 브라우저를 열어 수동 로그인+2FA → 영구 프로필 저장
    from mbam_nextgen.orchestrator import WorkflowOrchestrator
    result = await WorkflowOrchestrator().register_account_session(
        payload.get("naver_id", ""), payload.get("naver_pw")
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error", "기기 인증 실패"))
    return result


async def _handle_matjip_collect(payload: dict, log=None) -> dict:
    # 맛집 포스팅 소재 수집: 플레이스 방문자 리뷰 + 블로그 후기 → 원고 소재(source_data)
    from mbam_nextgen.services.matjip_service import collect_matjip_source
    return await collect_matjip_source(payload.get("place_url", ""), payload.get("keyword", ""), log=log)


async def _handle_cafe_targeted_comment(payload: dict, log=None) -> dict:
    # 카페 다중 타겟 댓글(소통육성): 클라우드가 위임한 잡을 집 IP·화면 있는 PC에서 실행.
    # log(callable)이 오면 진행 로그를 클라우드(task_status_store)로 실시간 중계한다.
    from mbam_nextgen.orchestrator import WorkflowOrchestrator

    def _log(msg):
        print(f"[cafe] {msg}")
        if log:
            try:
                log(msg)
            except Exception:
                pass

    result = await WorkflowOrchestrator().execute_targeted_multi_cafe_workflow(
        accounts_data=payload.get("accounts_data", []),
        target_urls=payload.get("urls", []),
        keyword=payload.get("keyword", ""),
        ai_provider=payload.get("ai_provider", "claude"),
        delay_min=int(payload.get("delay_min", 30) or 30),
        delay_max=int(payload.get("delay_max", 60) or 60),
        use_tethering=bool(payload.get("use_tethering", False)),
        comment_content=payload.get("comment_content", "") or "",
        do_like=bool(payload.get("do_like", True)),
        logger_func=_log,
    )
    return {"success": True, "result": result}


async def _handle_cafe_nurture_run(payload: dict, log=None) -> dict:
    # 카페 예약 육성: 클라우드가 예약 시각에 적재한 잡을 집 IP·화면 있는 PC에서 실행.
    # action: boost(게시글 부스트) / visit(방문 육성) / post(콘텐츠 자동 포스팅)
    import os
    from mbam_nextgen.orchestrator import WorkflowOrchestrator

    def _log(msg):
        print(f"[cafe-nurture] {msg}")
        if log:
            try:
                log(msg)
            except Exception:
                pass

    orch = WorkflowOrchestrator()
    naver_id = payload.get("naver_id", "")
    pw = payload.get("naver_pw", "")
    visits = int(payload.get("visits", 1) or 1)
    interval = int(payload.get("visit_interval_min", 30) or 30)
    action = payload.get("action")

    if action == "boost":
        _log(f"게시글 부스트: {payload.get('post_url')} (방문 {visits}회/{interval}분)")
        await orch.execute_cafe_boost(
            account_id=naver_id, post_url=payload.get("post_url", ""),
            do_view=bool(payload.get("do_view", True)), do_like=bool(payload.get("do_like", True)),
            visits=visits, naver_pw=pw, visit_interval_min=interval,
        )
    elif action == "visit":
        _log(f"방문 육성: {payload.get('post_url')} (방문 {visits}회/{interval}분)")
        await orch.execute_cafe_boost(
            account_id=naver_id, post_url=payload.get("post_url", ""),
            do_view=True, do_like=False, visits=visits, naver_pw=pw, visit_interval_min=interval,
        )
    elif action == "post":
        os.environ["NAVER_PW"] = pw  # execute_cafe_workflow 는 환경변수에서 비번을 읽음
        items = payload.get("items", []) or []
        _log(f"콘텐츠 자동 포스팅: {len(items)}건")
        for i, item in enumerate(items):
            _log(f"  -> [{i+1}/{len(items)}] {item.get('title', '')}")
            await orch.execute_cafe_workflow(
                account_id=naver_id, cafe_id=payload.get("cafe_url", ""),
                board_name=payload.get("board_name", ""),
                keyword=item.get("title", "정보 제공"), title=item.get("title", "정보 제공"),
                content=item.get("content", ""), auto_submit=True, action_type="post",
                prompt_category="cafe",  # 글감을 카페 톤으로 재작성(원문 그대로 게시 방지)
            )
    else:
        raise RuntimeError(f"알 수 없는 카페 작업 유형: {action}")
    return {"success": True, "action": action}


async def _handle_tistory_register(payload: dict) -> dict:
    # 티스토리 기기 인증: 사용자 PC에서 브라우저를 열어 카카오 수동 로그인 → 영구 프로필 저장
    from mbam_nextgen.orchestrator import WorkflowOrchestrator
    result = await WorkflowOrchestrator().register_tistory_session(payload.get("account_id", ""))
    if not result.get("success"):
        raise RuntimeError(result.get("error", "티스토리 기기 인증 실패"))
    return result


async def _handle_tistory_post(payload: dict, log=None) -> dict:
    # 티스토리 발행: 집 PC(로그인 유지된 영구 프로필)에서 글쓰기·발행
    from mbam_nextgen.orchestrator import WorkflowOrchestrator

    def _log(msg):
        print(f"[tistory] {msg}")
        if log:
            try:
                log(msg)
            except Exception:
                pass

    _log(f"티스토리 발행 시작: {payload.get('keyword', '')}")
    result = await WorkflowOrchestrator().execute_tistory_workflow(
        account_id=payload.get("account_id", ""),
        blog_name=payload.get("blog_name", ""),
        keyword=payload.get("keyword", "정보"),
        title=payload.get("title") or None,
        content=payload.get("content") or None,
        source_data=payload.get("source_data") or None,
        ai_provider=payload.get("ai_provider", "gemini"),
        prompt_category="tistory",
        auto_submit=True,
    )
    if not (result and result.get("success")):
        raise RuntimeError("티스토리 발행 실패: " + str((result or {}).get("error", "원인 미상")))
    return {"success": True, "result_url": result.get("result_url", ""), "title": result.get("title", "")}


async def _handle_cafe_rank_check(payload: dict) -> dict:
    # 카페 글 통합검색 순위 수집: 집 IP에서 네이버 검색 스크래핑.
    # 결과는 클라우드의 persist_cafe_rank 훅이 CafeRankHistory 에 기록.
    from mbam_nextgen.services.cafe_rank_service import find_cafe_rank
    res = await find_cafe_rank(payload.get("keyword", ""), payload.get("target_url", ""))
    return {
        "success": True,
        "tongsearch_rank": res.get("tongsearch_rank"),
        "cafetab_rank": res.get("cafetab_rank"),
        "found": res.get("found", False),
    }


HANDLERS = {
    "seo_search": _handle_seo_search,
    "auto_post": _handle_auto_post,
    "register_account": _handle_register_account,
    "seo_analyze": _handle_seo_analyze,
    "seo_cafe_urls": _handle_seo_cafe_urls,
    "seo_top3": _handle_seo_top3,
    "seo_cafe_post": _handle_seo_cafe_post,
    "blog_index": _handle_blog_index,
    "place_analyze": _handle_place_analyze,
    "shopping_analyze": _handle_shopping_analyze,
    "place_fetch_mid": _handle_place_fetch_mid,
    "place_fetch_reviews": _handle_place_fetch_reviews,
    "blog_daily_post": _handle_blog_daily_post,
    "place_news_publish": _handle_place_news_publish,
    "cafe_targeted_comment": _handle_cafe_targeted_comment,
    "cafe_nurture_run": _handle_cafe_nurture_run,
    "tistory_register": _handle_tistory_register,
    "tistory_post": _handle_tistory_post,
    "cafe_rank_check": _handle_cafe_rank_check,
    "matjip_collect": _handle_matjip_collect,
}


class AgentClient:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.token = None
        self.agent_id = _agent_id()

    async def login(self, client: httpx.AsyncClient) -> bool:
        try:
            r = await client.post(
                f"{self.cfg['cloud_url']}/api/auth/login",
                json={"email": self.cfg["email"], "password": self.cfg["password"], "hwid": self.agent_id},
                timeout=20,
            )
            if r.status_code == 200:
                self.token = r.json().get("access_token")
                print(f"[agent] 로그인 성공 (agent_id={self.agent_id})")
                return True
            print(f"[agent] 로그인 실패 {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"[agent] 로그인 오류: {e}")
        return False

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    async def run(self):
        async with httpx.AsyncClient() as client:
            while not self.token:
                if await self.login(client):
                    break
                await asyncio.sleep(5)

            print(f"[agent] 폴링 시작 → {self.cfg['cloud_url']} (간격 {self.cfg['poll_sec']}초)")
            while True:
                try:
                    r = await client.get(
                        f"{self.cfg['cloud_url']}/api/agent/next-job",
                        params={"agent_id": self.agent_id},
                        headers=self._headers(), timeout=30,
                    )
                    if r.status_code == 401:
                        print("[agent] 토큰 만료 → 재로그인")
                        self.token = None
                        await self.login(client)
                        continue
                    job = (r.json() or {}).get("job")
                    if not job:
                        await asyncio.sleep(self.cfg["poll_sec"])
                        continue
                    await self._process(client, job)
                except Exception as e:
                    print(f"[agent] 폴링 오류: {e}")
                    await asyncio.sleep(self.cfg["poll_sec"])

    async def _post_task_log(self, client: httpx.AsyncClient, task_id: str, line: str = None, status: str = None):
        """위임 작업의 진행 로그·상태를 클라우드 task_status_store 로 중계(프론트 실시간 표시)."""
        try:
            await client.post(f"{self.cfg['cloud_url']}/api/agent/task-log",
                              json={"task_id": task_id, "line": line, "status": status},
                              headers=self._headers(), timeout=15)
        except Exception:
            pass

    async def _process(self, client: httpx.AsyncClient, job: dict):
        import inspect
        job_id = job.get("job_id")
        job_type = job.get("job_type")
        payload = job.get("payload") or {}
        task_id = payload.get("task_id") if isinstance(payload, dict) else None
        print(f"[agent] 작업 수신: {job_type} ({job_id})")

        # 진행 로그 실시간 중계용 콜백(동기) — task_id 가 있는 위임 작업만.
        def live_log(line):
            if not task_id:
                return
            try:
                asyncio.create_task(self._post_task_log(client, task_id, line=str(line)))
            except Exception:
                pass

        handler = HANDLERS.get(job_type)
        body = {"job_id": job_id}
        if not handler:
            body.update({"status": "error", "error": f"미지원 작업 유형: {job_type}"})
        else:
            try:
                # log 파라미터를 받는 핸들러(카페 댓글 등)에는 실시간 로그 콜백을 넘김
                if "log" in inspect.signature(handler).parameters:
                    result = await handler(payload, log=live_log)
                else:
                    result = await handler(payload)
                body.update({"status": "done", "result": result})
                print(f"[agent] 작업 완료: {job_type} ({job_id})")
            except Exception as e:
                body.update({"status": "error", "error": str(e)})
                print(f"[agent] 작업 실패: {job_type} ({job_id}) — {e}")

        # 위임 작업이면 최종 상태를 task_status_store 로 반영(프론트 폴링 종료 신호)
        if task_id:
            if body.get("status") == "done":
                await self._post_task_log(client, task_id, line="✅ 작업이 완료되었습니다.", status="completed")
            else:
                await self._post_task_log(client, task_id, line=f"❌ 오류: {body.get('error', '')}", status="failed")

        try:
            await client.post(f"{self.cfg['cloud_url']}/api/agent/job-result",
                              json=body, headers=self._headers(), timeout=30)
        except Exception as e:
            print(f"[agent] 결과 전송 실패: {e}")


def _try_login(cloud_url: str, email: str, password: str):
    """동기 로그인 검증. 반환: (ok, msg) — ok True=성공 / False=계정 오류 / None=서버 연결 불가."""
    try:
        r = httpx.post(f"{(cloud_url or '').rstrip('/')}/api/auth/login",
                       json={"email": email, "password": password, "hwid": _agent_id()},
                       timeout=15)
        if r.status_code == 200:
            return True, ""
        try:
            detail = (r.json() or {}).get("detail") or ""
        except Exception:
            detail = r.text[:120]
        return False, detail or "이메일 또는 비밀번호가 올바르지 않습니다."
    except Exception as e:
        return None, f"서버 연결 실패: {e}"


def _prompt_login(cfg: dict) -> dict:
    """설정에 계정이 없으면 창을 띄워 marketlabs 계정을 입력받아 agent_config.json 에 저장.
    저장 전 서버에 실제 로그인해 검증 — 오타로 저장되면 백그라운드 에이전트가 조용히
    영영 실패하므로 반드시 여기서 걸러낸다. (설치형: 설치→최초 1회 로그인 후 이후 자동)"""
    try:
        import tkinter as tk
    except Exception:
        return cfg
    result = {}
    root = tk.Tk()
    root.title("마케팅연구소 에이전트 - 로그인")
    root.resizable(False, False)
    W, H = 400, 330
    try:
        root.update_idletasks()
        x = (root.winfo_screenwidth() - W) // 2
        y = (root.winfo_screenheight() - H) // 3
        root.geometry(f"{W}x{H}+{x}+{y}")
    except Exception:
        pass
    tk.Label(root, text="marketlabs 계정으로 로그인", font=("맑은 고딕", 13, "bold")).pack(pady=(18, 6))
    tk.Label(root, text="한 번만 로그인하면 이후 자동으로 실행됩니다.", font=("맑은 고딕", 9), fg="#666").pack()
    frm = tk.Frame(root)
    frm.pack(padx=24, pady=10, fill="x")
    tk.Label(frm, text="이메일 / 아이디", anchor="w").pack(fill="x")
    e_email = tk.Entry(frm); e_email.pack(fill="x", pady=(0, 8)); e_email.insert(0, cfg.get("email", "") or "")
    tk.Label(frm, text="비밀번호", anchor="w").pack(fill="x")
    pw_row = tk.Frame(frm); pw_row.pack(fill="x", pady=(0, 8))
    e_pw = tk.Entry(pw_row, show="*"); e_pw.pack(side="left", fill="x", expand=True)

    def _toggle_pw():
        hidden = e_pw.cget("show") == "*"
        e_pw.config(show="" if hidden else "*")
        btn_eye.config(text="숨기기" if hidden else "보기")

    btn_eye = tk.Button(pw_row, text="보기", command=_toggle_pw, width=6)
    btn_eye.pack(side="left", padx=(6, 0))
    tk.Label(frm, text="서버 주소 (기본값 권장)", anchor="w").pack(fill="x")
    e_url = tk.Entry(frm); e_url.pack(fill="x"); e_url.insert(0, cfg.get("cloud_url", "") or "")
    status = tk.Label(root, text="", font=("맑은 고딕", 9), fg="#dc2626")
    status.pack()

    def _save():
        email, pw = e_email.get().strip(), e_pw.get().strip()
        url = (e_url.get().strip() or cfg.get("cloud_url"))
        if not email or not pw:
            status.config(text="이메일과 비밀번호를 입력해주세요.", fg="#dc2626")
            return
        status.config(text="로그인 확인 중...", fg="#2563eb")
        root.update()
        ok, msg = _try_login(url, email, pw)
        if ok is False:
            status.config(text=msg, fg="#dc2626")
            return
        # ok is None(서버 연결 불가)이면 일단 저장 — 에이전트가 이후 자동 재시도
        result["email"], result["password"], result["cloud_url"] = email, pw, url
        result["verified"] = bool(ok)
        root.destroy()

    tk.Button(root, text="로그인 · 저장", command=_save, bg="#2563eb", fg="white",
              font=("맑은 고딕", 10, "bold")).pack(pady=12)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()

    if result.get("email") and result.get("password"):
        cfg.update(result)
        try:
            with open(os.path.join(APP_DIR, "agent_config.json"), "w", encoding="utf-8") as f:
                json.dump({"cloud_url": cfg.get("cloud_url"), "email": cfg["email"],
                           "password": cfg["password"], "poll_sec": cfg.get("poll_sec", 3)},
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[agent] 설정 저장 실패: {e}")
        if result.get("verified"):
            try:
                import tkinter as tk
                import tkinter.messagebox as mb
                _r = tk.Tk(); _r.withdraw()
                mb.showinfo("마케팅연구소 에이전트",
                            "로그인 성공! 설정이 저장되었습니다.\n"
                            "이제 컴퓨터를 켜면 에이전트가 자동으로 실행됩니다.")
                _r.destroy()
            except Exception:
                pass
    return cfg


def _setup_file_logging():
    """pythonw(콘솔 없음)에서도 발행 과정을 볼 수 있게 stdout/stderr + logging 을 파일로 남긴다.
    로그 파일: agent.py 와 같은 폴더의 agent.log (발행 실패 진단용)."""
    try:
        import datetime as _dt
        log_path = os.path.join(APP_DIR, "agent.log")
        try:
            if os.path.exists(log_path) and os.path.getsize(log_path) > 5 * 1024 * 1024:
                os.remove(log_path)  # 5MB 넘으면 새로 시작
        except Exception:
            pass
        f = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)
        sys.stdout = f
        sys.stderr = f
        try:
            import logging
            logging.basicConfig(level=logging.INFO, stream=f,
                                format="%(asctime)s %(levelname)s %(name)s %(message)s", force=True)
        except Exception:
            pass
        f.write(f"\n\n===== [agent] 시작 {_dt.datetime.now().isoformat()} (log: {log_path}) =====\n")
        return log_path
    except Exception:
        return None


def main():
    _setup_file_logging()
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    cfg = _load_config()
    if not cfg["email"] or not cfg["password"]:
        cfg = _prompt_login(cfg)   # 최초 실행: 로그인 창
    else:
        # 저장된 계정이 더 이상 유효하지 않으면(비밀번호 변경 등) 재로그인 창
        ok, _ = _try_login(cfg["cloud_url"], cfg["email"], cfg["password"])
        if ok is False:
            cfg = _prompt_login(cfg)
    if not cfg["email"] or not cfg["password"]:
        print("[agent] 계정 미설정. 종료.")
        return
    try:
        asyncio.run(AgentClient(cfg).run())
    except KeyboardInterrupt:
        print("[agent] 종료")


if __name__ == "__main__":
    main()
