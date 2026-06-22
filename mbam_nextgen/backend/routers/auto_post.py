from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncio
from mbam_nextgen.orchestrator import WorkflowOrchestrator, task_logger
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer

router = APIRouter()
seo_analyzer = SeoAnalyzer()

class AutoPostRequest(BaseModel):
    # For multiple accounts
    accounts: Optional[List[dict]] = None
    interval_mins: Optional[int] = 5
    wash_images: Optional[bool] = False
    image_folder_path: Optional[str] = None
    
    # Pre-generated contents
    generated_contents: Optional[List[dict]] = None
    
    login_mode: str = "manual" # "manual" | "auto"
    naver_id: Optional[str] = None
    naver_pw: Optional[str] = None
    
    post_mode: str = "ai_generate" # "manual_text" | "ai_generate"
    target_keyword: Optional[str] = None
    
    title: Optional[str] = None
    content: Optional[str] = None
    images: Optional[List[str]] = []
    
    publish_mode: str = "instant" # "instant" | "schedule"
    schedule_date: Optional[str] = None
    schedule_time: Optional[str] = None
    
    # AI Engine
    ai_provider: str = "claude" # "claude" | "gemini" | "openai"
    api_key: Optional[str] = None # Custom API Key
    post_purpose: Optional[str] = None
    promo_type: Optional[str] = None
    distribution_mode: Optional[str] = None
    
    # Cafe specific
    target_type: str = "blog" # "blog" | "cafe"
    cafe_url: Optional[str] = None
    board_name: Optional[str] = None
    cafe_action_type: str = "post" # "post" | "comment"

    # SEO Reference Data
    reference_data: Optional[dict] = None
    
    # URL based product posting
    product_url: Optional[str] = None
    extract_url_images: Optional[bool] = False
    
    # Automation / Content Collect Data
    source_data: Optional[str] = None
    generate_card_news: Optional[bool] = False
    prompt_category: Optional[str] = None  # 예: 'content_collect'(글감수집 전용 프롬프트)
    include_source_link: Optional[bool] = False  # 본문 끝에 [링크] 출처 자동 추가 (기본 OFF)
    
    # Proxy / Tethering
    use_tethering: Optional[bool] = False

# In-memory status store for monitoring (prototype level)
task_status_store = {}
active_tasks = {}

def scrape_product_info_sync(url: str, extract_images: bool = False) -> tuple[str, str]:
    from playwright.sync_api import sync_playwright
    import time
    import os
    import uuid
    import requests
    
    scraped_text = ""
    temp_img_dir = ""
    
    if extract_images:
        temp_img_dir = os.path.join(os.getcwd(), "temp_scraped_images", str(uuid.uuid4()))
        os.makedirs(temp_img_dir, exist_ok=True)
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            page.set_default_timeout(30000)
            page.goto(url)
            
            # 스크롤 내려서 Lazy Loading 이미지 불러오기
            for _ in range(5):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(1)
            time.sleep(2)
            
            # Extract basic text (title, price, body text)
            title = page.title()
            body_text = page.evaluate("document.body.innerText")
            # Heuristic: limit text length to avoid token explosion
            clean_text = "\n".join([line.strip() for line in body_text.split('\n') if len(line.strip()) > 5])
            scraped_text = f"상품 타이틀: {title}\n\n상세 정보:\n{clean_text[:3000]}"
            
            # 이미지 수집
            if extract_images:
                saved_count = 0
                for frame in page.frames:
                    try:
                        img_locators = frame.locator("img").all()
                        for img in img_locators:
                            try:
                                src = img.get_attribute("src")
                                if not src: continue
                                if src.startswith("//"): src = "https:" + src
                                if not src.startswith("http"): continue
                                
                                # 너무 작은 아이콘이나 픽셀 제외
                                box = img.bounding_box()
                                if box and (box["width"] < 150 or box["height"] < 150):
                                    continue
                                    
                                resp = requests.get(src, timeout=5)
                                if resp.status_code == 200:
                                    file_path = os.path.join(temp_img_dir, f"scraped_{saved_count}.jpg")
                                    with open(file_path, "wb") as f:
                                        f.write(resp.content)
                                    saved_count += 1
                                    if saved_count >= 15:  # 최대 15장으로 제한
                                        break
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if saved_count >= 15:
                        break
                        
            browser.close()
    except Exception as e:
        print(f"Failed to scrape product URL: {e}")
        scraped_text = f"상품 URL 스크래핑 실패: {str(e)}"
    return scraped_text, temp_img_dir

