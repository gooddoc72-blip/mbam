import os
import sys
import subprocess
import time
import platform
import urllib.request


def _adb_exe():
    """동봉된 adb.exe 경로를 우선 반환하고, 없으면 PATH의 adb를 사용한다."""
    candidates = []
    if getattr(sys, "frozen", False):
        # PyInstaller로 패키징된 경우: _MEIPASS(내부 리소스) 및 실행파일 옆 폴더 확인
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        candidates.append(os.path.join(base, "adb", "adb.exe"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "adb", "adb.exe"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "_internal", "adb", "adb.exe"))
    else:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "adb", "adb.exe"))
    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"  # 마지막 폴백: PATH에 등록된 adb


def _run_adb(args, log=print):
    """adb 명령을 실행하고 실패 시 사유를 로그로 남긴다."""
    try:
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            [_adb_exe()] + args,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            timeout=30,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            log(f"ADB 명령 실패({' '.join(args)}): {err}")
            return None
        return result.stdout.strip()
    except FileNotFoundError:
        log("⚠️ adb를 찾을 수 없습니다. 휴대폰 USB 테더링/ADB 설치 상태를 확인하세요. (IP 미변경)")
        return None
    except Exception as e:
        log(f"ADB 명령 실행 오류({' '.join(args)}): {e}")
        return None


def is_device_connected(log=print):
    """ADB로 연결된(authorized) 기기가 있는지 확인."""
    out = _run_adb(["devices"], log=log)
    if out is None:
        return False
    lines = [ln.strip() for ln in out.splitlines()[1:] if ln.strip()]
    devices = [ln for ln in lines if ln.endswith("\tdevice") or ln.endswith(" device")]
    unauthorized = [ln for ln in lines if "unauthorized" in ln]
    if unauthorized:
        log("⚠️ 휴대폰이 'unauthorized' 상태입니다. 휴대폰 화면에서 USB 디버깅 허용을 눌러주세요.")
    return len(devices) > 0


def get_public_ip(log=print):
    """현재 공인 IP를 조회한다. 실패하면 None."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                ip = resp.read().decode("utf-8", "ignore").strip()
                if ip:
                    return ip
        except Exception:
            continue
    return None


def _rotate_mobile_ip(log=print):
    """최신 안드로이드에서 동작하는 방식으로 모바일(테더링) IP를 재할당한다.

    구형 방식(am broadcast AIRPLANE_MODE)은 Android 10+에서
    'SecurityException: Permission Denial'로 차단되므로 더 이상 쓰지 않는다.
    성공한 방식 이름을 반환한다.
    """
    # 방식 A: 비행기 모드 (Android 11+ 의 cmd connectivity, shell 권한으로 동작)
    r = _run_adb(["shell", "cmd", "connectivity", "airplane-mode", "enable"], log=log)
    if r is not None:
        log("비행기 모드 ON (연결 끊는 중)...")
        time.sleep(5)
        _run_adb(["shell", "cmd", "connectivity", "airplane-mode", "disable"], log=log)
        log("비행기 모드 OFF (네트워크 복구 중)...")
        time.sleep(8)
        return "airplane-mode(cmd)"

    # 방식 B: 모바일 데이터 토글 (svc data) — 대부분의 기기에서 shell 권한으로 IP 재할당
    rd = _run_adb(["shell", "svc", "data", "disable"], log=log)
    if rd is not None:
        log("모바일 데이터 OFF (연결 끊는 중)...")
        time.sleep(5)
        _run_adb(["shell", "svc", "data", "enable"], log=log)
        log("모바일 데이터 ON (네트워크 복구 중)...")
        time.sleep(8)
        return "mobile-data(svc)"

    # 방식 C: 구형 폴백 (settings + broadcast) — 최신 기기에선 broadcast가 막혀 실패할 수 있음
    log("최신 방식이 동작하지 않아 구형 방식으로 시도합니다...")
    _run_adb(["shell", "settings", "put", "global", "airplane_mode_on", "1"], log=log)
    _run_adb(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true"], log=log)
    time.sleep(5)
    _run_adb(["shell", "settings", "put", "global", "airplane_mode_on", "0"], log=log)
    _run_adb(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"], log=log)
    time.sleep(8)
    return "legacy(settings+broadcast)"


def toggle_airplane_mode(log=print, verify=True):
    """모바일(테더링) IP를 재할당한다.

    반환값: IP 변경 성공(또는 성공으로 추정) True / 실패 False
    verify=True 이면 변경 전후 공인 IP를 비교해 실제로 바뀌었는지 확인한다.
    """
    if platform.system() == "Darwin":
        log("Mac 환경에서는 자동 IP 변경을 지원하지 않습니다. 수동으로 IP를 변경해주세요.")
        time.sleep(5)
        return False

    # 1) 기기 연결 확인 — 없으면 IP는 절대 안 바뀌므로 즉시 경고
    if not is_device_connected(log=log):
        log("⚠️ ADB로 연결된 휴대폰이 없어 IP를 변경하지 못했습니다. (USB 테더링/디버깅 확인 필요)")
        return False

    old_ip = get_public_ip(log=log) if verify else None
    if verify:
        log(f"현재 IP: {old_ip or '조회 실패'} → 변경 시도")

    method = _rotate_mobile_ip(log=log)

    if not verify:
        log(f"IP 변경 작업 완료 (방식: {method})")
        return True

    # 2) 네트워크가 복구되고 IP가 실제로 바뀌었는지 최대 여러 번 확인
    new_ip = None
    for _ in range(6):
        new_ip = get_public_ip(log=log)
        if new_ip and new_ip != old_ip:
            break
        time.sleep(3)

    if new_ip is None:
        log("⚠️ IP 조회에 실패했습니다(네트워크 복구 지연 가능). 변경 여부를 확인하지 못했습니다.")
        return False
    if old_ip and new_ip == old_ip:
        log(f"⚠️ IP가 변경되지 않았습니다 (여전히 {new_ip}, 방식: {method}). 통신사가 같은 IP를 재할당했을 수 있습니다.")
        return False

    log(f"✅ IP 변경 완료: {old_ip or '이전'} → {new_ip} (방식: {method})")
    return True


if __name__ == "__main__":
    toggle_airplane_mode()
