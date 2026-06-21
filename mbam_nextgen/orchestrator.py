import asyncio
import os
import random
import sys
import os
import glob
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from .core.stealth import StealthExecutor
from .services.soul import SoulRewriter
from .services.armor import ImageArmor
from .services.blog_service import BlogService
from .services.cafe_service import CafeService
from .services.neighbor_service import NeighborService
from .services.card_news_generator import CardNewsGenerator
from .infrastructure.session import SessionManager
from .infrastructure.proxy import ProxyManager
from .infrastructure.naver_auth import NaverAuthenticator
from .infrastructure.database import DatabaseManager
from .core.logger import logger
from .core.stealth import StealthExecutor

class WorkflowOrchestrator:
    """
    [Application Layer] 
    전체 워크플로우를 조율하는 마스터 클래스.
    """
    def __init__(self):
        self.session_manager = SessionManager()
        self.stealth_engine = StealthExecutor()
        self.soul = SoulRewriter()
        self.armor = ImageArmor()
        self.blog = BlogService(self.stealth_engine)
        self.cafe = CafeService(self.stealth_engine)
        self.neighbor = NeighborService(self.stealth_engine)
        self.card_news = CardNewsGenerator()
        self.proxy_manager = ProxyManager()
        self.authenticator = NaverAuthenticator()
        self.db = DatabaseManager()
