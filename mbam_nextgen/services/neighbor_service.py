import asyncio
from ..core.stealth import StealthExecutor

class NeighborService:
    """
    [Domain Service] 네이버 블로그 이웃추가 및 관리 자동화
    """
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth
        self.selectors = {
            "add_btn": "span:has-text('이웃추가'), a:has-text('이웃추가')",
            "mutual_radio": "label:has-text('서로이웃')",
            "message_area": "textarea#buddyAddMessage, .textarea_input",
            "submit_btn": "button:has-text('다음'), button:has-text('확인')"
        }

    async def click_like(self, target):
        """현재 글(mainFrame 또는 page)에서 공감 버튼 클릭. target 은 Page 또는 Frame."""
        try:
            like_btn = target.locator("a.u_likeit_list_btn, .u_likeit_list_btn, .btn_sympathy, .area_sympathy a")
            if await like_btn.count() == 0:
                return False
            # 이미 공감했으면(aria-pressed=true) 스킵
            try:
                if (await like_btn.first.get_attribute("aria-pressed")) == "true":
                    return True
            except Exception:
                pass
            await like_btn.first.click(timeout=5000)
            await asyncio.sleep(1)
            print("[NeighborService] ❤️ 공감 클릭 완료")
            return True
        except Exception:
            return False

    async def leave_comment(self, target, content: str):
        """현재 글(mainFrame 또는 page)에서 댓글 작성. target 은 Page 또는 Frame."""
        try:
            comment_area = target.locator("textarea.u_cbox_text, .u_cbox_text, #comment_area")
            if await comment_area.count() == 0:
                return False
            await comment_area.first.click(timeout=5000)
            await comment_area.first.fill(content, timeout=5000)
            await asyncio.sleep(0.5)
            submit_btn = target.locator(".u_cbox_btn_upload, button:has-text('등록')")
            if await submit_btn.count() == 0:
                return False
            await submit_btn.first.click(timeout=5000)
            await asyncio.sleep(2)
            print(f"[NeighborService] 💬 댓글 작성 완료: {content[:15]}...")
            return True
        except Exception as e:
            print(f"[NeighborService] ⚠️ 댓글 작성 실패: {e}")
            return False

    async def add_neighbor(self, page, target_id: str, message: str = "블로그 잘 보고 갑니다! 서로이웃 해요 :)", mutual: bool = True):
        """특정 블로그 이웃/서로이웃 신청.

        주의: PC용 blog.naver.com/BuddyAddForm.naver 는 폐지되어 '페이지 주소를 확인해주세요'
        오류가 난다. 모바일 m.blog.naver.com/BuddyAddForm.naver 가 현재 유효한 경로.
        모든 클릭에 짧은 타임아웃을 주어 비로그인/구조변경 시에도 멈추지 않고 빠르게 스킵한다.
        """
        print(f"[NeighborService] 이웃 추가 시도: {target_id}")
        try:
            await page.goto(
                f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={target_id}",
                wait_until="domcontentloaded", timeout=15000,
            )
            await asyncio.sleep(1.5)

            # 비로그인 → 로그인 페이지로 리다이렉트되면 중단
            if "nidlogin" in page.url or "nid.naver.com" in page.url:
                print("[NeighborService] ⚠️ 로그인 필요 — 이웃추가 건너뜀")
                return False
            # 폐지/오류 페이지 감지
            body = ""
            try:
                body = (await page.inner_text("body"))[:300]
            except Exception:
                pass
            if "사라졌거나" in body or "주소를 확인" in body:
                print("[NeighborService] ⚠️ 이웃추가 폼을 찾을 수 없음(페이지 변경) — 건너뜀")
                return False

            # 서로이웃 옵션 선택
            if mutual:
                opt = page.locator("input#each_buddy_add, input#each_buddy2, label:has-text('서로이웃')")
                if await opt.count() > 0:
                    try:
                        await opt.first.click(timeout=4000)
                    except Exception:
                        pass

            # 신청 메시지
            msg_area = page.locator("textarea#message, textarea#buddyAddMessage, textarea[name='message']")
            if await msg_area.count() > 0:
                try:
                    await msg_area.first.fill(message, timeout=4000)
                except Exception:
                    pass

            # 확인/다음
            submit = page.locator("a.btn_ok, a._submitButton, button:has-text('다음'), button:has-text('확인'), a:has-text('다음'), a:has-text('확인')")
            if await submit.count() == 0:
                print("[NeighborService] ⚠️ 이웃추가 확인 버튼을 찾지 못함 — 건너뜀")
                return False
            await submit.first.click(timeout=5000)
            await asyncio.sleep(2)
            print(f"✅ [NeighborService] {target_id} 이웃 신청 완료!")
            return True
        except Exception as e:
            print(f"❌ [NeighborService] 이웃 신청 실패: {e}")
            return False

    async def find_targets_from_search(self, page, keyword: str, limit: int = 10):
        """키워드 검색 결과에서 대상 블로그 포스팅 URL 및 ID 추출.

        네이버 검색은 결과 컨테이너의 클래스명을 난독화(fender-ui_…/sds-comps-…)하고
        수시로 바꾸므로 클래스 셀렉터에 의존하지 않는다. 대신 'blog.naver.com/아이디/글번호'
        패턴의 href 자체로 추출하면 난독화 변경에 강하다. (블로거당 1건씩 dedup)
        """
        import urllib.parse
        print(f"[NeighborService] '{keyword}' 검색 결과에서 대상 추출 중...")
        q = urllib.parse.quote(keyword)
        # 최신 블로그 탭(2025+) 우선, 실패 시 통합검색(view)로 폴백
        search_urls = [
            f"https://search.naver.com/search.naver?ssc=tab.blog.all&query={q}",
            f"https://search.naver.com/search.naver?where=view&query={q}",
        ]

        targets = []
        seen = set()
        for search_url in search_urls:
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                print(f"[NeighborService] 검색 페이지 로딩 실패({search_url}): {e}")
                continue
            await asyncio.sleep(2)

            # 결과는 스크롤 시 lazy-load 되므로 여러 번 내려준다
            for _ in range(6):
                try:
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                except Exception:
                    pass
                await asyncio.sleep(0.8)

            found = await page.evaluate(r'''() => {
                const rx = /blog\.naver\.com\/([^\/?#]+)\/(\d+)/;
                const res = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const m = a.href.match(rx);
                    if (!m) return;
                    res.push({ id: m[1], logno: m[2], txt: (a.innerText || '').trim() });
                });
                return res;
            }''')

            # 제목 텍스트가 있는 링크(=실제 글 제목)를 우선
            found.sort(key=lambda d: 0 if len(d.get("txt", "")) > 5 else 1)
            for d in found:
                uid = (d.get("id") or "").strip()
                if not uid or uid in seen:
                    continue
                # PostView.naver / PostList.naver 등 시스템 경로 제외
                if uid.endswith(".naver") or "." in uid:
                    continue
                seen.add(uid)
                targets.append({"id": uid, "post_url": f"https://blog.naver.com/{uid}/{d['logno']}"})
                if len(targets) >= limit:
                    break

            if targets:
                break

        if not targets:
            print(f"[NeighborService] ⚠️ '{keyword}'에 대한 검색 결과에서 대상을 찾지 못했습니다.")
            return []

        print(f"[NeighborService] {len(targets)}개의 대상 포착 완료")
        return targets