async def run_automation_task(task_id: str, req: AutoPostRequest):
    task_status_store[task_id] = {"status": "running", "logs": ["작업이 시작되었습니다."]}
    
    def log(msg: str):
        try:
            print(f"[{task_id}] {msg}")
        except UnicodeEncodeError:
            try:
                print(f"[{task_id}] " + msg.encode('cp949', errors='replace').decode('cp949'))
            except Exception:
                pass
        except Exception:
            pass
        task_status_store[task_id]["logs"].append(msg)
        
    task_logger.set(log)

    try:
        orchestrator = WorkflowOrchestrator()
        account_id = req.naver_id if req.naver_id else "unknown_account"

        if req.target_type == "blog":
            if req.accounts and len(req.accounts) > 0:
                log(f"[다중 계정 블로그] 워크플로우를 시작합니다. (계정 수: {len(req.accounts)})")
                result = await orchestrator.execute_multi_blog_workflow(
                    accounts=req.accounts,
                    interval_mins=req.interval_mins,
                    wash_images=req.wash_images,
                    image_folder_path=req.image_folder_path,
                    generated_contents=req.generated_contents,
                    keyword=req.target_keyword or "테스트",
                    publish_mode=req.publish_mode,
                    ai_provider=req.ai_provider,
                    reference_data=req.reference_data,
                    post_purpose=req.post_purpose,
                    promo_type=req.promo_type,
                    distribution_mode=req.distribution_mode,
                    source_data=req.source_data,
                    generate_card_news=req.generate_card_news,
                    use_tethering=req.use_tethering,
                    log_callback=log
                )
            else:
                log(f"[{req.target_type}] 단일 계정 워크플로우를 시작합니다...")
                result = await orchestrator.execute_blog_workflow(
                    account_id=account_id,
                    account_pw=req.naver_pw,
                    keyword=req.target_keyword or "테스트",
                    publish_mode=req.publish_mode,
                    schedule_date=req.schedule_date,
                    schedule_time=req.schedule_time,
                    ai_provider=req.ai_provider,
                    reference_data=req.reference_data,
                    post_purpose=req.post_purpose,
                    promo_type=req.promo_type,
                    distribution_mode=req.distribution_mode
                )
            if result.get("success"):
                log("✅ 블로그 포스팅이 성공적으로 완료되었습니다!")
            else:
                log(f"⚠️ 블로그 워크플로우 실패: {result.get('error')}")
                
        elif req.target_type == "cafe":
            account_id = req.naver_id if req.naver_id else "unknown_account"
            log(f"[{req.target_type}] 워크플로우를 시작합니다...")
            result = await orchestrator.execute_cafe_workflow(
                account_id=account_id,
                cafe_id=req.cafe_url,
                board_name=req.board_name,
                keyword=req.target_keyword or "테스트",
                auto_submit=True if req.publish_mode == "instant" else False,
                ai_provider=req.ai_provider,
                action_type=req.cafe_action_type,
                content=req.content,
                reference_data=req.reference_data,
                naver_pw=req.naver_pw,
                source_data=req.source_data,
                prompt_category=req.prompt_category,
                include_source_link=req.include_source_link
            )
            if result.get("success"):
                log("✅ 카페 포스팅이 성공적으로 완료되었습니다!")
            else:
                log(f"⚠️ 카페 워크플로우 실패: {result.get('error')}")

        task_status_store[task_id]["status"] = "completed"
        
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        log(f"오류 발생: {str(e)}\n{tb_str}")
        try:
            from mbam_nextgen.core.logger import logger
            logger.error(f"❌ [auto_post] {req.naver_id or '?'} 작업 실패: {str(e)} | {tb_str.splitlines()[-1] if tb_str else ''}")
        except Exception:
            pass
        task_status_store[task_id]["status"] = "failed"


