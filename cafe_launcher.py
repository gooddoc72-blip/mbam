# -*- coding: utf-8 -*-
r"""
네이버 카페 마케팅 프로그램 — 카페 전용 설치형 런처

동작:
  1) 기기 승인 인증 — 크롤링 프로그램과 같은 방식(인증코드 없음).
     이 PC 의 기기번호로 승인 여부를 확인하고, 미등록이면 승인 요청 창이 뜬다.
  2) 백엔드(:8010, MBAM_PRODUCT=cafe) + 프론트(:3010) 기동
  3) 브라우저 자동 열기
  4) 제어창 (닫으면 서버 종료)

풀버전(mbam_launcher.py)과 포트·설정폴더·인증이 모두 분리돼 있어
한 PC 에 둘 다 설치돼 있어도 서로 간섭하지 않는다.

설치형에서는 동봉된 runtime 의 Python·Node 를 우선 사용하고, 없으면 시스템
PATH 의 python/node 를 사용한다(개발 환경 호환).

Windows(Inno Setup) 와 macOS(.app 번들) 양쪽에서 이 파일 하나를 그대로 쓴다.
OS 마다 다른 것은 아래 IS_WIN / IS_MAC 로 갈라 두었다 —
  실행 파일 경로(python.exe vs bin/python3), 사용자 데이터 폴더,
  포트를 잡은 프로세스 조회·종료, 파일 열기, 한글 폰트.
"""
import os
import platform
import secrets
import signal
import socket
import subprocess
import sys
import time
import threading
import webbrowser
from pathlib import Path

from licensing.ui_font import ko, mono

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "mbam-web"

APP_NAME = "카페 마케팅"
PRODUCT = "cafe"

# 설정·로그는 사용자 폴더에 둔다. 설치 폴더(Program Files)는 일반 사용자 권한으로
# 쓸 수 없고, 재설치·업그레이드 때 지워질 수 있기 때문이다.
def _config_root() -> Path:
    """OS 별 '사용자 데이터' 폴더. 프로그램을 다시 설치해도 여기 것은 남는다."""
    if IS_WIN:
        return Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "MBAM-Cafe"
    if IS_MAC:
        # 맥의 표준 위치. ~/Library 는 Finder 에서 기본 숨김이라 고객이 실수로
        # 지울 일이 없고, 앱을 지웠다 다시 깔아도 저장한 계정이 유지된다.
        return Path.home() / "Library" / "Application Support" / "MBAM-Cafe"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "MBAM-Cafe"


CONFIG_DIR = _config_root()
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = CONFIG_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
SECRETS_FILE = CONFIG_DIR / "secrets.env"


def _ensure_secrets() -> dict:
    """JWT_SECRET / ENV_CIPHER_KEY 를 이 PC 에서 1회 만들어 두고 계속 재사용한다.

    - JWT_SECRET     : 로그인 토큰 서명. 없으면 백엔드가 기동 자체를 거부한다.
    - ENV_CIPHER_KEY : 저장된 네이버 계정 비밀번호 암호화 키.
                       매번 새로 만들면 이전에 저장한 비밀번호를 못 푼다 → 반드시 고정.

    개발 환경의 .env 는 고객 설치본에 넣지 않으므로(운영자 키가 들어 있음) 여기서 만든다.
    설치 폴더가 아니라 %LOCALAPPDATA%\\MBAM-Cafe 에 두어 프로그램을 다시 설치해도 유지된다.
    """
    data = {}
    if SECRETS_FILE.exists():
        try:
            for line in SECRETS_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
        except Exception:
            data = {}

    changed = False
    if not data.get("JWT_SECRET"):
        data["JWT_SECRET"] = secrets.token_urlsafe(48)
        changed = True
    if not data.get("ENV_CIPHER_KEY"):
        try:
            from cryptography.fernet import Fernet
            data["ENV_CIPHER_KEY"] = Fernet.generate_key().decode()
        except Exception:
            data["ENV_CIPHER_KEY"] = secrets.token_urlsafe(32)
        changed = True

    if changed:
        SECRETS_FILE.write_text(
            "# 이 파일은 이 PC 전용 보안키입니다. 삭제하면 저장된 계정 비밀번호를 복호화할 수 없습니다.\n"
            + "\n".join(f"{k}={v}" for k, v in data.items()) + "\n",
            encoding="utf-8")
    return data

