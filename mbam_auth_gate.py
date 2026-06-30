# -*- coding: utf-8 -*-
"""
실행 시 뜨는 인증창 (tkinter, 표준 라이브러리).

동작:
  - 저장된 코드가 있으면 자동 검증 → 통과 시 창 없이 True 반환
  - 미인증/거부 시 인증코드 입력창 표시
  - 인증 성공 시 True, 사용자가 닫으면 False 반환

다른 모듈에서:
    from mbam_auth_gate import run_auth_gate
    if not run_auth_gate():
        sys.exit(0)
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from licensing.client import LicenseClient


def run_auth_gate() -> bool:
    client = LicenseClient()

    # 1) 저장된 코드로 조용히 자동 검증
    pre = client.verify()
    if pre.ok:
        return True
    # 명시적 거부(차단/이전 등)인데 재인증 불가한 상태면 안내 후 종료
    if not pre.need_activation:
        _alert("인증 오류", pre.message)
        return False

    # 2) 인증창 표시
    result = {"ok": False}

    root = tk.Tk()
    root.title("MBAM 프로그램 인증")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    W, H = 460, 340
    root.geometry(f"{W}x{H}")
    # 화면 중앙
    root.update_idletasks()
    x = (root.winfo_screenwidth() - W) // 2
    y = (root.winfo_screenheight() - H) // 3
    root.geometry(f"{W}x{H}+{x}+{y}")

    pad = {"padx": 24}

    tk.Label(root, text="MBAM 마케팅 프로그램", font=("맑은 고딕", 15, "bold")).pack(pady=(22, 2))
    tk.Label(root, text="이 PC 에서 처음 실행합니다. 인증코드를 입력하세요.",
             font=("맑은 고딕", 9), fg="#555").pack(pady=(0, 4))

    info = tk.Label(root, text=f"이 PC 식별번호(HWID): {client.hwid}",
                    font=("Consolas", 8), fg="#888")
    info.pack(pady=(0, 12))

    tk.Label(root, text="인증코드", font=("맑은 고딕", 9, "bold"), anchor="w").pack(fill="x", **pad)
    entry = tk.Entry(root, font=("Consolas", 13), justify="center")
    entry.pack(fill="x", ipady=6, **pad)
    entry.insert(0, client.saved_code)
    entry.focus_set()

    status = tk.Label(root, text="", font=("맑은 고딕", 9), fg="#c0392b")
    status.pack(pady=(8, 0))

    btn = ttk.Button(root, text="인증하기")
    btn.pack(pady=14, ipadx=10, ipady=2)

    def do_activate(*_):
        code = entry.get()
        btn.config(state="disabled")
        status.config(text="인증 확인 중...", fg="#2980b9")
        root.update_idletasks()

        def work():
            res = client.activate(code)

            def done():
                if res.ok:
                    result["ok"] = True
                    root.destroy()
                else:
                    status.config(text=res.message, fg="#c0392b")
                    btn.config(state="normal")
            root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    btn.config(command=do_activate)
    entry.bind("<Return>", do_activate)

    tk.Label(root, text="※ 인증코드는 PC 1대에만 사용할 수 있습니다. 문의: 관리자",
             font=("맑은 고딕", 8), fg="#aaa").pack(side="bottom", pady=10)

    root.mainloop()
    return result["ok"]


def _alert(title, msg):
    r = tk.Tk()
    r.withdraw()
    messagebox.showerror(title, msg)
    r.destroy()


if __name__ == "__main__":
    print("인증 결과:", run_auth_gate())
