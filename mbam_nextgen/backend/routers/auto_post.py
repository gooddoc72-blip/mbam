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
    
    post_mode: str # "manual_text" | "ai_generate"
    target_keyword: Optional[str] = None
    
    title: Optional[str] = None
    content: Optional[str] = None
    images: Optional[List[str]] = []
    
    publish_mode: str # "instant" | "schedule"
    schedule_date: Optional[str] = None
    schedule_time: Optional[str] = None
    
    # AI Engine
    ai_provider: str = "claude" # "claude" | "gemini" | "openai"
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
    
    # Automation / Content Collect Data
    source_data: Optional[str] = None
    generate_card_news: Optional[bool] = False

# In-memory status store for monitoring (prototype level)
task_status_store = {}

async def run_automation_task(task_id: str, req: AutoPostRequest):
    task_status_store[task_id] = {"status": "running", "logs": ["작업이 시작되었습니다."]}
    
    def log(msg: str):
        print(f"[{task_id}] {msg}")
        task_status_store[task_id]["logs"].append(msg)
        
    task_logger.set(log)

    try:
        orchestrator = WorkflowOrchestrator()
        
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
                    log_callback=log
                )
            else:
                account_id = req.naver_id if req.naver_id else "unknown_account"
                log(f"[{req.target_type}] 단일 계정 워크플로우를 시작합니다...")
            result = await orchestrator.execute_blog_workflow(
                account_id=account_id,
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
                reference_data=req.reference_data
            )
            if result.get("success"):
                log("✅ 카페 포스팅이 성공적으로 완료되었습니다!")
            else:
                log(f"⚠️ 카페 워크플로우 실패: {result.get('error')}")

        task_status_store[task_id]["status"] = "completed"
        
    except Exception as e:
        log(f"오류 발생: {str(e)}")
        task_status_store[task_id]["status"] = "failed"


@router.post("/")
async def trigger_auto_post(req: AutoPostRequest, background_tasks: BackgroundTasks):
    import uuid
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_automation_task, task_id, req)
    return {
        "success": True, 
        "message": "자동화 작업이 백그라운드에서 시작되었습니다.", 
        "task_id": task_id
    }

@router.post("/generate-content")
async def generate_multiple_contents(req: AutoPostRequest):
    orchestrator = WorkflowOrchestrator()
    results = []
    num_accounts = len(req.accounts) if req.accounts and len(req.accounts) > 0 else 1
    
    for i in range(num_accounts):
        try:
            content_text = await orchestrator._generate_content_with_retry(
                keyword=req.target_keyword or "테스트",
                ai_provider=req.ai_provider,
                reference_data=req.reference_data,
                post_purpose=req.post_purpose,
                promo_type=req.promo_type,
                distribution_mode=req.distribution_mode,
                source_data=req.source_data
            )
            
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
                    
            results.append({
                "account_id": req.accounts[i].get("id") if req.accounts else "unknown",
                "title": title,
                "content": body
            })
        except Exception as e:
            results.append({
                "account_id": req.accounts[i].get("id") if req.accounts else "unknown",
                "title": "오류 발생",
                "content": f"원고 생성 중 오류가 발생했습니다: {str(e)}"
            })
            
    return {"success": True, "generated_contents": results}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_status_store[task_id]
