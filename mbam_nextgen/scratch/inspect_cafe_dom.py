"""
카페 글 페이지 DOM 구조 분석 — fetch_cafe_author_info() 구현용 셀렉터 추출
2026-05-26 분석 샘플:
  - https://cafe.naver.com/ungsangjang/828892
  - https://cafe.naver.com/mindy7857/5182039
"""
import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

SAMPLES = [
    ("ungsangjang", "https://cafe.naver.com/ungsangjang/828892"),
    ("mindy7857",   "https://cafe.naver.com/mindy7857/5182039"),
]

OUT_DIR = Path(__file__).parent / "cafe_dom_dumps"
OUT_DIR.mkdir(exist_ok=True)


async def inspect_one(p, label: str, url: str) -> dict:
    print(f"\n===== {label} :: {url} =====")
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    page = await context.new_page()

    summary = {"label": label, "url": url}

    try:
        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # 1) frame 구조 파악
        frames = [{"name": f.name, "url": f.url} for f in page.frames]
        summary["frames"] = frames

        # cafe_main 또는 mainFrame iframe 탐색
        frame = page.frame(name="cafe_main") or page.frame(name="mainFrame")
        if frame:
            try:
                await frame.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            await page.wait_for_timeout(800)

        target = frame if frame else page

        # 2) 전체 HTML 저장 (외부 페이지)
        outer_html = await page.content()
        (OUT_DIR / f"{label}_outer.html").write_text(outer_html, encoding="utf-8")

        # 3) iframe HTML 저장 (실제 본문)
        inner_html = await target.content()
        (OUT_DIR / f"{label}_inner.html").write_text(inner_html, encoding="utf-8")

        # 4) 작성자/메타 후보 셀렉터 평가 (iframe 안 우선)
        selectors_to_probe = [
            # 닉네임 후보
            ".nick_box .nickname",
            ".nick_box a.nickname",
            "a.nickname",
            ".nickname",
            ".profile_info .nickname",
            ".ArticleWriterProfile .nickname",
            ".nick_text",
            ".member_nick",
            # 등급
            ".LevelIcon",
            ".level_icon",
            ".LevelIcon img",
            ".level_icon img",
            ".tit_level",
            ".member_grade",
            ".grade_icon",
            "em.member_level",
            ".profile_area em",
            # 조회수
            ".count",
            ".article_info .count",
            ".ArticleTopBtns",
            ".article_info",
            ".date_num",
            ".no_count",
            # 댓글
            ".CommentBox",
            ".comment_count",
            ".btn_comment .num",
            "em.num",
            "#commentArea .comment_box",
            # 좋아요
            ".ReactionLikeIt",
            ".like_no",
            ".u_likeit_text",
            ".like_count",
            ".btn_like .num",
            # 본문 컨테이너
            ".se-main-container",
            ".article_viewer",
            ".ArticleContentBox",
            "#app",
            # 카페 헤더 / 회원수
            ".cafe_menu_info",
            ".cafe_info",
            ".member_num",
            ".cafe-name",
            ".tit-cafe",
        ]

        probe_results = {}
        for sel in selectors_to_probe:
            try:
                el = await target.query_selector(sel)
                if el:
                    txt = (await el.inner_text())[:160].strip()
                    outer = (await el.evaluate("e => e.outerHTML"))[:300]
                    probe_results[sel] = {"text": txt, "outerHTML": outer}
            except Exception as e:
                probe_results[sel] = {"error": str(e)[:120]}
        summary["selectors"] = probe_results

        # 5) 정규식으로 memberid / clubid 추출
        joined = outer_html + "\n" + inner_html
        summary["memberid_matches"] = list(set(re.findall(r'memberid=([a-zA-Z0-9_]+)', joined)))[:5]
        summary["clubid_matches"]   = list(set(re.findall(r'clubid=(\d+)', joined)))[:5]
        summary["cafeId_matches"]   = list(set(re.findall(r'cafeId["\']?\s*[:=]\s*["\']?(\d+)', joined)))[:5]

        # 6) 페이지 상단 메타 텍스트 일부 (조회/댓글/좋아요 형태)
        try:
            top_text = await target.evaluate("""
                () => {
                  const buckets = ['.ArticleTopBtns', '.article_info', '.article_top', '.tit-box', '.article_head'];
                  const out = {};
                  buckets.forEach(s => {
                    const el = document.querySelector(s);
                    if (el) out[s] = (el.innerText || '').slice(0, 400);
                  });
                  return out;
                }
            """)
            summary["top_text"] = top_text
        except Exception as e:
            summary["top_text_error"] = str(e)[:200]

        # 7) 작성자 영역 HTML 일부 (라벨링 도움)
        try:
            writer_block = await target.evaluate("""
                () => {
                  const cands = [
                    '.ArticleWriterProfile',
                    '.nick_box',
                    '.profile_area',
                    '.WriterInfo',
                    '.user_info',
                  ];
                  const out = {};
                  cands.forEach(s => {
                    const el = document.querySelector(s);
                    if (el) out[s] = el.outerHTML.slice(0, 800);
                  });
                  return out;
                }
            """)
            summary["writer_blocks"] = writer_block
        except Exception as e:
            summary["writer_blocks_error"] = str(e)[:200]

    except Exception as e:
        summary["fatal_error"] = str(e)
    finally:
        await browser.close()

    return summary


async def main():
    results = []
    async with async_playwright() as p:
        for label, url in SAMPLES:
            results.append(await inspect_one(p, label, url))

    out_path = OUT_DIR / "summary.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Saved summary to {out_path}")
    print(f"[OK] HTML dumps in {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
