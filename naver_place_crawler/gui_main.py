import customtkinter as ctk
import threading
import time

# 기본 테마 설정
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CrawlerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Crawler Pro v1.3 (USB 테더링 다목적 크롤러)")
        self.geometry("800x600")

        # 좌측 메뉴 프레임
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

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
        
        self.btn_request_auth = ctk.CTkButton(self.auth_frame, text="승인 요청", width=80, height=24, fg_color="#F4A460", hover_color="#D2691E", command=self.manual_request_auth)
        # 처음에는 숨겨둠 (미인증 시에만 표시)
        
        self.lbl_auth_status = ctk.CTkLabel(self.auth_frame, text="인증 상태: 확인 중...", font=ctk.CTkFont(weight="bold"))
        self.lbl_auth_status.pack(side="right", padx=10, pady=5)

        # 키워드 입력
        self.lbl_keyword = ctk.CTkLabel(self.main_frame, text="검색 키워드 (쉼표로 구분):")
        self.lbl_keyword.pack(pady=(10, 0), anchor="w", padx=10)
        
        self.entry_keyword = ctk.CTkEntry(self.main_frame, placeholder_text="예: 강남역 맛집, 홍대 카페", width=400)
        self.entry_keyword.pack(pady=5, padx=10, anchor="w")

        # 네이버 플레이스 수집 페이지 수 설정
        self.lbl_pages = ctk.CTkLabel(self.main_frame, text="네이버 수집할 페이지 수 (1페이지=약 50개):")
        self.lbl_pages.pack(pady=(10, 0), anchor="w", padx=10)
        
        self.entry_pages = ctk.CTkEntry(self.main_frame, width=100)
        self.entry_pages.pack(pady=5, padx=10, anchor="w")
        self.entry_pages.insert(0, "1")

        # 쿠팡 반복 회차 수 설정 (1회차 = 50건, 멈춘 지점에서 자동으로 다음 회차 진행)
        self.lbl_rounds = ctk.CTkLabel(self.main_frame, text="쿠팡 반복 회차 수 (1회차=50건, 마친 지점에서 자동 이어감):")
        self.lbl_rounds.pack(pady=(10, 0), anchor="w", padx=10)

        self.entry_rounds = ctk.CTkEntry(self.main_frame, width=100)
        self.entry_rounds.pack(pady=5, padx=10, anchor="w")
        self.entry_rounds.insert(0, "1")

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
        
        # 먼저 HWID를 UI에 표시 (너무 길면 자름)
        hwid = auth.get_hwid()
        display_hwid = hwid[:20] + "..." if len(hwid) > 20 else hwid
        self.lbl_hwid.configure(text=f"기기 번호: {display_hwid}")
        
        success, msg, _, status = auth.verify_pc_online()
        if success:
            self.lbl_auth_status.configure(text="인증 완료 ✅", text_color="green")
            self.btn_start.configure(state="normal")
            self.is_authorized = True
            self.btn_request_auth.pack_forget()
            self.log("라이선스 인증이 완료되었습니다. 크롤링을 시작할 수 있습니다.")
        else:
            self.lbl_auth_status.configure(text="미인증 기기 ❌", text_color="red")
            self.btn_request_auth.pack(side="left", padx=5, pady=5)
            self.log(f"라이선스 인증 실패: {msg}")
            if status == "unregistered":
                self.log(f"신규 기기입니다. [승인 요청] 팝업에서 관리자에게 승인을 요청해 주세요.")
                self.after(500, lambda: self.show_approval_popup(hwid))
            elif status == "pending":
                self.log(f"현재 관리자 승인을 대기 중입니다.")
            elif status == "blocked":
                self.log(f"이 기기는 차단되었습니다.")
            else:
                self.log(f"관리자에게 위의 [기기 번호]를 전달하거나 [승인 요청] 버튼을 눌러 승인을 요청하세요.")

    def manual_request_auth(self):
        import auth
        hwid = auth.get_hwid()
        self.show_approval_popup(hwid)

    def show_approval_popup(self, hwid):
        import auth
        popup = ctk.CTkToplevel(self)
        popup.title("관리자 승인 요청")
        popup.geometry("350x200")
        popup.transient(self)
        popup.grab_set()

        lbl = ctk.CTkLabel(popup, text="최초 실행 기기입니다.\n관리자가 식별할 수 있도록 이름/소속을 입력해 주세요.")
        lbl.pack(pady=15)

        entry_name = ctk.CTkEntry(popup, placeholder_text="예: 마케팅팀 홍길동", width=250)
        entry_name.pack(pady=10)

        def submit():
            name = entry_name.get().strip()
            if not name:
                self.log("이름/소속을 입력해 주세요.")
                return
            btn_submit.configure(state="disabled", text="요청 중...")
            success, msg = auth.request_approval(hwid, name)
            if success:
                self.log("승인 요청이 완료되었습니다. 관리자 승인 후 프로그램을 다시 실행해 주세요.")
                popup.destroy()
            else:
                self.log(f"승인 요청 실패: {msg}")
                btn_submit.configure(state="normal", text="승인 요청하기")

        btn_submit = ctk.CTkButton(popup, text="승인 요청하기", command=submit)
        btn_submit.pack(pady=15)

    def log(self, message):
        """텍스트 박스에 로그 추가"""
        self.textbox_log.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.textbox_log.see("end")

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
        def run_test():
            self.btn_test_ip.configure(state="disabled")
            try:
                ip_changer.toggle_airplane_mode()
                self.log("IP 변경 완료.")
            except Exception as e:
                self.log(f"IP 변경 실패: {e}")
            finally:
                self.btn_test_ip.configure(state="normal")
                
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
            self.crawler_engine = crawler.CrawlerEngine(log_callback=self.log)
            
            keywords = [k.strip() for k in keyword.split(",")]
            
            if target == "place":
                try:
                    max_pages = int(self.entry_pages.get().strip())
                except:
                    max_pages = 1
                self.crawler_engine.crawl_naver_place(keywords, use_ip_change, max_pages=max_pages)
            elif target == "shopping":
                self.crawler_engine.crawl_naver_shopping(keywords, use_ip_change)
            elif target == "coupang":
                try:
                    rounds = int(self.entry_rounds.get().strip())
                    if rounds < 1:
                        rounds = 1
                except:
                    rounds = 1
                self.crawler_engine.crawl_coupang(keywords, use_ip_change, rounds=rounds)
                
            self.log("크롤링 작업이 종료되었습니다.")
        except Exception as e:
            self.log(f"오류 발생: {e}")
        finally:
            self.is_running = False
            self.btn_start.configure(state="normal")

    def stop_crawling(self):
        self.log("중지 요청됨... (진행 중인 동작 완료 후 종료됩니다)")
        self.is_running = False
        if hasattr(self, 'crawler_engine'):
            self.crawler_engine.stop()

if __name__ == "__main__":
    app = CrawlerApp()
    app.mainloop()
