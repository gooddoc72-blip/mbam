import os

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\backend\routers\auth_router.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if "import httpx" not in content:
    content = content.replace("from fastapi import APIRouter", "from fastapi import APIRouter, Depends, HTTPException, status, Request\nfrom fastapi.responses import RedirectResponse\nimport httpx\nimport uuid")

oauth_code = '''

@router.get("/login/{provider}", summary="소셜 로그인 시작")
async def social_login(provider: str, request: Request):
    if provider == "kakao":
        client_id = os.environ.get("KAKAO_CLIENT_ID", "")
        redirect_uri = "http://localhost:8000/api/auth/callback/kakao"
        url = f"https://kauth.kakao.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
        return RedirectResponse(url)
    elif provider == "naver":
        client_id = os.environ.get("NAVER_CLIENT_ID", "")
        redirect_uri = "http://localhost:8000/api/auth/callback/naver"
        state = "mbam_state"
        url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}"
        return RedirectResponse(url)
    elif provider == "google":
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        redirect_uri = "http://localhost:8000/api/auth/callback/google"
        scope = "email profile"
        url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}"
        return RedirectResponse(url)
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

@router.get("/callback/{provider}", summary="소셜 로그인 콜백")
async def social_callback(provider: str, code: str, state: str = None, db: Session = Depends(get_db)):
    email = None
    social_id = None
    
    async with httpx.AsyncClient() as client:
        if provider == "kakao":
            client_id = os.environ.get("KAKAO_CLIENT_ID", "")
            redirect_uri = "http://localhost:8000/api/auth/callback/kakao"
            token_resp = await client.post("https://kauth.kakao.com/oauth/token", data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code": code
            }, headers={"Content-type": "application/x-www-form-urlencoded;charset=utf-8"})
            
            if token_resp.status_code != 200:
                return RedirectResponse("http://localhost:3000/login?error=kakao_token_failed")
            
            access_token = token_resp.json().get("access_token")
            user_resp = await client.get("https://kapi.kakao.com/v2/user/me", headers={
                "Authorization": f"Bearer {access_token}"
            })
            user_data = user_resp.json()
            social_id = str(user_data.get("id"))
            kakao_account = user_data.get("kakao_account", {})
            email = kakao_account.get("email")
            if not email:
                email = f"{social_id}@kakao.local"
                
        elif provider == "naver":
            client_id = os.environ.get("NAVER_CLIENT_ID", "")
            client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")
            token_resp = await client.post("https://nid.naver.com/oauth2.0/token", data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "state": state or "mbam_state",
                "code": code
            })
            if token_resp.status_code != 200:
                return RedirectResponse("http://localhost:3000/login?error=naver_token_failed")
                
            access_token = token_resp.json().get("access_token")
            user_resp = await client.get("https://openapi.naver.com/v1/nid/me", headers={
                "Authorization": f"Bearer {access_token}"
            })
            user_data = user_resp.json().get("response", {})
            social_id = user_data.get("id")
            email = user_data.get("email")
            if not email:
                email = f"{social_id}@naver.local"
                
        elif provider == "google":
            client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
            client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
            redirect_uri = "http://localhost:8000/api/auth/callback/google"
            token_resp = await client.post("https://oauth2.googleapis.com/token", data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code
            })
            if token_resp.status_code != 200:
                return RedirectResponse("http://localhost:3000/login?error=google_token_failed")
                
            access_token = token_resp.json().get("access_token")
            user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={
                "Authorization": f"Bearer {access_token}"
            })
            user_data = user_resp.json()
            social_id = user_data.get("id")
            email = user_data.get("email")

    if not email or not social_id:
        return RedirectResponse("http://localhost:3000/login?error=social_login_failed")

    # DB 연동
    user = db.query(Advertiser).filter(
        (Advertiser.email == email) | 
        ((Advertiser.socialProvider == provider) & (Advertiser.socialId == social_id))
    ).first()

    if not user:
        user = Advertiser(
            email=email,
            socialProvider=provider,
            socialId=social_id,
            businessName=f"{provider.capitalize()} 연동 회원",
            status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token(
        data={"sub": user.email, "role": "advertiser", "provider": provider},
        expires_delta=timedelta(days=7)
    )

    return RedirectResponse(f"http://localhost:3000/login?token={jwt_token}")
'''

if "social_login" not in content:
    content += oauth_code

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("auth_router.py updated with social login endpoints")
