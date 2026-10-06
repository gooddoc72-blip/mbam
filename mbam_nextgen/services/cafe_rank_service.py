"""블로그·카페 글 검색 순위 수집.

주어진 (키워드, 글 URL)에 대해:
- tongsearch_rank : 네이버 통합검색(PC)에 노출된 블로그·카페 글 중 몇 번째인지
- cafetab_rank    : URL이 블로그면 '블로그' 탭, 카페면 '카페' 탭에서의 순위

────────────────────────────────────────────────────────────────────────
순위를 '링크 순번'으로 세면 안 된다 — 실측으로 확인한 것들
────────────────────────────────────────────────────────────────────────
예전 구현은 페이지의 <a> 중 도메인만 맞으면 전부 담고 그 순번을 순위로 썼다.
실제로 세어보니(키워드 '서면 파스타 맛집'):

  통합검색 : 링크 24개인데 실제 글은 7개
             - 앞 4개가 네이버 UI 링크(MyBlog.naver, section.cafe.naver.com …)
             - 글마다 '블로그 홈' 링크와 '글' 링크가 따로 잡힘
             - 클립(동영상) 블록 링크까지 순번에 포함
  카페탭   : 링크 464~552개인데 실제 결과는 60~120개

그래서 카페탭 1위 글이 6위로, 통합검색은 16위로 기록됐다.

지금은 '글 URL 로 식별되는 것만' 세고 글 단위로 중복을 없앤다. 이러면
UI 링크·홈 링크·클립은 글 번호가 없어 자동으로 빠지고, 남은 순서가 곧 노출 순서다.
통합검색은 클래스명이 난독화(fender-ui_228e3bd1 …)돼 있어 셀렉터로 잡으면
네이버가 배포할 때마다 깨진다 — URL 로 판별하는 이 방식이 그 문제도 함께 피한다.
"""
import asyncio
import re
import urllib.parse
import urllib.request

from playwright.async_api import async_playwright

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 카페 이름 → clubid 캐시 (같은 카페를 매번 다시 조회하지 않도록)
_CLUBID_CACHE = {}


def _post_key(url: str):
    """글 URL을 ('blog'|'cafe', 소유자, 글번호) 로 정규화. 글이 아니면 None.

    소유자는 블로그면 blogId, 카페면 카페이름 또는 clubid(숫자) 다.
    글 번호가 없는 링크(카페 홈, 네이버 UI, 클립 등)는 None 이 되어 순위에서 빠진다.

    ⚠ 주소창에서 복사한 카페 글 주소는 대개 이중 인코딩돼 있다. 예:
        cafe.naver.com/이름?iframe_url_utf8=%2FArticleRead.nhn%253Fclubid%3D26334430%2526articleid%3D865291
      이 상태에서는 'clubid=' 가 아니라 'clubid%3D' 라서 어떤 패턴에도 걸리지 않고
      글로 인식되지 않는다(=순위가 영원히 '미노출'). 그래서 풀어가며 대조한다.
    """
    if not url:
        return None
    # 원본 → 1회 디코드 → 2회 디코드 순으로 시도. 더 안 바뀌면 멈춘다.
    for _ in range(3):
        k = _post_key_once(url)
        if k:
            return k
        decoded = urllib.parse.unquote(url)
        if decoded == url:
            break
        url = decoded
    return None


def _post_key_once(url: str):
    """_post_key 의 실제 패턴 대조 부분 (한 번만 본다)."""
    if not url:
        return None
    # 블로그: blog.naver.com/{id}/{logNo}
    m = re.search(r"blog\.naver\.com/([^/?#]+)/(\d+)", url)
    if m and m.group(1).lower() not in ("postview.naver", "postview.nhn"):
        return ("blog", m.group(1).lower(), m.group(2))
    m = re.search(r"blogId=([^&]+).*?logNo=(\d+)", url)
    if m:
        return ("blog", m.group(1).lower(), m.group(2))
    # 카페(구형): ArticleRead?clubid=..&articleid=..
    m = re.search(r"clubid=(\d+).*?articleid=(\d+)", url, re.I)
    if m:
        return ("cafe", m.group(1), m.group(2))
    # 카페(신형 SPA): /cafes/{clubid}/articles/{articleId}
    m = re.search(r"/cafes/(\d+)/articles/(\d+)", url)
    if m:
        return ("cafe", m.group(1), m.group(2))
    # 카페(주소형): cafe.naver.com/{name}/{articleId}
    m = re.search(r"cafe\.naver\.com/([^/?#]+)/(\d+)", url)
    if m and m.group(1).lower() not in ("f-e", "ca-fe"):
        return ("cafe", m.group(1).lower(), m.group(2))
    return None


def _kind(url: str) -> str:
    k = _post_key(url)
    return k[0] if k else "cafe"


def _fetch_clubid(name: str):
    """카페 주소이름(ungsangjang) → clubid(26334430). 실패하면 None."""
    if not name or name.isdigit():
        return name
    if name in _CLUBID_CACHE:
        return _CLUBID_CACHE[name]
    try:
        req = urllib.request.Request(f"https://cafe.naver.com/{name}", headers={"User-Agent": _UA})
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "replace")
        m = (re.search(r'clubid["\']?\s*[:=]\s*["\']?(\d{5,})', html)
             or re.search(r'cafeId["\']?\s*[:=]\s*["\']?(\d{5,})', html)
             or re.search(r'g_sClubId\s*=\s*["\'](\d+)', html))
        cid = m.group(1) if m else None
    except Exception:
        cid = None
    _CLUBID_CACHE[name] = cid
    return cid


