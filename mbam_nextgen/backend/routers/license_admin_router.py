"""설치형(카페·블로그·크롤러) 라이선스 서버 관리 — marketlabs 관리자 페이지에서 쓰는 중계 API.

브라우저는 라이선스 서버 관리자 토큰을 절대 보지 않는다.
  관리자(웹) ─JWT→ 이 라우터(verify_admin) ─X-Admin-Token→ license.blocklab.co.kr /admin/*
토큰은 Railway 환경변수 LICENSE_ADMIN_TOKEN 에만 둔다.
"""
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import verify_admin

router = APIRouter(prefix="/api/admin/license", tags=["admin-license"])

_ALLOWED_STATUS = {"approved", "blocked", "pending"}
_ALLOWED_CODE_ACTIONS = {"revoke", "unrevoke", "reset"}


def _cfg():
    url = (os.environ.get("LICENSE_SERVER_URL") or "https://license.blocklab.co.kr").rstrip("/")
    token = (os.environ.get("LICENSE_ADMIN_TOKEN") or "").strip()
    return url, token


async def _call(method: str, path: str, body: Optional[dict] = None):
    url, token = _cfg()
    if not token:
        raise HTTPException(status_code=503, detail="LICENSE_ADMIN_TOKEN 이 설정되지 않았습니다. (Railway 환경변수)")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.request(method, url + path, json=body, headers={"X-Admin-Token": token})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="라이선스 서버에 연결할 수 없습니다.")
    if r.status_code == 403:
        # 토큰 불일치 — 라이선스 서버 응답 본문은 그대로 넘기지 않는다
        raise HTTPException(status_code=502, detail="라이선스 서버가 관리자 토큰을 거부했습니다. LICENSE_ADMIN_TOKEN 을 확인하세요.")
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else None
        raise HTTPException(status_code=r.status_code if r.status_code < 500 else 502,
                            detail=detail if isinstance(detail, str) else "라이선스 서버 오류")
    return data


@router.get("/status", summary="라이선스 서버 연결 상태")
async def license_status(admin: dict = Depends(verify_admin)):
    url, token = _cfg()
    if not token:
        return {"configured": False, "ok": False, "server": url,
                "message": "Railway 환경변수 LICENSE_ADMIN_TOKEN 을 설정하세요."}
    try:
        await _call("GET", "/admin/devices")
        return {"configured": True, "ok": True, "server": url}
    except HTTPException as e:
        return {"configured": True, "ok": False, "server": url, "message": e.detail}


@router.get("/devices", summary="설치형 기기 목록")
async def license_devices(admin: dict = Depends(verify_admin)):
    return await _call("GET", "/admin/devices")


class DeviceStatusBody(BaseModel):
    hwid: str
    status: str
    product: str = ""
    days: Optional[int] = None  # 승인 시: None=만료일 유지, 0=무기한, N=N일 연장


@router.post("/device/status", summary="설치형 기기 승인·차단")
async def license_device_status(body: DeviceStatusBody, admin: dict = Depends(verify_admin)):
    if body.status not in _ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail="잘못된 상태값")
    return await _call("POST", "/admin/device/status", body.model_dump())


class DeviceExtendBody(BaseModel):
    hwid: str
    product: str
    days: int


@router.post("/device/extend", summary="설치형 기기 기간 연장")
async def license_device_extend(body: DeviceExtendBody, admin: dict = Depends(verify_admin)):
    if body.days < 0 or body.days > 3650:
        raise HTTPException(status_code=400, detail="연장 일수는 0(무기한)~3650 입니다.")
    return await _call("POST", "/admin/device/extend", body.model_dump())


@router.get("/codes", summary="인증코드 목록")
async def license_codes(admin: dict = Depends(verify_admin)):
    return await _call("GET", "/admin/list")


class IssueBody(BaseModel):
    count: int = 1
    memo: str = ""
    valid_days: int = 0
    max_activations: int = 1


@router.post("/codes/issue", summary="인증코드 발급")
async def license_codes_issue(body: IssueBody, admin: dict = Depends(verify_admin)):
    if not 1 <= body.count <= 100:
        raise HTTPException(status_code=400, detail="발급 개수는 1~100 입니다.")
    return await _call("POST", "/admin/issue", body.model_dump())


class CodeBody(BaseModel):
    code: str


@router.post("/codes/{action}", summary="인증코드 정지·재사용·PC 이전")
async def license_codes_action(action: str, body: CodeBody, admin: dict = Depends(verify_admin)):
    if action not in _ALLOWED_CODE_ACTIONS:
        raise HTTPException(status_code=404, detail="없는 작업")
    return await _call("POST", f"/admin/{action}", body.model_dump())