# ... (existing methods)

    async def execute_engagement_workflow(
        self,
        account_id: str,
        keyword: str,
        limit: int = 5,
        do_like: bool = True,
        do_comment: bool = True,
        comment_msg: str = None,
        do_neighbor: bool = True,
        neighbor_msg: str = "서로이웃 해요!",
        proxy: str = None,
        min_delay: int = 30,
        max_delay: int = 120
    ):
        """블로그 소통(공감/댓글/이웃) 워크플로우"""
        proxy_config = self.proxy_manager.get_browser_proxy_config(proxy)
        
        logger.info(f"🚀 [Orchestrator] 블로그 소통 워크플로우 시작: {account_id}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                proxy=proxy_config
            )
            
            # 1. 세션 준비 및 로그인
            has_session = await self.session_manager.load_session(context, account_id)
            page = await context.new_page()
            
            if not has_session:
                pw = os.getenv("NAVER_PW", "")
                await self.authenticator.login_with_bypass(page, account_id, pw)
                await self.session_manager.save_session(context, account_id)
            
            
            # 2. 타겟 수집
            targets = await self.neighbor.find_targets_from_search(page, keyword, limit=limit)
            
            results = []
            for target in targets:
                target_id = target["id"]
                post_url = target["post_url"]
                logger.info(f"👉 대상 블로그 진입: {target_id}")
                
                try:
                    # 포스팅 페이지 이동
                    await page.goto(post_url)
                    await asyncio.sleep(random.randint(3, 7)) # 체류 시간 흉내
                    
                    # 공감
                    if do_like:
                        await self.neighbor.click_like(page)
                    
                    # 댓글
                    if do_comment:
                        if comment_msg and comment_msg.strip():
                            comment_text = comment_msg
                        else:
                            # 포스트 내용을 읽어서 AI 댓글 생성 (선택 사항, 여기선 기본 구현)
                            comment_text = await self._generate_content_with_retry(f"{keyword} 관련해서 잘 읽었습니다!")
                        await self.neighbor.leave_comment(page, comment_text)
                    
                    # 이웃 추가
                    if do_neighbor:
                        await self.neighbor.add_neighbor(page, target_id, message=neighbor_msg)
                    
                    self.db.log_engagement(target_url=post_url, action_type="소통", comment_text=comment_text if do_comment else "공감/이웃", status="성공")
                    results.append({"id": target_id, "success": True})
                    
                    # 다음 작업 전 대기 (마지막 타겟이 아닐 경우만)
                    if target_id != targets[-1]["id"]:
                        delay = random.randint(min_delay, max_delay)
                        logger.info(f"⏳ 다음 블로그 방문 전 {delay}초 대기 중...")
                        await asyncio.sleep(delay)
                    
                except PlaywrightTimeoutError as e:
                    logger.warning(f"⚠️ {target_id} 타임아웃 오류 (로딩 실패): {e}")
                    self.db.log_engagement(target_url=post_url, action_type="소통", comment_text="", status=f"실패: 타임아웃")
                    results.append({"id": target_id, "success": False, "error": "Timeout"})
                except Exception as e:
                    logger.error(f"⚠️ {target_id} 작업 중 알 수 없는 오류: {e}")
                    self.db.log_engagement(target_url=post_url, action_type="소통", comment_text="", status=f"실패: {e}")
                    results.append({"id": target_id, "success": False, "error": str(e)})


    # ═══════════════════════════════════════════════
    # 공통 헬퍼
    # ═══════════════════════════════════════════════

    async def _generate_content_with_retry(
        self, keyword: str, max_attempts: int = 3, timeout: float = 120.0, ai_provider: str = "claude", reference_data: dict = None,
        post_purpose: str = None, promo_type: str = None, distribution_mode: str = None, source_data: str = None, api_key: str = None
    ) -> str:
        """AI 원고 생성 — 지수 백오프 재시도. 모두 실패 시 안전한 기본 원고 반환.

        soul.py가 예외를 raise하도록 바뀐 뒤로 호출자가 retry/폴백을 책임짐.
        타임아웃·네트워크 일시 장애·5xx는 재시도로 회복 가능."""
        last_exc = None
        
        # Prepare reference text if available
        ref_text = ""
        formula = ""
        if reference_data:
            formula = reference_data.get("formula", "")
            refs = reference_data.get("references", [])
            if refs:
                ref_text = "\n\n".join([f"참고글 {i+1}: {r.get('title', '')}\n메인키워드: {r.get('main_kw', '')}" for i, r in enumerate(refs)])
                
        # This will be injected into self.soul or self.soul.rewrite_for_blog
        # For prototype, we just pass the keyword but now we can add the ref_text to keyword context
        source_text = f"\n\n[수집된 원문 데이터]\n{source_data}" if source_data else ""
        enhanced_keyword = f"{keyword}{source_text}\n\n[참고 데이터]\n{ref_text}\n\n[상위노출 공식]\n{formula}" if (reference_data or source_data) else keyword
        
        for attempt in range(1, max_attempts + 1):
            try:
                content = await asyncio.wait_for(
                    self.soul.rewrite_for_blog("", enhanced_keyword, provider=ai_provider,
                                               post_purpose=post_purpose, promo_type=promo_type, distribution_mode=distribution_mode, api_key=api_key),
                    timeout=timeout,
                )
                logger.info(f"✅ [Orchestrator] 원고 생성 완료 ({attempt}회차)")
                return content
            except asyncio.TimeoutError as e:
                last_exc = e
                logger.warning(f"⚠️ [Orchestrator] AI 생성 타임아웃 ({attempt}/{max_attempts})")
            except Exception as e:
                last_exc = e
                if attempt < max_attempts:
                    wait = 2 ** attempt  # 2s, 4s
                    logger.warning(f"⚠️ [Orchestrator] AI 생성 {attempt}/{max_attempts} 실패: {e} — {wait}초 후 재시도")
                    await asyncio.sleep(wait)
        logger.error(f"❌ [Orchestrator] AI 생성 {max_attempts}회 모두 실패: {last_exc} — 기본 원고 사용")
        return f"제목: [오류] AI 원고 생성 실패\n현재 설정된 AI 엔진(API 키)에 문제가 발생했습니다.\n\n[상세 오류 내용]\n{str(last_exc)}\n\n* Gemini의 경우: 무료 크레딧 소진 또는 결제 필요\n* Claude의 경우: 계정 잔액 부족 또는 API 키 만료\n위 내용을 확인해주세요."

    async def execute_multi_blog_workflow(
        self,
        accounts: list,
        keyword: str = None,
        interval_mins: int = 5,
        wash_images: bool = False,
        image_folder_path: str = None,
        generated_contents: list = None,
        **kwargs
    ):
        logger.info(f"🔄 [Orchestrator] 다중 계정 워크플로우 시작 (총 {len(accounts)}계정, 텀: {interval_mins}분)")
        log_callback = kwargs.pop("log_callback", None)
        results = []
        
        for idx, acc in enumerate(accounts):
            account_id = acc.get("id")
            account_pw = acc.get("pw")
            
            # USB 테더링 IP 변경 처리
            use_tethering = kwargs.get("use_tethering", False)
            if use_tethering:
                if log_callback:
                    log_callback("📱 [Orchestrator] USB 테더링 IP 전환 중...")
                new_ip = await self.proxy_manager.rotate_tethering_ip()
                if log_callback:
                    log_callback(f"✨ [Orchestrator] 할당된 IP: {new_ip}")
            
            if log_callback:
                log_callback(f"🚀 [{idx+1}/{len(accounts)}] 계정 {account_id} 작업 시작...")
                
            # 사전 생성된 원고(generated_contents)에서 매칭되는 계정 찾기
            manual_title = None
            manual_content = None
            current_keyword = keyword
            post_mode = kwargs.get("post_mode", "ai_generate")
            
            if generated_contents:
                for gc in generated_contents:
                    if gc.get("account_id") == account_id:
                        manual_title = gc.get("title")
                        manual_content = gc.get("content")
                        if gc.get("keyword"):
                            current_keyword = gc.get("keyword")
                        post_mode = "manual_text"
                        break
                        
            # 실행 (계정별 예외 격리 — 한 계정 실패가 전체 배치를 중단시키지 않도록)
            try:
                result = await self.execute_blog_workflow(
                    account_id=account_id,
                    account_pw=account_pw,
                    keyword=current_keyword,
                    post_mode=post_mode,
                    manual_title=manual_title,
                    manual_content=manual_content,
                    wash_images=wash_images,
                    image_folder_path=image_folder_path,
                    **kwargs
                )
            except Exception as e:
                logger.error(f"❌ [Orchestrator] '{account_id}' 워크플로우 예외: {e}")
                result = {"success": False, "account_id": account_id, "error": str(e)}
            results.append(result)

            if log_callback:
                if result and result.get("success"):
                    log_callback(f"✅ [{account_id}] 포스팅 완료")
                else:
                    err = (result.get('error') if result else None) or '실패(발행 미완료 또는 상세 메시지 없음)'
                    log_callback(f"⚠️ [{account_id}] 작업 실패: {err}")
            
            # 대기 (마지막 계정이 아니면)
            if idx < len(accounts) - 1:
                if result and result.get("success"):
                    wait_sec = interval_mins * 60
                    if log_callback:
                        log_callback(f"⏳ 다음 계정 작업을 위해 {interval_mins}분 ({wait_sec}초) 대기합니다...")
                    await asyncio.sleep(wait_sec)
                else:
                    if log_callback:
                        log_callback(f"⏳ 작업 실패로 인해 긴 대기를 생략하고 10초 후 다음 계정으로 넘어갑니다...")
                    await asyncio.sleep(10)
                
        if log_callback:
            log_callback("🎉 모든 다중 계정 포스팅이 종료되었습니다.")
        return {"success": True}

    # ═══════════════════════════════════════════════
    # 단일 계정 워크플로우
    # ═══════════════════════════════════════════════

    async def execute_blog_workflow(
        self, 
        account_id: str, 
        keyword: str, 
        account_pw: str = None,
        test_image: str = None, 
        speed_mode: str = "normal", 
        speed_multiplier: float = 1.0,
        publish_mode: str = "instant",
        schedule_date: str = None,
        schedule_time: str = None,
        proxy: str = None,
        ai_provider: str = "claude",
        reference_data: dict = None,
        post_purpose: str = None,
        promo_type: str = None,
        distribution_mode: str = None,
        post_mode: str = "ai_generate",
        manual_title: str = None,
        manual_content: str = None,
        wash_images: bool = False,
        image_folder_path: str = None,
        source_data: str = None,
        generate_card_news: bool = False,
        **kwargs
    ):
        proxy_config = self.proxy_manager.get_browser_proxy_config(proxy)
        proxy_label = f"프록시: {proxy[:30]}..." if proxy else "직접 연결"
        
        logger.info(f"🚀 [Orchestrator] 워크플로우 시작: {account_id} / {keyword}")
        logger.info(f"⚡ 속도: {speed_mode} x{speed_multiplier} | 발행: {publish_mode} | {proxy_label}")
        
        async with async_playwright() as p:
            # 1. 환경 설정 (샌드박스 비활성화 및 안정화 옵션 추가)
            logger.info("🌐 [Orchestrator] 브라우저 엔진 시작 중...")
            try:
                # 계정별 영구 프로필 → 네이버가 '신뢰 기기'로 기억하여 2단계 인증 재요구를 줄임
                profile_dir = self.session_manager.get_profile_dir(account_id)
                self.session_manager.clear_stale_locks(account_id)  # 이전 비정상 종료 잠금 정리
                persistent_opts = dict(
                    headless=False,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                )
                if proxy_config:
                    persistent_opts["proxy"] = proxy_config
                context = await p.chromium.launch_persistent_context(profile_dir, **persistent_opts)
            except Exception as e:
                logger.info(f"❌ [Orchestrator] 브라우저 실행 실패: {e}")
                return {"success": False, "error": f"브라우저 실행 실패: {e}"}

            # 영구 프로필이 세션을 보유 → 등록(기기 인증) 완료 여부로 로그인 필요성 판단
            has_session = self.session_manager.is_registered(account_id)
            # 하위호환: 예전 쿠키 파일이 있으면 함께 주입
            await self.session_manager.load_session(context, account_id)
            page = context.pages[0] if context.pages else await context.new_page()
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
            
            if not has_session:
                pw = account_pw or os.getenv("NAVER_PW", "")
                ok = await self.authenticator.login_with_bypass(page, account_id, pw)
                if ok:
                    self.session_manager.mark_registered(account_id)
                await self.session_manager.save_session(context, account_id)
            
            
            # IP 확인 (프록시 검증)
            current_ip = await self.proxy_manager.verify_ip(page)
            logger.info(f"🌐 [Orchestrator] 현재 IP: {current_ip}")
            
            await page.goto(f"https://blog.naver.com/{account_id}")
            
            # 세션 만료 검증 및 재로그인 처리
            await asyncio.sleep(2)
            
            # 다이렉트 글쓰기 URL로 진입하여 로그인 여부 확실하게 검증
            write_url = f"https://blog.naver.com/PostWriteForm.naver?blogId={account_id}"
            await page.goto(write_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            is_logged_out = "nidlogin" in page.url or "nid.naver.com" in page.url
            
            if is_logged_out:
                logger.info("⚠️ [Orchestrator] 기존 세션이 만료되어 비로그인 상태입니다. 재로그인을 시도합니다.")
                pw = account_pw or os.getenv("NAVER_PW", "")
                success = await self.authenticator.login_with_bypass(page, account_id, pw)
                if not success:
                    error_msg = "로그인 실패: 비밀번호 오류이거나 2단계 인증/새로운 기기 차단입니다. 계정 관리에서 '계정 등록(기기 인증)'을 1회 실행해 수동 로그인+2단계 인증을 통과시켜 주세요. 이후에는 자동 로그인됩니다."
                    logger.error(f"❌ [Orchestrator] {error_msg}")
                    return {"success": False, "error": error_msg}
                self.session_manager.mark_registered(account_id)
                await self.session_manager.save_session(context, account_id)
                # 로그인 완료 후 다시 글쓰기 폼으로 이동
                await page.goto(write_url, wait_until="domcontentloaded")
            
            # 3. 콘텐츠 준비
            if post_mode == "manual_text" and manual_content:
                blog_content = manual_content
                blog_title = manual_title if manual_title else f"{keyword} 후기"
            else:
                # AI 생성 모드 등 다른 모드
                blog_title = f"{keyword} 후기"
                logger.info(f"🤖 [Orchestrator] AI 원고 생성 시작... (Provider: {ai_provider})")
                blog_content = await self._generate_content_with_retry(
                    keyword, ai_provider=ai_provider, reference_data=reference_data,
                    post_purpose=post_purpose, promo_type=promo_type, distribution_mode=distribution_mode,
                    source_data=source_data
                )
                if blog_content:
                    import re
                    blog_content = re.sub(r'(\*\*|~~|__)', '', blog_content)
            
            # 본문에 [제목]이 포함되어 있다면 추출해서 실제 제목으로 사용
            if blog_content:
                import re
                title_match = re.search(r'^\s*\[제목\](.*?)(?:\n|$)', blog_content)
                if title_match:
                    blog_title = title_match.group(1).strip()
                    blog_content = re.sub(r'^\s*\[제목\].*?\n+', '', blog_content, count=1).strip()
            
            # 4. 이미지 세척 및 준비
            washed_images = []
            
            # (A) 폴더 연동 방식
            if image_folder_path and os.path.exists(image_folder_path):
                logger.info(f"📂 [Orchestrator] 로컬 폴더 연동 시작: {image_folder_path}")
                img_paths = glob.glob(os.path.join(image_folder_path, "*.jpg")) + glob.glob(os.path.join(image_folder_path, "*.png"))
                if len(img_paths) > 0:
                    selected_imgs = random.sample(img_paths, min(3, len(img_paths))) # 최대 3장 추출
                    for idx, img in enumerate(selected_imgs):
                        if wash_images:
                            washed_name = f"washed_{account_id}_{idx}.jpg"
                            washed = self.armor.wash_image(img, washed_name)
                            if washed: washed_images.append(washed)
                        else:
                            washed_images.append(img)
            
            # (B) 테스트 이미지 (기존 방식)
            if not washed_images and test_image:
                logger.info("🖼️ [Orchestrator] 기본 이미지 세척 중...")
                washed_img = self.armor.wash_image(test_image, f"washed_{account_id}.jpg") if wash_images else test_image
                if washed_img: washed_images.append(washed_img)
            elif not washed_images and generate_card_news:
                logger.info("[Orchestrator] 등록된 이미지가 없어 AI 카드 뉴스 이미지(5장)를 자동 생성합니다.")
                # 카드 제목: '테스트'/빈 키워드면 실제 글 제목을 사용
                card_title = keyword if (keyword and keyword.strip() and keyword.strip() != "테스트") else (blog_title or "정보")
                card_title = str(card_title).strip().lstrip("[").rstrip("]")[:30]
                card_paths = self.card_news.generate_card_set(card_title, content=blog_content, count=5)
                for idx_c, gp in enumerate(card_paths):
                    if not gp:
                        continue
                    washed_img = self.armor.wash_image(gp, f"washed_gen_{account_id}_{idx_c}.jpg")
                    if washed_img:
                        washed_images.append(washed_img)

            # 4. 글쓰기 자동 진입 및 에디터 감지
            logger.info("📝 [Orchestrator] 네이버 에디터 진입 시도...")
            await self.blog.auto_enter_editor(page, account_id)
            editor_frame = await self.blog.wait_for_editor(context, page)
            
            # 5. 세션 업데이트
            await self.session_manager.save_session(context, account_id)

            # 6. 포스팅 작업 수행 (이미지와 텍스트 교차 삽입)
            await self.blog.dismiss_popups(editor_frame)
            await self.blog.write_post(
                editor_frame, blog_title, blog_content,
                images=washed_images,
                speed_mode=speed_mode, speed_multiplier=speed_multiplier
            )

            # 7. 발행 처리
            publish_result = False
            if publish_mode in ["now", "instant"]:
                publish_result = await self.blog.publish_now(editor_frame)
            elif publish_mode == "schedule":
                if schedule_date and schedule_time:
                    publish_result = await self.blog.schedule_publish(editor_frame, schedule_date, schedule_time)
                else:
                    logger.info("⚠️ [Orchestrator] 예약 발행에는 날짜와 시간이 필요합니다.")
            else:
                logger.info("🏁 [Orchestrator] 수동 발행 모드: 직접 [발행] 버튼을 눌러주세요. (발행 완료 전까지 화면이 유지됩니다)")
                publish_result = True
                try:
                    while "editor" in page.url:
                        await asyncio.sleep(2)
                    logger.info("✅ 수동 발행이 확인되었습니다. 다음 단계로 넘어갑니다.")
                except Exception:
                    pass

            return {
                "account_id": account_id,
                "keyword": keyword,
                "ip": current_ip,
                "publish_mode": publish_mode,
                "success": publish_result
            }

    # ═══════════════════════════════════════════════
    # 계정 등록 (기기 인증) — 1회 수동 로그인으로 영구 프로필을 신뢰 기기로 등록
    # ═══════════════════════════════════════════════

    async def register_account_session(self, account_id: str, account_pw: str = None, log_callback=None):
        """
        계정 전용 영구 프로필로 브라우저를 열어 사용자가 1회 수동 로그인(+2단계 인증)을
        완료하게 한 뒤 '신뢰 기기'로 등록한다. 이후 자동 포스팅은 2단계 인증 없이 로그인된다.
        """
        def _log(msg):
            logger.info(msg)
            if log_callback:
                try:
                    log_callback(msg)
                except Exception:
                    pass

        _log(f"🔐 [등록] '{account_id}' 기기 인증 시작. 열리는 브라우저 창에서 로그인을 완료해 주세요. (최대 4분)")
        async with async_playwright() as p:
            context = None
            try:
                profile_dir = self.session_manager.get_profile_dir(account_id)
                self.session_manager.clear_stale_locks(account_id)  # 이전 비정상 종료 잠금 정리
                context = await p.chromium.launch_persistent_context(
                    profile_dir,
                    headless=False,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                )
                page = context.pages[0] if context.pages else await context.new_page()
                page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

                pw = account_pw or os.getenv("NAVER_PW", "")
                success = await self.authenticator.login_with_bypass(page, account_id, pw, manual_wait_secs=240)
                if success:
                    self.session_manager.mark_registered(account_id)
                    await self.session_manager.save_session(context, account_id)
                    _log(f"✅ [등록] '{account_id}' 기기 인증 완료! 이후 자동 로그인됩니다.")
                    return {"success": True, "account_id": account_id}
                _log(f"❌ [등록] '{account_id}' 기기 인증 실패(시간 초과 또는 미완료).")
                return {"success": False, "account_id": account_id, "error": "기기 인증 미완료(시간 초과). 다시 시도해 주세요."}
            except Exception as e:
                _log(f"⚠️ [등록] 오류: {e}")
                return {"success": False, "account_id": account_id, "error": str(e)}
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass

    # ═══════════════════════════════════════════════
    # 멀티 계정 순차 워크플로우
    # ═══════════════════════════════════════════════

    async def execute_multi_workflow(self, accounts: list, global_config: dict = None):
        """
        여러 계정을 순차적으로 실행합니다.
        
        Args:
            accounts: 계정 설정 리스트
            global_config: 전역 설정 (speed_mode, speed_multiplier 등)
        """
        config = global_config or {}
        results = []
        total = len(accounts)
        
        logger.info("\n" + "═" * 50)
        logger.info(f"🚀 [멀티 계정 모드] 총 {total}개 계정 순차 실행")
        logger.info("═" * 50)
        
        for idx, account in enumerate(accounts):
            account_id = account["id"]
            keyword = account.get("keyword", "블로그 후기")
            
            logger.info(f"\n{'─' * 50}")
            logger.info(f"📌 [{idx+1}/{total}] 계정: {account_id}")
            logger.info(f"{'─' * 50}")
            
            # USB 테더링 IP 변경 처리
            if config.get("use_tethering"):
                logger.info("📱 [Orchestrator] USB 테더링 IP 전환 중...")
                new_ip = await self.proxy_manager.rotate_tethering_ip()
                logger.info(f"✨ [Orchestrator] 할당된 IP: {new_ip}")
            
            try:
                result = await self.execute_blog_workflow(
                    account_id=account_id,
                    keyword=keyword,
                    test_image=account.get("image", config.get("image")),
                    speed_mode=account.get("speed_mode", config.get("speed_mode", "normal")),
                    speed_multiplier=account.get("speed_multiplier", config.get("speed_multiplier", 1.0)),
                    publish_mode=account.get("publish_mode", config.get("publish_mode", "none")),
                    schedule_date=account.get("date"),
                    schedule_time=account.get("time"),
                    proxy=account.get("proxy")
                )
                results.append(result)
                
            except Exception as e:
                logger.info(f"❌ [{account_id}] 실행 실패: {e}")
                results.append({
                    "account_id": account_id,
                    "keyword": keyword,
                    "ip": "N/A",
                    "publish_mode": account.get("publish_mode", "none"),
                    "success": False,
                    "error": str(e)
                })
            
            # 마지막 계정이 아니면 대기
            if idx < total - 1:
                if result and result.get("success"):
                    delay = self.proxy_manager.get_random_delay(
                        min_sec=config.get("min_delay", 180),
                        max_sec=config.get("max_delay", 600)
                    )
                    logger.info(f"\n⏳ 다음 계정까지 {delay}초 ({delay//60}분 {delay%60}초) 대기 중...")
                    await asyncio.sleep(delay)
                else:
                    logger.info(f"\n⏳ 이전 계정 작업 실패로 긴 대기를 생략하고 10초 후 다음 계정으로 전환합니다...")
                    await asyncio.sleep(10)
        
        # 실행 결과 리포트
        self._print_report(results)
        return results
    
    def _print_report(self, results: list):
        """실행 결과 리포트 출력"""
        logger.info("\n" + "═" * 55)
        logger.info("📊 멀티 계정 실행 결과 리포트")
        logger.info("═" * 55)
        
        for idx, r in enumerate(results):
            status = "✅ 성공" if r.get("success") else "❌ 실패"
            mode_label = {
                "now": "즉시 발행",
                "schedule": "예약 발행",
                "none": "수동 발행"
            }.get(r.get("publish_mode", "none"), "수동")
            
            error_msg = f" ({r.get('error', '')[:30]})" if r.get("error") else ""
            
            logger.info(f"  [{idx+1}] {r['account_id']:15s} | {r['keyword']:10s} | IP: {r.get('ip','N/A'):15s} | {mode_label} | {status}{error_msg}")
        
        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"\n  총 {len(results)}건 중 {success_count}건 성공")
        logger.info("═" * 55)

    # ═══════════════════════════════════════════════
    # 카페 워크플로우
    # ═══════════════════════════════════════════════
    
    async def execute_cafe_workflow(
        self,
        account_id: str,
        cafe_id: str,
        board_name: str,
        keyword: str,
        title: str = None,
        test_image: str = None,
        speed_mode: str = "normal",
        speed_multiplier: float = 1.0,
        auto_submit: bool = False,
        ai_provider: str = "claude",
        action_type: str = "post",
        content: str = None,
        reference_data: dict = None,
        proxy: str = None,
        naver_pw: str = None
    ):
        """네이버 카페 자동 포스팅 워크플로우"""
        proxy_config = self.proxy_manager.get_browser_proxy_config(proxy)
        
        logger.info(f"\n☕ [Orchestrator] 카페 워크플로우 시작")
        logger.info(f"   계정: {account_id} | 카페: {cafe_id} | 게시판: {board_name}")
        logger.info(f"   키워드: {keyword} | 자동등록: {'ON' if auto_submit else 'OFF'}")
        
        async with async_playwright() as p:
            context = None
            try:
                # 계정별 영구 프로필 (네이버 신뢰 기기 유지 → 2단계 인증 재요구 감소)
                profile_dir = self.session_manager.get_profile_dir(account_id)
                self.session_manager.clear_stale_locks(account_id)  # 이전 비정상 종료 잠금 정리
                persistent_opts = dict(
                    headless=False,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                )
                if proxy_config:
                    persistent_opts["proxy"] = proxy_config
                context = await p.chromium.launch_persistent_context(profile_dir, **persistent_opts)

                # 1. 세션 준비 및 로그인 (영구 프로필 등록 여부로 판단)
                has_session = self.session_manager.is_registered(account_id)
                await self.session_manager.load_session(context, account_id)
                page = context.pages[0] if context.pages else await context.new_page()

                if not has_session:
                    pw = naver_pw or os.getenv("NAVER_PW", "")
                    ok = await self.authenticator.login_with_bypass(page, account_id, pw)
                    if ok:
                        self.session_manager.mark_registered(account_id)
                    await self.session_manager.save_session(context, account_id)
                
                
                # IP 확인
                current_ip = await self.proxy_manager.verify_ip(page)
                logger.info(f"🌐 현재 IP: {current_ip}")
                
                # 2. 카페 진입
                await self.cafe.navigate_to_cafe(page, cafe_id)
                
                if action_type == "comment":
                    logger.info("[Orchestrator] 카페 댓글 자동화 시작...")
                    # 3. 게시판 진입
                    board_success = await self.cafe.navigate_to_board(page, cafe_id, board_name)
                    if board_success:
                        # 4. 게시글 순회 및 댓글 작성
                        await self.cafe.auto_comment_loop(
                            page=page,
                            keyword=keyword,
                            limit=5,
                            content=content,
                            ai_provider=ai_provider,
                            soul=self.soul
                        )
                        submit_result = True
                        logger.info("🏁 [Orchestrator] 카페 자동 댓글 작업이 완료되었습니다.")
                    else:
                        submit_result = False
                        logger.info("⚠️ [Orchestrator] 게시판 진입 실패로 댓글 자동화를 중단합니다.")
                    
                    self.db.log_cafe(account_id=account_id, cafe_id=cafe_id, keyword=keyword, status="성공" if submit_result else "실패")
                    return {
                        "account_id": account_id,
                        "cafe_id": cafe_id,
                        "keyword": keyword,
                        "ip": current_ip,
                        "success": submit_result
                    }
                
                else:
                    # 3. AI 콘텐츠 생성
                    logger.info("[Orchestrator] AI 카페 원고 생성 중...")
                    if content:
                        cafe_content = content
                    else:
                        cafe_content = await self._generate_content_with_retry(keyword, ai_provider=ai_provider, reference_data=reference_data)
                    
                    # 4. 이미지 세척 / 대체
                    washed_images = []
                    if test_image:
                        washed_images.append(self.armor.wash_image(test_image, f"washed_cafe_{account_id}.jpg"))
                    else:
                        logger.info("[Orchestrator] 등록된 이미지가 없어 AI 카드 뉴스 이미지(5장)를 자동 생성합니다.")
                        card_title = keyword if (keyword and keyword.strip() and keyword.strip() != "테스트") else (title or "정보")
                        card_title = str(card_title).strip().lstrip("[").rstrip("]")[:30]
                        for idx_c, gp in enumerate(self.card_news.generate_card_set(card_title, content=cafe_content, count=5)):
                            if not gp:
                                continue
                            wimg = self.armor.wash_image(gp, f"washed_gen_cafe_{account_id}_{idx_c}.jpg")
                            if wimg:
                                washed_images.append(wimg)
                    
                    # 5. 글쓰기 진입
                    await self.cafe.auto_enter_editor(page)
                    editor_frame = await self.cafe.wait_for_editor(context, page)
                    
                    # 6. 세션 업데이트
                    await self.session_manager.save_session(context, account_id)
                    
                    # 7. 팝업 제거 및 게시판 선택
                    await self.cafe.dismiss_popups(editor_frame)
                    await self.cafe.select_board(editor_frame, board_name)
                    
                    # 본문에 [제목]이 포함되어 있다면 추출해서 실제 제목으로 사용
                    if cafe_content:
                        import re
                        title_match = re.search(r'^\s*\[제목\](.*?)(?:\n|$)', cafe_content)
                        if title_match:
                            extracted_title = title_match.group(1).strip()
                            if not title:
                                title = extracted_title
                            cafe_content = re.sub(r'^\s*\[제목\].*?\n+', '', cafe_content, count=1).strip()
                            
                    # 8. 원고 타이핑
                    post_title = title if title else f"{keyword} 관련 테스트"
                    await self.cafe.write_post(
                        editor_frame, post_title, cafe_content,
                        speed_mode=speed_mode, speed_multiplier=speed_multiplier
                    )
                    
                    # 9. 이미지 업로드
                    if washed_images:
                        await self.cafe.upload_images(editor_frame, washed_images)
                    
                    # 10. 등록
                    if auto_submit:
                        submit_result = await self.cafe.submit_post(editor_frame)
                    else:
                        logger.info("🏁 [Orchestrator] 수동 등록 모드: 직접 [등록] 버튼을 눌러주세요.")
                        submit_result = True
                    logger.info("\n✅ [Orchestrator] 카페 태스크 완료.")
                    self.db.log_cafe(account_id=account_id, cafe_id=cafe_id, keyword=keyword, status="성공" if submit_result else "실패")
                    
                    return {
                        "account_id": account_id,
                        "cafe_id": cafe_id,
                        "keyword": keyword,
                        "ip": current_ip,
                        "success": submit_result
                    }
            except asyncio.CancelledError:
                logger.info("🛑 [Orchestrator] 카페 작업이 취소되었습니다. 브라우저를 강제 종료합니다.")
                raise
            except Exception as e:
                logger.info(f"⚠️ [Orchestrator] 카페 워크플로우 오류: {e}")
                self.db.log_cafe(account_id=account_id, cafe_id=cafe_id, keyword=keyword, status=f"실패: {str(e)[:50]}")
                return {"account_id": account_id, "success": False, "error": str(e)}
            finally:
                if context:
                    try:
                        await context.close()
                    except: pass

    # ═══════════════════════════════════════════════
    # 카페 다중 계정 타겟 댓글 워크플로우
    # ═══════════════════════════════════════════════

    async def execute_targeted_multi_cafe_workflow(
        self,
        accounts_data: list,
        target_urls: list,
        keyword: str,
        ai_provider: str = "claude",
        delay_min: int = 30,
        delay_max: int = 60,
        logger_func=None
    ):
        """다중 계정으로 특정 게시글 URL들을 순회하며 댓글 작업 (여론 형성 모드)"""
        if not logger_func:
            logger_func = logger.info
            
        logger_func("\n" + "═" * 50)
        logger_func(f"🚀 [다중 타겟 모드] 계정 {len(accounts_data)}개로 {len(target_urls)}개 타겟 작업 시작")
        logger_func("═" * 50)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            
            try:
                for acc_idx, acc in enumerate(accounts_data):
                    account_id = acc["id"]
                    pw = acc.get("pw", "")
                    
                    logger_func(f"\n👉 [{acc_idx+1}/{len(accounts_data)}] 계정 로그인: {account_id}")
                    
                    context = await browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    
                    # 로그인
                    await self.authenticator.login_with_bypass(page, account_id, pw)
                    await asyncio.sleep(2)
                    
                    # 타겟 URL 순회
                    for url_idx, target_url in enumerate(target_urls):
                        logger_func(f"  🔗 타겟 접속 ({url_idx+1}/{len(target_urls)}): {target_url}")
                        
                        try:
                            await page.goto(target_url)
                            await asyncio.sleep(random.randint(3, 5))
                            
                            # 1. 카페 본문 읽기
                            cafe_frame = page.frame(name="cafe_main")
                            if not cafe_frame:
                                logger_func("  ⚠️ cafe_main 프레임을 찾을 수 없습니다.")
                                continue
                                
                            content_loc = cafe_frame.locator(".se-main-container, .se-content, .ContentRenderer")
                            post_content_text = ""
                            if await content_loc.count() > 0:
                                post_content_text = await content_loc.first.inner_text()
                                
                            # 2. AI 댓글 생성
                            prompt = f"다음 카페글 본문에 대해 '{keyword}'의 뉘앙스로 자연스럽게 동조/호응하는 짧은 1문장 댓글을 달아줘. 본문: {post_content_text[:300]}"
                            try:
                                comment_text = await self.soul.rewrite_for_blog("", prompt, provider=ai_provider)
                            except Exception as e:
                                logger_func(f"  ⚠️ AI 생성 오류: {e}")
                                comment_text = f"잘 읽었습니다! ({keyword})"
                                
                            logger_func(f"  💬 작성 댓글: {comment_text}")
                            
                            # 3. 댓글 달기
                            comment_input = cafe_frame.locator(".comment_inbox_text")
                            if await comment_input.count() > 0:
                                await comment_input.first.click()
                                await asyncio.sleep(0.5)
                                await self.stealth_engine.human_type(cafe_frame, ".comment_inbox_text", comment_text)
                                await asyncio.sleep(1)
                                
                                submit_btn = cafe_frame.locator(".btn_register")
                                if await submit_btn.count() > 0:
                                    await submit_btn.first.click()
                                    logger_func("  ✅ 등록 완료")
                                    self.db.log_cafe(account_id=account_id, cafe_id=target_url, keyword=keyword, status="타겟 댓글 성공")
                                else:
                                    logger_func("  ⚠️ 등록 버튼 찾기 실패")
                            else:
                                logger_func("  ⚠️ 댓글 입력창을 찾을 수 없습니다. (막힘 또는 에러)")
                                
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            logger_func(f"  ⚠️ 작업 중 예외 발생: {e}")
                            
                        # 마지막 타겟이 아니면 딜레이
                        if url_idx < len(target_urls) - 1:
                            delay = random.randint(delay_min, delay_max)
                            logger_func(f"  ⏳ {delay}초 대기...")
                            await asyncio.sleep(delay)
                    
                    # 컨텍스트(세션) 종료 후 다음 계정으로
                    await context.close()
                    
                    if acc_idx < len(accounts_data) - 1:
                        logger_func(f"⏳ 계정 전환을 위해 10초 대기...")
                        await asyncio.sleep(10)
                        
                logger_func("🎉 다중 타겟 댓글 작업 종료")
                return True
            except asyncio.CancelledError:
                logger_func("🛑 다중 타겟 댓글 작업이 강제 취소되었습니다.")
                raise
            finally:
                if browser:
                    try:
                        await browser.close()
                    except: pass

from contextvars import ContextVar
task_logger = ContextVar("task_logger", default=print)
