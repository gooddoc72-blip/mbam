# -*- coding: utf-8 -*-
"""
이 PC 를 고유하게 식별하는 HWID 계산 (Windows / macOS, 그 외 폴백 포함).

- Windows: 레지스트리 MachineGuid (Windows 설치마다 고유, 안정적) 를 기준으로 사용.
- macOS  : IOPlatformUUID (기기마다 고유, OS 재설치해도 안 바뀜) 를 기준으로 사용.
- 추가로 머신 이름 + MAC(uuid.getnode) 을 섞어 해시 → 16자리 짧은 지문 생성.
- 어떤 경우에도 같은 PC 에서는 항상 같은 값이 나오도록 설계.

⚠ 이미 승인받은 Windows 고객의 HWID 가 바뀌면 전부 '미승인' 으로 돌아간다.
  아래 seed 구성에서 Windows 가 만들어내는 값은 절대 건드리지 말 것
  (macOS 항목은 Windows 에서 항상 빈 문자열이라 seed 에 끼어들지 않는다).
"""
import hashlib
import os
import platform
import socket
import subprocess
import sys
import uuid
from pathlib import Path


def _windows_machine_guid() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import winreg  # Windows 전용
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return str(val)
    except Exception:
        return ""


def _macos_platform_uuid() -> str:
    """macOS 기기 고유 UUID.

    맥에는 MachineGuid 가 없어서 예전 코드로는 지문이 uuid.getnode() 하나에만
    기대게 된다. 그런데 최근 macOS 는 Wi-Fi MAC 주소를 무작위로 바꾸므로
    (사설 Wi-Fi 주소), 그 상태면 '승인받은 기기가 며칠 뒤 미승인으로 돌아간다'.
    IOPlatformUUID 는 메인보드에 묶인 값이라 흔들리지 않는다.
    """
    if sys.platform != "darwin":
        return ""
    try:
        out = subprocess.check_output(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            text=True, timeout=5, stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                # 예: |   "IOPlatformUUID" = "1F2E3D4C-..."
                parts = line.split('"')
                if len(parts) >= 4:
                    return parts[-2]
    except Exception:
        pass
    return ""


def _macos_serial() -> str:
    """macOS 하드웨어 시리얼번호. IOPlatformUUID 를 못 읽었을 때의 2차 수단."""
    if sys.platform != "darwin":
        return ""
    try:
        out = subprocess.check_output(
            ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            text=True, timeout=5, stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if "IOPlatformSerialNumber" in line:
                parts = line.split('"')
                if len(parts) >= 4:
                    return parts[-2]
    except Exception:
        pass
    return ""


def _stored_fallback_id() -> str:
    """하드웨어 식별자를 하나도 못 구했을 때 쓰는 최후 수단.

    한 번 만들어 파일에 적어두고 계속 같은 값을 읽는다. uuid.getnode() 로 대신하면
    안 된다 — 맥은 Wi-Fi MAC 을 무작위로 바꾸고, 랜카드가 꺼져 있으면 파이썬이
    그때그때 임의의 값을 돌려주기 때문에 실행할 때마다 기기번호가 달라진다.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    p = Path(base) / "MBAM" / "hwid_fallback.txt"
    try:
        if p.exists():
            v = p.read_text(encoding="utf-8").strip()
            if v:
                return v
        v = uuid.uuid4().hex
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v, encoding="utf-8")
        return v
    except Exception:
        return ""


def machine_name() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return platform.node() or "unknown-pc"


def get_hwid() -> str:
    """이 PC 의 고유 지문(16 hex). 같은 PC 면 항상 동일해야 한다.

    ⚠ 이 값이 실행할 때마다 달라지면 승인이 절대 유지되지 않는다.
      (맥에서 실제로 그랬다 — 한 대에서 세 개의 기기번호가 나와 승인이 계속 풀렸다)

    Windows 는 기존 고객의 기기번호가 바뀌면 전부 미승인으로 돌아가므로,
    아래 else 갈래(= MachineGuid 가 있는 경우)의 seed 구성은 절대 건드리지 말 것.
    """
    win = _windows_machine_guid()
    mac = _macos_platform_uuid() or _macos_serial()

    if not win and sys.platform == "darwin":
        # macOS — 하드웨어에 묶인 값만 쓰고 uuid.getnode() 는 섞지 않는다.
        # 맥은 '사설 Wi-Fi 주소' 기능으로 MAC 주소를 수시로 바꾸고, 유선/무선이
        # 꺼져 있으면 파이썬이 매번 임의의 값을 돌려준다. 그걸 섞으면 기기번호가
        # 실행할 때마다 달라진다.
        parts = [mac or _stored_fallback_id(), platform.system()]
    else:
        parts = [
            win,                              # Windows 설치 고유 GUID
            mac,                              # macOS 기기 고유 UUID (윈도에서는 빈 값)
            platform.system(),
            str(uuid.getnode()),              # MAC 기반 노드 ID
        ]

    seed = "|".join(p for p in parts if p)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:16].upper()


if __name__ == "__main__":
    print("HWID:", get_hwid())
    print("PC name:", machine_name())
