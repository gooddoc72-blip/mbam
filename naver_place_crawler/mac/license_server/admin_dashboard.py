import tkinter as tk
from tkinter import messagebox
import requests

BASE_URL = "http://127.0.0.1:8005"

def load_data():
    try:
        res = requests.get(f"{BASE_URL}/admin/list")
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return {}

def update_status(hwid, status):
    try:
        res = requests.post(f"{BASE_URL}/admin/update_status", json={"hwid": hwid, "status": status})
        if res.status_code == 200:
            messagebox.showinfo("성공", f"상태가 '{status}'(으)로 변경되었습니다!")
            refresh_list()
        else:
            messagebox.showerror("오류", "상태 변경 실패")
    except Exception as e:
        messagebox.showerror("서버 접속 오류", "서버가 켜져있는지 확인하세요.\n" + str(e))

def refresh_list():
    for row in tree_frame.winfo_children():
        row.destroy()
        
    data = load_data()
    if not data:
        tk.Label(tree_frame, text="아직 등록을 요청한 기기가 없습니다.", fg="gray").pack(pady=20)
        return

    for hwid, info in data.items():
        row = tk.Frame(tree_frame, pady=5, bd=1, relief="solid")
        row.pack(fill="x", pady=2)
        
        status = info.get('status', 'unknown')
        status_color = "orange" if status == "pending" else "green" if status == "approved" else "red"
        status_text = "승인 대기" if status == "pending" else "승인됨" if status == "approved" else "차단됨"
        
        tk.Label(row, text=info.get('username', '이름 없음'), width=12, anchor="w", font=("Arial", 12, "bold")).pack(side="left", padx=10)
        tk.Label(row, text=status_text, fg=status_color, width=10, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        tk.Label(row, text=hwid[:10] + "...", width=15, anchor="w").pack(side="left")
        
        tk.Button(row, text="✅ 승인", fg="green", command=lambda h=hwid: update_status(h, "approved")).pack(side="right", padx=5)
        tk.Button(row, text="🚫 차단", fg="red", command=lambda h=hwid: update_status(h, "revoked")).pack(side="right", padx=5)

root = tk.Tk()
root.title("라이선스 관리자 대시보드")
root.geometry("600x400")

tk.Label(root, text="서버 접속 기기 목록 (Admin)", font=("Arial", 18, "bold")).pack(pady=15)

tk.Button(root, text="🔄 새로고침", width=15, command=refresh_list).pack(pady=5)

# 리스트 컨테이너
tree_frame = tk.Frame(root)
tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

refresh_list()
root.mainloop()
