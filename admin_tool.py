import requests
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

# 서버 주소 및 관리자 토큰 (서버 설정과 일치해야 함)
SERVER_URL = "http://18.209.162.250:8005"
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

def change_status(hwid, new_status):
    try:
        headers = {"x-admin-token": ADMIN_TOKEN}
        payload = {"hwid": hwid, "status": new_status}
        response = requests.post(f"{SERVER_URL}/admin/device/status", json=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            messagebox.showinfo("성공", f"기기 상태가 '{new_status}'(으)로 변경되었습니다.")
            refresh_list()
        else:
            messagebox.showerror("오류", "상태 변경에 실패했습니다.")
    except Exception as e:
        messagebox.showerror("오류", str(e))

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
        
        tree.insert("", "end", values=(d.get("name", "이름 없음"), d.get("hwid", "")[:15]+"...", status_kr, created_at, d.get("hwid", "")))

def on_approve():
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("선택", "승인할 기기를 선택해주세요.")
        return
    hwid = tree.item(selected[0])["values"][4]
    change_status(hwid, "approved")

def on_block():
    selected = tree.selection()
    if not selected:
        messagebox.showwarning("선택", "차단할 기기를 선택해주세요.")
        return
    hwid = tree.item(selected[0])["values"][4]
    change_status(hwid, "blocked")

root = tk.Tk()
root.title("크롤러 기기 승인 관리자")
root.geometry("600x400")

top_frame = tk.Frame(root, padx=10, pady=10)
top_frame.pack(fill="x")

btn_refresh = tk.Button(top_frame, text="목록 새로고침", command=refresh_list, bg="#3b82f6", fg="white")
btn_refresh.pack(side="left", padx=5)

btn_approve = tk.Button(top_frame, text="✅ 선택 기기 승인", command=on_approve, bg="#10b981", fg="white")
btn_approve.pack(side="right", padx=5)

btn_block = tk.Button(top_frame, text="❌ 선택 기기 차단", command=on_block, bg="#ef4444", fg="white")
btn_block.pack(side="right", padx=5)

columns = ("name", "hwid_short", "status", "created_at", "hwid_full")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("name", text="신청자 이름/소속")
tree.heading("hwid_short", text="기기 번호(요약)")
tree.heading("status", text="현재 상태")
tree.heading("created_at", text="신청 일시")

tree.column("name", width=150)
tree.column("hwid_short", width=150)
tree.column("status", width=100)
tree.column("created_at", width=150)
tree.column("hwid_full", width=0, stretch=tk.NO) # 숨김 컬럼

tree.pack(fill="both", expand=True, padx=10, pady=10)

# 시작 시 자동 새로고침
refresh_list()

root.mainloop()
