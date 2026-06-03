import asyncio
import random
import os
from playwright.async_api import Page
from mbam_nextgen.core.stealth import StealthExecutor
from mbam_nextgen.services.armor import ImageArmor

class PlaceAutomator:
    """
    [Place Module]
    네이버 플레이스 예약 및 영수증 리뷰 자동화 모듈
    """
    
    def __init__(self, stealth: StealthExecutor, armor: ImageArmor):
        self.stealth = stealth
        self.armor = armor

    async def reserve_place(self, page: Page, booking_url: str, date: str, time: str, guests: int = 2):
        """
        플레이스 예약 프로세스를 수행합니다.
        """
        print(f"[Place] 예약 페이지 접속: {booking_url}")
        await page.goto(booking_url)
        await asyncio.sleep(random.uniform(3.0, 5.0))
        
        # 1. 날짜 선택
        # 날짜 텍스트를 포함한 요소를 찾아 클릭
        day = date.split("-")[-1].lstrip("0")
        day_selector = f"text='{day}'"
        await self.stealth.human_mouse_move(page, day_selector)
        await page.click(day_selector)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # 2. 시간 선택
        time_selector = f"text='{time}'"
        if await page.locator(time_selector).is_visible():
            await self.stealth.human_mouse_move(page, time_selector)
            await page.click(time_selector)
        
        # 3. 인원수 조절
        for _ in range(guests - 1):
            await page.click(".btn_plus, text='+'")
            await asyncio.sleep(0.3)
            
        # 4. 다음/예약하기 버튼
        await self.stealth.human_mouse_move(page, "text='다음'")
        # await page.click("text='예약 신청하기'")
        print(f"[Place] 예약 신청 완료 시뮬레이션: {date} {time}")

    async def write_receipt_review(self, page: Page, original_image_path: str, review_text: str):
        """
        영수증 리뷰를 작성합니다 (이미지 세척 포함).
        """
        print("[Place] 영수증 리뷰 프로세스 시작...")
        
        # 1. 이미지 세척 (The Armor 연동)
        washed_path = self.armor.wash_image(original_image_path, "place_review_final.jpg")
        abs_washed_path = os.path.abspath(washed_path)
        
        # 2. 리뷰 작성 페이지 이동
        await page.goto("https://m.place.naver.com/my/review/write")
        await asyncio.sleep(3)
        
        # 3. 이미지 업로드 (실제 파일 경로 주입)
        file_input = page.locator("input[type='file']")
        await file_input.set_input_files(abs_washed_path)
        print(f"[Place] 세척된 이미지 업로드 완료: {abs_washed_path}")
        
        # OCR 대기 및 키워드 선택 시뮬레이션
        await asyncio.sleep(random.uniform(5.0, 8.0))
        
        # 4. 리뷰 텍스트 입력
        await self.stealth.human_type(page, "textarea", review_text)
        
        # 5. 등록
        # await page.click("text='등록'")
        print("[Place] 영수증 리뷰 작성 완료 시뮬레이션")
