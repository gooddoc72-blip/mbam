import asyncio
import threading
import json
import os
from datetime import datetime

# 실행 로그 저장 경로
LOG_PATH = "mbam_nextgen/logs"
os.makedirs(LOG_PATH, exist_ok=True)

class EngineRunner:
    """
    [Bridge] Streamlit(동기) ↔ Orchestrator(비동기) 연결 브릿지
    """
    
    def __init__(self):
        self._status = "idle"       # idle | running | completed | error
        self._progress = ""
        self._result = None
        self._thread = None
        
        # 백그라운드 스케줄러 시작
        self._stop_scheduler = threading.Event()
        self._sched_thread = threading.Thread(target=self._background_scheduler, daemon=True)
        self._sched_thread.start()

    def _background_scheduler(self):
        """매일 오전 9시 자동 수집 및 앱 기동 시 미실행분 즉시 수집 (Catch-up)"""
        import time
        from mbam_nextgen.services.gov_data import GovDataCollector
        collector = GovDataCollector()
        
        # 데이터 디렉토리 확인
        os.makedirs("mbam_nextgen/data", exist_ok=True)
        sched_file = "mbam_nextgen/data/scheduler_state.json"
        
        print("[Scheduler] 백그라운드 서비스 시작됨")
        
        while not self._stop_scheduler.is_set():
            try:
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")
                
                # 마지막 실행 정보 로드
                last_run = ""
                if os.path.exists(sched_file):
                    try:
                        with open(sched_file, "r") as f:
                            last_run = json.load(f).get("last_gov_collect", "")
                    except: pass
                
                # 실행 조건 판단
                # 1. 9시~10시 사이이고 아직 오늘 실행 안 함
                # 2. 혹은 앱 기동 시점에 이미 9시가 넘었는데 오늘 실행 기록이 없음 (Catch-up)
                is_schedule_time = (now.hour == 9 and 0 <= now.minute <= 59)
                is_missed_today = (now.hour >= 9 and last_run != today_str)
                
                if is_schedule_time or is_missed_today:
                    if last_run != today_str:
                        print(f"[Scheduler] [{today_str}] 정기 글감 수집 트리거 (이유: {'정기' if is_schedule_time else '지연분 보충'})")
                        
                        # 비동기 루프 생성하여 수집 실행
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(collector.fetch_all_categories_batch())
                        loop.close()
                        
                        # 성공 시 상태 저장
                        with open(sched_file, "w") as f:
                            json.dump({"last_gov_collect": today_str, "last_success": now.isoformat()}, f)
                        print(f"[Scheduler] [{today_str}] 수집 작업 완료.")
                
            except Exception as e:
                print(f"[Scheduler] 오류 발생: {e}")
            
            # 5분마다 체크 (부하 방지 및 지연 대응)
            time.sleep(300)

    @property
    def status(self):
        return self._status
    
    @property
    def progress(self):
        return self._progress

    @property
    def result(self):
        return self._result

    def is_running(self):
        return self._status == "running"

    def run_blog(self, config: dict):
        """블로그 워크플로우를 백그라운드에서 실행"""
        self._status = "running"
        self._progress = "블로그 엔진 초기화 중..."
        self._thread = threading.Thread(target=self._run_async, args=(self._blog_task, config))
        self._thread.start()

    def run_cafe(self, config: dict):
        """카페 워크플로우를 백그라운드에서 실행"""
        self._status = "running"
        self._progress = "카페 엔진 초기화 중..."
        self._thread = threading.Thread(target=self._run_async, args=(self._cafe_task, config))
        self._thread.start()

    def run_multi(self, accounts: list, global_config: dict):
        """멀티 워크플로우를 백그라운드에서 실행"""
        self._status = "running"
        self._progress = "멀티 계정 엔진 초기화 중..."
        self._thread = threading.Thread(target=self._run_async, args=(self._multi_task, (accounts, global_config)))
        self._thread.start()

    def run_engagement(self, config: dict):
        """블로그 소통(공감/댓글/이웃) 워크플로우를 백그라운드에서 실행"""
        self._status = "running"
        self._progress = "소통 자동화 초기화 중..."
        self._thread = threading.Thread(target=self._run_async, args=(self._engagement_task, config))
        self._thread.start()

    def _run_async(self, coro_func, config):
        """비동기 함수를 새 이벤트 루프에서 실행"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro_func(config))
            self._result = result
            self._status = "completed"
            self._save_log(result)
        except Exception as e:
            err_result = {
                "success": False,
                "error": str(e),
                "account_id": config.get("account_id", "Unknown"),
                "keyword": config.get("keyword", "N/A"),
                "timestamp": datetime.now().isoformat()
            }
            self._result = err_result
            self._status = "error"
            self._progress = f"오류 발생: {e}"
            self._save_log(err_result)
        finally:
            loop.close()

    async def _blog_task(self, config):
        from .orchestrator import WorkflowOrchestrator
        orch = WorkflowOrchestrator()
        return await orch.execute_blog_workflow(**config)

    async def _cafe_task(self, config):
        from .orchestrator import WorkflowOrchestrator
        orch = WorkflowOrchestrator()
        return await orch.execute_cafe_workflow(**config)

    async def _multi_task(self, args):
        accounts, global_config = args
        from .orchestrator import WorkflowOrchestrator
        orch = WorkflowOrchestrator()
        return await orch.execute_multi_workflow(accounts, global_config)

    async def _engagement_task(self, config):
        from .orchestrator import WorkflowOrchestrator
        orch = WorkflowOrchestrator()
        return await orch.execute_engagement_workflow(**config)

    def _save_log(self, result):
        """실행 결과를 JSON 로그로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(LOG_PATH, f"run_{timestamp}.json")
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": timestamp,
                "result": result
            }, f, ensure_ascii=False, indent=2, default=str)

    _log_cache = {"data": [], "last_sync": 0}

    @classmethod
    def get_logs(cls, limit: int = 20) -> list:
        """최근 실행 로그를 반환 (성능 최적화를 위한 2초 캐싱)"""
        import time
        now = time.time()
        
        # 2초 이내의 요청은 캐시 데이터 반환
        if now - cls._log_cache["last_sync"] < 2:
            return cls._log_cache["data"][:limit]

        logs = []
        if not os.path.exists(LOG_PATH):
            return logs
        try:
            # 파일 목록을 읽고 최신순으로 정렬
            all_files = sorted(os.listdir(LOG_PATH), reverse=True)
            files = all_files[:limit]
            for f in files:
                try:
                    with open(os.path.join(LOG_PATH, f), "r", encoding="utf-8") as fp:
                        logs.append(json.load(fp))
                except: continue
            
            # 캐시 업데이트
            cls._log_cache["data"] = logs
            cls._log_cache["last_sync"] = now
            
        except Exception as e:
            print(f"[Runner] 로그 읽기 오류: {e}")
            
        return logs
