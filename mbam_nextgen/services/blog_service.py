import asyncio
import os
from ..core.stealth import StealthExecutor

class BlogService:
    """
    [Domain Service] 네이버 블로그 자동화 특화 로직
    UI 구조 변경 시 이 클래스만 수정하면 됨 (Single Responsibility)
    """
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth
        self.selectors = {
            "write_btn": ".se-toolbar-button-image, .se-image-toolbar-button",
            "title": ".se-placeholder, .se-title-text, span:has-text('제목')",
            "body": ".se-content, .se-placeholder:has-text('본문')",
            "popup_close": "button.se-popup-button-cancel, button.se-help-close-button"
        }

    async def auto_enter_editor(self, page):
        """블로그 홈에서 [글쓰기] 버튼을 자동 클릭"""
        try:
            write_btn = page.locator("a:has-text('글쓰기'), button:has-text('글쓰기')")
            await write_btn.first.wait_for(timeout=10000)
            await write_btn.first.click()
            print("[BlogService] ✅ [글쓰기] 버튼 자동 클릭 완료")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[BlogService] ⚠️ 글쓰기 버튼 클릭 실패: {e}")
            print("[BlogService] 📌 브라우저에서 직접 [글쓰기]를 눌러주세요.")

    async def wait_for_editor(self, context, page):
        """에디터 진입 시점을 포착하여 해당 프레임을 반환 (최대 15초 대기)"""
        print("🔍 [BlogService] 에디터 진입 감시 중...")
        for _ in range(15): # 15초 동안 시도
            for p in context.pages:
                for f in p.frames:
                    try:
                        # 본문 영역이 존재하는지 확인
                        if await f.locator(self.selectors["body"]).count() > 0:
                            print(f"✨ [BlogService] 에디터 포착: {f.name}")
                            return f
                    except: continue
            await asyncio.sleep(1)
        
        # 실패 시 현재 페이지의 메인 프레임 시도
        print("⚠️ [BlogService] 에디터 감지 실패. 기본 프레임으로 진행합니다.")
        return page.main_frame

    async def dismiss_popups(self, frame):
        """방해 팝업(임시저장, 도움말 등) 제거"""
        print("[BlogService] 방해 팝업 체크 중...")
        popups = [
            "button.se-popup-button-cancel", 
            "button.se-help-close-button",
            ".se-alert-button-close",
            "button:has-text('취소')",
            "button:has-text('닫기')"
        ]
        for sel in popups:
            try:
                btn = frame.locator(sel)
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    print(f"[BlogService] 팝업 제거 완료: {sel}")
            except: pass

    async def write_post(self, frame, title: str, content: str, speed_mode: str = "normal", speed_multiplier: float = 1.0):
        """원고 타이핑 (스텔스 적용, 속도 조절 가능)"""
        print(f"[BlogService] 타이핑 시작: {title[:15]}... (속도: {speed_mode} x{speed_multiplier})")
        
        # 제목 입력
        await frame.wait_for_selector(self.selectors["title"], timeout=10000)
        await frame.click(self.selectors["title"])
        await self.stealth.human_type(frame, self.selectors["title"], title, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
        
        # 본문 입력
        await frame.click(self.selectors["body"])
        await self.stealth.human_type(frame, self.selectors["body"], content, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
        print("✅ [BlogService] 원고 타이핑 완료")

    async def upload_images(self, frame, image_paths: list):
        """세척된 이미지 순차 업로드"""
        for path in image_paths:
            if os.path.exists(path):
                await self.stealth.upload_image(frame, path)
                await asyncio.sleep(2)

    async def publish_now(self, frame):
        """
        [즉시 발행] 발행 버튼을 클릭하여 포스팅을 즉시 공개합니다.
        """
        page = StealthExecutor._get_page_obj(frame)
        print("[BlogService] 🚀 즉시 발행 시도 중...")
        
        try:
            # 1. 상단의 [발행] 버튼 클릭
            publish_btn = frame.locator("button:has-text('발행'), a:has-text('발행')")
            if await publish_btn.count() == 0:
                # 프레임 밖(상위 페이지)에 있을 수 있음
                publish_btn = page.locator("button:has-text('발행'), a:has-text('발행')")
            
            await publish_btn.first.click()
            await asyncio.sleep(2)
            
            # 2. 발행 확인 다이얼로그에서 [발행] 확인 버튼 클릭
            confirm_selectors = [
                "button.publish_btn__confirm",
                "button:has-text('발행')",
                ".se-popup-button-confirm",
                "button.confirm"
            ]
            
            for sel in confirm_selectors:
                try:
                    confirm = page.locator(sel)
                    if await confirm.count() > 0:
                        await confirm.last.click()
                        print("✅ [BlogService] 즉시 발행 완료!")
                        await asyncio.sleep(3)
                        return True
                except: continue
            
            print("⚠️ [BlogService] 발행 확인 버튼을 찾지 못했습니다. 수동 확인 필요.")
            return False
            
        except Exception as e:
            print(f"⚠️ [BlogService] 발행 중 오류: {e}")
            return False

    async def schedule_publish(self, frame, schedule_date: str, schedule_time: str):
        """
        [예약 발행] 지정된 날짜/시간에 자동 발행되도록 예약합니다.
        
        Args:
            schedule_date: "2026-05-15" 형식
            schedule_time: "10:30" 형식
        """
        page = StealthExecutor._get_page_obj(frame)
        print(f"[BlogService] ⏰ 예약 발행 설정 중... ({schedule_date} {schedule_time})")
        
        try:
            # 1. 상단의 [발행] 버튼 클릭 (발행 설정 패널 열기)
            publish_btn = frame.locator("button:has-text('발행'), a:has-text('발행')")
            if await publish_btn.count() == 0:
                publish_btn = page.locator("button:has-text('발행'), a:has-text('발행')")
            
            await publish_btn.first.click()
            await asyncio.sleep(2)
            
            # 2. 예약 발행 옵션 선택
            reserve_selectors = [
                "label:has-text('예약')",
                "input[value='reserve']",
                "span:has-text('예약')",
                ".se-publish-reserve"
            ]
            
            for sel in reserve_selectors:
                try:
                    reserve_opt = page.locator(sel)
                    if await reserve_opt.count() > 0:
                        await reserve_opt.first.click()
                        print("[BlogService] 예약 옵션 선택 완료")
                        await asyncio.sleep(1)
                        break
                except: continue
            
            # 3. 날짜 입력
            date_input = page.locator("input[type='date'], input.se-publish-date, input[placeholder*='날짜']")
            if await date_input.count() > 0:
                await date_input.first.fill(schedule_date)
                print(f"[BlogService] 날짜 설정: {schedule_date}")
            
            # 4. 시간 입력
            time_input = page.locator("input[type='time'], input.se-publish-time, input[placeholder*='시간']")
            if await time_input.count() > 0:
                await time_input.first.fill(schedule_time)
                print(f"[BlogService] 시간 설정: {schedule_time}")
            
            await asyncio.sleep(1)
            
            # 5. 예약 확인 버튼 클릭
            confirm_selectors = [
                "button:has-text('예약')",
                "button.publish_btn__confirm",
                ".se-popup-button-confirm",
                "button:has-text('확인')"
            ]
            
            for sel in confirm_selectors:
                try:
                    confirm = page.locator(sel)
                    if await confirm.count() > 0:
                        await confirm.last.click()
                        print(f"✅ [BlogService] 예약 발행 완료! ({schedule_date} {schedule_time})")
                        await asyncio.sleep(3)
                        return True
                except: continue
            
            print("⚠️ [BlogService] 예약 확인 버튼을 찾지 못했습니다. 수동 확인 필요.")
            return False
            
        except Exception as e:
            print(f"⚠️ [BlogService] 예약 발행 중 오류: {e}")
            return False
