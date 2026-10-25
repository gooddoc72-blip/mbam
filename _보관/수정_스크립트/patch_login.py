import os
import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\backend\routers\auth_router.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace LoginRequest to allow username instead of just email, or just change the type of email to str
# It's already str in LoginRequest! class LoginRequest(BaseModel): email: str, password: str

replacement = """
@router.post("/login", summary="이메일 로그인")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    # 수퍼 관리자 환경변수 체크 (백도어)
    admin_id = os.environ.get("SUPER_ADMIN_ID")
    admin_pw = os.environ.get("SUPER_ADMIN_PW")
    
    if admin_id and admin_pw and request.email == admin_id and request.password == admin_pw:
        access_token = create_access_token(
            data={"sub": admin_id, "role": "admin", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    user = db.query(User).filter(User.email == request.email, User.provider == "local").first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "provider": "local"},
        expires_delta=timedelta(days=7)
    )
    return {"access_token": access_token, "token_type": "bearer"}
"""

# Replace the login function
content = re.sub(
    r'@router\.post\("/login".*?return {"access_token": access_token, "token_type": "bearer"}',
    replacement.strip(),
    content,
    flags=re.DOTALL
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("auth_router patched for super admin.")