# 풀버전(8000/3000)과 겹치지 않는 포트. 프론트 빌드의 /api 프록시 대상도
# 이 포트로 굽는다(build_cafe_payload.ps1 의 BACKEND_URL) — 두 값은 항상 같아야 한다.
BACKEND_PORT = 8010
FRONTEND_PORT = 3010

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# ── 런타임 경로 해석 (설치형 동봉 우선, 없으면 시스템) ──────────────────
# 동봉 런타임의 실행 파일 위치는 OS 마다 다르다.
#   Windows : runtime\python\python.exe        runtime\node\node.exe
#   macOS   : runtime/python/bin/python3        runtime/node/bin/node
_PY_CANDS = ((("runtime", "python", "python.exe"), ("runtime", "python", "pythonw.exe")) if IS_WIN
             else (("runtime", "python", "bin", "python3"), ("runtime", "python", "bin", "python")))
_NODE_CAND = ("runtime", "node", "node.exe") if IS_WIN else ("runtime", "node", "bin", "node")
_NPM_CAND  = ("runtime", "node", "npm.cmd") if IS_WIN else ("runtime", "node", "bin", "npm")


def _python_exe() -> str:
    for parts in _PY_CANDS:
        cand = APP_DIR.joinpath(*parts)
        if cand.exists():
            return str(cand)
    return sys.executable or "python3"


def _node_exe() -> str:
    cand = APP_DIR.joinpath(*_NODE_CAND)
    return str(cand) if cand.exists() else "node"


def _npm_cmd() -> str:
    cand = APP_DIR.joinpath(*_NPM_CAND)
    return str(cand) if cand.exists() else "npm"


# ── 포트 유틸 ──────────────────────────────────────────────────────────
def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _port_pids(port: int) -> set:
    if IS_WIN:
        try:
            out = subprocess.check_output(
                f'netstat -aon | findstr :{port} | findstr LISTENING',
                shell=True, text=True, creationflags=CREATE_NO_WINDOW,
            )
            return {line.split()[-1] for line in out.splitlines() if line.strip()}
        except Exception:
            return set()
    # macOS/Linux — lsof 는 맥에 기본 탑재돼 있다.
    try:
        out = subprocess.check_output(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        )
        return {line.strip() for line in out.splitlines() if line.strip()}
    except Exception:
        return set()


def _pid_name(pid: str) -> str:
    """포트를 잡고 있는 게 우리 프로그램인지 남의 프로그램인지 알려면 이름이 필요하다."""
    try:
        if IS_WIN:
            out = subprocess.check_output(
                f'tasklist /FI "PID eq {pid}" /FO CSV /NH',
                shell=True, text=True, creationflags=CREATE_NO_WINDOW,
            ).strip()
            return out.split(",")[0].strip('"') if out and "," in out else ""
        out = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "comm="],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
        return os.path.basename(out) if out else ""
    except Exception:
        return ""


def _kill_port(port: int):
    for pid in _port_pids(port):
        try:
            if IS_WIN:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True,
                               creationflags=CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(int(pid), signal.SIGKILL)
        except Exception:
            pass


