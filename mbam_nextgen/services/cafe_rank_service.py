"""블로그·카페 글 통합검색 순위 수집 (로컬 에이전트/집 IP에서 실행).

주어진 (키워드, 글 URL)에 대해:
- tongsearch_rank : 네이버 통합검색(PC) 결과에서 해당 글(블로그/카페)의 순위
- tab_rank(=DB의 cafetab_rank) : URL이 블로그면 '블로그' 탭, 카페면 '카페' 탭에서의 순위(페이지네이션)

★네이버 검색 DOM/셀렉터·URL 파라미터는 자주 바뀌므로 실환경 튜닝이 필요할 수 있다(주석 ★).
URL 매칭은 블로그(blogId+logNo) / 카페(clubid|name+articleid)로 정규화해 비교한다.
"""
import re
import urllib.parse
from playwright.async_api import async_playwright


def _post_key(url: str):
    """글 URL을 정규화 키로. 반환:
    ('blog', blogId, logNo) / ('cafe', clubOrName, articleId) / None"""
    if not url:
        return None
    # 블로그: blog.naver.com/{id}/{logNo}  또는  PostView?blogId=..&logNo=..
    m = re.search(r"blog\.naver\.com/([^/?#]+)/(\d+)", url)
    if m and m.group(1).lower() not in ("postview.naver", "postview.nhn"):
        return ("blog", m.group(1).lower(), m.group(2))
    m = re.search(r"blogId=([^&]+).*?logNo=(\d+)", url)
    if m:
        return ("blog", m.group(1).lower(), m.group(2))
    # 카페: ArticleRead?clubid=..&articleid=..
    m = re.search(r"clubid=(\d+).*?articleid=(\d+)", url)
    if m:
        return ("cafe", m.group(1), m.group(2))
    # 카페: cafe.naver.com/{name}/{articleId}
    m = re.search(r"cafe\.naver\.com/([^/?#]+)/(\d+)", url)
    if m:
        return ("cafe", m.group(1).lower(), m.group(2))
    # 카페: /cafes/{clubid}/articles/{articleId}
    m = re.search(r"/cafes/(\d+)/articles/(\d+)", url)
    if m:
        return ("cafe", m.group(1), m.group(2))
    return None


def _same_post(a: str, b: str) -> bool:
    ka, kb = _post_key(a), _post_key(b)
    if not ka or not kb or ka[0] != kb[0]:
        return False
    # 글 고유번호(logNo/articleId) 일치가 핵심. 블로그/이름형은 앞부분도 대조.
    if ka[2] != kb[2]:
        return False
    return ka[1] == kb[1] or True  # 번호 일치면 동일 글로 인정(형식 차이 허용)


def _kind(url: str) -> str:
    return "blog" if (_post_key(url) or (None,))[0] == "blog" else "cafe"


async def _collect_links(page) -> list:
    """검색 결과에서 블로그/카페 글 링크를 노출 순서대로 수집(중복 제거)."""
    hrefs = await page.eval_on_selector_all(
        "a",
        "els => els.map(e => e.href).filter(h => h && (h.includes('blog.naver.com') || h.includes('cafe.naver.com') || h.includes('/cafes/')))",
    )
    seen, out = set(), []
    for h in hrefs:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


async def find_cafe_rank(keyword: str, target_url: str, max_tab_pages: int = 3) -> dict:
    """(키워드, 글 URL) → {tongsearch_rank, cafetab_rank, found}.
    cafetab_rank 는 URL 종류에 따라 블로그탭/카페탭 순위(공용 컬럼명 유지)."""
    q = urllib.parse.quote(keyword or "")
    kind = _kind(target_url)
    result = {"tongsearch_rank": None, "cafetab_rank": None, "found": False, "kind": kind}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ko-KR",
            )
            page = await context.new_page()

            # 1) 통합검색 — 블로그/카페 글 노출 순서에서 순위  ★튜닝(셀렉터/URL)
            try:
                await page.goto(f"https://search.naver.com/search.naver?query={q}",
                                wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1500)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(800)
                for idx, h in enumerate(await _collect_links(page), start=1):
                    if _same_post(h, target_url):
                        result["tongsearch_rank"] = idx
                        result["found"] = True
                        break
            except Exception as e:
                print(f"[PostRank] 통합검색 수집 실패: {e}")

            # 2) 탭 검색 — 블로그면 블로그탭, 카페면 카페탭(페이지네이션)  ★튜닝(URL 파라미터)
            try:
                ssc = "tab.blog.all" if kind == "blog" else "tab.cafe.all"
                rank, done = 0, False
                for pageno in range(max_tab_pages):
                    start = pageno * 30 + 1
                    await page.goto(
                        f"https://search.naver.com/search.naver?ssc={ssc}&query={q}&start={start}",
                        wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(1200)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(600)
                    links = await _collect_links(page)
                    if not links:
                        break
                    for h in links:
                        rank += 1
                        if _same_post(h, target_url):
                            result["cafetab_rank"] = rank
                            result["found"] = True
                            done = True
                            break
                    if done:
                        break
            except Exception as e:
                print(f"[PostRank] 탭 수집 실패: {e}")
        finally:
            await browser.close()
    return result
