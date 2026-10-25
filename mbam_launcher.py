# -*- coding: utf-8 -*-
r"""
MBAM 통합 런처
  1) 인증창(run_auth_gate) — PC 1대당 인증코드 확인
  2) 백엔드(:8000) + 프론트(:3000) 자동 기동
  3) 브라우저 자동 열기
  4) 작은 제어창(상태 표시 + 종료 버튼)

설치형(Inno Setup)에서는 동봉된 runtime\python, runtime\node 를 우선 사용하고,
없으면 시스템 PATH 의 python/node 를 사용합니다(개발 환경 호환).
"""
import os
import secrets
import socket
import subprocess
import sys
import time
import threading
import webbrowser
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "mbam-web"

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "MBAM" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
SECRETS_FILE = LOG_DIR.parent / "secrets.env"


def _ensure_secrets() -> dict:
    """JWT_SECRET / ENV_CIPHER_KEY 를 이 PC 에서 1회 만들어 두고 계속 재사용한다. (cafe_launcher 와 같은 처리)

    - JWT_SECRET     : 로그인 토큰 서명. 없으면 백엔드가 기동 자체를 거부한다.
    - ENV_CIPHER_KEY : 저장된 네이버 계정 비밀번호 암호화 키. 매번 새로 만들면 이전에 저장한 비밀번호를 못 푼다.

    개발 환경의 .env 는 고객 설치본에 넣지 않으므로(운영자 키가 들어 있음) 여기서 만든다.
    설치 폴더가 아니라 %LOCALAPPDATA%\\MBAM 에 두어 프로그램을 다시 설치해도 유지된다.
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

BACKEND_PORT = 8000
FRONTEND_PORT = 3000

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# ── 런타임 경로 해석 (설치형 동봉 우선, 없으면 시스템) ──────────────────
def _python_exe() -> str:
    for cand in (APP_DIR / "runtime" / "python" / "python.exe",
                 APP_DIR / "runtime" / "python" / "pythonw.exe"):
        if cand.exists():
            return str(cand)
    return sys.executable or "python"


def _node_exe() -> str:
    cand = APP_DIR / "runtime" / "node" / "node.exe"
    return str(cand) if cand.exists() else "node"


def _npm_cmd() -> str:
    cand = APP_DIR / "runtime" / "node" / "npm.cmd"
    return str(cand) if cand.exists() else "npm"


# ── 포트 유틸 ──────────────────────────────────────────────────────────
def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _kill_port(port: int):
    if os.name != "nt":
        return
    try:
        out = subprocess.check_output(
            f'netstat -aon | findstr :{port} | findstr LISTENING',
            shell=True, text=True, creationflags=CREATE_NO_WINDOW,
        )
        pids = {line.split()[-1] for line in out.splitlines() if line.strip()}
        for pid in pids:
            subprocess.run(f"taskkill /F /PID {pid}", shell=True,
                           creationflags=CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ── 서버 기동 ──────────────────────────────────────────────────────────
def start_backend():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(APP_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    # 보안키 주입 — 없으면 백엔드가 JWT_SECRET 없다고 기동을 거부한다.
    env.update(_ensure_secrets())
    # 설치형: 동봉된 Chromium(Playwright) 경로를 백엔드에 알려줌
    bundled_browsers = APP_DIR / "runtime" / "ms-playwright"
    if bundled_browsers.exists():
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browsers)
    log = open(LOG_DIR / "backend.log", "a", encoding="utf-8")
    return subprocess.Popen(
        [_python_exe(), str(APP_DIR / "run_backend.py")],
        cwd=str(APP_DIR), env=env,
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )


def start_agent():
    """[방법 B] 로컬 에이전트(agent.py) 기동 — 클라우드 폴링·집 IP 실행.
    설치형 동봉 Python·Chromium 경로를 그대로 사용(에이전트도 Playwright를 돌리므로)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(APP_DIR)
    env["PYTHONIOENCODING"] = "utf-8"
    bundled_browsers = APP_DIR / "runtime" / "ms-playwright"
    if bundled_browsers.exists():
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browsers)
    log = open(LOG_DIR / "agent.log", "a", encoding="utf-8")
    return subprocess.Popen(
        [_python_exe(), str(APP_DIR / "agent.py")],
        cwd=str(APP_DIR), env=env,
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )


def start_frontend():
    log = open(LOG_DIR / "frontend.log", "a", encoding="utf-8")
    built = (WEB_DIR / ".next" / "BUILD_ID").exists()
    next_bin = WEB_DIR / "node_modules" / "next" / "dist" / "bin" / "next"
    if built and next_bin.exists():
        cmd = [_node_exe(), str(next_bin), "start", "-p", str(FRONTEND_PORT)]
    else:
        # 빌드본이 없으면 개발 서버로 폴백
        cmd = [_npm_cmd(), "run", "dev"]
    return subprocess.Popen(
        cmd, cwd=str(WEB_DIR),
        stdout=log, stderr=subprocess.STDOUT, shell=(cmd[0].endswith(".cmd")),
        creationflags=CREATE_NO_WINDOW,
    )


def wait_for_port(port: int, timeout: int = 90) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if _port_open(port):
            return True
        time.sleep(0.5)
    return False


