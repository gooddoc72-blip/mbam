"""프록시 풀 — 등록된 프록시 IP를 자동 로테이션/계정고정으로 배정.

정책(하이브리드, 프록시_전략.md 반영):
- 로그인·발행·소통이웃 등 '계정 정체성이 중요한 작업' → 계정별 고정(sticky): 같은 계정은 항상 같은 IP.
- 방문·부스트·순위수집 등 '계정 상관 적은 작업' → 라운드로빈 회전(돌려가며).

Playwright 는 인증형 프록시를 {"server","username","password"} 로 받으므로 파싱해서 넘긴다.
"""
import random
import hashlib
from mbam_nextgen.backend.database import ProxyServer

# 계정 로그인이 개입돼 '고정'이 안전한 작업 종류
_STICKY_KINDS = {"post", "publish", "blog", "cafe", "engagement", "nurture"}


def parse_proxy_line(line: str):
    """유연 파싱: 'user:pass@host:port', 'host:port', 'scheme://user:pass@host:port' 등.
    반환: {"server","username","password"} 또는 None(무효)."""
    s = (line or "").strip()
    if not s:
        return None
    scheme = "http"
    if "://" in s:
        scheme, s = s.split("://", 1)
        scheme = (scheme.strip() or "http").lower()
    user = pw = None
    if "@" in s:
        cred, s = s.rsplit("@", 1)
        if ":" in cred:
            user, pw = cred.split(":", 1)
        else:
            user = cred
    host_port = s.strip()
    # host:port 필수 (포트 없으면 무효)
    if not host_port or ":" not in host_port:
        return None
    host, _, port = host_port.rpartition(":")
    if not host or not port.isdigit():
        return None
    return {"server": f"{scheme}://{host_port}", "username": (user or None), "password": (pw or None)}


def to_playwright(proxy) -> dict:
    """ProxyServer 행 → Playwright proxy config."""
    if not proxy or not getattr(proxy, "server", None):
        return None
    cfg = {"server": proxy.server}
    if getattr(proxy, "username", None):
        cfg["username"] = proxy.username
    if getattr(proxy, "password", None):
        cfg["password"] = proxy.password
    return cfg


def list_active(db, user_id):
    return (db.query(ProxyServer)
            .filter(ProxyServer.user_id == user_id, ProxyServer.is_active == 1)
            .order_by(ProxyServer.created_at).all())


def _sticky_index(account_id: str, n: int) -> int:
    h = hashlib.md5((account_id or "").encode("utf-8")).hexdigest()
    return int(h, 16) % n


def pick(db, user_id, mode: str = "hybrid", account_id: str = None, task_kind: str = "post") -> dict:
    """풀에서 프록시 1개를 정책에 맞게 골라 Playwright config 로 반환(없으면 None).

    mode: "hybrid"(기본) | "roundrobin"(무조건 회전) | "sticky"(무조건 계정고정)
    """
    pool = list_active(db, user_id)
    if not pool:
        return None
    m = (mode or "hybrid").lower()
    if m == "roundrobin":
        return to_playwright(random.choice(pool))
    if m == "sticky":
        return to_playwright(pool[_sticky_index(account_id, len(pool))])
    # hybrid: 계정 로그인 작업은 고정, 그 외는 회전
    if account_id and (task_kind in _STICKY_KINDS):
        return to_playwright(pool[_sticky_index(account_id, len(pool))])
    return to_playwright(random.choice(pool))
