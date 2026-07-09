# -*- coding: utf-8 -*-
"""스마트플레이스 '새소식' 발행 자동화 (V1 — 사용자 PC/에이전트에서 실행).

기기 인증된 영구 프로필로 스마트플레이스에 로그인 → 업체 선택 → 소식 작성 → 등록.
스마트플레이스 UI 는 수시로 바뀌므로 텍스트 기반 로케이터를 여러 후보로 시도하고,
자동화가 막히는 단계에서는 브라우저를 열어둔 채 사용자가 직접 마무리할 수 있게 한다.
"""
import os
import asyncio


async def _first_visible(page, selectors, timeout=4000):
    """후보 셀렉터들 중 처음 보이는 요소를 반환 (없으면 None)."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    return None


async def publish_smartplace_news(naver_id: str, title: str, content: str,
                                  video_path: str = None, log=print) -> dict:
    try:
        from playwright.async_api import async_playwright
        from mbam_nextgen.infrastructure.session import get_profile_dir, clear_stale_locks
    except ImportError as e:
        return {"success": False, "error": f"모듈 로드 실패: {e}"}

    clear_stale_locks(naver_id)
    profile_dir = get_profile_dir(naver_id)
    text = (title + "\n\n" + content).strip() if title else content

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            profile_dir, headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            viewport={"width": 1280, "height": 900}, locale="ko-KR", timezone_id="Asia/Seoul",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            log("스마트플레이스 접속 중...")
            await page.goto("https://new.smartplace.naver.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 로그인 여부 확인 — 로그인 페이지로 튕기면 기기 인증(프로필)이 없는 것
            if "nid.naver.com" in page.url:
                await context.close()
                return {"success": False,
                        "error": f"'{naver_id}' 프로필이 네이버에 로그인되어 있지 않습니다. 먼저 기기 인증을 완료해 주세요."}

            # 업체(플레이스) 진입 — 업체 목록이 뜨면 첫 업체 클릭
            biz = await _first_visible(page, [
                "a[href*='/bizes/place/']",
                "a:has-text('내 업체')",
            ], timeout=6000)
            if biz:
                await biz.click()
                await asyncio.sleep(3)

            # '소식' 메뉴 → 작성 화면
            news_menu = await _first_visible(page, [
                "a:has-text('소식')", "button:has-text('소식')",
            ], timeout=6000)
            if news_menu:
                await news_menu.click()
                await asyncio.sleep(2.5)
            write_btn = await _first_visible(page, [
                "a:has-text('소식 작성')", "button:has-text('소식 작성')",
                "a:has-text('글쓰기')", "button:has-text('글쓰기')",
                "a:has-text('작성')", "button:has-text('작성')",
            ], timeout=6000)
            if write_btn:
                await write_btn.click()
                await asyncio.sleep(3)

            # 본문 입력 — textarea 또는 contenteditable
            editor = await _first_visible(page, [
                "textarea", "[contenteditable='true']",
            ], timeout=8000)
            if not editor:
                log("작성 에디터를 찾지 못했습니다 — 브라우저에서 직접 작성해 주세요. (원고는 클립보드에 복사됨, 4분 유지)")
                try:
                    import pyperclip
                    pyperclip.copy(text)
                except Exception:
                    pass
                await asyncio.sleep(240)
                await context.close()
                return {"success": False, "error": "에디터 자동 탐지 실패 — 브라우저에서 직접 마무리해 주세요. (원고는 클립보드에 복사해 두었습니다)"}

            await editor.click()
            await editor.fill(text) if await _is_textarea(editor) else await page.keyboard.insert_text(text)
            log("원고 입력 완료.")

            # 영상/이미지 첨부 (있고 파일이 존재할 때만)
            if video_path and os.path.exists(video_path):
                try:
                    file_input = page.locator("input[type='file']").first
                    await file_input.set_input_files(video_path, timeout=5000)
                    log("클립 영상 첨부 완료.")
                    await asyncio.sleep(5)
                except Exception as fe:
                    log(f"영상 첨부 실패(본문만 발행): {fe}")

            # 등록/발행 버튼
            submit = await _first_visible(page, [
                "button:has-text('등록')", "button:has-text('발행')", "button:has-text('완료')",
            ], timeout=6000)
            if not submit:
                log("등록 버튼을 찾지 못했습니다 — 브라우저에서 직접 '등록'을 눌러 주세요. (3분 유지)")
                await asyncio.sleep(180)
                await context.close()
                return {"success": False, "error": "등록 버튼 자동 탐지 실패 — 원고는 입력됐으니 브라우저에서 '등록'만 눌러 주세요."}
            await submit.click()
            await asyncio.sleep(4)
            log("✅ 스마트플레이스 새소식 등록 완료.")
            await context.close()
            return {"success": True}
        except Exception as e:
            try:
                await context.close()
            except Exception:
                pass
            return {"success": False, "error": f"발행 중 오류: {e}"}


async def _is_textarea(loc) -> bool:
    try:
        return (await loc.evaluate("el => el.tagName")) == "TEXTAREA"
    except Exception:
        return False