# ── 제어창 ─────────────────────────────────────────────────────────────
def show_control_window(procs):
    import tkinter as tk

    root = tk.Tk()
    root.title("MBAM 실행 중")
    root.resizable(False, False)
    W, H = 380, 200
    root.update_idletasks()
    x = (root.winfo_screenwidth() - W) // 2
    y = (root.winfo_screenheight() - H) // 3
    root.geometry(f"{W}x{H}+{x}+{y}")

    tk.Label(root, text="MBAM 마케팅 프로그램", font=("맑은 고딕", 14, "bold")).pack(pady=(20, 4))
    state = tk.Label(root, text="서버 준비 중...", font=("맑은 고딕", 10), fg="#2980b9")
    state.pack(pady=4)
    tk.Label(root, text="http://localhost:3000", font=("Consolas", 10), fg="#888").pack()

    def open_browser():
        webbrowser.open(f"http://localhost:{FRONTEND_PORT}")

    tk.Button(root, text="브라우저 다시 열기", command=open_browser).pack(pady=(12, 2))

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
             font=("맑은 고딕", 8), fg="#aaa").pack(side="bottom", pady=8)

    root.protocol("WM_DELETE_WINDOW", quit_all)

    def poll_ready():
        if _port_open(FRONTEND_PORT):
            state.config(text="실행 중 ✓", fg="#27ae60")
        else:
            root.after(1000, poll_ready)

    root.after(1500, poll_ready)
    root.mainloop()


def show_agent_window(proc):
    """[방법 B] 에이전트 모드 상태창."""
    import tkinter as tk
    root = tk.Tk()
    root.title("마케팅연구소 에이전트")
    root.resizable(False, False)
    W, H = 420, 210
    root.update_idletasks()
    x = (root.winfo_screenwidth() - W) // 2
    y = (root.winfo_screenheight() - H) // 3
    root.geometry(f"{W}x{H}+{x}+{y}")

    tk.Label(root, text="마케팅연구소 에이전트", font=("맑은 고딕", 14, "bold")).pack(pady=(20, 4))
    tk.Label(root, text="실행 중 ✓", font=("맑은 고딕", 11), fg="#27ae60").pack()
    tk.Label(root, text="웹(marketlabs.kr)에서 분석하면\n이 PC가 집 IP로 대신 처리합니다.",
             font=("맑은 고딕", 9), fg="#555", justify="center").pack(pady=8)

    def quit_all():
        try:
            proc.terminate()
        except Exception:
            pass
        root.destroy()

    tk.Button(root, text="에이전트 종료", command=quit_all, bg="#c0392b", fg="white").pack(pady=6)
    tk.Label(root, text="※ 이 창을 닫으면 에이전트가 종료됩니다.",
             font=("맑은 고딕", 8), fg="#aaa").pack(side="bottom", pady=8)
    root.protocol("WM_DELETE_WINDOW", quit_all)
    root.mainloop()


def run_agent_mode():
    """[방법 B] 웹 관제형 — 로컬 백엔드/프론트 없이 에이전트만 구동."""
    cfg = APP_DIR / "agent_config.json"
    if not cfg.exists():
        try:
            import tkinter.messagebox as mb
            mb.showwarning("설정 필요",
                           "agent_config.json 이 없습니다.\n"
                           "cloud_url / email / password 를 설정한 뒤 다시 실행하세요.\n"
                           "(agent_config.example.json 참고)")
        except Exception:
            print("[launcher] agent_config.json 이 없습니다. (agent_config.example.json 참고)")
        return
    proc = start_agent()
    show_agent_window(proc)


APP_NAME = "MBAM 마케팅 프로그램"
PRODUCT = "mbam"          # 업데이트 서버 경로: /update/mbam/latest


def _check_update():
    """새 버전이 있으면 물어보고 바뀐 부분만 교체한다. (구현은 licensing/update_prompt.py 공용)

    설치본 전체를 다시 받게 하지 않는다 — 바뀌는 건 파이썬 소스와 프론트 빌드뿐이다.
    실패해도 무시하고 그냥 실행한다.
    """
    try:
        from licensing.update_prompt import run_update_check
        run_update_check(APP_DIR, product=PRODUCT, app_name=APP_NAME)
    except Exception as e:
        print(f"[Update] 확인 생략(무시): {e}")


def main():
    # [방법 B] MBAM_MODE=agent → 웹 관제형(에이전트만)
    if os.environ.get("MBAM_MODE", "full").strip().lower() == "agent":
        run_agent_mode()
        return

    # 0) 업데이트 확인 — 서버를 띄우기 전에 해야 파일이 잠기지 않는다.
    _check_update()

    # 0-2) 동봉 런타임 보정 — 예전 설치본에는 C++ 런타임(msvcp140.dll)이 빠져 있어
    #      백엔드가 greenlet 로드 실패('DLL load failed while importing _greenlet')로
    #      아예 뜨지 않는다. 업데이트에 함께 실려 온 DLL 을 동봉 Python 옆에 옮겨 놓는다.
    #      정상 설치본에서는 아무 일도 하지 않는다. 반드시 백엔드 기동 '전' 이어야 한다.
    from licensing.native_fix import ensure_msvc_runtime
    _fix_msg = ensure_msvc_runtime(APP_DIR)
    if _fix_msg:
        print(_fix_msg)

    # 1) 인증
    from mbam_auth_gate import run_auth_gate
    if not run_auth_gate():
        return

    # 2) 기존 포트 정리
    _kill_port(BACKEND_PORT)
    _kill_port(FRONTEND_PORT)

    # 3) 서버 기동
    procs = [start_backend(), start_frontend()]

    # 4) 준비되면 브라우저 열기 (백그라운드 대기)
    def open_when_ready():
        if wait_for_port(FRONTEND_PORT, timeout=120):
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{FRONTEND_PORT}")
    threading.Thread(target=open_when_ready, daemon=True).start()

    # 5) 제어창 (닫으면 서버 종료)
    show_control_window(procs)


if __name__ == "__main__":
    main()