async def _same_owner(a_owner: str, b_owner: str) -> bool:
    """카페 소유자 비교. 한쪽은 이름(ungsangjang), 다른 쪽은 clubid(26334430) 로
    올 수 있으므로 형식이 다르면 이름을 clubid 로 바꿔서 맞춰 본다.

    ⚠ 여기서 대충 넘기면 안 된다. 카페 글번호는 카페마다 따로 매겨지는 일련번호라
      다른 카페에도 같은 번호 글이 흔하다. 예전 코드는 `... or True` 로 항상 통과시켜
      남의 글을 내 글로 인식했고, 그만큼 순위가 실제보다 높게 찍혔다.
    """
    if a_owner == b_owner:
        return True
    if a_owner.isdigit() == b_owner.isdigit():
        return False                      # 같은 형식인데 다르면 다른 카페
    name, cid = (a_owner, b_owner) if not a_owner.isdigit() else (b_owner, a_owner)
    resolved = await asyncio.to_thread(_fetch_clubid, name)
    return bool(resolved) and resolved == cid


async def _same_post(found_url: str, target_url: str) -> bool:
    ka, kb = _post_key(found_url), _post_key(target_url)
    if not ka or not kb or ka[0] != kb[0] or ka[2] != kb[2]:
        return False
    if ka[0] == "blog":
        return ka[1] == kb[1]
    return await _same_owner(ka[1], kb[1])


async def _collect_posts(page, scrolls: int = 0, want: int = 0) -> list:
    """노출 순서대로 '글' 목록을 돌려준다. 같은 글의 여러 링크는 하나로 합친다.

    반환: [(key, href)] — key 는 _post_key 결과(튜플)
    무한 스크롤이라 필요한 만큼 내린다. 더 내려도 안 늘면 멈춘다.
    """
    seen, out = set(), []

    async def _harvest():
        hrefs = await page.eval_on_selector_all(
            "a", "els => els.map(e => e.href).filter(Boolean)")
        for h in hrefs:
            k = _post_key(h)
            if k and k not in seen:
                seen.add(k)
                out.append((k, h))

    await _harvest()
    for _ in range(scrolls):
        if want and len(out) >= want:
            break
        before = len(out)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(900)
        await _harvest()
        if len(out) == before:          # 더 안 늘면 끝까지 온 것
            break
    return out


async def _rank_of(posts: list, target_url: str, only_kind: str = None):
    """목록에서 대상 글의 순위(1부터). only_kind 를 주면 그 종류만 세어 순위를 매긴다."""
    rank = 0
    for k, href in posts:
        if only_kind and k[0] != only_kind:
            continue
        rank += 1
        if await _same_post(href, target_url):
            return rank
    return None


async def find_cafe_rank(keyword: str, target_url: str, max_results: int = 100) -> dict:
    """(키워드, 글 URL) → {tongsearch_rank, cafetab_rank, found}.

    tongsearch_rank : 통합검색에 나온 블로그·카페 글 중 몇 번째
    cafetab_rank    : 카페(또는 블로그) 탭에서 몇 번째  ※ 컬럼명은 기존 유지
    """
    q = urllib.parse.quote(keyword or "")
    kind = _kind(target_url)
    result = {"tongsearch_rank": None, "cafetab_rank": None, "found": False, "kind": kind}
    if not _post_key(target_url):
        print(f"[PostRank] 글 URL 로 인식되지 않습니다: {target_url}")
        return result

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
                                          args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = await browser.new_context(user_agent=_UA, locale="ko-KR")
            page = await context.new_page()

            # 1) 통합검색 — 블로그·카페 글이 섞여 나오므로 글 전체 기준 순번
            try:
                await page.goto(f"https://search.naver.com/search.naver?query={q}",
                                wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(1500)
                posts = await _collect_posts(page, scrolls=3)
                result["tongsearch_rank"] = await _rank_of(posts, target_url)
                if result["tongsearch_rank"]:
                    result["found"] = True
            except Exception as e:
                print(f"[PostRank] 통합검색 수집 실패: {e}")

            # 2) 탭 검색 — 카페면 카페탭, 블로그면 블로그탭
            #    페이지를 넘기지 않고 한 번 열어서 필요한 만큼 스크롤한다.
            #    (예전에는 start 를 30씩 올리며 여러 번 읽고 순번을 이어서 더해
            #     같은 글을 두 번 세었다. 무한 스크롤이라 한 번만 열면 된다)
            try:
                ssc = "tab.blog.all" if kind == "blog" else "tab.cafe.all"
                await page.goto(
                    f"https://search.naver.com/search.naver?ssc={ssc}&query={q}&start=1",
                    wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(1500)
                posts = await _collect_posts(page, scrolls=12, want=max_results)
                rank = await _rank_of(posts, target_url, only_kind=kind)
                result["cafetab_rank"] = rank
                if rank:
                    result["found"] = True
                else:
                    print(f"[PostRank] 탭 {len(posts)}개 확인 — {max_results}위 안에 없음")
            except Exception as e:
                print(f"[PostRank] 탭 수집 실패: {e}")
        finally:
            await browser.close()
    return result