@router.post("")
@router.post("/")
async def trigger_auto_post(req: AutoPostRequest):
    import uuid
    task_id = str(uuid.uuid4())
    task = asyncio.create_task(run_automation_task(task_id, req))
    active_tasks[task_id] = task
    return {
        "success": True, 
        "message": "자동화 작업이 백그라운드에서 시작되었습니다.", 
        "task_id": task_id
    }

class RegisterAccountRequest(BaseModel):
    naver_id: str
    naver_pw: Optional[str] = None


async def run_register_task(task_id: str, naver_id: str, naver_pw: Optional[str]):
    task_status_store[task_id] = {"status": "running", "logs": [f"[계정 등록] '{naver_id}' 기기 인증을 시작합니다..."]}

    def log(msg: str):
        try:
            print(f"[{task_id}] {msg}")
        except Exception:
            pass
        task_status_store[task_id]["logs"].append(msg)

    try:
        orchestrator = WorkflowOrchestrator()
        result = await orchestrator.register_account_session(naver_id, naver_pw, log_callback=log)
        if result.get("success"):
            task_status_store[task_id]["status"] = "completed"
            log("✅ 계정 등록(기기 인증)이 완료되었습니다! 이제 자동 로그인됩니다.")
        else:
            task_status_store[task_id]["status"] = "failed"
            log(f"⚠️ 등록 실패: {result.get('error')}")
    except Exception as e:
        import traceback
        task_status_store[task_id]["status"] = "failed"
        log(f"오류 발생: {str(e)}\n{traceback.format_exc()}")
    finally:
        active_tasks.pop(task_id, None)


@router.post("/register-account", summary="네이버 계정 등록(기기 인증) — 1회 수동 로그인")
async def register_account(req: RegisterAccountRequest):
    import uuid
    task_id = str(uuid.uuid4())
    task = asyncio.create_task(run_register_task(task_id, req.naver_id, req.naver_pw))
    active_tasks[task_id] = task
    return {
        "success": True,
        "task_id": task_id,
        "message": "계정 등록(기기 인증) 작업이 시작되었습니다. 열리는 브라우저 창에서 로그인 + 2단계 인증을 완료해 주세요.",
    }


@router.post("/focus-running", summary="진행 중인 자동화 브라우저 창을 앞으로 가져오기")
async def focus_running():
    from mbam_nextgen.orchestrator import RUNNING_PAGES
    focused, stale = [], []
    for acc, pg in list(RUNNING_PAGES.items()):
        try:
            await pg.bring_to_front()
            focused.append(acc)
        except Exception:
            stale.append(acc)
    for acc in stale:
        RUNNING_PAGES.pop(acc, None)
    return {"success": True, "focused": focused}


@router.get("/registered-accounts", summary="기기 인증(영구 프로필) 완료된 계정 ID 목록")
async def registered_accounts():
    import os
    from mbam_nextgen.infrastructure.session import is_registered, PROFILES_DIR
    ids = []
    try:
        if os.path.isdir(PROFILES_DIR):
            for name in os.listdir(PROFILES_DIR):
                if is_registered(name):
                    ids.append(name)
    except Exception:
        pass
    return {"registered": ids}


@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str):
    if task_id in active_tasks:
        active_tasks[task_id].cancel()
        # 작업 task가 store를 초기화하기 전 취소돼도 KeyError 안 나도록 가드
        entry = task_status_store.setdefault(task_id, {"status": "running", "logs": []})
        entry["status"] = "failed"
        entry["logs"].append("🛑 사용자에 의해 작업이 강제 중단되었습니다.")
        return {"success": True, "message": "작업이 중단되었습니다."}
    return {"success": False, "message": "실행 중인 작업을 찾을 수 없습니다."}

