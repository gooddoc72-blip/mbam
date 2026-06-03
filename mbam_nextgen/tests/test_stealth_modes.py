import asyncio
import os
import sys
from playwright.async_api import async_playwright

# 패키지 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.stealth import StealthExecutor

async def run_speed_test():
    async with async_playwright() as p:
        print("=== [MBAM Next-Gen] 채널별 타이핑 텀 테스트 시작 ===")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 테스트용 빈 입력창 페이지 생성
        await page.set_content("""
            <html>
                <body style='padding:50px; font-family: sans-serif;'>
                    <h2>MBAM Stealth Typing Test</h2>
                    <div style='margin-bottom:20px;'>
                        <label>현재 모드: </label><span id='mode-display' style='font-weight:bold; color:blue;'>대기 중</span>
                    </div>
                    <textarea id='target' style='width:100%; height:300px; font-size:16px; padding:10px;'></textarea>
                </body>
            </html>
        """)
        
        stealth = StealthExecutor()
        target = "textarea#target"
        display = "span#mode-display"

        # 시나리오 1: Blog (Slow)
        print("\n[테스트 1] Blog 모드 - 정성글 (느리고 신중함)")
        await page.evaluate("document.getElementById('mode-display').innerText = 'Blog (Slow) - 정성글 작성 중...'")
        blog_text = "이곳은 정말 분위기가 좋네요.\n사장님도 친절하시고 인테리어가 감성적이라 사진 찍기에도 딱이에요! ✨"
        await stealth.human_type(page, target, blog_text, speed_mode="slow")
        
        await asyncio.sleep(2)
        await page.fill(target, "") # 초기화

        # 시나리오 2: Cafe (Normal)
        print("\n[테스트 2] Cafe 모드 - 일상 게시글 (보통 속도)")
        await page.evaluate("document.getElementById('mode-display').innerText = 'Cafe (Normal) - 자유게시판 글 작성 중...'")
        cafe_text = "오늘 날씨가 너무 좋아서 산책 다녀왔어요.\n다들 주말 잘 보내고 계신가요? 맛있는 거 추천 좀 해주세요~"
        await stealth.human_type(page, target, cafe_text, speed_mode="normal")

        await asyncio.sleep(2)
        await page.fill(target, "") # 초기화

        # 시나리오 3: Review (Fast)
        print("\n[테스트 3] Review 모드 - 영수증 리뷰 (빠름, 오타 주의)")
        await page.evaluate("document.getElementById('mode-display').innerText = 'Review (Fast) - 모바일 리뷰 작성 중...'")
        review_text = "고기 넘 맛있어요!! 담에 또 올게요 ㅋㅋㅋ 최고최고"
        await stealth.human_type(page, target, review_text, speed_mode="fast")

        print("\n=== [MBAM Next-Gen] 모든 모드 테스트 완료 ===")
        await asyncio.sleep(3)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_speed_test())
