import os
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List
from mbam_nextgen.infrastructure.database import DatabaseManager
from mbam_nextgen.backend.auth import get_current_user

router = APIRouter()
db = DatabaseManager()


# ── 앱 로그(mbam_sys.log) 끝부분 보기 — [로그] 화면용, 읽기 전용 ──────────────────
# 로그 파일은 백엔드 전역 하나다. 설치형(카페·블로그 전용판)은 백엔드가 고객 PC 에
# 있어 그 고객 것뿐이지만, 웹(클라우드)에서는 전 고객 기록이 섞이므로 관리자만 본다.
# 경로가 두 단계("/system-log/tail")라 아래 "/{table_name}" 과 겹치지 않는다.
_MAX_LINES = 1000
_TAIL_BYTES = 1024 * 1024  # 끝에서 최대 1MB 만 읽는다(로그가 커도 가볍게)

# 로그에 섞여 들어갔을 수 있는 비밀값을 가린다.
_SECRET_PATTERNS = [
    # key=value / "key": "value" 꼴 (비밀번호·토큰·API 키 등)
    (re.compile(r'(?i)((?:pass(?:word)?|passwd|pw|naver_pw|secret|token|api[_-]?key|access[_-]?key|authorization|cookie|session)'
                r'["\']?\s*[:=]\s*["\']?)([^"\'\s,;&}]+)'), r'\1****'),
    (re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._\-]+'), r'\1****'),
    (re.compile(r'eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}'), '****(JWT)'),
    (re.compile(r'\bsk-(?:ant-)?[A-Za-z0-9_\-]{12,}'), 'sk-****'),
    (re.compile(r'\bAIza[0-9A-Za-z_\-]{20,}'), 'AIza****'),
    (re.compile(r'\b(?:ghp|gho|xox[abp])_?[A-Za-z0-9\-]{16,}'), '****'),
]


def _mask_secrets(line: str) -> str:
    for pat, rep in _SECRET_PATTERNS:
        line = pat.sub(rep, line)
    return line


def _log_file_path() -> str:
    """core.logger 가 실제로 쓰는 파일 경로(없으면 기본 위치)."""
    try:
        import logging
        from mbam_nextgen.core.logger import logger as _app_logger
        for h in _app_logger.handlers:
            if isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None):
                return h.baseFilename
    except Exception:
        pass
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "logs", "mbam_sys.log")


@router.get("/system-log/tail", summary="앱 로그(mbam_sys.log) 마지막 N줄 — 비밀값 가림")
async def tail_system_log(lines: int = Query(200, ge=1, le=_MAX_LINES),
                          current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    product = (os.getenv("MBAM_PRODUCT", "mbam") or "mbam").strip().lower()
    standalone = product in ("cafe", "blog")
    if not standalone and (current_user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="앱 로그는 관리자만 볼 수 있습니다.")

    path = _log_file_path()
    if not os.path.exists(path):
        return {"success": True, "path": os.path.basename(path), "lines": [], "size": 0}
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        if size > _TAIL_BYTES:
            f.seek(size - _TAIL_BYTES)
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    rows = text.splitlines()
    if size > _TAIL_BYTES and rows:
        rows = rows[1:]  # 중간에서 잘린 첫 줄은 버린다
    tail = [_mask_secrets(r) for r in rows[-lines:]]
    return {"success": True, "path": os.path.basename(path), "lines": tail, "size": size}


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
