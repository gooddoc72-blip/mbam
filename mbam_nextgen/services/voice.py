import random
import asyncio
from typing import List
from playwright.async_api import Page
from mbam_nextgen.core.stealth import StealthExecutor

class VoiceManager:
    """
    [L5. The Voice]
    Handles community engagement, cafe level-up, and auto-commenting.
    """
    
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth

    async def run_cafe_levelup(self, page: Page, cafe_id: str, content: str):
        """
        Posts daily content in a designated category to increase account activity index.
        """
        print(f"[Voice] Increasing activity index for cafe: {cafe_id}...")
        # 1. Navigate to cafe
        # 2. Select 'Greeting' or 'Daily' category
        # 3. Type content using human mimicry
        # 4. Post
        await self.stealth.human_type(page, "textarea#content", content)
        await asyncio.sleep(random.uniform(1.0, 3.0))
        print("[Voice] Cafe level-up post completed.")

    async def auto_comment(self, page: Page, post_url: str, comment_text: str):
        """
        Navigates to a post and writes a natural-looking comment.
        """
        print(f"[Voice] Writing auto-comment on: {post_url}...")
        await page.goto(post_url)
        await asyncio.sleep(random.uniform(2.0, 5.0))
        
        # Scroll to comment section
        await self.stealth.natural_scroll(page)
        
        # 댓글 창이 보일 때만 타이핑 시도
        comment_selector = "textarea.comment_input, #comment_area"
        if await page.locator(comment_selector).is_visible(timeout=5000):
            await self.stealth.human_type(page, comment_selector, comment_text)
            await asyncio.sleep(random.uniform(1.0, 2.0))
            print("[Voice] Auto-comment submitted.")
        else:
            print("[Voice] Comment input not found. Skipping.")

    async def simulate_engagement_loop(self, page: Page, post_urls: List[str]):
        """
        Cycles through a list of posts to click 'Like' and scroll.
        """
        for url in post_urls:
            await page.goto(url)
            await self.stealth.natural_scroll(page)
            # await page.click("a.btn_like")
            await asyncio.sleep(random.uniform(3.0, 7.0))
