"""블로그스팟(Blogger API) 발행 공용 서비스.

네이버와 달리 Blogger 는 공식 REST API 라 데이터센터 IP(클라우드)에서도 직접 발행된다.
- access_token 은 ~1시간 만료 → 발행 직전 refresh_token 으로 새로 발급(refresh_access_token).
- 원고는 관리자 'blogspot' 프롬프트 + 글감으로 생성하되 HTML(<h2>/<h3>/<p>)로 출력.
- 제목은 생성물 첫 줄 '제목:' 에서 추출(없으면 키워드).
"""
import re
import httpx

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def refresh_access_token(acc) -> str:
    """refresh_token 으로 새 access_token 발급. 실패 시 기존 토큰 반환(그대로 시도)."""
    if not (acc.refresh_token and acc.client_id and acc.client_secret):
        return acc.access_token or ""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": acc.client_id,
                "client_secret": acc.client_secret,
                "refresh_token": acc.refresh_token,
                "grant_type": "refresh_token",
            }, timeout=30)
        if r.status_code == 200:
            tok = (r.json() or {}).get("access_token")
            if tok:
                return tok
    except Exception as e:
        print(f"[Blogspot] 토큰 갱신 실패(기존 토큰 사용): {e}")
    return acc.access_token or ""


def _read_blogspot_prompt(provider: str) -> str:
    """관리자 'blogspot' 프롬프트(DB 우선) — provider 별 텍스트."""
    try:
        from mbam_nextgen.backend.routers.settings import read_prompts
        data = read_prompts() or {}
        cat = data.get("blogspot")
        if isinstance(cat, dict):
            key = "gemini_prompt" if provider == "gemini" else "claude_prompt"
            return cat.get(key, "") or ""
    except Exception as e:
        print(f"[Blogspot] 프롬프트 로드 실패: {e}")
    return ""


async def generate_blogspot_article(keyword: str, source_data: str = "",
                                     provider: str = "gemini",
                                     custom_prompt: str = None) -> dict:
    """블로그스팟용 HTML 원고 생성. 반환: {title, html}."""
    from mbam_nextgen.services.soul import SoulRewriter

    base = (custom_prompt if custom_prompt and custom_prompt.strip()
            else _read_blogspot_prompt(provider))
    guide = f"""{base}

[작성 대상]
- 타깃 키워드: {keyword}
- 참고 글감(공식 정보): {source_data or "(없음 — 키워드 기반으로 작성)"}

[출력 규격 — 반드시 지켜라]
- 첫 줄에 '제목: (키워드를 앞쪽에 넣은 35자 이내 제목)' 을 쓰고, 그다음 줄부터 본문.
- 본문은 HTML 로만 작성: <h2>=대주제 소제목, <h3>=세부, <p>=문단, <strong>=강조, <ul><li>=목록.
- <html>·<body> 태그와 마크다운 코드펜스(```)는 쓰지 마라. 이모지 금지.
- 과장·보장('무조건·누구나') 금지. 수치·제도 정보엔 (기관명, 기준시점) 을 병기하라.
""".strip()

    text = await SoulRewriter()._dissect_ai_call((provider or "gemini").lower(), guide)
    text = (text or "").replace("```html", "").replace("```", "").strip()

    # 제목 추출: 첫 줄 '제목:' / 'title:' → 없으면 키워드
    title, body = "", text
    if text:
        first, _, rest = text.partition("\n")
        m = re.match(r'^\s*(?:제목|title)\s*[:：]\s*(.+)$', first, re.I)
        if m:
            title = m.group(1).strip()
            body = rest.strip()
        else:
            # <h1>제목</h1> 형태면 그걸 제목으로
            hm = re.match(r'^\s*<h1[^>]*>(.*?)</h1>\s*', text, re.I | re.S)
            if hm:
                title = re.sub(r'<[^>]+>', '', hm.group(1)).strip()
                body = text[hm.end():].strip()
    if not title:
        title = (keyword or "정보").strip()
    return {"title": title, "html": body or text}


async def publish_to_blogger(acc, title: str, html: str) -> dict:
    """Blogger API 로 발행. 발행 직전 토큰을 갱신한다. 반환: {success, url, error}."""
    access_token = await refresh_access_token(acc)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"kind": "blogger#post", "blog": {"id": acc.blog_id}, "title": title, "content": html}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"https://www.googleapis.com/blogger/v3/blogs/{acc.blog_id}/posts/",
                headers=headers, json=payload, timeout=60,
            )
        data = res.json() if res.content else {}
        if res.status_code == 200:
            return {"success": True, "url": data.get("url", ""), "error": None}
        return {"success": False, "url": "", "error": data or f"HTTP {res.status_code}"}
    except Exception as e:
        return {"success": False, "url": "", "error": str(e)}
