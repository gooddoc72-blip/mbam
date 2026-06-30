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


def main():
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
