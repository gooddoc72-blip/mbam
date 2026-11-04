# -*- coding: utf-8 -*-
"""
기기 승인 방식 인증 (크롤링 프로그램과 동일한 방식).

인증코드를 입력받지 않는다. 대신:
  1) 실행하면 이 PC 의 기기번호(HWID)를 서버에 보내 승인 여부를 확인한다.
  2) 미등록이면 사용자가 이름/소속을 적어 [승인 요청] → 서버에 pending 으로 등록된다.
  3) 관리자가 승인도구(admin_tool.py)에서 승인하면, 다음 실행부터 바로 열린다.

제품(product) 별로 승인이 분리된다.
  ""     — 기존 devices 테이블 (크롤러 등 기존 클라이언트)
  "cafe" — 네이버 카페 전용판
  "blog" — 블로그 자동화 전용판
같은 PC 라도 제품마다 따로 승인받아야 한다.

서버 주소 우선순위: 환경변수 MBAM_LICENSE_SERVER > license_config.json > 기본값
(licensing.client 와 같은 규칙을 쓴다 — 설치본에 license_config.json 이 동봉된다)

표준 라이브러리만 사용한다(추가 설치 불필요).
"""
import json
import os
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .client import _server_url, VERIFY_TIMEOUT, APP_NAME
from .hwid import get_hwid, machine_name

# 서버 접속 불가 시, 마지막으로 '승인됨'을 확인한 뒤 며칠까지 봐줄지.
# (출장·인터넷 장애로 프로그램이 아예 안 열리는 상황을 막는다)
OFFLINE_GRACE_DAYS = 7


def _parse_utc(iso):
    """서버가 주는 만료일(UTC, 타임존 없음) → aware datetime. 없거나 깨졌으면 None."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except Exception:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _expired_message(iso) -> str:
    when = f" (만료일 {iso[:10]})" if iso else ""
    return (f"사용 기간이 만료되었습니다{when}.\n"
            "연장하려면 아래 [연장 요청하기] 를 누른 뒤 관리자에게 결제·연장을 문의하세요.")


class DeviceResult:
    """
    ok        : 실행 허용 여부
    status    : unregistered | pending | approved | blocked | expired | offline | error
    message   : 사용자에게 보여줄 안내 문구
    can_request: [승인 요청] 버튼을 띄워도 되는 상태인지
    """

    def __init__(self, ok: bool, status: str, message: str = "", can_request: bool = False):
        self.ok = ok
        self.status = status
        self.message = message
        self.can_request = can_request


class DeviceAuthClient:
    def __init__(self, product: str = ""):
        self.product = (os.environ.get("MBAM_PRODUCT") or product or "").strip().lower()
        self.hwid = get_hwid()
        self.machine_name = machine_name()
        self.server = _server_url()

    # ── 로컬 캐시 (오프라인 유예용) ────────────────────────────
    def _cache_path(self) -> Path:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = Path(base) / APP_NAME
        d.mkdir(parents=True, exist_ok=True)
        name = f"device_{self.product}.json" if self.product else "device.json"
        return d / name

    def _load(self) -> dict:
        p = self._cache_path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self, data: dict):
        try:
            self._cache_path().write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── 서버 통신 ─────────────────────────────────────────────
    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(self.server + path,
                                     data=json.dumps(body).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=VERIFY_TIMEOUT) as resp:
            return json.loads(resp.read().decode())

    # ── 공개 API ─────────────────────────────────────────────
    def verify(self) -> DeviceResult:
        """이 PC 가 승인된 기기인지 확인."""
        try:
            res = self._post("/verify", {"hwid": self.hwid, "product": self.product})
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, OSError):
            return self._offline_grace()

        status = res.get("status", "unknown")
        if res.get("authorized"):
            self._save({
                "hwid": self.hwid,
                "product": self.product,
                "last_verified": datetime.now(timezone.utc).isoformat(),
                # 오프라인 유예 중에도 구독 만료일은 지킨다(None=무기한)
                "expires_at": res.get("expires_at"),
            })
            return DeviceResult(True, "approved", res.get("message", "인증 성공"))

        if status == "expired":
            return DeviceResult(False, "expired", _expired_message(res.get("expires_at")),
                                can_request=True)
        if status == "pending":
            return DeviceResult(False, "pending",
                                "관리자 승인을 기다리는 중입니다.\n승인되면 다시 실행해 주세요.")
        if status == "blocked":
            return DeviceResult(False, "blocked",
                                "차단된 기기입니다. 관리자에게 문의하세요.")
        # unregistered / unknown
        return DeviceResult(False, "unregistered",
                            "이 PC 는 아직 등록되지 않았습니다.\n아래에서 승인을 요청하세요.",
                            can_request=True)

    def request_approval(self, name: str) -> tuple:
        """관리자에게 승인 요청. (성공여부, 메시지)"""
        name = (name or "").strip()
        if not name:
            return False, "이름/소속을 입력해 주세요."
        try:
            res = self._post("/request_approval", {
                "hwid": self.hwid, "name": name[:120], "product": self.product,
            })
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, OSError):
            return False, "인증 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요."
        return bool(res.get("success")), res.get("message", "요청 완료")

    def _offline_grace(self) -> DeviceResult:
        """서버에 못 붙을 때 — 마지막 승인 확인이 유예기간 안이면 통과시킨다."""
        cached = self._load()
        last = cached.get("last_verified")
        if not last:
            return DeviceResult(False, "error",
                                "인증 서버에 연결할 수 없습니다.\n최초 실행은 인터넷 연결이 필요합니다.")
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return DeviceResult(False, "error", "인증 정보를 읽을 수 없습니다.")
        exp = _parse_utc(cached.get("expires_at"))
        if exp and exp < datetime.now(timezone.utc):
            return DeviceResult(False, "expired", _expired_message(cached.get("expires_at")))
        days = (datetime.now(timezone.utc) - last_dt).days
        if days <= OFFLINE_GRACE_DAYS:
            return DeviceResult(True, "offline", f"오프라인 모드 (마지막 확인 {days}일 전)")
        return DeviceResult(False, "error",
                            f"오프라인 사용 기간({OFFLINE_GRACE_DAYS}일)을 초과했습니다.\n"
                            "인터넷에 연결한 뒤 다시 실행하세요.")


if __name__ == "__main__":
    c = DeviceAuthClient(product="cafe")
    print("서버:", c.server)
    print("HWID:", c.hwid)
    r = c.verify()
    print(f"결과: ok={r.ok} status={r.status} msg={r.message}")
