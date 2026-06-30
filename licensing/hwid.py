# -*- coding: utf-8 -*-
"""
이 PC 를 고유하게 식별하는 HWID 계산 (Windows 우선, 타 OS 폴백 포함).

- Windows: 레지스트리 MachineGuid (Windows 설치마다 고유, 안정적) 를 기준으로 사용.
- 추가로 머신 이름 + MAC(uuid.getnode) 을 섞어 해시 → 16자리 짧은 지문 생성.
- 어떤 경우에도 같은 PC 에서는 항상 같은 값이 나오도록 설계.
"""
import hashlib
import platform
import socket
import uuid


def _windows_machine_guid() -> str:
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


def machine_name() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return platform.node() or "unknown-pc"


def get_hwid() -> str:
    """이 PC 의 고유 지문(16 hex). 같은 PC 면 항상 동일."""
    parts = [
        _windows_machine_guid(),          # Windows 설치 고유 GUID
        platform.system(),
        str(uuid.getnode()),              # MAC 기반 노드 ID
    ]
    seed = "|".join(p for p in parts if p)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:16].upper()


if __name__ == "__main__":
    print("HWID:", get_hwid())
    print("PC name:", machine_name())
