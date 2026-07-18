import asyncio
import os
import random
import re
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

# 현재 실행 중인 자동화 브라우저 페이지 레지스트리 (account_id -> playwright Page)
# 사이드바 '진행 중 작업' 클릭 시 해당 브라우저 창을 앞으로 가져오기 위해 사용.
RUNNING_PAGES = {}

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
        account_pw: str = None,
        limit: int = 5,
        do_like: bool = True,
        do_comment: bool = True,
        comment_msg: str = None,
        do_neighbor: bool = True,
        neighbor_msg: str = "서로이웃 해요!",
        proxy: str = None,
        min_delay: int = 30,
        max_delay: int = 120,
        stop_event=None
    ):
        """블로그 소통(공감/댓글/이웃) 워크플로우"""
        proxy_config = self.proxy_manager.get_browser_proxy_config(proxy)
        # 진행 상황을 UI 모니터링 로그로 전달 (communication 라우터가 task_logger.set 으로 주입)
        try:
            report = task_logger.get()
        except Exception:
            report = print

        logger.info(f"🚀 [Orchestrator] 블로그 소통 워크플로우 시작: {account_id}")

        async with async_playwright() as p:
            # 계정별 영구 프로필 → '기기 인증(1회 수동 로그인)' 세션을 재사용해 로그인 유지
            profile_dir = self.session_manager.get_profile_dir(account_id)
            self.session_manager.clear_stale_locks(account_id)  # 이전 비정상 종료 잠금/좀비 크롬 정리
            persistent_opts = dict(
                headless=False,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                viewport={'width': 1280, 'height': 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )
            if proxy_config:
                persistent_opts["proxy"] = proxy_config
            try:
                context = await p.chromium.launch_persistent_context(profile_dir, **persistent_opts)
            except Exception as e:
                report(f"❌ 브라우저 실행 실패: {e}")
                return {"success": False, "error": f"브라우저 실행 실패: {e}"}

            page = context.pages[0] if context.pages else await context.new_page()
            RUNNING_PAGES[account_id] = page
            page.on("dialog", lambda d: asyncio.create_task(d.accept()))

            # 1. 로그인 확인 (기기 인증된 영구 프로필은 이미 로그인 상태)
            if not self.session_manager.is_registered(account_id):
                report("로그인 세션이 없어 로그인을 시도합니다. (캡챠/2단계 인증은 창에서 직접 완료해 주세요)")
                pw = account_pw or os.getenv("NAVER_PW", "")
                ok = await self.authenticator.login_with_bypass(page, account_id, pw, manual_wait_secs=180)
                if ok:
                    self.session_manager.mark_registered(account_id)
                    report("✅ 로그인 완료")
                else:
                    report("⚠️ 로그인이 확인되지 않았습니다. [계정 관리 > 기기인증]을 먼저 1회 진행하면 이후 자동 로그인됩니다. (공감/댓글/이웃추가는 로그인 상태라야 동작)")

            # 2. 타겟 수집
            report(f"'{keyword}' 검색에서 대상 블로그 수집 중...")
            targets = await self.neighbor.find_targets_from_search(page, keyword, limit=limit)
            report(f"대상 블로그 {len(targets)}곳을 찾았습니다.")

            results = []
            for idx, target in enumerate(targets):
                if stop_event is not None and stop_event.is_set():
                    report("⏹ 사용자 요청으로 중지되었습니다.")
                    break
                target_id = target["id"]
                post_url = target["post_url"]
                report(f"[{idx+1}/{len(targets)}] {target_id} 방문 중...")

                try:
                    await page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(random.randint(3, 7))  # 체류 시간 흉내

                    # 블로그 본문·공감·댓글은 mainFrame iframe 내부에 있음
                    frame = page.frame(name="mainFrame")
                    content_target = frame if frame else page

                    actions = []
                    # 공감
                    if do_like:
                        liked = await self.neighbor.click_like(content_target)
                        actions.append("공감✓" if liked else "공감✗")

                    # 댓글
                    comment_text = ""
                    if do_comment:
                        if comment_msg and comment_msg.strip():
                            comment_text = comment_msg
                        else:
                            comment_text = await self._generate_content_with_retry(f"{keyword} 관련해서 잘 읽었습니다!")
                        commented = await self.neighbor.leave_comment(content_target, comment_text)
                        actions.append("댓글✓" if commented else "댓글✗")

                    # 이웃 추가 (모바일 폼 사용 — 별도 페이지 이동)
                    if do_neighbor:
                        added = await self.neighbor.add_neighbor(page, target_id, message=neighbor_msg)
                        actions.append("이웃✓" if added else "이웃✗")

                    report(f"   → {target_id}: {', '.join(actions) if actions else '액션 없음'}")
                    self.db.log_engagement(target_url=post_url, action_type="소통", comment_text=comment_text if do_comment else "공감/이웃", status="성공")
                    results.append({"id": target_id, "success": True, "actions": actions})

                    # 다음 작업 전 대기 (마지막 타겟 제외) — 대기 중에도 중지 요청에 즉시 반응
                    if idx < len(targets) - 1:
                        delay = random.randint(min_delay, max_delay)
                        report(f"   ⏳ 다음 방문까지 {delay}초 대기...")
                        if stop_event is not None:
                            try:
                                await asyncio.wait_for(stop_event.wait(), timeout=delay)
                                report("⏹ 사용자 요청으로 중지되었습니다.")
                                break
                            except asyncio.TimeoutError:
                                pass
                        else:
                            await asyncio.sleep(delay)

                except PlaywrightTimeoutError as e:
                    report(f"   ⚠️ {target_id} 타임아웃")
                    self.db.log_engagement(target_url=post_url, action_type="소통", comment_text="", status="실패: 타임아웃")
                    results.append({"id": target_id, "success": False, "error": "Timeout"})
                except Exception as e:
                    report(f"   ⚠️ {target_id} 오류: {e}")
                    self.db.log_engagement(target_url=post_url, action_type="소통", comment_text="", status=f"실패: {e}")
                    results.append({"id": target_id, "success": False, "error": str(e)})

            try:
                await context.close()
            except Exception:
                pass
            return results


    # ═══════════════════════════════════════════════
    # 공통 헬퍼
    # ═══════════════════════════════════════════════

    def _strip_markdown(self, text: str) -> str:
        """네이버 에디터에서 자동 서식(굵게/취소선/헤딩/리스트)으로 오변환되는 마크다운 기호 제거."""
        import re
        if not text:
            return text
        text = re.sub(r'(\*\*+|~~+|__+|`+)', '', text)                    # **굵게** ~~취소선~~ __ `코드`
        text = re.sub(r'^\s{0,3}#{1,6}\s*', '', text, flags=re.MULTILINE)  # ## 헤딩
        text = re.sub(r'^\s{0,3}[-*]\s+', '', text, flags=re.MULTILINE)    # - / * 리스트 기호
        text = re.sub(r'^\s{0,3}\d+[.)]\s+', '', text, flags=re.MULTILINE)  # 1. 2. 번호 (네이버 자동 번호목록 방지)
        text = re.sub(r'^\s*[-–—=]{2,}\s*$', '', text, flags=re.MULTILINE)  # --- === 구분선 줄
        return text

    @staticmethod
    def _align_card_markers(content: str, n_images: int) -> str:
        """카드 이미지를 [표지=맨 위] + 본문 곳곳에 '분산' 배치하도록 [이미지] 마커를 재정렬.
        우선순위: 소제목(■/[소제목]) 앞 → 부족하면 단락 경계(빈 줄)에 균등 분산.
        (소제목이 적은 카페 글에서 이미지가 맨 끝에 몰리는 문제 방지)"""
        if not content or n_images <= 0:
            return content
        content = re.sub(r'\s*\[이미지\]\s*', '\n', content)  # 기존 마커 제거
        BULLETS = "■▶◆●▣◼▪□▷"
        lines = content.split('\n')

        head_pos, para_pos = [], []
        for idx, line in enumerate(lines):
            s = line.strip()
            if s.startswith("[소제목]") or (len(s) > 0 and s[0] in BULLETS and len(s) <= 50):
                head_pos.append(idx)
            elif s == "":
                para_pos.append(idx)

        rest = max(0, n_images - 1)              # 표지 1장 제외
        positions = list(head_pos[:rest])        # 1순위: 소제목 앞
        if len(positions) < rest and para_pos:   # 부족분: 단락 경계에 균등 분산
            need = rest - len(positions)
            step = max(1, len(para_pos) // need)
            for p in para_pos[::step]:
                if p not in positions:
                    positions.append(p)
                if len(positions) >= rest:
                    break
        pos_set = set(positions)

        out = ["[이미지]"]   # 표지(첫 카드)는 본문 맨 위
        for idx, line in enumerate(lines):
            if idx in pos_set:
                out.append("[이미지]")
            out.append(line)
        return "\n".join(out)

    @staticmethod
    def _append_source_link(content: str, source_data: str) -> str:
        """source_data 의 [링크] http... 를 본문 끝에 출처로 덧붙인다 (유효 URL 있을 때만)."""
        if not content or not source_data:
            return content
        m = re.search(r"\[링크\]\s*(https?://\S+)", source_data)
        if not m:
            return content
        url = m.group(1).strip()
        if url in content:  # 이미 포함되어 있으면 중복 방지
            return content
        return f"{content}\n\n▶ 자세히 보기: {url}"

    async def _generate_content_with_retry(
        self, keyword: str, max_attempts: int = 3, timeout: float = 120.0, ai_provider: str = "claude", reference_data: dict = None,
        post_purpose: str = None, promo_type: str = None, distribution_mode: str = None, source_data: str = None, api_key: str = None,
        prompt_category: str = None, include_source_link: bool = False, sub_keywords: list = None, custom_prompt: str = None
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

        # 서브(연관) 키워드 — 본문에 자연스럽게 녹여 SEO 강화
        sub_list = [k.strip() for k in (sub_keywords or []) if k and k.strip()][:5]
        if sub_list:
            enhanced_keyword = (
                f"{enhanced_keyword}\n\n[서브 키워드(연관 키워드)] 다음 키워드를 본문에 "
                f"각각 1~2회씩 문맥에 어울리게 자연스럽게 포함해 검색 노출을 강화하세요(키워드 나열 금지): "
                f"{', '.join(sub_list)}"
            )

        # 검색량 기반 '메인+롱테일' 제목 최적화 — 재시도 전 1회만 계산(실패해도 원고 생성엔 지장 없음)
        title_main = (keyword or "").splitlines()[0].strip() if keyword else ""
        long_tail = None
        if title_main:
            try:
                from mbam_nextgen.services.keyword_seo import suggest_seo_title_keywords
                _sk = await suggest_seo_title_keywords(title_main)
                long_tail = _sk.get("long_tail")
                if long_tail:
                    logger.info(f"📊 [Orchestrator] 제목 SEO: 메인='{title_main}' + 롱테일='{long_tail}'")
                else:
                    logger.info(f"📊 [Orchestrator] 제목 SEO: 롱테일 후보 없음(메인만 사용) — '{title_main}'")
            except Exception as e:
                logger.warning(f"⚠️ [Orchestrator] 제목 SEO 키워드 계산 실패(무시): {e}")

        for attempt in range(1, max_attempts + 1):
            try:
                content = await asyncio.wait_for(
                    self.soul.rewrite_for_blog("", enhanced_keyword, provider=ai_provider,
                                               post_purpose=post_purpose, promo_type=promo_type, distribution_mode=distribution_mode, api_key=api_key,
                                               prompt_category=prompt_category, custom_prompt=custom_prompt,
                                               long_tail=long_tail, title_main=title_main),
                    timeout=timeout,
                )
                logger.info(f"✅ [Orchestrator] 원고 생성 완료 ({attempt}회차)")
                if include_source_link:
                    content = self._append_source_link(content, source_data)
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
                    proxy=acc.get("proxy"),
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
                
        ok = sum(1 for r in results if r and r.get("success"))
        if log_callback:
            log_callback(f"🎉 다중 계정 포스팅 종료: 성공 {ok} / 총 {len(results)}건")
        return {"success": ok > 0, "succeeded": ok, "total": len(results), "results": results}

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
        prompt_category: str = None,   # 관리자 프롬프트 카테고리(예: 'blog_daily' 매일 자동배포)
        custom_prompt: str = None,     # 잡 payload로 주입된 프롬프트 원문(에이전트 로컬 파일 없이 적용)
        post_mode: str = "ai_generate",
        manual_title: str = None,
        manual_content: str = None,
        wash_images: bool = False,
        image_folder_path: str = None,
        source_data: str = None,
        generate_card_news: bool = False,
        generate_ai_images: bool = False,   # 나노바나나(Gemini) AI 이미지 자동 생성·삽입 (병원 등)
        ai_supplement_count: int = 0,        # 실사진이 있어도 AI 연출컷을 N장 추가(상품 블로그 등)
        blog_id: str = None,   # 로그인ID와 다른 실제 블로그 주소(예: bonetacasa). 있으면 다이렉트 진입에 사용
        **kwargs
    ):
        proxy_config = self.proxy_manager.get_browser_proxy_config(proxy)
        # 로그엔 인증정보 노출 없이 서버 호스트만 표기
        proxy_label = f"프록시: {(proxy_config or {}).get('server', '?')}" if proxy_config else "직접 연결"

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
            RUNNING_PAGES[account_id] = page  # 진행 중 브라우저 추적(사이드바에서 앞으로 가져오기)
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
                    try:
                        self.db.log_blog(account_id=account_id, target_keyword=keyword, status="실패: 로그인", result_url="")
                    except Exception:
                        pass
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
                    source_data=source_data, prompt_category=prompt_category, custom_prompt=custom_prompt
                )

            # 마크다운 기호 제거 (모든 모드 공통) — 네이버 에디터의 굵게/취소선/헤딩/리스트 자동변환 방지
            if blog_content:
                blog_content = self._strip_markdown(blog_content)
            
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

            # (A') 실사진 + AI 연출컷 보조 — 실사진이 있어도 나노바나나 연출컷을 N장 추가(상품 블로그 등)
            #      제품 실물은 실사진으로, 연출컷은 분위기/사용장면(실물 재현 X)으로 보강.
            if washed_images and int(ai_supplement_count or 0) > 0:
                try:
                    from mbam_nextgen.services.soul import SoulRewriter
                    import uuid as _uuid_sup
                    _soul = SoulRewriter()
                    _n = max(1, min(int(ai_supplement_count), 3))
                    _prompts = await _soul.generate_blog_image_prompts(
                        title=blog_title, content=blog_content, keyword=keyword, category="product", n=_n)
                    if _prompts:
                        _out = os.path.join(os.getcwd(), "generated_images", "ai", f"{account_id}_sup_{_uuid_sup.uuid4().hex[:6]}")
                        _paths = await _soul.generate_images(_prompts, _out, filename_prefix=f"aisup_{account_id}")
                        for _i, _gp in enumerate(_paths):
                            _w = self.armor.wash_image(_gp, f"washed_aisup_{account_id}_{_i}.jpg") if wash_images else _gp
                            washed_images.append(_w if _w else _gp)
                        logger.info(f"[Orchestrator] AI 연출컷 {len(_paths)}장 추가 (실사진+연출컷 총 {len(washed_images)}장)")
                        blog_content = self._align_card_markers(blog_content, len(washed_images))
                except Exception as _e:
                    logger.error(f"[Orchestrator] AI 연출컷 추가 실패(무시): {_e}")

            # (B) 테스트 이미지 (기존 방식)
            if not washed_images and test_image:
                logger.info("🖼️ [Orchestrator] 기본 이미지 세척 중...")
                washed_img = self.armor.wash_image(test_image, f"washed_{account_id}.jpg") if wash_images else test_image
                if washed_img: washed_images.append(washed_img)
            elif not washed_images and generate_ai_images:
                # (B') 나노바나나(Gemini) AI 이미지 자동 생성 — 사용자 이미지가 없을 때 본문 기반으로 생성
                logger.info("[Orchestrator] 등록된 이미지가 없어 AI 이미지(나노바나나 5장)를 자동 생성합니다.")
                try:
                    from mbam_nextgen.services.soul import SoulRewriter
                    import uuid
                    soul = SoulRewriter()
                    img_prompts = await soul.generate_blog_image_prompts(
                        title=blog_title, content=blog_content, keyword=keyword,
                        category=promo_type, n=5
                    )
                    if img_prompts:
                        ai_out = os.path.join(os.getcwd(), "generated_images", "ai", f"{account_id}_{uuid.uuid4().hex[:8]}")
                        ai_paths = await soul.generate_images(img_prompts, ai_out, filename_prefix=f"ai_{account_id}")
                        for idx_a, gp in enumerate(ai_paths):
                            washed = self.armor.wash_image(gp, f"washed_ai_{account_id}_{idx_a}.jpg")
                            washed_images.append(washed if washed else gp)
                        logger.info(f"[Orchestrator] AI 이미지 {len(washed_images)}장 생성 완료")
                    else:
                        logger.info("[Orchestrator] AI 이미지 프롬프트 생성 실패 → 이미지 없이 진행")
                except Exception as e:
                    logger.error(f"[Orchestrator] AI 이미지 생성 실패: {e}")
                # 생성된 이미지를 소제목 위치에 분산 배치(표지 + 본문 곳곳)
                if washed_images:
                    blog_content = self._align_card_markers(blog_content, len(washed_images))
            elif not washed_images and generate_card_news:
                logger.info("[Orchestrator] 등록된 이미지가 없어 AI 카드 뉴스 이미지(5장)를 자동 생성합니다.")
                # 카드 제목: '테스트'/빈 키워드면 실제 글 제목을 사용
                card_title = keyword if (keyword and keyword.strip() and keyword.strip() != "테스트") else (blog_title or "정보")
                card_title = str(card_title).strip().lstrip("[").rstrip("]")[:30]
                card_paths = await self.card_news.generate_cards(card_title, content=blog_content, count=5)
                for idx_c, gp in enumerate(card_paths):
                    if not gp:
                        continue
                    washed_img = self.armor.wash_image(gp, f"washed_gen_{account_id}_{idx_c}.jpg")
                    if washed_img:
                        washed_images.append(washed_img)
                # 카드(표지 + 소제목별)를 소제목 위치에 맞춰 배치: 본문 [이미지] 마커 재정렬
                blog_content = self._align_card_markers(blog_content, len(washed_images))

            # 4. 글쓰기 자동 진입 및 에디터 감지
            # blog_id(블로그 주소)가 화면에서 안 넘어왔으면 계정관리(DB)에 저장된 값을 자동 조회.
            # → 로그인ID≠블로그주소 계정(ch_2101/bonetacasa)이 어느 경로로 발행하든 적용됨.
            if not blog_id:
                try:
                    from mbam_nextgen.backend.database import SessionLocal, NaverAccount
                    _db = SessionLocal()
                    try:
                        acc = (_db.query(NaverAccount)
                               .filter(NaverAccount.naver_id == account_id, NaverAccount.blog_addr.isnot(None))
                               .order_by(NaverAccount.created_at.desc()).first())
                        if acc and (acc.blog_addr or "").strip():
                            blog_id = acc.blog_addr.strip()
                            logger.info(f"[Orchestrator] ({account_id}) 계정관리 저장값에서 블로그 주소 사용: {blog_id}")
                    finally:
                        _db.close()
                except Exception as e:
                    logger.info(f"[Orchestrator] 블로그 주소 조회 실패: {e}")

            logger.info(f"🖼️ [Orchestrator] ({account_id}) 이미지 준비 완료: {len(washed_images)}장")
            logger.info("📝 [Orchestrator] 네이버 에디터 진입 시도...")
            await self.blog.auto_enter_editor(page, account_id, blog_id=blog_id)
            editor_frame = await self.blog.wait_for_editor(context, page)
            logger.info(f"✅ [Orchestrator] ({account_id}) 에디터 프레임 확보: {getattr(editor_frame, 'name', '?')}")
            
            # 5. 세션 업데이트
            await self.session_manager.save_session(context, account_id)

            # 6. 포스팅 작업 수행 (이미지와 텍스트 교차 삽입)
            await self.blog.dismiss_popups(editor_frame)
            await self.blog.write_post(
                editor_frame, blog_title, blog_content,
                images=washed_images,
                speed_mode=speed_mode, speed_multiplier=speed_multiplier
            )

            # 6.5 지도(장소) 삽입 — 본문 작성 후 글 하단에 추가
            _insert_map = kwargs.get("insert_map")
            _map_query = (kwargs.get("map_query") or "").strip()
            if _insert_map and _map_query:
                try:
                    await self.blog.insert_place_map(editor_frame, _map_query)
                except Exception as _e:
                    logger.error(f"[Orchestrator] 지도 삽입 중 오류(무시): {_e}")

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

            # 대시보드 '블로그 자동화' 작업내역 기록
            result_url = ""
            try:
                cur_url = page.url
                result_url = cur_url if ("PostWriteForm" not in cur_url and "editor" not in cur_url) else ""
                logger.info(f"📌 [Orchestrator] {account_id} 발행 결과: {'성공' if publish_result else '발행 미완료'} | URL: {result_url or '(편집화면 유지)'}")
                self.db.log_blog(account_id=account_id, target_keyword=keyword,
                                 status="성공" if publish_result else "발행 미완료", result_url=result_url,
                                 post_title=(blog_title or ""))
            except Exception:
                pass

            return {
                "account_id": account_id,
                "keyword": keyword,
                "ip": current_ip,
                "publish_mode": publish_mode,
                "success": publish_result,
                "result_url": result_url,
                "title": (blog_title or keyword or "").strip(),
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
                RUNNING_PAGES[account_id] = page  # 진행 중 브라우저 추적(사이드바에서 앞으로 가져오기)
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
    # 티스토리 (카카오 로그인 → 에디터 자동화) — 공식 API 없어 브라우저 자동화
    #   ★에디터/발행 버튼 셀렉터는 실계정으로 1회 튜닝 필요(주석 표시 지점)
    # ═══════════════════════════════════════════════

    def _tistory_profile_key(self, account_id: str) -> str:
        return f"tistory_{account_id}"

    async def register_tistory_session(self, account_id: str, log_callback=None):
        """티스토리(카카오) 1회 수동 로그인 → 영구 프로필을 신뢰 기기로 등록(이후 자동 발행)."""
        def _log(msg):
            logger.info(msg)
            if log_callback:
                try:
                    log_callback(msg)
                except Exception:
                    pass

        pkey = self._tistory_profile_key(account_id)
        _log(f"🔐 [티스토리 등록] '{account_id}' 로그인 창을 엽니다. 카카오 로그인을 완료해 주세요. (최대 4분)")
        async with async_playwright() as p:
            context = None
            try:
                profile_dir = self.session_manager.get_profile_dir(pkey)
                self.session_manager.clear_stale_locks(pkey)
                context = await p.chromium.launch_persistent_context(
                    profile_dir, headless=False,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="ko-KR", timezone_id="Asia/Seoul",
                )
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto("https://www.tistory.com/auth/login", wait_until="domcontentloaded", timeout=30000)
                # 로그인 성공 판정: auth/login·kakao 페이지를 벗어나 tistory.com 으로 돌아오면 완료
                logged_in = False
                for _ in range(80):  # 최대 ~4분
                    await asyncio.sleep(3)
                    url = page.url or ""
                    if "tistory.com" in url and "auth/login" not in url and "accounts.kakao" not in url:
                        logged_in = True
                        break
                if logged_in:
                    self.session_manager.mark_registered(pkey)
                    await self.session_manager.save_session(context, pkey)
                    _log("✅ [티스토리 등록] 로그인 완료! 이후 자동 발행됩니다.")
                    return {"success": True, "account_id": account_id}
                return {"success": False, "account_id": account_id, "error": "로그인 미완료(시간 초과). 다시 시도해 주세요."}
            except Exception as e:
                _log(f"⚠️ [티스토리 등록] 오류: {e}")
                return {"success": False, "account_id": account_id, "error": str(e)}
            finally:
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass

    async def execute_tistory_workflow(self, account_id: str, blog_name: str, keyword: str,
                                       title: str = None, content: str = None, source_data: str = None,
                                       ai_provider: str = "gemini", prompt_category: str = "tistory",
                                       auto_submit: bool = True):
        """티스토리 글 발행: 영구 프로필(로그인 유지) → 글쓰기 → 제목/본문 → 발행."""
        import re as _re
        async with async_playwright() as p:
            context = None
            try:
                pkey = self._tistory_profile_key(account_id)
                profile_dir = self.session_manager.get_profile_dir(pkey)
                self.session_manager.clear_stale_locks(pkey)
                context = await p.chromium.launch_persistent_context(
                    profile_dir, headless=False,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="ko-KR", timezone_id="Asia/Seoul",
                )
                page = context.pages[0] if context.pages else await context.new_page()

                # 1. 원고 생성(글감을 티스토리 프롬프트로 재작성)
                if content and not source_data:
                    source_data = content
                blog_text = await self._generate_content_with_retry(
                    keyword, ai_provider=ai_provider, source_data=source_data, prompt_category=prompt_category)
                blog_text = self._strip_markdown(blog_text or "")
                post_title = title or keyword
                m = _re.search(r'^\s*\[제목\](.*?)(?:\n|$)', blog_text)
                if m:
                    post_title = m.group(1).strip()
                    blog_text = _re.sub(r'^\s*\[제목\].*?\n+', '', blog_text, count=1).strip()
                blog_text = blog_text.replace("[이미지]", "").strip()  # 티스토리는 자동 이미지 미지원 — 텍스트만

                # 2. 글쓰기 페이지 진입
                write_url = f"https://{blog_name}.tistory.com/manage/newpost/"
                await page.goto(write_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                if "auth/login" in (page.url or "") or "accounts.kakao" in (page.url or ""):
                    return {"success": False, "error": "로그인 세션 만료 — 티스토리 기기 인증을 다시 해주세요."}
                try:
                    await page.keyboard.press("Escape")  # '작성 중인 글 이어쓰기' 등 팝업 닫기(best effort)
                except Exception:
                    pass

                # 3. 제목 입력  ★셀렉터 튜닝 지점
                try:
                    title_sel = "#post-title-inp, input#title, textarea#title, textarea[placeholder*='제목']"
                    await page.wait_for_selector(title_sel, timeout=15000)
                    await page.fill(title_sel, post_title)
                except Exception as e:
                    logger.warning(f"[Tistory] 제목 입력 실패(셀렉터 튜닝 필요): {e}")

                # 4. 본문 입력 — 에디터 iframe/contenteditable  ★셀렉터 튜닝 지점
                try:
                    frame = None
                    for f in page.frames:
                        if "editor" in (f.name or "") or "mce" in (f.url or ""):
                            frame = f
                            break
                    target = frame or page
                    body_sel = "body#tinymce, .mce-content-body, [contenteditable='true']"
                    await target.wait_for_selector(body_sel, timeout=15000)
                    await target.click(body_sel)
                    await page.keyboard.type(blog_text, delay=8)
                except Exception as e:
                    logger.warning(f"[Tistory] 본문 입력 실패(셀렉터 튜닝 필요): {e}")

                result_url = ""
                if auto_submit:
                    # 5. 발행: 완료 → 공개 발행  ★셀렉터 튜닝 지점
                    try:
                        await page.click("button.btn-post, #publish-layer-btn, button:has-text('완료')", timeout=10000)
                        await asyncio.sleep(1)
                        await page.click("#publish-btn, button:has-text('공개 발행'), button:has-text('발행')", timeout=10000)
                        await asyncio.sleep(3)
                        result_url = page.url if "manage" not in (page.url or "") else ""
                    except Exception as e:
                        logger.warning(f"[Tistory] 발행 버튼 실패(셀렉터 튜닝 필요): {e}")

                logger.info(f"[Tistory] 발행 처리 완료 | 제목: {post_title} | URL: {result_url or '(확인필요)'}")
                return {"success": True, "title": post_title, "result_url": result_url}
            except Exception as e:
                logger.error(f"[Tistory] 워크플로우 오류: {e}")
                return {"success": False, "error": str(e)}
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
                    blog_id=(account.get("blogAddr") or account.get("blog_id") or "").strip() or None,
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
    
    async def execute_cafe_boost(self, account_id: str, post_url: str, do_view: bool = True,
                                 do_like: bool = False, visits: int = 1, naver_pw: str = None,
                                 use_tethering: bool = False, visit_interval_min: int = 30):
        """게시글 부스트: 대상 카페 글을 방문해 조회수를 올리고(반복 방문) 좋아요를 누른다.
        방문은 visit_interval_min(분) 간격으로 분산 수행하며, 대기 중에는 브라우저를 닫아 리소스를 점유하지 않는다.
        좋아요는 첫 방문에서 1회만 누른다. post_url이 카페 메인 주소면 방문(육성)만 수행."""
        import asyncio as _aio, random as _rnd, re as _re
        n = max(1, int(visits or 1))
        # 카페 메인 주소면 '방문 육성' → 공지 제외 랜덤 일반글을 둘러보고 나오는 자연 브라우징 수행
        _is_main = not _re.search(r'/articles?/|ArticleRead|articleid=', str(post_url or ''), _re.I)
        interval = max(0, int(visit_interval_min or 0)) * 60
        logger.info(f"\n👍 [Orchestrator] 카페 부스트 | 계정:{account_id} | 방문:{n}회 | 간격:{visit_interval_min}분 | 좋아요:{do_like}")
        logger.info(f"   대상: {post_url}")

        liked = False
        ok_visits = 0
        for v in range(n):
            # 방문마다 IP 회전(테더링) → 조회가 서로 다른 IP로 인정되도록
            if use_tethering:
                try:
                    new_ip = await self.proxy_manager.rotate_tethering_ip()
                    logger.info(f"✨ [Orchestrator] 방문 {v+1} IP: {new_ip}")
                except Exception as e:
                    logger.warning(f"⚠️ 테더링 실패(계속): {e}")
            # 방문마다 브라우저 열고 → 방문/좋아요 → 닫기 (대기 시간엔 미점유)
            async with async_playwright() as p:
                context = None
                try:
                    profile_dir = self.session_manager.get_profile_dir(account_id)
                    self.session_manager.clear_stale_locks(account_id)
                    context = await p.chromium.launch_persistent_context(
                        profile_dir, headless=False,
                        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                        viewport={'width': 1920, 'height': 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        locale="ko-KR", timezone_id="Asia/Seoul",
                    )
                    has_session = self.session_manager.is_registered(account_id)
                    await self.session_manager.load_session(context, account_id)
                    page = context.pages[0] if context.pages else await context.new_page()
                    if not has_session:
                        pw = naver_pw or os.getenv("NAVER_PW", "")
                        if await self.authenticator.login_with_bypass(page, account_id, pw):
                            self.session_manager.mark_registered(account_id)
                        await self.session_manager.save_session(context, account_id)

                    await page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
                    await _aio.sleep(_rnd.uniform(2.5, 5.0))  # 체류(조회수 인정)
                    try:
                        await page.evaluate("window.scrollBy(0, 600)")
                    except Exception:
                        pass
                    await _aio.sleep(_rnd.uniform(1.0, 2.5))
                    # 방문 육성(카페 메인): 공지 제외 랜덤 일반글 1~2개 열람 → 읽고 → 목록 복귀
                    if _is_main:
                        try:
                            await self.cafe.natural_browse(page, n_posts=_rnd.randint(1, 2), logger=logger)
                        except Exception as e:
                            logger.warning(f"자연 브라우징 실패(계속): {e}")
                    if do_like and not liked:
                        try:
                            liked = await self.cafe.click_like(page)
                        except Exception as e:
                            logger.warning(f"좋아요 클릭 실패: {e}")
                    ok_visits += 1
                    logger.info(f"   - 방문 {v+1}/{n} 완료" + (" (좋아요)" if (do_like and liked) else ""))
                except Exception as e:
                    logger.error(f"방문 {v+1}/{n} 실패: {e}")
                finally:
                    if context:
                        try:
                            await context.close()
                        except Exception:
                            pass
            # 다음 방문 전 텀 대기(브라우저 닫힌 상태)
            if v < n - 1 and interval > 0:
                logger.info(f"⏳ [Orchestrator] 다음 방문까지 {interval // 60}분 대기...")
                await _aio.sleep(interval)

        self.db.log_cafe(account_id=account_id, cafe_id=post_url, keyword="부스트", status="성공" if ok_visits else "실패")
        return {"success": ok_visits > 0, "visits": ok_visits, "liked": liked}

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
        naver_pw: str = None,
        source_data: str = None,
        prompt_category: str = None,
        include_source_link: bool = False,
        image_folder_path: str = None,
        use_tethering: bool = False,
        generate_card_news: bool = True,   # 첨부 이미지 없을 때 AI 카드뉴스 자동 생성 여부
        card_count: int = 3,               # 카드뉴스 장수
        insert_map: bool = False,          # 본문 하단에 네이버 장소(지도) 삽입
        map_query: str = None              # 삽입할 장소명/주소
    ):
        """네이버 카페 자동 포스팅 워크플로우"""
        proxy_config = self.proxy_manager.get_browser_proxy_config(proxy)

        logger.info(f"\n☕ [Orchestrator] 카페 워크플로우 시작")
        logger.info(f"   계정: {account_id} | 카페: {cafe_id} | 게시판: {board_name}")
        logger.info(f"   키워드: {keyword} | 자동등록: {'ON' if auto_submit else 'OFF'}")

        # USB 테더링 IP 변경 처리 (계정 발행 전 IP 회전)
        if use_tethering:
            try:
                logger.info("📱 [Orchestrator] USB 테더링 IP 전환 중...")
                new_ip = await self.proxy_manager.rotate_tethering_ip()
                logger.info(f"✨ [Orchestrator] 할당된 IP: {new_ip}")
            except Exception as e:
                logger.warning(f"⚠️ [Orchestrator] 테더링 IP 전환 실패(계속 진행): {e}")
        
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
                RUNNING_PAGES[account_id] = page  # 진행 중 브라우저 추적(사이드바에서 앞으로 가져오기)

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
                    # 사진 매핑 원고: 맛집 사진 비전 생성이 이미 '[이미지:N]'(입구컷부터 순서)로 사진 자리를
                    # 정해둔 경우 → 재생성/재정렬하지 않고 그대로 사용(사진↔글 매칭·순서 보존).
                    import re as _re_map
                    has_photo_map = bool(content and _re_map.search(r'\[이미지:\s*\d+\]', content))
                    if has_photo_map:
                        logger.info("[Orchestrator] 사진 매핑 원고 감지 — 재생성/재정렬 없이 그대로 사용([이미지:N] 순서 보존)")
                        cafe_content = content
                    elif prompt_category and (content or source_data):
                        # 글감수집 등 지정 프롬프트로 AI 생성 (content/source_data를 소스로 사용)
                        cafe_content = await self._generate_content_with_retry(
                            keyword, ai_provider=ai_provider, reference_data=reference_data,
                            source_data=(source_data or content), prompt_category=prompt_category,
                            include_source_link=include_source_link)
                    elif content:
                        cafe_content = content
                    else:
                        cafe_content = await self._generate_content_with_retry(
                            keyword, ai_provider=ai_provider, reference_data=reference_data,
                            source_data=source_data, prompt_category=prompt_category,
                            include_source_link=include_source_link)
                    cafe_content = self._strip_markdown(cafe_content)

                    # 4. 이미지 세척 / 대체
                    washed_images = []
                    _img_folder = image_folder_path
                    if _img_folder and os.path.isdir(_img_folder):
                        # 사용자가 첨부한 이미지(글감 생성용 업로드 등)를 글에 첨부
                        import glob as _glob
                        files = sorted(_glob.glob(os.path.join(_img_folder, "*")))
                        for idx_f, fp in enumerate(files):
                            if fp.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                                wimg = self.armor.wash_image(fp, f"washed_cafe_up_{account_id}_{idx_f}.jpg")
                                if wimg:
                                    washed_images.append(wimg)
                        logger.info(f"[Orchestrator] 첨부 이미지 폴더에서 {len(washed_images)}장 사용")
                    _n_cards = max(1, int(card_count or 3))
                    if washed_images:
                        pass
                    elif test_image:
                        washed_images.append(self.armor.wash_image(test_image, f"washed_cafe_{account_id}.jpg"))
                    elif generate_card_news:
                        logger.info(f"[Orchestrator] 등록된 이미지가 없어 AI 카드 뉴스 이미지({_n_cards}장)를 자동 생성합니다.")
                        card_title = keyword if (keyword and keyword.strip() and keyword.strip() != "테스트") else (title or "정보")
                        card_title = str(card_title).strip().lstrip("[").rstrip("]")[:30]
                        for idx_c, gp in enumerate(await self.card_news.generate_cards(card_title, content=cafe_content, count=_n_cards)):
                            if not gp:
                                continue
                            wimg = self.armor.wash_image(gp, f"washed_gen_cafe_{account_id}_{idx_c}.jpg")
                            if wimg:
                                washed_images.append(wimg)
                    else:
                        logger.info("[Orchestrator] 카드뉴스 생성 꺼짐 — 이미지 없이 텍스트만 발행합니다.")
                    
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

                    # 카드(표지+소제목별)를 소제목 위치에 맞춰 배치 (블로그와 동일)
                    # 단, 사진 매핑 원고([이미지:N])는 이미 AI가 순서·위치를 정했으므로 재정렬하지 않는다.
                    if not has_photo_map:
                        cafe_content = self._align_card_markers(cafe_content, len(washed_images))

                    # 8. 원고 타이핑 (이미지를 [이미지] 마커 위치에 인라인 삽입)
                    post_title = title if title else f"{keyword} 관련 테스트"
                    await self.cafe.write_post(
                        editor_frame, post_title, cafe_content,
                        images=washed_images,
                        speed_mode=speed_mode, speed_multiplier=speed_multiplier
                    )

                    # 9.5 지도(장소) 삽입 — 본문 작성 후 글 하단에 추가 (블로그와 동일)
                    _map_q = (map_query or "").strip()
                    if insert_map and _map_q:
                        try:
                            await self.cafe.insert_place_map(editor_frame, _map_q)
                        except Exception as _e:
                            logger.error(f"[Orchestrator] 카페 지도 삽입 중 오류(무시): {_e}")

                    # 10. 등록
                    if auto_submit:
                        submit_result = await self.cafe.submit_post(editor_frame)
                    else:
                        logger.info("🏁 [Orchestrator] 수동 등록 모드: 직접 [등록] 버튼을 눌러주세요.")
                        submit_result = True
                    logger.info("\n✅ [Orchestrator] 카페 태스크 완료.")
                    self.db.log_cafe(account_id=account_id, cafe_id=cafe_id, keyword=keyword, status="성공" if submit_result else "실패", post_title=(post_title or ""))

                    # 발행된 글 URL 캡처(best-effort) — 등록 성공 시 보통 작성 글로 리다이렉트됨
                    result_url = ""
                    try:
                        await asyncio.sleep(1.5)
                        cur = page.url or ""
                        if submit_result and "cafe.naver.com" in cur and "write" not in cur.lower() and "articlewrite" not in cur.lower():
                            result_url = cur
                    except Exception:
                        pass

                    return {
                        "account_id": account_id,
                        "cafe_id": cafe_id,
                        "keyword": keyword,
                        "title": (post_title or "").strip(),
                        "ip": current_ip,
                        "success": submit_result,
                        "result_url": result_url,
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
        use_tethering: bool = False,
        comment_content: str = "",
        do_like: bool = True,
        logger_func=None,
        stop_event=None,
    ):
        """다중 계정으로 특정 카페 게시글 URL들을 순회하며 댓글 작업 (여론 형성 모드).

        do_like: True면 댓글 작성과 함께 게시글 좋아요(공감)도 누름.

        comment_content: 직접 입력한 댓글 내용. 여러 줄이면 게시글/계정마다 무작위로 하나 선택.
                         비어 있으면 keyword 뉘앙스로 AI 자동 생성(폴백).

        재작성 포인트:
        - 계정별 영구 프로필(기기인증) 로그인 재사용 (블로그 소통과 동일 방식)
        - (옵션) USB 테더링으로 계정마다 IP 로테이션 + 현재 IP 로그
        - 신형 카페(ca-fe SPA) 대응: cafe_main iframe 내부 .se-main-container 본문 읽기,
          댓글창은 다중 폴백 셀렉터로 탐색 + 실패 시 DOM 덤프(로그인 상태 셀렉터 확정용)
        - 인코딩 안전 로깅 + 취소(CancelledError) 즉시 반응
        """
        import os
        import time as _time
        if not logger_func:
            logger_func = logger.info

        def _safe(msg):
            try:
                logger_func(msg)
            except Exception:
                try:
                    logger_func(str(msg).encode("ascii", "replace").decode("ascii"))
                except Exception:
                    pass

        # 직접 입력 댓글(여러 줄 = 여러 후보). 있으면 AI 대신 이 중에서 무작위 선택.
        manual_comments = [l.strip() for l in (comment_content or "").splitlines() if l.strip()]

        _safe("═" * 40)
        _safe(f"🚀 [다중 타겟 댓글] 계정 {len(accounts_data)}개 × 타겟 {len(target_urls)}개 시작 "
              f"(댓글={'직접입력 ' + str(len(manual_comments)) + '개' if manual_comments else 'AI 자동'}, "
              f"테더링={'ON' if use_tethering else 'OFF'})")

        async def _write_comment(cafe_frame, text):
            """신형 ca-fe 댓글창에 댓글 작성. 성공 True. 댓글창 못 찾으면 DOM 덤프."""
            try:
                await cafe_frame.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.2)
            except Exception:
                pass
            input_sels = [
                "textarea.comment_inbox_text", ".comment_inbox_text",
                ".CommentWriter textarea", ".comment_inbox textarea",
                "textarea[placeholder*='댓글']", "[class*=comment] textarea",
                "div.comment_inbox_text[contenteditable=true]",
                ".CommentWriter [contenteditable=true]",
            ]
            chosen = None
            for s in input_sels:
                try:
                    loc = cafe_frame.locator(s).first
                    if await loc.count() > 0 and await loc.is_visible():
                        chosen = (s, loc)
                        break
                except Exception:
                    continue
            if not chosen:
                try:
                    html = await cafe_frame.evaluate(
                        "() => { const a = document.querySelector('[class*=Comment], [class*=comment], #cmt, .comment_area');"
                        " return a ? a.outerHTML.slice(0,5000) : document.body.innerHTML.slice(0,5000); }"
                    )
                    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
                    os.makedirs(log_dir, exist_ok=True)
                    path = os.path.join(log_dir, f"cafe_comment_dom_{int(_time.time())}.html")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(html or "")
                    _safe(f"  ⚠️ 댓글창 못 찾음 — 로그인 상태 DOM 덤프 저장: {path} (이 파일 주시면 셀렉터 확정)")
                except Exception as e:
                    _safe(f"  ⚠️ 댓글창 못 찾음 (덤프 실패: {e})")
                return False
            sel, loc = chosen
            try:
                await loc.click()
                await asyncio.sleep(0.4)
                if "textarea" in sel:
                    await loc.fill(text)
                else:
                    await loc.type(text, delay=30)
            except Exception:
                try:
                    await self.stealth_engine.human_type(cafe_frame, sel, text)
                except Exception as e:
                    _safe(f"  ⚠️ 댓글 입력 실패: {e}")
                    return False
            await asyncio.sleep(0.8)
            submit_sels = [
                ".btn_register", "a.btn_register", "button.btn_register",
                "button:has-text('등록')", "a:has-text('등록')",
                ".CommentWriter button[type=submit]",
            ]
            for s in submit_sels:
                try:
                    btn = cafe_frame.locator(s).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1.5)
                        return True
                except Exception:
                    continue
            _safe("  ⚠️ 등록 버튼 못 찾음")
            return False

        async def _click_like(cafe_frame):
            """게시글 좋아요(공감) 버튼 클릭. 신형 카페 LikeIt 위젯(.ReactionLikeIt). 이미 눌렀으면 건너뜀."""
            like_sels = [
                ".ReactionLikeIt", "a.ReactionLikeIt", "button.ReactionLikeIt",
                ".u_likeit_list_btn", "a.u_likeit_list_btn",
                ".like_article .u_likeit_list_btn", "[class*=LikeIt]:not([class*=count])",
                "a:has-text('좋아요')",
            ]
            for s in like_sels:
                try:
                    btn = cafe_frame.locator(s).first
                    if await btn.count() == 0 or not await btn.is_visible():
                        continue
                    # 이미 눌린 상태면(on/selected) 건너뜀
                    cls = (await btn.get_attribute("class")) or ""
                    pressed = (await btn.get_attribute("aria-pressed")) or ""
                    if "on" in cls.split() or "is-selected" in cls or pressed == "true":
                        _safe("  ❤️ 이미 좋아요 상태 — 건너뜀")
                        return True
                    await btn.click()
                    await asyncio.sleep(1.0)
                    _safe("  ❤️ 좋아요 완료")
                    return True
                except Exception:
                    continue
            _safe("  ⚠️ 좋아요 버튼 못 찾음")
            return False

        async def _interruptible_sleep(seconds):
            for _ in range(int(seconds)):
                if stop_event is not None and stop_event.is_set():
                    return
                await asyncio.sleep(1)

        async with async_playwright() as p:
            for acc_idx, acc in enumerate(accounts_data):
                if stop_event is not None and stop_event.is_set():
                    _safe("⏹ 중지 요청으로 종료합니다.")
                    break
                account_id = acc["id"]
                pw = acc.get("pw", "")
                _safe(f"👉 [{acc_idx+1}/{len(accounts_data)}] 계정: {account_id}")

                # (옵션) USB 테더링 IP 로테이션 — 계정마다 새 IP
                if use_tethering:
                    _safe("📶 USB 테더링 IP 변경 중...")
                    try:
                        new_ip = await self.proxy_manager.rotate_tethering_ip()
                        _safe(f"  ✨ 새 IP: {new_ip}")
                    except Exception as e:
                        _safe(f"  ⚠️ 테더링 IP 변경 실패(계속 진행): {e}")

                profile_dir = self.session_manager.get_profile_dir(account_id)
                self.session_manager.clear_stale_locks(account_id)
                try:
                    context = await p.chromium.launch_persistent_context(
                        profile_dir,
                        headless=False,
                        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                        viewport={'width': 1280, 'height': 900},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        locale="ko-KR",
                        timezone_id="Asia/Seoul",
                    )
                except Exception as e:
                    _safe(f"  ❌ 브라우저 실행 실패: {e}")
                    continue

                page = context.pages[0] if context.pages else await context.new_page()
                page.on("dialog", lambda d: asyncio.create_task(d.accept()))

                try:
                    # 로그인 확인 (기기인증된 영구 프로필은 이미 로그인 상태)
                    if not self.session_manager.is_registered(account_id):
                        _safe("  🔑 로그인 세션 없음 → 로그인 시도 (캡챠/2단계는 창에서 직접 완료)")
                        ok = await self.authenticator.login_with_bypass(page, account_id, pw, manual_wait_secs=180)
                        if ok:
                            self.session_manager.mark_registered(account_id)
                            _safe("  ✅ 로그인 완료")
                        else:
                            _safe("  ⚠️ 로그인 미확인 — [계정관리 > 기기인증] 1회 진행 필요 (댓글은 로그인 상태라야 동작)")

                    try:
                        cur_ip = await self.proxy_manager.verify_ip(page)
                        _safe(f"  🌐 현재 IP: {cur_ip}")
                    except Exception:
                        pass

                    for url_idx, target_url in enumerate(target_urls):
                        if stop_event is not None and stop_event.is_set():
                            _safe("⏹ 중지 요청"); break
                        _safe(f"  🔗 ({url_idx+1}/{len(target_urls)}) {target_url}")
                        try:
                            await page.goto(target_url, timeout=20000)
                            await asyncio.sleep(random.randint(3, 5))

                            cafe_frame = page.frame(name="cafe_main")
                            if not cafe_frame:
                                _safe("  ⚠️ cafe_main 프레임 없음 — 스킵")
                                continue

                            # 본문 읽기 (신형 ca-fe: .se-main-container 확인됨)
                            content_text = ""
                            try:
                                cl = cafe_frame.locator(".se-main-container, .ArticleContentBox, .article_viewer").first
                                if await cl.count() > 0:
                                    content_text = (await cl.inner_text())[:400]
                            except Exception:
                                pass

                            # 댓글 결정 — ① 직접 입력(있으면 무작위 선택) ② 없으면 AI 자동 생성
                            if manual_comments:
                                comment_text = random.choice(manual_comments)
                            else:
                                prompt = (f"다음 카페글에 '{keyword}' 뉘앙스로 자연스럽게 호응하는 짧은 1문장 댓글을 작성해줘. "
                                          f"광고/홍보 느낌 없이 진심 어린 톤. 댓글 문장만 출력. 본문: {content_text[:300]}")
                                try:
                                    comment_text = await self.soul.rewrite_for_blog("", prompt, provider=ai_provider)
                                    comment_text = (comment_text or "").strip().split("\n")[0][:80]
                                    # AI 메타/거절성 응답이면 버리고 안전 기본값 사용 (예: "요청하신 내용을 살펴보니...")
                                    _bad = ("요청하신", "살펴보니", "두 가지", "작업이 섞", "죄송", "도와드릴",
                                            "무엇을", "어떤 도움", "assistant", "AI", "말씀")
                                    if not comment_text or any(b in comment_text for b in _bad):
                                        comment_text = f"잘 봤습니다! ({keyword})"
                                except Exception as e:
                                    _safe(f"  ⚠️ AI 생성 실패 — 기본 댓글 사용: {e}")
                                    comment_text = f"잘 봤습니다! ({keyword})"
                            _safe(f"  💬 {comment_text}")

                            ok = await _write_comment(cafe_frame, comment_text)
                            if ok:
                                _safe("  ✅ 댓글 등록 완료")
                                try:
                                    self.db.log_cafe(account_id=account_id, cafe_id=target_url, keyword=keyword, status="타겟 댓글 성공")
                                except Exception:
                                    pass
                            else:
                                _safe("  ❌ 댓글 등록 실패")

                            # 좋아요(공감) — 댓글과 함께
                            if do_like:
                                try:
                                    await _click_like(cafe_frame)
                                except Exception as e:
                                    _safe(f"  ⚠️ 좋아요 처리 예외: {e}")
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            _safe(f"  ⚠️ 처리 중 예외: {e}")

                        if url_idx < len(target_urls) - 1:
                            d = random.randint(delay_min, delay_max)
                            _safe(f"  ⏳ {d}초 대기...")
                            await _interruptible_sleep(d)
                finally:
                    try:
                        await context.close()
                    except Exception:
                        pass

                if acc_idx < len(accounts_data) - 1 and not (stop_event is not None and stop_event.is_set()):
                    _safe("⏳ 계정 전환 10초 대기...")
                    await _interruptible_sleep(10)

            _safe("🎉 다중 타겟 댓글 작업 종료")
            return True

from contextvars import ContextVar
task_logger = ContextVar("task_logger", default=print)
