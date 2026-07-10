"""카페 글 통합검색 순위 수집 (로컬 에이전트/집 IP에서 실행).

주어진 (키워드, 카페 글 URL)에 대해:
- tongsearch_rank : 네이버 통합검색(PC) 결과에서 카페 글들 중 해당 URL의 순위
- cafetab_rank    : 네이버 '카페' 탭 검색 결과에서 해당 URL의 순위(더 깊은 순위까지, 페이지네이션)

★네이버 검색 DOM/셀렉터·URL 파라미터는 자주 바뀌므로 실제 환경에서 1회 튜닝이 필요하다
  (해당 지점에 '★튜닝' 주석 표시). URL 매칭은 카페 clubid/articleid 로 정규화해 비교한다.
"""
import re
import urllib.parse
from playwright.async_api import async_playwright


def _cafe_ids(url: str):
    """카페 글 URL에서 (clubid, articleid) 또는 (cafename, articleid)를 뽑아 정규화 키 반환."""
    if not url:
        return None
    u = url.split("?")[0] if "ArticleRead" not in url else url
    # 1) ArticleRead.nhn?clubid=..&articleid=..
    m = re.search(r"clubid=(\d+).*?articleid=(\d+)", url)
    if m:
        return ("club", m.group(1), m.group(2))
    # 2) cafe.naver.com/<name>/<articleid>
    m = re.search(r"cafe\.naver\.com/([^/?#]+)/(\d+)", u)
    if m:
        return ("name", m.group(1).lower(), m.group(2))
    # 3) f-e/cafes/<clubid>/articles/<articleid>
    m = re.search(r"/cafes/(\d+)/articles/(\d+)", url)
    if m:
        return ("club", m.group(1), m.group(2))
    return None


def _same_cafe_post(a: str, b: str) -> bool:
    ka, kb = _cafe_ids(a), _cafe_ids(b)
    if not ka or not kb:
        return False
    # articleid 가 같고(가장 신뢰), 클럽/이름 중 하나가 일치하면 동일 글로 본다
    if ka[2] != kb[2]:
        return False
    return ka[1] == kb[1] or ka[0] != kb[0]  # 형식이 다르면 articleid 일치로 인정


async def _collect_links(page, selector: str) -> list:
    """검색 결과에서 카페 글 링크를 노출 순서대로 수집."""
    hrefs = await page.eval_on_selector_all(
        selector,
        "els => els.map(e => e.href).filter(h => h && (h.includes('cafe.naver.com') || h.includes('/cafes/')))",
    )
    # 중복 제거(순서 유지)
    seen, out = set(), []
    for h in hrefs:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


async def find_cafe_rank(keyword: str, target_url: str, max_cafetab_pages: int = 3) -> dict:
    """(키워드, 카페 글 URL) → {tongsearch_rank, cafetab_rank, found}."""
    q = urllib.parse.quote(keyword or "")
    result = {"tongsearch_rank": None, "cafetab_rank": None, "found": False}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ko-KR",
            )
            page = await context.new_page()

            # 1) 통합검색 — 카페 글 노출 순서에서 순위  ★튜닝(셀렉터/URL)
            try:
                await page.goto(f"https://search.naver.com/search.naver?query={q}",
                                wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1500)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(800)
                links = await _collect_links(page, "a")
                for idx, h in enumerate(links, start=1):
                    if _same_cafe_post(h, target_url):
                        result["tongsearch_rank"] = idx
                        result["found"] = True
                        break
            except Exception as e:
                print(f"[CafeRank] 통합검색 수집 실패: {e}")

            # 2) 카페 탭 — 더 깊은 순위(페이지네이션)  ★튜닝(URL 파라미터/페이지 이동)
            try:
                rank = 0
                done = False
                for pageno in range(max_cafetab_pages):
                    start = pageno * 30 + 1
                    await page.goto(
                        f"https://search.naver.com/search.naver?ssc=tab.cafe.all&query={q}&start={start}",
                        wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(1200)
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(600)
                    links = await _collect_links(page, "a")
                    if not links:
                        break
                    for h in links:
                        rank += 1
                        if _same_cafe_post(h, target_url):
                            result["cafetab_rank"] = rank
                            result["found"] = True
                            done = True
                            break
                    if done:
                        break
            except Exception as e:
                print(f"[CafeRank] 카페탭 수집 실패: {e}")
        finally:
            await browser.close()
    return result