async def _generate_impl(req: AutoPostRequest):
    print(f"[DEBUG] generate_multiple_contents called. product_url: {req.product_url}")
    results = []
    num_accounts = len(req.accounts) if req.accounts and len(req.accounts) > 0 else 1
    
    # URL 스크래핑
    scraped_info = ""
    scraped_image_folder = ""
    if req.product_url and req.product_url.strip():
        print(f"[DEBUG] Scraping URL: {req.product_url}, Extract Images: {req.extract_url_images}")
        try:
            scraped_info, scraped_image_folder = await asyncio.to_thread(scrape_product_info_sync, req.product_url, req.extract_url_images)
            print(f"[DEBUG] Scraping success. Length: {len(scraped_info)}, ImgFolder: {scraped_image_folder}")
        except Exception as e:
            print(f"[DEBUG] Scraping failed: {e}")
            scraped_info = f"[URL 수집 실패] {str(e)}"
            
    final_source_data = req.source_data or ""
    if scraped_info:
        final_source_data = f"{final_source_data}\n\n[타겟 상품 스크래핑 정보]\n{scraped_info}"

    async def generate_single(i):
        try:
            # 병렬 처리 충돌(Errno 22) 방지를 위해 개별 orchestrator 생성
            local_orchestrator = WorkflowOrchestrator()
            content_text = await local_orchestrator._generate_content_with_retry(
                keyword=req.target_keyword or "테스트",
                ai_provider=req.ai_provider,
                reference_data=req.reference_data,
                post_purpose=req.post_purpose,
                promo_type=req.promo_type,
                distribution_mode=req.distribution_mode,
                source_data=final_source_data,
                api_key=req.api_key,
                prompt_category=req.prompt_category,
                include_source_link=req.include_source_link
            )
            
            if content_text:
                import re
                content_text = re.sub(r'(\*\*|~~|__)', '', content_text)
            
            title = f"[{req.target_keyword}] 포스팅"
            body = content_text
            lines = content_text.split('\n')
            if lines:
                first_line = lines[0].strip()
                if first_line.startswith('제목:') or first_line.startswith('[제목]') or first_line.startswith('#'):
                    title = first_line.replace('제목:', '').replace('[제목]', '').replace('#', '').strip()
                    body = '\n'.join(lines[1:]).strip()
                elif len(first_line) > 0 and len(first_line) < 50:
                    title = first_line
                    body = '\n'.join(lines[1:]).strip()
                    
            return {
                "account_id": req.accounts[i].get("id") if req.accounts else "unknown",
                "title": title,
                "content": body
            }
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            with open("error_traceback.txt", "w", encoding="utf-8") as f:
                f.write(str(e) + "\n\n" + err_msg)
            return {
                "account_id": req.accounts[i].get("id") if req.accounts else "unknown",
                "title": "오류 발생",
                "content": f"원고 생성 중 오류가 발생했습니다: {str(e)}"
            }

    # Run all generations concurrently
    results = await asyncio.gather(*(generate_single(i) for i in range(num_accounts)))
    
    return {
        "success": True,
        "generated_contents": results,
        "scraped_image_folder": scraped_image_folder if scraped_image_folder else None
    }


@router.post("/generate-content")
async def generate_multiple_contents(req: AutoPostRequest):
    """원고 생성은 30초 이상 걸릴 수 있어 백그라운드 작업으로 처리(프록시 30초 타임아웃 회피).
    프론트는 반환된 task_id 로 /status/{task_id} 폴링 후 result.generated_contents 를 사용한다."""
    import uuid
    task_id = str(uuid.uuid4())
    task_status_store[task_id] = {"status": "running", "logs": ["원고 생성 중..."]}

    async def _run():
        try:
            result = await _generate_impl(req)
            task_status_store[task_id]["result"] = result
            task_status_store[task_id]["status"] = "completed"
        except Exception as e:
            import traceback
            task_status_store[task_id]["status"] = "failed"
            task_status_store[task_id]["error"] = str(e)
            task_status_store[task_id]["logs"].append(traceback.format_exc())
        finally:
            active_tasks.pop(task_id, None)

    active_tasks[task_id] = asyncio.create_task(_run())
    return {"success": True, "task_id": task_id}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_status_store[task_id]

@router.get("/active_tasks")
async def get_active_tasks():
    active = []
    for t_id, data in task_status_store.items():
        if data.get("status") == "running":
            title = data.get("logs", ["알 수 없는 작업"])[0] if data.get("logs") else "알 수 없는 작업"
            active.append({"task_id": t_id, "title": title})
    return {"tasks": active}
