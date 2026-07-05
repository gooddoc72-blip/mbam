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


def _load_config() -> dict:
    cfg = {
        "cloud_url": "http://127.0.0.1:8000",
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
    return {"success": True, "logs": [str(l) for l in st.get("logs", [])[-6:]]}


async def _handle_register_account(payload: dict) -> dict:
    # 기기 인증: 사용자 PC에서 브라우저를 열어 수동 로그인+2FA → 영구 프로필 저장
    from mbam_nextgen.orchestrator import WorkflowOrchestrator
    result = await WorkflowOrchestrator().register_account_session(
        payload.get("naver_id", ""), payload.get("naver_pw")
    )
    if not result.get("success"):
        raise RuntimeError(result.get("error", "기기 인증 실패"))
    return result


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
    "place_fetch_mid": _handle_place_fetch_mid,
    "place_fetch_reviews": _handle_place_fetch_reviews,
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

    async def _process(self, client: httpx.AsyncClient, job: dict):
        job_id = job.get("job_id")
        job_type = job.get("job_type")
        payload = job.get("payload") or {}
        print(f"[agent] 작업 수신: {job_type} ({job_id})")
        handler = HANDLERS.get(job_type)
        body = {"job_id": job_id}
        if not handler:
            body.update({"status": "error", "error": f"미지원 작업 유형: {job_type}"})
        else:
            try:
                result = await handler(payload)
                body.update({"status": "done", "result": result})
                print(f"[agent] 작업 완료: {job_type} ({job_id})")
            except Exception as e:
                body.update({"status": "error", "error": str(e)})
                print(f"[agent] 작업 실패: {job_type} ({job_id}) — {e}")
        try:
            await client.post(f"{self.cfg['cloud_url']}/api/agent/job-result",
                              json=body, headers=self._headers(), timeout=30)
        except Exception as e:
            print(f"[agent] 결과 전송 실패: {e}")


def main():
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    cfg = _load_config()
    if not cfg["email"] or not cfg["password"]:
        print("[agent] 계정 미설정. AGENT_EMAIL / AGENT_PASSWORD (또는 agent_config.json) 을 지정하세요.")
        return
    try:
        asyncio.run(AgentClient(cfg).run())
    except KeyboardInterrupt:
        print("[agent] 종료")


if __name__ == "__main__":
    main()
