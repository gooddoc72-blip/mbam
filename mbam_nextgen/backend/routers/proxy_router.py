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


# ⚠ 슬래시 없는 경로도 반드시 함께 등록한다(다른 라우터들도 같은 이유로 그렇게 돼 있다).
#   없으면 FastAPI 가 /api/proxy → /api/proxy/ 로 307 리다이렉트를 내는데, 그 Location 이
#   백엔드 절대주소(http://127.0.0.1:8010/...)라 브라우저에는 '교차 출처 리다이렉트'가 된다.
#   그러면 Authorization 헤더가 벗겨져 401 이 나고, 프론트가 401 에 새로고침으로 대응해
#   화면이 계속 깜박이며 아무것도 클릭할 수 없게 된다.
@router.get("", summary="프록시 풀 목록 + IP 방식 설정", include_in_schema=False)
@router.get("/", summary="프록시 풀 목록 + IP 방식 설정")
def list_proxies(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _uid(current_user)
    rows = db.query(ProxyServer).filter(ProxyServer.user_id == uid).order_by(ProxyServer.created_at).all()
    return {"success": True, "items": [_serialize(r) for r in rows], "settings": get_ip_settings(db, uid)}


@router.post("", summary="프록시 여러 개 일괄 등록(줄 단위)", include_in_schema=False)
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


@router.delete("/all", summary="등록된 프록시 전체 삭제")
def delete_all_proxies(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # ⚠ 이 경로는 반드시 /{proxy_id} 보다 먼저 선언해야 한다.
    #   뒤에 두면 FastAPI 가 'all' 을 proxy_id 로 받아버려 아무것도 지워지지 않는다.
    uid = _uid(current_user)
    n = db.query(ProxyServer).filter(ProxyServer.user_id == uid).delete()
    db.commit()
    return {"success": True, "deleted": n, "message": f"프록시 {n}개를 모두 삭제했습니다."}


# ── USB 테더링 (안드로이드 폰의 비행기모드 토글로 IP 교체) ──────────────────
@router.get("/tethering/status", summary="테더링용 폰이 연결됐는지 확인")
async def tethering_status():
    """ADB 로 연결된 안드로이드 기기를 확인한다.

    화면에서 '왜 안 되는지' 알 수 없어 기능이 없는 것처럼 보였다.
    연결 여부와 원인을 그대로 돌려준다.
    """
    from mbam_nextgen.infrastructure.tethering import TetheringManager
    tm = TetheringManager()
    try:
        # ⚠ check_device() 는 (연결여부, 기기목록) 튜플을 돌려준다.
        #   그대로 bool() 하면 비어 있지 않은 튜플이라 '항상 연결됨'이 되어,
        #   폰이 없는데도 연결됐다고 표시된다(실제로 그랬다).
        res = tm.check_device()
        connected, devices = res if isinstance(res, tuple) else (bool(res), [])
    except FileNotFoundError:
        return {"connected": False, "adb": False,
                "message": "adb 를 찾을 수 없습니다. 안드로이드 플랫폼 도구(adb)를 설치하고 "
                           "PATH 에 등록해야 USB 테더링을 쓸 수 있습니다."}
    except Exception as e:
        return {"connected": False, "adb": True, "message": f"확인 중 오류: {e}"}
    return {
        "connected": bool(connected), "adb": True, "devices": devices,
        "message": (f"폰이 연결되어 있습니다({len(devices)}대). 계정마다 IP 를 바꿔가며 작업할 수 있습니다."
                    if connected else
                    "연결된 폰이 없습니다. USB 로 연결하고 [USB 디버깅]을 켠 뒤 "
                    "휴대폰 화면의 '이 컴퓨터를 허용하시겠습니까?'에 확인을 눌러주세요."),
    }


@router.post("/tethering/rotate", summary="테더링 IP 교체 시험 — 실제로 바뀌는지 확인")
async def tethering_rotate():
    from mbam_nextgen.infrastructure.tethering import TetheringManager
    from mbam_nextgen.infrastructure.proxy import ProxyManager
    tm = TetheringManager()
    res = tm.check_device()
    connected = res[0] if isinstance(res, tuple) else bool(res)   # (여부, 목록) 튜플이다
    if not connected:
        raise HTTPException(status_code=400, detail="연결된 폰이 없습니다. USB 연결과 [USB 디버깅]을 확인하세요.")
    before = await ProxyManager.verify_ip()
    try:
        await tm.rotate_ip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"IP 교체 실패: {e}")
    after = await ProxyManager.verify_ip()
    return {"success": True, "before": before, "after": after,
            "changed": bool(before and after and before != after and after != "확인 불가"),
            "message": (f"IP 가 {before} → {after} 로 바뀌었습니다."
                        if before != after else
                        f"IP 가 바뀌지 않았습니다({after}). 폰이 데이터(LTE/5G)로 연결돼 있는지 확인하세요.")}


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
            if r.status_code != 200:
                return {"success": False, "error": f"HTTP {r.status_code}"}
            ip = r.text.strip()

            # ⚠ 국가까지 확인한다.
            #   브라우저는 항상 locale=ko-KR / timezone=Asia/Seoul 로 뜨는데,
            #   프록시가 해외 IP 면 '한국 사람이라면서 접속은 미국에서' 가 되어
            #   네이버가 이상 접속으로 본다. 등록 시점에 눈으로 확인할 수 있게 한다.
            info = {}
            try:
                g = await client.get(
                    f"http://ip-api.com/json/{ip}"
                    "?fields=status,country,countryCode,isp,org,as,hosting,proxy,mobile")
                if g.status_code == 200 and (g.json() or {}).get("status") == "success":
                    info = g.json()
            except Exception:
                pass

            country_code = info.get("countryCode")
            out = {
                "success": True, "ip": ip,
                "country": info.get("country"), "country_code": country_code,
                "isp": info.get("isp"), "org": info.get("org"),
                "hosting": info.get("hosting"), "proxy_flag": info.get("proxy"),
                "mobile": info.get("mobile"),
            }

            # 네이버가 위험하게 보는 순서: ① 해외 ② 데이터센터/알려진 프록시 ③ 정상 가정용
            warn = []
            if country_code and country_code != "KR":
                warn.append(f"해외 IP 입니다({info.get('country')}). 프로그램은 한국 사용자로 접속하는데 "
                            f"IP 만 해외라 네이버가 이상 접속으로 봅니다.")
            if info.get("hosting"):
                warn.append(f"데이터센터(서버실) IP 입니다. 제공자: {info.get('isp') or '알 수 없음'}\n"
                            f"가정집·휴대폰 회선이 아니라서, 한국 IP 라도 네이버가 '사람이 아닌 접속'으로 "
                            f"구분하기 쉽습니다. 주거용(residential) 프록시를 권합니다.")
            if info.get("proxy"):
                warn.append("이미 '프록시/VPN 으로 알려진 IP' 입니다. 다른 사람도 같은 IP 를 쓰고 있을 수 있어 "
                            "네이버 쪽에 이미 표시돼 있을 가능성이 높습니다.")
            if warn:
                out["warning"] = "\n\n".join(warn)
            return out
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}
