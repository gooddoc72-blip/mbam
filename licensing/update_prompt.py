# -*- coding: utf-8 -*-
"""새 버전 확인 → 물어보고 → 바뀐 부분만 받아 교체 (카페·블로그 전용판·마케팅연구소 공용).

설치본 2.4GB 중 실제로 바뀌는 건 파이썬 소스와 프론트 빌드뿐(약 15MB)이라
전체를 다시 받게 하지 않는다. 동봉 Python·Chromium·Node·node_modules 는
코드를 고쳐도 한 바이트도 안 바뀐다.

⚠ 여기서 무슨 일이 나든 프로그램은 떠야 한다. 인터넷이 안 되거나 서버가 조용하면
  조용히 넘어간다 — 업데이트 때문에 프로그램이 안 켜지는 일은 없어야 한다.

런처들이 각자 복사본을 갖고 있으면 한쪽만 고쳐져 어긋나므로 여기 한 곳에 둔다.
"""
import json
from pathlib import Path

from .ui_font import ko


def read_license_server(app_dir: Path) -> str:
    """license_config.json 의 서버 주소.

    ⚠ utf-8-sig 로 읽는다. 이 파일은 PowerShell 빌드가 만드는데
      Set-Content -Encoding UTF8 이 BOM 을 붙인다. utf-8 로 읽으면 예외가 나고
      서버 주소가 빈 값이 돼 업데이트 확인이 조용히 생략된다(실제로 그랬다).
    """
    try:
        with open(Path(app_dir) / "license_config.json", "r", encoding="utf-8-sig") as f:
            return (json.load(f).get("server") or "").strip()
    except Exception:
        return ""


def run_update_check(app_dir: Path, product: str, app_name: str, server: str = None) -> None:
    """새 버전이 있으면 물어보고 적용한다. 조용히 실패해도 호출자는 그냥 진행하면 된다."""
    import sys

    app_dir = Path(app_dir)
    server = (server or read_license_server(app_dir)).strip()
    if not server:
        return
    try:
        sys.path.insert(0, str(app_dir))
        from licensing import updater
    except Exception as e:
        print(f"[Update] 업데이트 모듈을 불러오지 못했습니다(무시): {e}")
        return

    try:
        man = updater.check(app_dir, server, product=product)
    except Exception as e:
        print(f"[Update] 확인 중 오류(무시): {e}")
        return
    if not man:
        return

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    notes = (man.get("notes") or "").strip()
    cur = updater.local_version(app_dir)
    msg = f"새 버전 {man['version']} 이 있습니다.\n(현재 {cur})\n\n"
    if notes:
        msg += f"{notes}\n\n"
    size_mb = int(man.get("size") or 0) // 1024 // 1024
    msg += f"지금 업데이트할까요? (약 {size_mb or 15}MB, 1분 이내)"
    if not messagebox.askyesno(f"{app_name} 업데이트", msg):
        root.destroy()
        print("[Update] 사용자가 나중에 하기로 했습니다.")
        return

    # 진행 창 — 다운로드가 몇십 초 걸릴 수 있어 멈춘 것처럼 보이면 안 된다.
    prog = tk.Toplevel()
    prog.title("업데이트 중")
    prog.resizable(False, False)
    prog.geometry("360x110")
    tk.Label(prog, text="업데이트를 내려받는 중입니다...", font=ko(10)).pack(pady=(18, 6))
    lbl = tk.Label(prog, text="0%", font=ko(10, "bold"), fg="#16a34a")
    lbl.pack()
    prog.update()

    def on_progress(done, total):
        pct = int(done * 100 / total) if total else 0
        try:
            lbl.config(text=f"{pct}%  ({done // 1024 // 1024}MB / {total // 1024 // 1024}MB)")
            prog.update()
        except Exception:
            pass

    ok, message = updater.apply(app_dir, man, progress=on_progress)
    try:
        prog.destroy()
    except Exception:
        pass
    messagebox.showinfo(f"{app_name} 업데이트", message)
    root.destroy()
