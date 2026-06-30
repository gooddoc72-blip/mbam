# -*- coding: utf-8 -*-
"""
클라이언트 라이선스 검증 (표준 라이브러리만 사용 — 추가 설치 불필요).

흐름:
  1) 로컬 캐시(license.json)에서 코드/마지막검증시각 로드
  2) 코드가 있으면 서버에 /verify → 성공 시 통과, 실패 시 차단
  3) 서버 접속 불가(오프라인) 시: 마지막 성공 검증이 OFFLINE_GRACE_DAYS 이내면 통과
  4) 코드가 없으면 activate 필요 (인증창에서 입력)

서버 주소 우선순위: 환경변수 MBAM_LICENSE_SERVER > license_config.json > 기본값
"""
import json
import os
import socket
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from .hwid import get_hwid, machine_name

# 기본 서버 주소 — 배포 시 license_config.json 또는 환경변수로 덮어쓰기
DEFAULT_SERVER = "http://127.0.0.1:8005"
OFFLINE_GRACE_DAYS = 7          # 서버 접속 불가 시 허용할 오프라인 일수
VERIFY_TIMEOUT = 8             # 초

APP_NAME = "MBAM"


def _config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _license_path() -> Path:
    return _config_dir() / "license.json"


def _server_url() -> str:
    env = os.environ.get("MBAM_LICENSE_SERVER")
    if env:
        return env.rstrip("/")
    # 설치 폴더에 동봉되는 설정 파일
    cfg = Path(__file__).resolve().parent.parent / "license_config.json"
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding="utf-8")).get("server", DEFAULT_SERVER).rstrip("/")
        except Exception:
            pass
    return DEFAULT_SERVER


class LicenseResult:
    def __init__(self, ok: bool, message: str = "", need_activation: bool = False, offline: bool = False):
        self.ok = ok
        self.message = message
        self.need_activation = need_activation
        self.offline = offline


class LicenseClient:
    def __init__(self):
        self.hwid = get_hwid()
        self.machine_name = machine_name()
        self.server = _server_url()

    # ── 로컬 캐시 ─────────────────────────────────────────────
    def _load(self) -> dict:
        p = _license_path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self, data: dict):
        _license_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def saved_code(self) -> str:
        return self._load().get("code", "")

    # ── 서버 통신 ─────────────────────────────────────────────
    def _post(self, path: str, body: dict) -> dict:
        url = self.server + path
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=VERIFY_TIMEOUT) as resp:
            return json.loads(resp.read().decode())

    # ── 공개 API ─────────────────────────────────────────────
    def activate(self, code: str) -> LicenseResult:
        """인증창에서 코드 입력 → 서버에 바인딩 요청."""
        code = (code or "").strip().upper().replace(" ", "")
        if not code:
            return LicenseResult(False, "인증코드를 입력하세요.", need_activation=True)
        try:
            res = self._post("/activate", {
                "code": code, "hwid": self.hwid, "machine_name": self.machine_name,
            })
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode()).get("detail", "")
            except Exception:
                detail = ""
            return LicenseResult(False, detail or f"인증 실패(HTTP {e.code})", need_activation=True)
        except (urllib.error.URLError, socket.timeout):
            return LicenseResult(False, "라이선스 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요.",
                                 need_activation=True)
        if res.get("authorized"):
            self._save({
                "code": code,
                "hwid": self.hwid,
                "last_verified": datetime.now(timezone.utc).isoformat(),
                "expires_at": res.get("expires_at"),
            })
            return LicenseResult(True, res.get("message", "인증 완료"))
        return LicenseResult(False, res.get("message", "인증 실패"), need_activation=True)

    def verify(self) -> LicenseResult:
        """실행 시 자동 검증. 저장된 코드가 없으면 need_activation."""
        cached = self._load()
        code = cached.get("code", "")
        if not code:
            return LicenseResult(False, "인증코드를 입력해야 합니다.", need_activation=True)

        try:
            res = self._post("/verify", {"code": code, "hwid": self.hwid})
        except (urllib.error.URLError, socket.timeout):
            # 오프라인 → 유예기간 검사
            return self._offline_grace(cached)
        except urllib.error.HTTPError:
            return self._offline_grace(cached)

        if res.get("authorized"):
            cached["last_verified"] = datetime.now(timezone.utc).isoformat()
            cached["expires_at"] = res.get("expires_at")
            self._save(cached)
            return LicenseResult(True, "정상 인증")
        # 서버가 명시적으로 거부 → 캐시 무효화하고 재인증 요구
        return LicenseResult(False, res.get("message", "인증 실패"),
                             need_activation=True)

    def _offline_grace(self, cached: dict) -> LicenseResult:
        last = cached.get("last_verified")
        if not last:
            return LicenseResult(False, "최초 인증은 인터넷 연결이 필요합니다.", need_activation=True)
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return LicenseResult(False, "인증 정보를 읽을 수 없습니다.", need_activation=True)
        days = (datetime.now(timezone.utc) - last_dt).days
        if days <= OFFLINE_GRACE_DAYS:
            return LicenseResult(True, f"오프라인 모드 (마지막 인증 {days}일 전)", offline=True)
        return LicenseResult(
            False,
            f"오프라인 사용 기간({OFFLINE_GRACE_DAYS}일)을 초과했습니다. 인터넷에 연결 후 다시 실행하세요.",
            need_activation=False,
        )

    def deactivate_local(self):
        """로컬 캐시 삭제 (코드 재입력 강제)."""
        p = _license_path()
        if p.exists():
            p.unlink()
