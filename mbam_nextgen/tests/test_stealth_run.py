import asyncio
import sys
import os
from playwright.async_api import async_playwright

# Add parent dir to path to import mbam_nextgen modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.stealth import StealthExecutor
from services.soul import SoulRewriter

async def run_test_mission():
    """
    Simulates a standalone mission: AI Rewriting -> Stealth Browsing.
    """
    print("=== [MBAM Next-Gen] Standalone Test Start ===")
    
    # 1. AI Content Generation
    soul = SoulRewriter(api_key="dummy_key")
    raw_info = "강남역 삼겹살 맛집 '하마네 고기집'. 고기가 두껍고 밑반찬이 맛있음."
    keyword = "강남역 삼겹살 맛집"
    
    blog_content = await soul.rewrite_for_blog(raw_info, keyword)
    print(f"\n[AI Content Ready]\n{blog_content}\n")
    
    # 2. Stealth Browser Execution
    async with async_playwright() as p:
        print("[Stealth] Launching browser...")
        browser = await p.chromium.launch(headless=False) # See it in action
        context = await browser.new_context()
        page = await context.new_page()
        
        stealth = StealthExecutor()
        
        # Navigate to Naver (Simulated)
        print("[Stealth] Navigating to Naver...")
        await page.goto("https://www.naver.com")
        await asyncio.sleep(2)
        
        # Move mouse to search box naturally
        print("[Stealth] Moving mouse to search box...")
        await stealth.human_mouse_move(page, "input#query")
        
        # Type keyword naturally
        print("[Stealth] Typing keyword...")
        await stealth.human_type(page, "input#query", keyword)
        await page.keyboard.press("Enter")
        
        # Scroll naturally
        print("[Stealth] Reading search results...")
        await stealth.natural_scroll(page)
        
        await asyncio.sleep(3)
        await browser.close()
        
    print("\n=== [MBAM Next-Gen] Test Completed Successfully ===")

if __name__ == "__main__":
    asyncio.run(run_test_mission())
