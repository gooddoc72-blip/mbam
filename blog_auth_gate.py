# -*- coding: utf-8 -*-
"""
블로그 전용판 인증창 (tkinter, 표준 라이브러리).

크롤링 프로그램과 같은 '기기 승인' 방식이다 — 인증코드를 입력하지 않는다.

  1) 실행하면 이 PC 의 기기번호(HWID)로 승인 여부를 조용히 확인한다.
     승인된 PC 면 창 없이 바로 True 를 돌려주고 프로그램이 뜬다.
  2) 미등록이면 창이 떠서 기기번호를 보여주고, 이름/소속을 받아 [승인 요청] 한다.
  3) 관리자가 승인도구에서 승인하면 [다시 확인] 또는 재실행으로 통과된다.

다른 모듈에서:
    from blog_auth_gate import run_device_auth_gate
    if not run_device_auth_gate(product="blog", app_title="블로그 마케팅"):
        sys.exit(0)
"""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from licensing.device_auth import DeviceAuthClient


def run_device_auth_gate(product: str = "blog", app_title: str = "블로그 마케팅") -> bool:
    client = DeviceAuthClient(product=product)

    # 1) 조용히 자동 확인 — 승인된 PC 면 창 없이 통과
    pre = client.verify()
    if pre.ok:
        return True

    # 2) 인증창 표시
    result = {"ok": False}

    root = tk.Tk()
    root.title(f"{app_title} 인증")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    W, H = 500, 420
    root.update_idletasks()
    x = (root.winfo_screenwidth() - W) // 2
    y = (root.winfo_screenheight() - H) // 3
    root.geometry(f"{W}x{H}+{x}+{y}")

    pad = {"padx": 26}

    expired = pre.status == "expired"
    tk.Label(root, text=app_title, font=("맑은 고딕", 15, "bold"), fg="#2563eb").pack(pady=(20, 2))
    tk.Label(root, text=("사용 기간이 끝났습니다. 연장 후 다시 사용할 수 있습니다." if expired
                         else "이 PC 를 사용하려면 관리자 승인이 필요합니다."),
             font=("맑은 고딕", 9), fg="#555").pack(pady=(0, 12))

    # ── 기기번호 (복사 가능하도록 Entry 로) ──
    tk.Label(root, text="이 PC 의 기기번호", font=("맑은 고딕", 9, "bold"),
             anchor="w").pack(fill="x", **pad)
    hwid_row = tk.Frame(root)
    hwid_row.pack(fill="x", **pad)
    hwid_entry = tk.Entry(hwid_row, font=("Consolas", 11), justify="center", readonlybackground="#f1f5f9")
    hwid_entry.insert(0, client.hwid)
    hwid_entry.config(state="readonly")
    hwid_entry.pack(side="left", fill="x", expand=True, ipady=4)

    def copy_hwid():
        root.clipboard_clear()
        root.clipboard_append(client.hwid)
        status.config(text="기기번호가 복사되었습니다. 관리자에게 전달하세요.", fg="#2980b9")

    tk.Button(hwid_row, text="복사", width=6, command=copy_hwid).pack(side="left", padx=(6, 0))

    # ── 이름/소속 ──
    tk.Label(root, text="이름 / 소속  (관리자가 누구인지 알아볼 수 있게)",
             font=("맑은 고딕", 9, "bold"), anchor="w").pack(fill="x", pady=(14, 0), **pad)
    name_entry = tk.Entry(root, font=("맑은 고딕", 11))
    name_entry.insert(0, client.machine_name)
    name_entry.pack(fill="x", ipady=4, **pad)
    name_entry.focus_set()

    status = tk.Label(root, text=pre.message, font=("맑은 고딕", 9),
                      fg="#c0392b", justify="center", wraplength=440)
    status.pack(pady=(12, 0), **pad)

    btn_row = tk.Frame(root)
    btn_row.pack(pady=14)

    btn_request = ttk.Button(btn_row, text="연장 요청하기" if expired else "승인 요청하기")
    btn_recheck = ttk.Button(btn_row, text="다시 확인")

    def set_busy(busy: bool):
        state = "disabled" if busy else "normal"
        btn_request.config(state=state)
        btn_recheck.config(state=state)

    def do_request(*_):
        name = name_entry.get().strip()
        if not name:
            status.config(text="이름/소속을 입력해 주세요.", fg="#c0392b")
            return
        set_busy(True)
        status.config(text="승인 요청 중...", fg="#2980b9")
        root.update_idletasks()

        def work():
            ok, msg = client.request_approval(name)

            def done():
                set_busy(False)
                if ok:
                    status.config(
                        text=("연장 요청이 접수되었습니다.\n" if expired else "승인 요청이 접수되었습니다.\n")
                             + "관리자 승인 후 [다시 확인] 을 누르거나 프로그램을 다시 실행하세요.",
                        fg="#27ae60")
                else:
                    status.config(text=msg, fg="#c0392b")
            root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def do_recheck(*_):
        set_busy(True)
        status.config(text="승인 상태 확인 중...", fg="#2980b9")
        root.update_idletasks()

        def work():
            res = client.verify()

            def done():
                set_busy(False)
                if res.ok:
                    result["ok"] = True
                    root.destroy()
                else:
                    status.config(text=res.message, fg="#c0392b")
            root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    btn_request.config(command=do_request)
    btn_recheck.config(command=do_recheck)
    btn_request.pack(side="left", padx=4, ipadx=8, ipady=2)
    btn_recheck.pack(side="left", padx=4, ipadx=8, ipady=2)
    name_entry.bind("<Return>", do_request)

    # 이미 승인 대기/차단 상태면 '승인 요청' 대신 '다시 확인'이 주 동작
    if not pre.can_request:
        btn_request.config(state="disabled")

    tk.Label(root, text="※ 기기번호는 PC 1대를 식별합니다. 관리자 승인 후에만 실행됩니다.",
             font=("맑은 고딕", 8), fg="#aaa").pack(side="bottom", pady=10)

    root.mainloop()
    return result["ok"]


def _alert(title, msg):
    r = tk.Tk()
    r.withdraw()
    messagebox.showerror(title, msg)
    r.destroy()


if __name__ == "__main__":
    print("인증 결과:", run_device_auth_gate())
