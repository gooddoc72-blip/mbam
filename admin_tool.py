import requests
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

# 서버 주소 및 관리자 토큰 (서버 설정과 일치해야 함)
# 도메인으로 부른다 — 서버 IP가 바뀌어도 DNS만 고치면 되고, 관리자 토큰이 평문으로 나가지 않는다
SERVER_URL = "https://license.blocklab.co.kr"
ADMIN_TOKEN = "change-this-admin-token"

def fetch_devices():
    try:
        headers = {"x-admin-token": ADMIN_TOKEN}
        response = requests.get(f"{SERVER_URL}/admin/devices", headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            messagebox.showerror("오류", f"기기 목록을 가져올 수 없습니다. (상태코드: {response.status_code})")
            return []
    except requests.exceptions.RequestException as e:
        messagebox.showerror("서버 접속 오류", "서버에 연결할 수 없습니다. 서버 상태나 AWS 보안 그룹(포트 8005)을 확인해주세요.")
        return []

def change_status(hwid, new_status, product=""):
    try:
        headers = {"x-admin-token": ADMIN_TOKEN}
        # product 를 같이 보내야 서버가 올바른 쪽(기존 devices / 제품별 product_devices)을 고친다
        payload = {"hwid": hwid, "status": new_status, "product": product}
        response = requests.post(f"{SERVER_URL}/admin/device/status", json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            messagebox.showinfo("성공", f"기기 상태가 '{new_status}'(으)로 변경되었습니다.")
            refresh_list()
        else:
            messagebox.showerror("오류", "상태 변경에 실패했습니다.")
    except Exception as e:
        messagebox.showerror("오류", str(e))

# 제품 코드 → 화면에 보여줄 이름. 빈 값은 기존(크롤러) 기기.
PRODUCT_NAMES = {
    "": "크롤러",
    "cafe": "카페 마케팅",
    "blog": "블로그 마케팅",
    "mbam": "마케팅 연구소",
}


def refresh_list():
    for row in tree.get_children():
        tree.delete(row)

    devices = fetch_devices()
    for d in devices:
        created_at = d.get("created_at", "")
        if created_at:
            created_at = created_at[:19].replace("T", " ")

        status = d.get("status", "")
        status_kr = "승인 대기" if status == "pending" else "승인 완료" if status == "approved" else "차단됨"

        product = d.get("product", "") or ""
        product_kr = PRODUCT_NAMES.get(product, product)

        tree.insert("", "end", values=(
            product_kr,
            d.get("name", "이름 없음"),
            d.get("hwid", "")[:15] + "...",
            status_kr,
            created_at,
            d.get("hwid", ""),
            product,
        ))


def _selected_device():
    """선택된 행의 (hwid, product). 선택이 없으면 (None, None)."""
    selected = tree.selection()
    if not selected:
        return None, None
    vals = tree.item(selected[0])["values"]
    return vals[5], (vals[6] if len(vals) > 6 else "")


def on_approve():
    hwid, product = _selected_device()
    if not hwid:
        messagebox.showwarning("선택", "승인할 기기를 선택해주세요.")
        return
    change_status(hwid, "approved", product)


def on_block():
    hwid, product = _selected_device()
    if not hwid:
        messagebox.showwarning("선택", "차단할 기기를 선택해주세요.")
        return
    change_status(hwid, "blocked", product)


# ──────────────────────────────────────────────────────────────────────────
# 인증코드 (마케팅 연구소 설치형) — issue_codes.py 와 같은 서버 API 를 쓴다
# ──────────────────────────────────────────────────────────────────────────

# 콤보박스 표시값 → 서버에 보낼 valid_days (0 = 무기한)
PERIODS = {"1개월 (30일)": 30, "3개월 (90일)": 90, "6개월 (180일)": 180, "1년 (365일)": 365, "무기한": 0}


def _code_api(method, path, body=None):
    """관리자 API 호출. 실패하면 오류창을 띄우고 None."""
    try:
        r = requests.request(method, f"{SERVER_URL}{path}", json=body,
                             headers={"x-admin-token": ADMIN_TOKEN}, timeout=10)
    except requests.exceptions.RequestException:
        messagebox.showerror("서버 접속 오류", "서버에 연결할 수 없습니다. 인터넷 연결과 서버 상태를 확인해주세요.")
        return None
    if r.status_code != 200:
        messagebox.showerror("오류", f"요청에 실패했습니다. (상태코드: {r.status_code})\n{r.text[:200]}")
        return None
    return r.json()


def _code_status(c):
    if not c.get("is_active"):
        return "사용 중지"
    exp = c.get("expires_at")
    if exp and datetime.fromisoformat(exp) < datetime.utcnow():
        return "기간 만료"
    return "사용 중" if c.get("hwid") else "미사용"


def _short_date(iso):
    return iso[:10] if iso else ""


def refresh_codes():
    for row in code_tree.get_children():
        code_tree.delete(row)
    codes = _code_api("GET", "/admin/list")
    if codes is None:
        return
    for c in codes:
        code_tree.insert("", "end", values=(
            c.get("code", ""),
            c.get("memo") or "",
            _code_status(c),
            c.get("machine_name") or "",
            _short_date(c.get("expires_at")) or "무기한",
            _short_date(c.get("created_at")),
        ))
    code_count.config(text=f"총 {len(codes)}개")


def _copy(text):
    root.clipboard_clear()
    root.clipboard_append(text)


def on_issue():
    memo = memo_entry.get().strip()
    if not memo:
        messagebox.showwarning("입력", "고객 이름(메모)을 입력해주세요.\n나중에 누구 코드인지 알아볼 수 있어야 합니다.")
        return
    try:
        count, pcs = int(count_spin.get()), int(pcs_spin.get())
    except ValueError:
        messagebox.showwarning("입력", "개수와 PC 대수는 숫자로 입력해주세요.")
        return
    res = _code_api("POST", "/admin/issue", {
        "count": count, "memo": memo,
        "valid_days": PERIODS[period_combo.get()], "max_activations": pcs,
    })
    if res is None:
        return
    issued = res.get("issued", [])
    _copy("\n".join(issued))
    refresh_codes()
    messagebox.showinfo("발급 완료",
                        f"{memo} 님 인증코드 {len(issued)}개를 발급했습니다.\n\n"
                        + "\n".join(issued)
                        + "\n\n클립보드에 복사했습니다. 고객에게 붙여넣어 보내세요.")


def _selected_code():
    sel = code_tree.selection()
    if not sel:
        messagebox.showwarning("선택", "목록에서 인증코드를 선택해주세요.")
        return None, None
    vals = code_tree.item(sel[0])["values"]
    return str(vals[0]), str(vals[1])


def on_copy_code():
    code, _ = _selected_code()
    if code:
        _copy(code)
        messagebox.showinfo("복사", f"{code}\n\n클립보드에 복사했습니다.")


def _code_action(path, confirm, done):
    code, memo = _selected_code()
    if not code:
        return
    if not messagebox.askyesno("확인", f"{memo}  {code}\n\n{confirm}"):
        return
    if _code_api("POST", path, {"code": code}) is not None:
        refresh_codes()
        messagebox.showinfo("완료", done)


def on_revoke():
    _code_action("/admin/revoke", "이 코드를 사용 중지할까요?\n고객 PC 에서 다음 실행부터 열리지 않습니다.",
                 "사용 중지했습니다.")


def on_unrevoke():
    _code_action("/admin/unrevoke", "이 코드를 다시 사용할 수 있게 할까요?", "다시 사용할 수 있게 했습니다.")


def on_reset():
    _code_action("/admin/reset", "PC 교체를 허용할까요?\n지금 PC 와의 연결이 풀리고, 새 PC 에서 같은 코드로 인증할 수 있습니다.",
                 "PC 교체를 허용했습니다. 고객이 새 PC 에서 같은 코드로 인증하면 됩니다.")


root = tk.Tk()
root.title("마케팅연구소 관리자 도구 (기기 승인 · 인증코드)")
root.geometry("860x520")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=6, pady=6)

# ── 탭 1: 기기 승인 (크롤러 · 카페 · 블로그) ──
device_tab = tk.Frame(notebook)
notebook.add(device_tab, text="  기기 승인 (크롤러 · 카페 · 블로그)  ")

top_frame = tk.Frame(device_tab, padx=10, pady=10)
top_frame.pack(fill="x")

btn_refresh = tk.Button(top_frame, text="목록 새로고침", command=refresh_list, bg="#3b82f6", fg="white")
btn_refresh.pack(side="left", padx=5)

btn_approve = tk.Button(top_frame, text="✅ 선택 기기 승인", command=on_approve, bg="#10b981", fg="white")
btn_approve.pack(side="right", padx=5)

btn_block = tk.Button(top_frame, text="❌ 선택 기기 차단", command=on_block, bg="#ef4444", fg="white")
btn_block.pack(side="right", padx=5)

columns = ("product", "name", "hwid_short", "status", "created_at", "hwid_full", "product_code")
tree = ttk.Treeview(device_tab, columns=columns, show="headings", selectmode="browse")
tree.heading("product", text="제품")
tree.heading("name", text="신청자 이름/소속")
tree.heading("hwid_short", text="기기 번호(요약)")
tree.heading("status", text="현재 상태")
tree.heading("created_at", text="신청 일시")

tree.column("product", width=100)
tree.column("name", width=150)
tree.column("hwid_short", width=150)
tree.column("status", width=90)
tree.column("created_at", width=140)
tree.column("hwid_full", width=0, stretch=tk.NO)      # 숨김 컬럼
tree.column("product_code", width=0, stretch=tk.NO)   # 숨김 컬럼(서버 전송용 원본 값)

tree.pack(fill="both", expand=True, padx=10, pady=10)

# ── 탭 2: 인증코드 (마케팅 연구소 설치형) ──
code_tab = tk.Frame(notebook)
notebook.add(code_tab, text="  인증코드 (마케팅 연구소 설치형)  ")

issue_box = tk.LabelFrame(code_tab, text=" 새 인증코드 발급 ", padx=10, pady=8)
issue_box.pack(fill="x", padx=10, pady=(10, 4))

tk.Label(issue_box, text="고객 이름/메모").grid(row=0, column=0, sticky="w")
memo_entry = tk.Entry(issue_box, width=22)
memo_entry.grid(row=1, column=0, padx=(0, 10))

tk.Label(issue_box, text="사용 기간").grid(row=0, column=1, sticky="w")
period_combo = ttk.Combobox(issue_box, values=list(PERIODS), state="readonly", width=13)
period_combo.set("1년 (365일)")
period_combo.grid(row=1, column=1, padx=(0, 10))

tk.Label(issue_box, text="PC 대수").grid(row=0, column=2, sticky="w")
pcs_spin = tk.Spinbox(issue_box, from_=1, to=20, width=5)
pcs_spin.grid(row=1, column=2, padx=(0, 10))

tk.Label(issue_box, text="발급 개수").grid(row=0, column=3, sticky="w")
count_spin = tk.Spinbox(issue_box, from_=1, to=50, width=5)
count_spin.grid(row=1, column=3, padx=(0, 10))

tk.Button(issue_box, text="🔑 발급", command=on_issue, bg="#2563eb", fg="white", width=10).grid(row=1, column=4)

code_bar = tk.Frame(code_tab, padx=10, pady=4)
code_bar.pack(fill="x")
tk.Button(code_bar, text="목록 새로고침", command=refresh_codes, bg="#3b82f6", fg="white").pack(side="left", padx=5)
code_count = tk.Label(code_bar, text="", fg="#555")
code_count.pack(side="left", padx=5)
tk.Button(code_bar, text="PC 교체 허용", command=on_reset).pack(side="right", padx=3)
tk.Button(code_bar, text="다시 사용", command=on_unrevoke).pack(side="right", padx=3)
tk.Button(code_bar, text="❌ 사용 중지", command=on_revoke, bg="#ef4444", fg="white").pack(side="right", padx=3)
tk.Button(code_bar, text="📋 코드 복사", command=on_copy_code).pack(side="right", padx=3)

code_columns = ("code", "memo", "status", "machine", "expires", "created")
code_tree = ttk.Treeview(code_tab, columns=code_columns, show="headings", selectmode="browse")
for col, title, width in (("code", "인증코드", 170), ("memo", "고객 이름/메모", 150), ("status", "상태", 80),
                          ("machine", "사용 중인 PC", 140), ("expires", "만료일", 90), ("created", "발급일", 90)):
    code_tree.heading(col, text=title)
    code_tree.column(col, width=width)
code_tree.pack(fill="both", expand=True, padx=10, pady=(4, 10))

# 시작 시 자동 새로고침
refresh_list()
refresh_codes()

root.mainloop()
