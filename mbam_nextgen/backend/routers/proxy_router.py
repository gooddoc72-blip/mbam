"""프록시 풀 관리 라우터 — 프록시 IP 등록/목록/삭제/토글/테스트 + IP 방식 설정.

IP 방식(ip_mode): "none"(안 씀) | "tethering"(USB 테더링) | "proxy"(프록시 풀)
로테이션(proxy_rotation): "hybrid"(기본·권장) | "roundrobin"(무조건 회전) | "sticky"(계정고정)
설정은 사용자별로 AppSetting(KV)에 JSON 저장.
"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mbam_nextgen.backend.database import get_db, ProxyServer, AppSetting
from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.services.proxy_pool import parse_proxy_line

router = APIRouter(prefix="/api/proxy", tags=["Proxy Pool"])

_DEFAULT_SETTINGS = {"ip_mode": "none", "proxy_rotation": "hybrid"}


def _uid(cu):
    return cu.get("sub")


def _settings_key(user_id):
    return f"ip_settings:{user_id}"


def get_ip_settings(db, user_id) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == _settings_key(user_id)).first()
    if row and row.value:
        try:
            v = json.loads(row.value)
            return {**_DEFAULT_SETTINGS, **(v or {})}
        except Exception:
            pass
    return dict(_DEFAULT_SETTINGS)


class ProxyAdd(BaseModel):
    lines: str                       # 한 줄에 하나씩(여러 개 일괄). 'user:pass@host:port' 등
    label: Optional[str] = None


class SettingsUpdate(BaseModel):
    ip_mode: Optional[str] = None
    proxy_rotation: Optional[str] = None


def _serialize(p):
    # 비밀번호는 마스킹해서 반환(노출 방지)
    return {
        "id": p.id, "server": p.server, "username": p.username,
        "password_set": bool(p.password), "label": p.label,
        "is_active": bool(p.is_active),
    }


@router.get("/", summary="프록시 풀 목록 + IP 방식 설정")
def list_proxies(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _uid(current_user)
    rows = db.query(ProxyServer).filter(ProxyServer.user_id == uid).order_by(ProxyServer.created_at).all()
    return {"success": True, "items": [_serialize(r) for r in rows], "settings": get_ip_settings(db, uid)}


@router.post("/", summary="프록시 여러 개 일괄 등록(줄 단위)")
def add_proxies(req: ProxyAdd, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _uid(current_user)
    added, bad = 0, []
    for raw in (req.lines or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        cfg = parse_proxy_line(line)
        if not cfg:
            bad.append(line)
            continue
        db.add(ProxyServer(user_id=uid, server=cfg["server"], username=cfg.get("username"),
                           password=cfg.get("password"), label=(req.label or None), is_active=1))
        added += 1
    db.commit()
    return {"success": True, "added": added, "invalid": bad}


@router.delete("/{proxy_id}", summary="프록시 삭제")
def delete_proxy(proxy_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(ProxyServer).filter(ProxyServer.id == proxy_id, ProxyServer.user_id == _uid(current_user)).first()
    if p:
        db.delete(p)
        db.commit()
    return {"success": True}


@router.post("/{proxy_id}/toggle", summary="프록시 사용/중지 토글")
def toggle_proxy(proxy_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(ProxyServer).filter(ProxyServer.id == proxy_id, ProxyServer.user_id == _uid(current_user)).first()
    if not p:
        raise HTTPException(status_code=404, detail="프록시를 찾을 수 없습니다.")
    p.is_active = 0 if p.is_active else 1
    db.commit()
    return {"success": True, "is_active": bool(p.is_active)}


@router.post("/settings", summary="IP 방식 설정 저장(none/tethering/proxy + 로테이션)")
def update_settings(req: SettingsUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _uid(current_user)
    cur = get_ip_settings(db, uid)
    if req.ip_mode in ("none", "tethering", "proxy"):
        cur["ip_mode"] = req.ip_mode
    if req.proxy_rotation in ("hybrid", "roundrobin", "sticky"):
        cur["proxy_rotation"] = req.proxy_rotation
    key = _settings_key(uid)
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = json.dumps(cur)
    else:
        db.add(AppSetting(key=key, value=json.dumps(cur)))
    db.commit()
    return {"success": True, "settings": cur}


@router.post("/{proxy_id}/test", summary="프록시로 실제 외부IP 확인(연결 테스트)")
async def test_proxy(proxy_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    p = db.query(ProxyServer).filter(ProxyServer.id == proxy_id, ProxyServer.user_id == _uid(current_user)).first()
    if not p:
        raise HTTPException(status_code=404, detail="프록시를 찾을 수 없습니다.")
    # httpx로 프록시 경유 외부 IP 조회(인증 포함). socks5는 httpx[socks] 필요할 수 있음.
    try:
        import httpx
        proxy_url = p.server
        if p.username:
            scheme, host = p.server.split("://", 1) if "://" in p.server else ("http", p.server)
            cred = p.username + (f":{p.password}" if p.password else "")
            proxy_url = f"{scheme}://{cred}@{host}"
        async with httpx.AsyncClient(proxies=proxy_url, timeout=10.0) as client:
            r = await client.get("https://api.ipify.org?format=text")
            if r.status_code == 200:
                return {"success": True, "ip": r.text.strip()}
            return {"success": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
