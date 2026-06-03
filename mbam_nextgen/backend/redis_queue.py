import redis
import json
import os
from datetime import datetime

# Redis 설정
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

class TaskQueueManager:
    """
    [SaaS 아키텍처 핵심]
    백엔드 재시작에도 작업 상태를 유지하고, 
    동시 접속 유저의 작업을 분산 처리(Celery/RQ)하기 위한 Redis 큐 매니저
    """
    def __init__(self):
        try:
            self.redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            # 서버 구동 시 Redis 연결 테스트
            self.redis_client.ping()
        except redis.ConnectionError:
            # 로컬 환경에서 Redis 컨테이너가 없을 때 다운되지 않도록 예외 처리
            self.redis_client = None

    def publish_task(self, task_id: str, user_id: str, task_type: str, payload: dict):
        """작업을 큐에 등록하고 상태를 'pending'으로 설정합니다."""
        if not self.redis_client: return False
        
        task_data = {
            "status": "pending",
            "user_id": user_id,
            "task_type": task_type,
            "created_at": datetime.utcnow().isoformat(),
            "payload": json.dumps(payload)
        }
        
        # 해시 맵에 상태 저장
        self.redis_client.hset(f"task:{task_id}", mapping=task_data)
        # 작업 큐에 푸시 (FIFO)
        self.redis_client.lpush("mbam_task_queue", task_id)
        return True

    def get_task_status(self, task_id: str):
        """클라이언트(프론트엔드)가 API를 통해 현재 작업의 상태를 조회할 때 사용합니다."""
        if not self.redis_client: return {"status": "redis_offline"}
        
        data = self.redis_client.hgetall(f"task:{task_id}")
        if data and "payload" in data:
            try:
                data["payload"] = json.loads(data["payload"])
            except: pass
        if data and "result" in data:
            try:
                data["result"] = json.loads(data["result"])
            except: pass
            
        return data if data else {"status": "not_found"}

    def update_task_status(self, task_id: str, status: str, result: dict = None):
        """독립된 워커 프로세스(Playwright 엔진)가 작업 상태와 결과를 업데이트할 때 사용합니다."""
        if not self.redis_client: return
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        if result:
            update_data["result"] = json.dumps(result)
            
        self.redis_client.hset(f"task:{task_id}", mapping=update_data)

task_manager = TaskQueueManager()