def _can_bind(port: int) -> bool:
    """이 PC 에서 그 포트를 열 수 있는지 직접 시험한다.

    백신·보안 프로그램(V3, nProtect 류)이 서명 없는 python.exe/node.exe 의
    리슨을 막으면 서버는 조용히 죽고 창은 '서버 준비 중' 에서 멈춘다.
    미리 여기서 걸러야 원인을 말해 줄 수 있다.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
            s.listen(1)
        return True
    except Exception:
        return False


# ── 서버 기동 ──────────────────────────────────────────────────────────
def _base_env() -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(APP_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    # 카페 전용판 — 백엔드가 카페 관련 라우터만 마운트한다.
    env["MBAM_PRODUCT"] = PRODUCT
    # 보안키 주입 — 없으면 백엔드가 JWT_SECRET 없다고 기동을 거부한다.
    env.update(_ensure_secrets())
    # 설치형: 동봉된 Chromium(Playwright) 경로를 알려줌
    bundled_browsers = APP_DIR / "runtime" / "ms-playwright"
    if bundled_browsers.exists():
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browsers)
    # 동봉 Node 를 PATH 앞에 둔다. npm 은 셸 스크립트라 자기 자신을 실행할 node 를
    # PATH 에서 찾는데, 맥 고객 PC 에는 node 가 없는 게 정상이다(윈도는 npm.cmd 라
    # 이 문제가 없어서 지금까지 드러나지 않았다).
    node_bin = APP_DIR / "runtime" / "node" / ("" if IS_WIN else "bin")
    if node_bin.exists():
        env["PATH"] = str(node_bin) + os.pathsep + env.get("PATH", "")
    return env


def start_backend():
    env = _base_env()
    env["PORT"] = str(BACKEND_PORT)
    # 프론트가 3010 에서 뜨므로 CORS 허용 목록에 넣어준다.
    env["ALLOWED_ORIGINS"] = f"http://localhost:{FRONTEND_PORT},http://127.0.0.1:{FRONTEND_PORT}"
    log = open(LOG_DIR / "backend.log", "a", encoding="utf-8")
    return subprocess.Popen(
        [_python_exe(), str(APP_DIR / "run_backend.py")],
        cwd=str(APP_DIR), env=env,
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )


def start_frontend():
    env = _base_env()
    env["NEXT_PUBLIC_PRODUCT"] = PRODUCT
    # 빌드본은 /api 프록시 대상이 이미 구워져 있지만(routes-manifest),
    # 개발 서버 폴백으로 뜰 때를 위해 런타임에도 넣어둔다.
    env["BACKEND_URL"] = f"http://127.0.0.1:{BACKEND_PORT}"
    log = open(LOG_DIR / "frontend.log", "a", encoding="utf-8")
    built = (WEB_DIR / ".next" / "BUILD_ID").exists()
    next_bin = WEB_DIR / "node_modules" / "next" / "dist" / "bin" / "next"
    if built and next_bin.exists():
        cmd = [_node_exe(), str(next_bin), "start", "-p", str(FRONTEND_PORT)]
    else:
        # 빌드본이 없으면 개발 서버로 폴백
        cmd = [_npm_cmd(), "run", "dev", "--", "-p", str(FRONTEND_PORT)]
    return subprocess.Popen(
        cmd, cwd=str(WEB_DIR), env=env,
        stdout=log, stderr=subprocess.STDOUT, shell=(cmd[0].endswith(".cmd")),
        creationflags=CREATE_NO_WINDOW,
    )


def wait_for_port(port: int, timeout: int = 120) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if _port_open(port):
            return True
        time.sleep(0.5)
    return False


# ── 설치 상태 사전 점검 ────────────────────────────────────────────────
def preflight() -> list:
    """서버를 띄우기 전에 '이러면 절대 안 뜬다' 를 잡아낸다.

    고객 PC 에서 '서버 준비 중' 이 안 끝나는 사고는 대부분 아래 셋 중 하나였다.
    잡아내지 못하면 창은 그냥 '준비 중' 인 채로 남아 고객도 우리도 원인을 모른다.
      1) 설치 폴더에 쓸 수 없음 → 백엔드가 sqlite3.OperationalError 로 즉사
      2) 동봉 실행 파일이 없음 → 백신이 서명 없는 python.exe/node.exe 를 격리
      3) 포트를 못 엶     → 보안 프로그램이 리슨을 차단, 또는 남의 프로그램이 점유
    """
    problems = []

    # 0) macOS 전용 — '앱 실행 위치 무작위화(App Translocation)'.
    #    서명 없는 앱을 DMG 나 다운로드 폴더에서 바로 실행하면 macOS 가 앱을
    #    읽기 전용 임시 경로에 복사해 띄운다. 이 상태에서는 DB 도 로그인 프로필도
    #    만들 수 없어 무조건 실패하는데, 원인이 화면에 전혀 드러나지 않는다.
    #    Finder 로 '응용 프로그램' 폴더에 옮기면 해제된다.
    if IS_MAC and "/AppTranslocation/" in str(APP_DIR):
        problems.append(
            "앱이 임시 위치에서 실행되고 있습니다.\n"
            "   Finder 에서 이 앱을 '응용 프로그램' 폴더로 끌어다 옮긴 뒤,\n"
            "   '응용 프로그램' 폴더에서 다시 실행해 주세요.")

    # 1) 설치 폴더 쓰기 권한. DB·세션·임시 이미지를 설치 폴더 안에 만든다.
    for d in (APP_DIR, APP_DIR / "mbam_nextgen", APP_DIR / "mbam_nextgen" / "data"):
        try:
            d.mkdir(parents=True, exist_ok=True)
            probe = d / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except Exception as e:
            fix = ("이 앱을 '응용 프로그램' 폴더나 홈 폴더로 옮긴 뒤 실행해 주세요."
                   if IS_MAC else
                   "백신의 '제어된 폴더 액세스' 를 끄거나, 프로그램을 다시 설치해 주세요.")
            problems.append(
                f"설치 폴더에 파일을 만들 수 없습니다 → {d}\n"
                f"   ({type(e).__name__}: {e})\n"
                f"   {fix}")
            break

    # 2) 동봉 런타임. 백신이 지우면(윈도) / 압축이 덜 풀리면(맥) 서버가 아예 안 뜬다.
    why = ("설치가 덜 됐을 수 있습니다. 다시 설치해 주세요." if IS_MAC else
           "백신이 지웠을 수 있습니다. 예외 등록 후 다시 설치해 주세요.")
    for label, path in (("파이썬", Path(_python_exe())), ("노드", Path(_node_exe()))):
        # 동봉본이 없으면 _python_exe() 가 시스템 PATH 의 이름("python3")을 돌려준다.
        # 그건 설치본으로서는 정상이 아니므로 절대경로가 아닌 경우도 문제로 잡는다.
        if not path.is_absolute() or not path.exists():
            problems.append(f"{label} 실행 파일이 없습니다 → {path}\n   {why}")

    # 3) 화면 빌드
    if not (WEB_DIR / ".next" / "BUILD_ID").exists():
        problems.append(f"화면 빌드가 없습니다 → {WEB_DIR / '.next'}\n"
                        f"   설치가 덜 됐습니다. 다시 설치해 주세요.")
    elif not (WEB_DIR / "node_modules" / "next" / "dist" / "bin" / "next").exists():
        problems.append(f"화면 실행 파일이 없습니다 → {WEB_DIR / 'node_modules' / 'next'}\n"
                        f"   설치가 덜 됐습니다. 다시 설치해 주세요.")

    # 4) 포트. 먼저 이전 실행분을 정리하고, 그래도 못 열면 차단당한 것이다.
    for label, port in (("백엔드", BACKEND_PORT), ("화면", FRONTEND_PORT)):
        if _port_pids(port):
            _kill_port(port)
            # taskkill 은 비동기다. 바로 bind 를 시험하면 아직 안 풀려서
            # 멀쩡한 재시작인데도 '포트를 못 연다' 는 거짓 경고가 뜬다.
            for _ in range(12):
                if not _port_open(port):
                    break
                time.sleep(0.25)
        if _can_bind(port):
            continue
        holders = ", ".join(f"{pid}({_pid_name(pid) or '알 수 없음'})" for pid in _port_pids(port))
        problems.append(
            f"{label} 포트 {port} 를 열 수 없습니다.\n"
            + (f"   다른 프로그램이 쓰고 있습니다: {holders}" if holders else
               ("   방화벽이 막고 있을 수 있습니다." if IS_MAC else
                "   백신·보안 프로그램이 막고 있을 수 있습니다.")))

    return problems


def save_report(problems=None) -> Path:
    """고객이 그대로 보낼 수 있는 진단 파일 한 장. 바탕화면에 만든다."""
    import shutil as _shutil

    lines = [
        f"=== {APP_NAME} 진단 정보 ===",
        f"만든 시각 : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"버전      : {_local_version()}",
        f"운영체제  : {platform.platform()}",
        f"설치 폴더 : {APP_DIR}",
        f"설정 폴더 : {CONFIG_DIR}",
        "",
        "[ 파일 확인 ]",
    ]
    for label, path in (("동봉 파이썬", Path(_python_exe())),
                        ("동봉 노드", Path(_node_exe())),
                        (".next/BUILD_ID", WEB_DIR / ".next" / "BUILD_ID"),
                        ("node_modules/next", WEB_DIR / "node_modules" / "next")):
        lines.append(f"  {label:18} {'있음' if path.exists() else '없음 ← 문제'}")
    try:
        free = _shutil.disk_usage(str(APP_DIR)).free // (1024 ** 3)
        lines.append(f"  남은 디스크         {free}GB")
    except Exception:
        pass

    lines += ["", "[ 포트 ]"]
    for label, port in (("백엔드", BACKEND_PORT), ("화면", FRONTEND_PORT)):
        holders = ", ".join(f"{pid}({_pid_name(pid) or '?'})" for pid in _port_pids(port)) or "없음"
        lines.append(f"  {label} {port}: 열림={_port_open(port)} / 점유={holders}")

    if problems:
        lines += ["", "[ 사전 점검에서 잡힌 문제 ]"] + [f"  - {p}" for p in problems]

    for name in ("backend.log", "frontend.log"):
        lines += ["", f"[ {name} 마지막 80줄 ]"] + [f"  {ln}" for ln in _log_tail(LOG_DIR / name, 80)]

    desktop = Path(os.path.expanduser("~")) / "Desktop"
    out = (desktop if desktop.exists() else CONFIG_DIR) / "카페마케팅_진단.txt"
    try:
        out.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        out = CONFIG_DIR / "카페마케팅_진단.txt"
        out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _reveal(path: Path):
    """만든 파일을 OS 기본 프로그램으로 연다. os.startfile 은 Windows 에만 있다."""
    if IS_WIN:
        os.startfile(str(path))          # noqa: S606 - Windows 전용 API
    elif IS_MAC:
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _local_version() -> str:
    try:
        import json
        with open(APP_DIR / "version.json", "r", encoding="utf-8-sig") as f:
            return str(json.load(f).get("version") or "?")
    except Exception:
        return "?"


# ── 자동 업데이트 ───────────────────────────────────────────────────────
def _license_server() -> str:
    """license_config.json 의 서버 주소(설치본이 바라보는 라이선스 서버)."""
    try:
        import json
        # utf-8-sig — 이 파일도 PowerShell 빌드가 만들어 BOM 이 붙는다.
        # utf-8 로 읽으면 예외가 나 서버 주소가 빈 값이 되고, 업데이트 확인이 조용히 생략된다.
        with open(APP_DIR / "license_config.json", "r", encoding="utf-8-sig") as f:
            return (json.load(f).get("server") or "").strip()
    except Exception:
        return ""


def _check_update():
    """새 버전이 있으면 물어보고 바뀜 부분만 교체한다. (구현은 licensing/update_prompt.py 공용)"""
    # ⚠ 업데이트 서버에는 Windows 페이로드만 올라간다. 맥에서 그걸 받아 덮어쓰면
    #   runtime\python\python.exe 같은 윈도 전용 파일로 갈아끼워져 앱이 죽는다.
    #   맥 패키지를 서버에 올리기 전까지는 확인 자체를 하지 않는다.
    if not IS_WIN:
        return
    from licensing.update_prompt import run_update_check
    run_update_check(APP_DIR, product=PRODUCT, app_name=APP_NAME, server=_license_server())


# ── 로그 읽기 (실패 원인 표시용) ────────────────────────────────────────
def _log_tail(path: Path, n: int = 200) -> list:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except Exception:
        return []


def _last_error_line(path: Path) -> str:
    """로그 끝에서 실패 원인으로 보이는 줄 하나를 뽑는다.

    파이썬은 예외의 '마지막 줄'(ModuleNotFoundError: ... 같은)에 원인이 있고
    그 위는 전부 스택이라 고객에게 보여줄 게 못 된다. INFO/경고 잡음은 건너뛴다.
    """
    skip = ("INFO:", "WARNING:", "DEBUG:", "  ", "\t", "Traceback")
    for line in reversed(_log_tail(path)):
        s = line.rstrip()
        if not s.strip() or s.startswith(skip):
            continue
        return s.strip()[:150]
    return ""


# ── 제어창 ─────────────────────────────────────────────────────────────
def show_control_window(procs, problems=None):
    import tkinter as tk

    backend_proc, frontend_proc = procs[0], procs[1]
    problems = problems or []

    root = tk.Tk()
    root.title(f"{APP_NAME} 실행 중")
    root.resizable(False, False)
    W, H = 470, 290
    root.update_idletasks()
    x = (root.winfo_screenwidth() - W) // 2
    y = (root.winfo_screenheight() - H) // 3
    root.geometry(f"{W}x{H}+{x}+{y}")

    tk.Label(root, text=APP_NAME, font=ko(14, "bold"), fg="#16a34a").pack(pady=(18, 4))
    state = tk.Label(root, text="서버 준비 중...", font=ko(10), fg="#2980b9")
    state.pack(pady=2)
    # 실패했을 때 원인 한 줄. 평소에는 빈 칸이라 창 모양이 달라지지 않는다.
    detail = tk.Label(root, text="", font=ko(8), fg="#c0392b",
                      wraplength=W - 40, justify="center")
    detail.pack(pady=(2, 4))
    tk.Label(root, text=f"http://localhost:{FRONTEND_PORT}",
             font=mono(10), fg="#888").pack()

    def open_browser():
        webbrowser.open(f"http://localhost:{FRONTEND_PORT}")

    def save_diag():
        # 고객에게 "로그 폴더 들어가서 파일 찾아 보내주세요" 는 통하지 않는다.
        # 바탕화면에 파일 한 장을 만들고 그걸 바로 열어 준다.
        try:
            out = save_report(problems)
            detail.config(text=f"바탕화면에 '{out.name}' 을 저장했습니다. 이 파일을 보내 주세요.",
                          fg="#2980b9")
            _reveal(out)
        except Exception as e:
            detail.config(text=f"진단 파일 저장 실패: {e}", fg="#c0392b")

    tk.Button(root, text="브라우저 다시 열기", command=open_browser).pack(pady=(10, 2))
    tk.Button(root, text="진단 파일 저장 (문제 있을 때)", command=save_diag).pack(pady=2)

    def quit_all():
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        _kill_port(BACKEND_PORT)
        _kill_port(FRONTEND_PORT)
        root.destroy()

    tk.Button(root, text="프로그램 종료", command=quit_all,
              bg="#c0392b", fg="white").pack(pady=2)
    tk.Label(root, text="※ 이 창을 닫으면 서버가 종료됩니다.",
             font=ko(8), fg="#aaa").pack(side="bottom", pady=8)

    root.protocol("WM_DELETE_WINDOW", quit_all)

    started = time.time()

    def fail(msg: str, why: str):
        state.config(text=msg, fg="#c0392b")
        # 고객이 아무것도 안 해도 보낼 파일이 남아 있게 한다.
        try:
            out = save_report(problems)
            hint = f"바탕화면 '{out.name}' 을 보내 주세요."
        except Exception:
            hint = "'진단 파일 저장' 을 눌러 주세요."
        detail.config(text=f"{why}\n{hint}" if why else hint, fg="#c0392b")

    def poll_ready():
        # 프론트만 보고 '실행 중' 이라고 하면 안 된다 — 백엔드는 임포트가 무거워
        # 20초쯤 뒤에 뜨는데, 그 사이 화면은 열리지만 모든 기능이 실패한다.
        be, fe = _port_open(BACKEND_PORT), _port_open(FRONTEND_PORT)
        if be and fe:
            state.config(text="실행 중 ✓", fg="#27ae60")
            detail.config(text="")
            return

        # ⚠ 서버가 죽었는데도 '준비 중' 을 계속 띄우면 고객은 영원히 기다린다.
        #   (설치 직후 백엔드가 임포트 오류로 즉시 죽는 사고가 실제로 이렇게 보였다)
        #   자식 프로세스가 끝났으면 그 자리에서 원인을 보여준다.
        for name, proc, log_name in (("백엔드", backend_proc, "backend.log"),
                                     ("화면", frontend_proc, "frontend.log")):
            if proc.poll() is not None:
                fail(f"{name} 서버가 종료됐습니다 (코드 {proc.returncode})",
                     _last_error_line(LOG_DIR / log_name))
                return

        elapsed = int(time.time() - started)
        if elapsed > 300:
            # 프로세스는 살아 있는데 포트가 안 열린다 — 백신·보안 프로그램 차단이 대표적.
            fail("서버가 5분째 응답하지 않습니다",
                 f"백엔드 {'✓' if be else '✗'} · 화면 {'✓' if fe else '✗'} — 백신이 막고 있을 수 있습니다.")
            return

        state.config(
            text=f"서버 준비 중... {elapsed}초  (백엔드 {'✓' if be else '…'} · 화면 {'✓' if fe else '…'})",
            fg="#e67e22")
        root.after(1000, poll_ready)

    if problems:
        # 사전 점검에서 이미 걸린 게 있으면 기다릴 필요가 없다 — 바로 원인을 보여준다.
        fail("설치 상태에 문제가 있습니다", problems[0].splitlines()[0])
    else:
        root.after(1500, poll_ready)
    root.mainloop()


def main():
    # 1) 인증 — 크롤링 프로그램과 같은 기기 승인 방식.
    #    인증코드 없이 이 PC 의 기기번호로 승인 여부를 확인하고,
    #    미등록이면 관리자에게 승인을 요청하는 창이 뜬다.
    from cafe_auth_gate import run_device_auth_gate
    if not run_device_auth_gate(product=PRODUCT, app_title=APP_NAME):
        return

    # 1-2) 업데이트 확인 — 반드시 서버를 띄우기 '전' 에 한다.
    #      기동 후에는 파이썬/노드가 파일을 잡고 있어 교체가 실패한다.
    _check_update()

    # 1-3) 동봉 런타임 보정 — 1.1.5 이하 설치본에는 C++ 런타임(msvcp140.dll)이 빠져 있어
    #      백엔드가 greenlet 로드 실패('DLL load failed while importing _greenlet')로
    #      아예 뜨지 않는다. 업데이트에 함께 실려 온 DLL 을 동봉 Python 옆에 옮겨 놓는다.
    #      정상 설치본에서는 아무 일도 하지 않는다. 반드시 백엔드 기동 '전' 이어야 한다.
    from licensing.native_fix import ensure_msvc_runtime
    _fix_msg = ensure_msvc_runtime(APP_DIR)
    if _fix_msg:
        print(_fix_msg)

    # 2) 사전 점검 (포트 정리도 여기서 같이 한다)
    problems = preflight()

    # 3) 서버 기동 — 점검에 걸린 게 있어도 일단 띄워 본다.
    #    점검이 틀렸을 수도 있고, 뜨기만 하면 고객은 쓸 수 있기 때문이다.
    procs = [start_backend(), start_frontend()]

    # 4) 준비되면 브라우저 열기 (백그라운드 대기)
    def open_when_ready():
        # ⚠ 프론트(3010)는 백엔드(8010)보다 20초쯤 먼저 뜬다. 프론트만 보고 창을 열면
        #   그 20초 동안 /api 프록시가 ECONNREFUSED 로 죽어 화면의 모든 동작이
        #   'HTTP 500' 으로 실패한다. 원인을 알 수 없는 오류라 고객은 고장으로 받아들인다.
        #   반드시 백엔드까지 뜬 뒤에 연다.
        if wait_for_port(FRONTEND_PORT, timeout=120) and wait_for_port(BACKEND_PORT, timeout=180):
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{FRONTEND_PORT}")
    threading.Thread(target=open_when_ready, daemon=True).start()

    # 5) 제어창 (닫으면 서버 종료)
    show_control_window(procs, problems)


if __name__ == "__main__":
    main()
