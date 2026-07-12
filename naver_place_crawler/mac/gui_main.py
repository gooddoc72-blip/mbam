import customtkinter as ctk
import threading
import time

# 기본 테마 설정
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CrawlerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Crawler Pro (USB 테더링 다목적 크롤러)")
        self.geometry("800x600")

        # 좌측 메뉴 프레임
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # 이어하기 데이터 저장소
        self.resume_checkpoint = None

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Crawler Pro", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20)

        # 타겟 선택 라디오 버튼
        self.target_var = ctk.StringVar(value="place")
        self.radio_place = ctk.CTkRadioButton(self.sidebar_frame, text="네이버 플레이스", variable=self.target_var, value="place")
        self.radio_place.pack(pady=10, padx=20, anchor="w")
        

        self.radio_coupang = ctk.CTkRadioButton(self.sidebar_frame, text="쿠팡 판매자", variable=self.target_var, value="coupang")
        self.radio_coupang.pack(pady=10, padx=20, anchor="w")

        # IP 변경 옵션
        self.ip_change_var = ctk.BooleanVar(value=True)
        self.check_ip = ctk.CTkCheckBox(self.sidebar_frame, text="자동 IP 변경 (USB)", variable=self.ip_change_var)
        self.check_ip.pack(pady=30, padx=20, anchor="w")

        self.btn_test_ip = ctk.CTkButton(self.sidebar_frame, text="IP 변경 테스트", command=self.test_ip_change)
        self.btn_test_ip.pack(pady=10, padx=20)

        # 우측 메인 콘텐츠 프레임
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # 인증 정보 표시 프레임
        self.auth_frame = ctk.CTkFrame(self.main_frame, fg_color="#333333")
        self.auth_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.lbl_hwid = ctk.CTkLabel(self.auth_frame, text="기기 번호(HWID): 불러오는 중...", text_color="yellow")
        self.lbl_hwid.pack(side="left", padx=10, pady=5)
        
        self.btn_copy_hwid = ctk.CTkButton(self.auth_frame, text="복사", width=40, height=24, command=self.copy_hwid)
        self.btn_copy_hwid.pack(side="left", padx=5, pady=5)
        
        self.lbl_auth_status = ctk.CTkLabel(self.auth_frame, text="인증 상태: 확인 중...", font=ctk.CTkFont(weight="bold"))
        self.lbl_auth_status.pack(side="right", padx=10, pady=5)

        # 키워드 입력
        self.lbl_keyword = ctk.CTkLabel(self.main_frame, text="검색 키워드 (쉼표로 구분):")
        self.lbl_keyword.pack(pady=(10, 0), anchor="w", padx=10)
        
        self.entry_keyword = ctk.CTkEntry(self.main_frame, placeholder_text="예: 강남역 맛집, 홍대 카페", width=400)
        self.entry_keyword.pack(pady=5, padx=10, anchor="w")

        # 버튼 컨테이너
        self.btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.btn_frame.pack(pady=10, padx=10, anchor="w")

        self.btn_start = ctk.CTkButton(self.btn_frame, text="크롤링 시작", command=self.start_crawling, state="disabled")
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = ctk.CTkButton(self.btn_frame, text="중지", fg_color="red", hover_color="darkred", command=self.stop_crawling)
        self.btn_stop.pack(side="left", padx=(0, 10))

        self.btn_open_folder = ctk.CTkButton(self.btn_frame, text="결과 폴더 열기", fg_color="gray", command=self.open_folder)
        self.btn_open_folder.pack(side="left")

        self.btn_clear_history = ctk.CTkButton(self.btn_frame, text="수집 이력 초기화", fg_color="#F4A460", hover_color="#D2691E", command=self.clear_history)
        self.btn_clear_history.pack(side="left", padx=(10, 0))

        # 로그 텍스트 박스
        self.lbl_log = ctk.CTkLabel(self.main_frame, text="실행 로그:")
        self.lbl_log.pack(pady=(10, 0), anchor="w", padx=10)

        self.textbox_log = ctk.CTkTextbox(self.main_frame, width=550, height=350)
        self.textbox_log.pack(pady=5, padx=10, fill="both", expand=True)
        self.textbox_log.insert("0.0", "프로그램이 준비되었습니다. 라이선스를 확인합니다...\n")

        self.is_running = False
        self.is_authorized = False
        
        # 비동기로 라이선스 인증 수행
        threading.Thread(target=self.verify_license, daemon=True).start()

    def verify_license(self):
        import auth
        
        # HWID 추출 후 UI 업데이트 (안전하게 메인 스레드로 전달)
        hwid = auth.get_hwid()
        self.after(0, lambda: self.lbl_hwid.configure(text=f"기기 번호(HWID): {hwid}"))
        
        success, status, _ = auth.verify_pc_online()
        
        # 결과에 따른 UI 업데이트 (안전하게 메인 스레드로 전달)
        def update_ui():
            if success:
                self.lbl_auth_status.configure(text="인증 완료 ✅", text_color="green")
                self.btn_start.configure(state="normal")
                self.is_authorized = True
                self.log("라이선스 인증이 완료되었습니다. 크롤링을 시작할 수 있습니다.")
                self.after(100, self.check_and_load_checkpoint)
            else:
                if status == "SERVER_URL_MISSING" or status == "서버 연결 오류" or "연결할 수 없습니다" in status:
                    self.lbl_auth_status.configure(text="서버 연결 오류 ⚠️", text_color="red")
                    self.log("서버에 연결할 수 없거나 주소가 등록되지 않았습니다.")
                    self.after(100, self.prompt_server_url)
                elif status == "unregistered":
                    self.lbl_auth_status.configure(text="미등록 기기 ⚠️", text_color="orange")
                    self.log("등록되지 않은 기기입니다. 팝업 창에 이름을 입력해주세요.")
                    self.after(100, self.prompt_registration, hwid)
                elif status == "pending":
                    self.lbl_auth_status.configure(text="승인 대기 중 ⏳", text_color="orange")
                    self.log("관리자의 승인을 대기 중입니다. 관리자 승인 후 프로그램을 다시 실행해주세요.")
                elif status == "revoked":
                    self.lbl_auth_status.configure(text="차단된 기기 🚫", text_color="red")
                    self.log("사용이 차단된 기기입니다. 관리자에게 문의하세요.")
                else:
                    self.lbl_auth_status.configure(text="미인증 기기 ❌", text_color="red")
                    self.log(f"라이선스 서버 연결 실패: {status}")
        
        self.after(0, update_ui)

    def prompt_server_url(self):
        import tkinter.simpledialog as simpledialog
        import auth
        url = simpledialog.askstring("서버 주소 입력", "관리자에게 발급받은 임시 서버 주소(URL)를 입력하세요:\n(예: https://xxxx.serveo.net)", parent=self)
        if url and url.strip():
            url = url.strip()
            if not url.startswith("http"):
                url = "https://" + url
            if url.endswith("/"):
                url = url[:-1]
            if not url.endswith("/verify"):
                url = url + "/verify"
                
            auth.set_server_url(url)
            self.log(f"서버 주소가 설정되었습니다: {url}\n다시 연결을 시도합니다...")
            self.after(500, self.verify_license)
        else:
            self.log("서버 주소 입력이 취소되었습니다. 앱을 재시작하면 다시 입력할 수 있습니다.")

    def prompt_registration(self, hwid):
        import tkinter.simpledialog as simpledialog
        import auth
        import threading
        import requests
        
        # UI 스레드에서 팝업 실행
        username = simpledialog.askstring("기기 등록", "처음 접속하는 기기입니다.\n관리자에게 식별될 '이름' 또는 '상호명'을 입력해주세요:", parent=self)
        if username and username.strip():
            def do_register():
                try:
                    # /verify 주소를 /register로 치환하여 전송
                    reg_url = auth.AUTH_SERVER_URL.replace("/verify", "/register")
                    res = requests.post(reg_url, json={"hwid": hwid, "username": username.strip()})
                    if res.status_code == 200:
                        self.after(0, lambda: self.lbl_auth_status.configure(text="승인 대기 중 ⏳", text_color="orange"))
                        self.log("등록이 완료되었습니다! 관리자 승인 후 프로그램을 다시 실행해 주세요.")
                    else:
                        self.log("등록 요청 중 서버 오류가 발생했습니다.")
                except Exception as e:
                    self.log(f"서버 접속 오류: {e}")
            threading.Thread(target=do_register, daemon=True).start()
        else:
            self.log("등록을 취소했습니다. 사용하려면 프로그램 재시작 후 이름을 다시 입력해주세요.")

    def check_and_load_checkpoint(self):
        from checkpoint_manager import CheckpointManager
        checkpoint = CheckpointManager.load_checkpoint()
        if checkpoint:
            from tkinter import messagebox
            target = checkpoint.get("target", "place")
            keywords = checkpoint.get("keywords", [])
            current_index = checkpoint.get("current_index", 0)
            
            if current_index < len(keywords):
                remaining_keywords = keywords[current_index:]
                ans = messagebox.askyesno(
                    "작업 이어받기",
                    f"이전에 중단된 크롤링 작업이 있습니다.\n"
                    f"대상: {target}\n"
                    f"남은 키워드: {', '.join(remaining_keywords)}\n\n"
                    f"이어서 진행하시겠습니까?"
                )
                if ans:
                    self.target_var.set(target)
                    self.entry_keyword.delete(0, "end")
                    self.entry_keyword.insert(0, ", ".join(remaining_keywords))
                    self.resume_checkpoint = checkpoint
                    self.log(f"이전 중단된 작업({target})의 남은 키워드와 데이터를 성공적으로 불러왔습니다. [시작]을 누르면 이어서 수집합니다.")
                else:
                    self.resume_checkpoint = None
                    CheckpointManager.clear_checkpoint()

    def log(self, message):
        """텍스트 박스에 로그 추가 (스레드 안전)"""
        def _insert():
            self.textbox_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.textbox_log.see("end")
        self.after(0, _insert)

    def open_folder(self):
        """결과물이 저장된 폴더 열기"""
        import os
        import platform
        import subprocess
        
        folder_path = os.getcwd()
        if platform.system() == "Windows":
            os.startfile(folder_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
        self.log(f"결과 폴더를 열었습니다: {folder_path}")

    def copy_hwid(self):
        """HWID를 클립보드에 복사"""
        import auth
        hwid = auth.get_hwid()
        self.clipboard_clear()
        self.clipboard_append(hwid)
        self.log("기기 번호가 클립보드에 복사되었습니다.")

    def clear_history(self):
        import os
        if os.path.exists("history.json"):
            try:
                os.remove("history.json")
                self.log("수집 이력(history.json)이 성공적으로 삭제되었습니다. 이제 처음부터 다시 수집합니다.")
            except Exception as e:
                self.log(f"이력 삭제 실패: {e}")
        else:
            self.log("삭제할 수집 이력이 존재하지 않습니다.")

    def test_ip_change(self):
        self.log("IP 변경(비행기 모드 전환)을 테스트합니다...")
        import ip_changer
        self.btn_test_ip.configure(state="disabled")
        def run_test():
            try:
                ip_changer.toggle_airplane_mode()
                self.after(100, lambda: self.log("IP 변경 완료."))
            except Exception as e:
                err_msg = f"IP 변경 실패: {e}"
                self.after(100, lambda msg=err_msg: self.log(msg))
            finally:
                self.after(100, lambda: self.btn_test_ip.configure(state="normal"))
                
        threading.Thread(target=run_test, daemon=True).start()

    def start_crawling(self):
        if self.is_running:
            return
            
        keyword = self.entry_keyword.get().strip()
        if not keyword:
            self.log("키워드를 입력해주세요.")
            return

        self.is_running = True
        self.btn_start.configure(state="disabled")
        target = self.target_var.get()
        use_ip_change = self.ip_change_var.get()
        
        self.log(f"크롤링 시작: 대상={target}, 키워드={keyword}, IP변경={use_ip_change}")
        
        # 크롤링 로직은 별도 스레드에서 실행
        threading.Thread(target=self._crawling_thread, args=(keyword, target, use_ip_change), daemon=True).start()

    def _crawling_thread(self, keyword, target, use_ip_change):
        try:
            import crawler
            
            keywords_list = [k.strip() for k in keyword.split(",")]
            
            # 이어하기 검증
            passed_checkpoint = None
            if hasattr(self, 'resume_checkpoint') and self.resume_checkpoint and self.resume_checkpoint.get("target") == target:
                # 사용자가 키워드를 인위적으로 바꾸지 않았는지 검사
                loaded_keywords = ", ".join(self.resume_checkpoint.get("keywords", [])[self.resume_checkpoint.get("current_index", 0):])
                if keyword == loaded_keywords:
                    passed_checkpoint = self.resume_checkpoint
                    self.log("✅ 정밀 이어하기 시스템이 가동되었습니다. 중단된 시점부터 이어서 시작합니다.")
                else:
                    self.log("⚠️ 이어하기 데이터를 불러왔으나 키워드가 변경되어 처음부터 새로 수집합니다.")
            
            self.crawler_engine = crawler.CrawlerEngine(log_callback=self.log)
            
            if target == "place":
                self.crawler_engine.crawl_naver_place(keywords_list, use_ip_change=use_ip_change, resume_checkpoint=passed_checkpoint)
            elif target == "shopping":
                self.crawler_engine.crawl_naver_shopping(keywords_list, use_ip_change=use_ip_change)
            elif target == "coupang":
                self.crawler_engine.crawl_coupang(keywords_list, use_ip_change=use_ip_change, resume_checkpoint=passed_checkpoint)
                
            self.log("크롤링 작업이 종료되었습니다.")
        except Exception as e:
            self.log(f"오류 발생: {e}")
        finally:
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.after(1000, self.check_and_load_checkpoint)

    def stop_crawling(self):
        self.log("중지 요청됨... (진행 중인 동작 완료 후 종료됩니다)")
        self.is_running = False
        if hasattr(self, 'crawler_engine'):
            self.crawler_engine.stop()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    app = CrawlerApp()
    app.mainloop()
