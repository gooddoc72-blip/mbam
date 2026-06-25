import random
import re
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

    # ── 네이버 SmartEditor ONE(SE3) 툴바 제어 (소제목 폰트 크기/굵게) ──────────
    @staticmethod
    async def _se3_click(obj, data_name: str) -> bool:
        """SE3 툴바 버튼(data-name) 클릭. 성공 True. (frame 내 버튼)"""
        try:
            btn = obj.locator(f'button[data-name="{data_name}"]').first
            if await btn.count() == 0:
                return False
            await btn.click(timeout=2000)
            await asyncio.sleep(0.2)
            return True
        except Exception:
            return False

    @staticmethod
    async def _se3_bold_is_on(obj) -> bool:
        """굵게 버튼이 현재 활성(눌림) 상태인지."""
        try:
            btn = obj.locator('button[data-name="bold"]').first
            if await btn.count() == 0:
                return False
            cls = (await btn.get_attribute("class")) or ""
            pressed = (await btn.get_attribute("aria-pressed")) or ""
            return ("se-is-on" in cls) or ("is-selected" in cls) or (pressed == "true")
        except Exception:
            return False

    @staticmethod
    async def _se3_set_font_size(obj, size_text: str) -> bool:
        """폰트 크기 드롭다운을 열어 size_text(예 '19','16')를 선택."""
        try:
            if not await StealthExecutor._se3_click(obj, "font-size"):
                return False
            await asyncio.sleep(0.2)
            # SE3 옵션 버튼은 data-value="fs16"/"fs19" 형태 (검증됨). 클래스/텍스트보다 신뢰도 높음.
            opt = obj.locator(f'button[data-value="fs{size_text}"]')
            if await opt.count() == 0:
                opt = obj.locator(f'button[class*="fs{size_text}"]')
            if await opt.count() == 0:
                return False
            await opt.first.click(timeout=2000)
            await asyncio.sleep(0.2)
            return True
        except Exception:
            return False

    @staticmethod
    async def _move_cursor_end(obj, selector: str):
        """본문 에디터의 커서를 맨 끝으로 이동(선택 해제) — 이미지/서식 보존하며 이어쓰기."""
        try:
            await obj.locator(selector).first.evaluate("""el => {
                if (el.isContentEditable || el.getAttribute('contenteditable') === 'true') {
                    el.focus();
                    const r = document.createRange();
                    r.selectNodeContents(el);
                    r.collapse(false);
                    const s = window.getSelection();
                    s.removeAllRanges();
                    s.addRange(r);
                }
            }""")
        except Exception:
            pass

    @staticmethod
    def format_body(content: str) -> str:
        """본문 줄바꿈/단락 가공 (블로그·카페 공용):
        - 문장(. ! ?)마다 줄바꿈, 긴 문단(4문장↑)은 3문장씩 블록 분리
        - 소제목(■/[소제목])·해시태그(#태그 2개↑) 줄 앞에 한 줄 띄움
        - [이미지] 마커는 보존(이후 이미지 인라인 삽입에 사용)"""
        bullets = "■▶◆●▣◼▪□▷"
        # 긴 문장을 절(쉼표/연결어미) 경계에서 끊기 위한 연결어미 목록
        CONNECTIVES = ('지만', '으니', '니까', '면서', '는데', '어서', '아서', '하여',
                       '하고', '이고', '되고', '되며', '하며', '때문에', '통해', '위해',
                       '라면', '다면', '거나', '으며', '데요', '지요', '으면', '려면')

        def _split_long(sent, limit=42, soft=20):
            """한 문장이 길면 쉼표·연결어미 뒤에서 끊어 여러 줄로. 짧으면 그대로."""
            if len(sent) <= limit:
                return [sent]
            lines, cur = [], ''
            for w in sent.split(' '):
                cur = (cur + ' ' + w).strip() if cur else w
                w_clean = w.rstrip(',.')
                ends_clause = w.endswith(',') or any(w_clean.endswith(c) for c in CONNECTIVES)
                if ends_clause and len(cur) >= soft:
                    lines.append(cur)
                    cur = ''
                elif len(cur) >= limit and ' ' in cur:
                    lines.append(cur)  # 절 경계가 없어도 너무 길면 단어 경계에서 끊음
                    cur = ''
            if cur:
                lines.append(cur)
            return lines if lines else [sent]

        out_lines = []
        for line in (content or "").split('\n'):
            s = line.strip()
            if not s or s.startswith('[소제목]') or s.startswith('[이미지]') or s[:1] in bullets:
                out_lines.append(line)
                continue
            sents = [x.strip() for x in re.split(r'(?<=[.!?])\s+', s) if x.strip()]

            def _emit(group):
                for sent in group:
                    out_lines.extend(_split_long(sent))

            if len(sents) <= 3:
                _emit(sents)
            else:
                for i in range(0, len(sents), 3):
                    _emit(sents[i:i + 3])
                    if i + 3 < len(sents):
                        out_lines.append('')
        content = '\n'.join(out_lines)
        content = re.sub(r'\n[ \t]*(?=(?:\[소제목\]|[■▶◆●▣◼▪□▷]))', r'\n\n', content)
        content = re.sub(r'\n(?=[^\n]*#\S+[^\n]*#\S+)', r'\n\n', content)
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content

    @staticmethod
    async def human_type(obj, selector: str, text: str, speed_mode: str = "normal", speed_multiplier: float = 1.0, do_click: bool = True):
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
        
        # 에디터 포커스: 본문 타이핑(do_click=False)은 중앙 클릭을 생략한다.
        # 중앙 클릭이 (앞서 삽입된) 이미지를 '선택'하면 다음 글자 입력 시 이미지가 글자로 대체(삭제)되기 때문.
        if do_click:
            await StealthExecutor.human_mouse_move(obj, selector)
            await obj.locator(selector).first.click()
            await asyncio.sleep(random.uniform(0.5, 1.5))
        # 커서를 본문 맨 끝으로 이동(선택 해제) → 이미지 보존하며 이어쓰기
        try:
            await obj.locator(selector).first.evaluate("""el => {
                if (el.isContentEditable || el.getAttribute('contenteditable') === 'true') {
                    el.focus();
                    const r = document.createRange();
                    r.selectNodeContents(el);
                    r.collapse(false);
                    const s = window.getSelection();
                    s.removeAllRanges();
                    s.addRange(r);
                }
            }""")
        except Exception:
            pass

        SUBTITLE_MARK = "[소제목]"
        HEADING_BULLETS = ("■", "▶", "◆", "●", "▣", "◼", "▪", "□", "▷")
        HEADING_SIZE = "19"   # 소제목 폰트 크기(본문 기본 16 → 19)
        paragraphs = text.split('\n')

        async def _style_current_line(size_text, want_bold):
            """방금 입력한 (짧은) 소제목 줄을 선택해 굵게→폰트크기 순으로 적용. 본문엔 사용하지 않음."""
            try:
                await page.keyboard.press("Shift+Home")
                await asyncio.sleep(0.12)
                bold_on = await StealthExecutor._se3_bold_is_on(obj)
                if want_bold != bold_on:
                    await StealthExecutor._se3_click(obj, "bold")
                    await asyncio.sleep(0.1)
                await page.keyboard.press("End")
                await page.keyboard.press("Shift+Home")
                await asyncio.sleep(0.12)
                await StealthExecutor._se3_set_font_size(obj, size_text)
                await page.keyboard.press("End")
                await asyncio.sleep(0.1)
            except Exception:
                pass

        async def _reset_typing_format():
            """선택 없이 '입력 서식'을 본문 기본(16/굵게 off)으로 — 다음 타이핑부터 적용.
            줄바꿈(wrap)된 본문도 처음부터 정상 서식으로 입력되어 굵게/크기 번짐이 없다."""
            try:
                if await StealthExecutor._se3_bold_is_on(obj):
                    await StealthExecutor._se3_click(obj, "bold")
                    await asyncio.sleep(0.1)
                await StealthExecutor._se3_set_font_size(obj, "16")
                await asyncio.sleep(0.1)
            except Exception:
                pass

        # 세그먼트 시작 시 본문 기본 서식으로 초기화 (이전 세그먼트 소제목 19/굵게가 새지 않도록)
        await _reset_typing_format()

        for p_idx, paragraph in enumerate(paragraphs):
            # 소제목 줄 판별 — 마커 '[소제목]'(토큰) 또는 줄 맨 앞 헤딩 불릿(■ ▶ ◆ 등, 짧은 줄)
            stripped = paragraph.lstrip()
            is_sub = False
            if stripped.startswith(SUBTITLE_MARK):
                paragraph = stripped[len(SUBTITLE_MARK):].lstrip()
                is_sub = True
            elif stripped[:1] in HEADING_BULLETS and len(stripped) <= 50:
                paragraph = stripped  # 불릿(■ 등)은 유지
                is_sub = True

            # 빈 줄(단락 경계) → 한 줄 띄움 (SE3가 빈 단락을 무시하지 않도록 공백 입력) — coco8go 동일
            if not paragraph:
                await page.keyboard.type(" ")
                await asyncio.sleep(0.1)

            for char in paragraph:
                await page.keyboard.type(char)
                delay = abs(np.random.normal(mean_delay, std_dev))
                if random.random() < typo_chance:
                    await page.keyboard.type(random.choice("qwertyuiop"))
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Backspace")
                if char in [',', '.', '!', '?']: delay += random.uniform(0.4, 1.2) * speed_multiplier
                await asyncio.sleep(max(0.01, delay))

            # 소제목 줄 → (선택해서) 크게+굵게 적용 후, 다음 본문을 위해 입력서식을 16/일반으로 복귀
            # 본문 줄은 이미 _reset_typing_format 상태로 입력되므로 별도 처리 불필요(굵게/크기 번짐 없음)
            if is_sub and paragraph:
                await _style_current_line(HEADING_SIZE, want_bold=True)
                await _reset_typing_format()

            # 줄바꿈: 모든 줄 끝에서 Enter (문장=새 줄, 빈 줄=한 줄 띄움) — coco8go 동일
            if p_idx < len(paragraphs) - 1:
                await page.keyboard.press("Enter", delay=100)
                await asyncio.sleep(random.uniform(0.8, 1.8) * speed_multiplier)

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
