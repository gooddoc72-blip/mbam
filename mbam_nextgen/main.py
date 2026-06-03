import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .orchestrator import WorkflowOrchestrator

async def main():
    """
    [Presentation Layer]
    애플리케이션 부트스트래퍼 - 블로그/카페, 단일/멀티 계정 모드 지원
    """
    if os.name == 'nt':
        import sys
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            if sys.stdout.encoding != 'utf-8':
                sys.stdout.reconfigure(encoding='utf-8')
        except: pass

    orchestrator = WorkflowOrchestrator()
    
    # ═══════════════════════════════════════════════════════
    # ⚙️ 실행 모드 선택
    # ═══════════════════════════════════════════════════════
    #   "blog_single" → 블로그 단일 계정
    #   "blog_multi"  → 블로그 멀티 계정
    #   "cafe_single" → 카페 단일 계정
    # ═══════════════════════════════════════════════════════
    
    RUN_MODE = "blog_single"
    
    # ───────────────────────────────────────────────────────
    # 📌 [블로그 단일 모드]
    # ───────────────────────────────────────────────────────
    if RUN_MODE == "blog_single":
        await orchestrator.execute_blog_workflow(
            account_id   = "ch_2101",
            keyword      = "정부지원금",
            test_image   = "mbam_nextgen/test_image.jpg",
            speed_mode   = "normal",
            speed_multiplier = 0.5,
            publish_mode = "none",          # "none" | "now" | "schedule"
            schedule_date = None,
            schedule_time = None,
            proxy        = None
        )
    
    # ───────────────────────────────────────────────────────
    # 📌 [블로그 멀티 모드]
    # ───────────────────────────────────────────────────────
    elif RUN_MODE == "blog_multi":
        accounts = [
            {
                "id": "ch_2101",
                "keyword": "정부지원금",
                "publish_mode": "now",
                "proxy": None,
            },
            {
                "id": "blog_account_2",
                "keyword": "정부지원금",
                "publish_mode": "schedule",
                "date": "2026-05-15",
                "time": "10:30",
                "proxy": None,
            },
        ]
        
        global_config = {
            "speed_mode": "normal",
            "speed_multiplier": 0.5,
            "image": "mbam_nextgen/test_image.jpg",
            "min_delay": 180,
            "max_delay": 600,
        }
        
        await orchestrator.execute_multi_workflow(accounts, global_config)

    # ───────────────────────────────────────────────────────
    # ☕ [카페 단일 모드]
    # ───────────────────────────────────────────────────────
    elif RUN_MODE == "cafe_single":
        await orchestrator.execute_cafe_workflow(
            account_id   = "ch_2101",           # 네이버 로그인 ID
            cafe_id      = "your_cafe_id",      # ⚠️ 카페 URL ID (예: "joonggonara")
            board_name   = "자유게시판",          # ⚠️ 게시판 이름
            keyword      = "정부지원금",
            test_image   = "mbam_nextgen/test_image.jpg",
            speed_mode   = "normal",
            speed_multiplier = 0.5,
            auto_submit  = False,               # True: 자동등록 / False: 수동등록
            proxy        = None
        )


if __name__ == "__main__":
    asyncio.run(main())
