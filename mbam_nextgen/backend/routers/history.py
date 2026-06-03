from fastapi import APIRouter
from typing import Dict, Any, List
from mbam_nextgen.infrastructure.database import DatabaseManager

router = APIRouter()
db = DatabaseManager()

@router.get("/{table_name}")
async def get_history(table_name: str, limit: int = 50) -> Dict[str, Any]:
    """SaaS 대시보드에서 각 테이블의 운영 내역을 가져옵니다."""
    try:
        rows = db.get_history(table_name, limit)
        return {
            "success": True,
            "data": rows
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
