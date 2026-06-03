import random
import asyncio
import numpy as np
from playwright.async_api import Page, Frame

class StealthExecutor:
    """
    [L4. The Stealth - Ultimate Pro]
    Page/Frame 호환형 마우스 이동, 타이핑, 스크롤 통합 모듈
    """
    
    @staticmethod
    def _get_page_obj(obj):
        """Page 또는 Frame 객체에서 실제 Page 객체를 추출합니다."""
        if hasattr(obj, "mouse"):
            return obj
        return obj.page

    @staticmethod
    async def human_mouse_move(obj, selector: str):
        """마우스를 요소로 자연스럽게 이동 (Page/Frame 호환)"""
        page = StealthExecutor._get_page_obj(obj)
        element = obj.locator(selector).first
        if not await element.is_visible(): return
        box = await element.bounding_box()
        if not box: return
        
        target_x = box['x'] + box['width'] / 2 + random.uniform(-5, 5)
        target_y = box['y'] + box['height'] / 2 + random.uniform(-5, 5)
        
        # 현재 위치 (알 수 없으면 랜덤 시작)
        start_x, start_y = random.randint(0, 300), random.randint(0, 300)
        
        # 제어점 생성 (베지어 곡선)
        cp1_x = start_x + (target_x - start_x) * random.uniform(0.1, 0.4)
        cp1_y = start_y + (target_y - start_y) * random.uniform(0.5, 0.9)
        cp2_x = start_x + (target_x - start_x) * random.uniform(0.6, 0.9)
        cp2_y = start_y + (target_y - start_y) * random.uniform(0.1, 0.5)
        
        steps = random.randint(15, 30)
        for i in range(steps + 1):
            t = i / steps
            x = (1-t)**3 * start_x + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * target_x
            y = (1-t)**3 * start_y + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * target_y
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.005, 0.01))
            
        await page.mouse.move(target_x, target_y)

    @staticmethod
    async def human_type(obj, selector: str, text: str, speed_mode: str = "normal", speed_multiplier: float = 1.0):
        """
        채널별 속도에 따른 인간형 타이핑 (Page/Frame 호환)
        
        Args:
            speed_mode: "slow" | "normal" | "fast" 프리셋
            speed_multiplier: 속도 배수 (0.3=초고속, 0.5=빠름, 1.0=기본, 2.0=느림, 3.0=매우느림)
        """
        page = StealthExecutor._get_page_obj(obj)
        modes = {
            "slow": (0.22, 0.08, 0.02),
            "normal": (0.12, 0.05, 0.04),
            "fast": (0.06, 0.03, 0.08)
        }
        mean_delay, std_dev, typo_chance = modes.get(speed_mode, modes["normal"])
        
        # 속도 배수 적용 (배수가 클수록 느려짐)
        mean_delay *= speed_multiplier
        std_dev *= speed_multiplier
        
        print(f"[Stealth] 타이핑 시작 (모드: {speed_mode}, 배수: {speed_multiplier}x, 평균딜레이: {mean_delay:.3f}s)")
        
        # 에디터 클릭
        await StealthExecutor.human_mouse_move(obj, selector)
        await obj.locator(selector).first.click()
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        paragraphs = text.split('\n')
        for p_idx, paragraph in enumerate(paragraphs):
            for char in paragraph:
                await page.keyboard.type(char)
                delay = abs(np.random.normal(mean_delay, std_dev))
                if random.random() < typo_chance:
                    await page.keyboard.type(random.choice("qwertyuiop"))
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Backspace")
                if char in [',', '.', '!', '?']: delay += random.uniform(0.4, 1.2) * speed_multiplier
                await asyncio.sleep(max(0.01, delay))
            
            if p_idx < len(paragraphs) - 1:
                await page.keyboard.press("Enter")
                await asyncio.sleep(random.uniform(1.5, 3.5) * speed_multiplier)

    @staticmethod
    async def natural_scroll(obj):
        """읽기 패턴을 고려한 자연스러운 스크롤 (Page/Frame 호환)"""
        page = StealthExecutor._get_page_obj(obj)
        for _ in range(random.randint(2, 4)):
            scroll_y = random.randint(400, 800)
            await page.mouse.wheel(0, scroll_y)
            await asyncio.sleep(random.uniform(1.5, 3.0))
            if random.random() < 0.2:
                await page.mouse.wheel(0, -random.randint(100, 300))
                await asyncio.sleep(1.0)

    @staticmethod
    async def upload_image(obj, file_path: str):
        """에디터에 이미지를 업로드합니다 (Page/Frame 호환)"""
        import os
        print(f"[Stealth] 이미지 업로드 시도: {os.path.basename(file_path)}")
        
        page = StealthExecutor._get_page_obj(obj)
        
        # 방법 1: 파일 선택 다이얼로그 가로채기
        try:
            # 네이버 에디터의 사진 버튼 셀렉터 (여러 변형 대응)
            photo_selectors = [
                "button.se-image-toolbar-button",
                ".se-toolbar-button-image", 
                "button[data-name='image']",
                ".se-toolbar button:has(.se-toolbar-icon-image)"
            ]
            
            clicked = False
            for sel in photo_selectors:
                try:
                    if await obj.locator(sel).count() > 0:
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await obj.locator(sel).first.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(file_path)
                        clicked = True
                        print(f"✅ 이미지 업로드 완료: {os.path.basename(file_path)}")
                        await asyncio.sleep(3)
                        break
                except Exception:
                    continue
            
            # 방법 2: 파일 선택 실패 시 input[type=file]에 직접 주입
            if not clicked:
                file_input = obj.locator("input[type='file']").first
                if await file_input.count() > 0:
                    await file_input.set_input_files(file_path)
                    print(f"✅ 이미지 직접 주입 완료: {os.path.basename(file_path)}")
                    await asyncio.sleep(3)
                else:
                    print("⚠️ 이미지 업로드 버튼을 찾을 수 없습니다.")
                    
        except Exception as e:
            print(f"⚠️ 이미지 업로드 중 오류: {e}")
