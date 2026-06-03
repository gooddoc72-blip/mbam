import httpx
import os
import json
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from mbam_nextgen.backend.database import get_db, BlogspotAccount, BlogspotPostHistory, BlogspotKeywordTracker

router = APIRouter(
    prefix="/api/blogspot",
    tags=["Blogspot Automation"]
)

class AddAccountRequest(BaseModel):
    account_name: str
    blog_id: str
    access_token: str
    refresh_token: str
    client_id: str
    client_secret: str

class AutoPostRequest(BaseModel):
    account_id: str
    keyword: str
    ai_provider: str = "gemini" # "gemini" or "claude"
    generate_image: bool = True

@router.get("/accounts")
def get_accounts(db: Session = Depends(get_db)):
    accounts = db.query(BlogspotAccount).all()
    return {"success": True, "accounts": [{"id": a.id, "account_name": a.account_name, "blog_id": a.blog_id} for a in accounts]}

@router.post("/accounts")
def add_account(req: AddAccountRequest, db: Session = Depends(get_db)):
    # Validate token or just save
    new_acc = BlogspotAccount(
        account_name=req.account_name,
        blog_id=req.blog_id,
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        client_id=req.client_id,
        client_secret=req.client_secret
    )
    db.add(new_acc)
    db.commit()
    db.refresh(new_acc)
    return {"success": True, "message": "Account added", "id": new_acc.id}

@router.delete("/accounts/{account_id}")
def delete_account(account_id: str, db: Session = Depends(get_db)):
    acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()
    return {"success": True, "message": "Account deleted"}

async def generate_article(keyword: str, provider: str) -> str:
    # 1. 키워드 기반 글감 수집 (여기서는 생략 및 모의 구현)
    # 2. AI 글 작성
    html_content = ""
    prompt = f"당신은 전문 SEO 블로거입니다. '{keyword}'에 대한 흥미롭고 유익한 블로그 글을 작성해주세요. HTML 형식(h2, h3, p, strong 태그 등)으로 작성하고, <body> 태그는 제외하고 내부 태그만 출력하세요."
    
    if provider == "gemini":
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key: return f"<h2>{keyword}</h2><p>Gemini API 키가 설정되지 않았습니다.</p>"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]}
            )
            data = resp.json()
            try: html_content = data['candidates'][0]['content']['parts'][0]['text']
            except: html_content = f"<p>Gemini 에러: {str(data)}</p>"
            
    elif provider == "claude":
        claude_key = os.environ.get("ANTHROPIC_API_KEY")
        if not claude_key: return f"<h2>{keyword}</h2><p>Claude API 키가 설정되지 않았습니다.</p>"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": claude_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-3-haiku-20240307", "max_tokens": 1500, "messages": [{"role": "user", "content": prompt}]}
            )
            data = resp.json()
            try: html_content = data['content'][0]['text']
            except: html_content = f"<p>Claude 에러: {str(data)}</p>"
            
    return html_content.replace("```html", "").replace("```", "")

@router.post("/post")
async def auto_post(req: AutoPostRequest, db: Session = Depends(get_db)):
    acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == req.account_id).first()
    if not acc: raise HTTPException(status_code=404, detail="Account not found")
    
    # 1. AI 글 생성
    content = await generate_article(req.keyword, req.ai_provider)
    
    # 2. 대표 이미지 생성 (Placeholder for DALL-E)
    if req.generate_image:
        image_html = f'<div style="text-align:center;"><img src="https://source.unsplash.com/800x400/?{req.keyword}" alt="{req.keyword}"></div><br/>'
        content = image_html + content
        
    title = f"{req.keyword} 완벽 가이드 및 총정리"
    
    # 3. Blogger API 포스팅
    headers = {"Authorization": f"Bearer {acc.access_token}", "Content-Type": "application/json"}
    payload = {
        "kind": "blogger#post",
        "blog": {"id": acc.blog_id},
        "title": title,
        "content": content
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(f"https://www.googleapis.com/blogger/v3/blogs/{acc.blog_id}/posts/", headers=headers, json=payload)
        post_data = res.json()
        
    status_str = "success" if res.status_code == 200 else "failed"
    post_url = post_data.get("url", "")
    
    history = BlogspotPostHistory(
        account_id=acc.id,
        keyword=req.keyword,
        title=title,
        post_url=post_url,
        status=status_str
    )
    db.add(history)
    db.commit()
    
    if res.status_code != 200:
        return {"success": False, "error": post_data}
        
    return {"success": True, "post_url": post_url}

class TrackKeywordRequest(BaseModel):
    account_id: str
    keyword: str

@router.get("/rank")
def get_tracked_keywords(db: Session = Depends(get_db)):
    # Join with BlogspotAccount to get the account name
    results = db.query(BlogspotKeywordTracker, BlogspotAccount.account_name)\
                .join(BlogspotAccount, BlogspotKeywordTracker.account_id == BlogspotAccount.id)\
                .all()
    
    keywords = []
    for k, acc_name in results:
        keywords.append({
            "id": k.id,
            "account_id": k.account_id,
            "account_name": acc_name,
            "keyword": k.keyword,
            "current_rank": k.current_rank,
            "last_checked_at": k.last_checked_at.strftime("%Y-%m-%d %H:%M") if k.last_checked_at else None
        })
        
    return {"success": True, "keywords": keywords}

@router.post("/rank")
def add_tracked_keyword(req: TrackKeywordRequest, db: Session = Depends(get_db)):
    acc = db.query(BlogspotAccount).filter(BlogspotAccount.id == req.account_id).first()
    if not acc: raise HTTPException(status_code=404, detail="Account not found")
    
    tracker = BlogspotKeywordTracker(
        account_id=req.account_id,
        keyword=req.keyword,
        current_rank=0 # 초기값
    )
    db.add(tracker)
    db.commit()
    db.refresh(tracker)
    return {"success": True, "id": tracker.id}
