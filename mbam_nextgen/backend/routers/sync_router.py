"""계정 동기화 — 여러 PC 에서 같은 네이버 계정 목록을 쓰기 위한 것.

동작
    [A PC] 설정 > 계정 동기화 > [서버에 올리기]
        → 네이버 계정 목록을 이 PC 에서 암호화 → 라이선스 서버에 보관
    [B PC] 설정 > 계정 동기화 > [서버에서 가져오기]
        → 받아서 이 PC 에서 복호화 → 계정 목록에 합침

⚠ 암호화를 왜 클라이언트에서 하는가
    naver_accounts 의 비밀번호는 평문으로 저장된다. 이걸 그대로 서버에 올리면
    서버가 뚫렸을 때 고객의 네이버 계정이 통째로 새어 나간다.
    그래서 서버에는 '열어볼 수 없는 덩어리'만 보낸다. 복호화 키는 고객이 입력한
    비밀번호에서 이 PC 가 직접 만들고, 서버로 보내지 않는다.

    비밀번호를 잊으면 서버에 있는 백업도 풀 수 없다(설계상 당연하다). 화면에 그렇게 안내한다.

⚠ 가져올 때 '합치기'로 동작한다
    같은 아이디는 서버 값으로 갱신하고, 이 PC 에만 있는 계정은 지우지 않는다.
    통째로 덮어쓰면 B PC 에서만 쓰던 계정이 소리 없이 사라진다.
"""

import base64
import json
import os
from datetime import datetime
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db, NaverAccount, JoinedCafe
from ..auth import get_current_user

router = APIRouter(prefix="/api/sync", tags=["Account Sync"])

TIMEOUT = 20
PBKDF2_ROUNDS = 200_000


def _server() -> str:
    """라이선스 서버 주소 — 기기 승인에 쓰는 것과 같은 곳."""
    try:
        from licensing.client import _server_url
        return _server_url()
    except Exception:
        return os.getenv("MBAM_LICENSE_SERVER", "https://license.blocklab.co.kr").rstrip("/")


def _uid(current_user: dict) -> str:
    return current_user.get("sub")


def _derive_key(password: str, salt: bytes) -> bytes:
    """비밀번호 → 암호화 키. 서버는 이 값을 절대 받지 않는다."""
    import hashlib
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS, dklen=32)
    return base64.urlsafe_b64encode(dk)


def _encrypt(payload: dict, password: str) -> str:
    from cryptography.fernet import Fernet
    salt = os.urandom(16)
    token = Fernet(_derive_key(password, salt)).encrypt(
        json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    # salt 를 함께 담아야 다른 PC 에서 같은 키를 다시 만들 수 있다.
    return base64.urlsafe_b64encode(salt).decode() + ":" + token.decode()


def _decrypt(blob: str, password: str) -> dict:
    from cryptography.fernet import Fernet, InvalidToken
    try:
        salt_b64, token = blob.split(":", 1)
        salt = base64.urlsafe_b64decode(salt_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="백업 형식이 올바르지 않습니다.")
    try:
        raw = Fernet(_derive_key(password, salt)).decrypt(token.encode())
    except InvalidToken:
        raise HTTPException(status_code=400,
                            detail="비밀번호가 맞지 않습니다. 올릴 때 쓴 비밀번호를 그대로 입력하세요.")
    return json.loads(raw.decode("utf-8"))


def _login(email: str, password: str) -> str:
    """라이선스 서버 로그인 → 토큰. 비밀번호는 로그인 확인에만 쓰고 저장하지 않는다."""
    try:
        r = requests.post(f"{_server()}/login", json={"email": email, "password": password}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"서버에 연결할 수 없습니다: {e}")
    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"로그인 실패 (서버 응답 {r.status_code})")
    token = (r.json() or {}).get("access_token") or (r.json() or {}).get("token")
    if not token:
        raise HTTPException(status_code=502, detail="서버가 토큰을 주지 않았습니다.")
    return token


class SyncRequest(BaseModel):
    email: str
    password: str


@router.post("/upload", summary="이 PC 의 네이버 계정을 암호화해 서버에 보관")
async def upload(req: SyncRequest, db: Session = Depends(get_db),
                 current_user: dict = Depends(get_current_user)):
    uid = _uid(current_user)
    accounts = db.query(NaverAccount).filter(NaverAccount.user_id == uid).all()
    if not accounts:
        raise HTTPException(status_code=400, detail="올릴 계정이 없습니다.")

    payload = {"version": 1, "exported_at": datetime.utcnow().isoformat(), "accounts": []}
    for a in accounts:
        cafes = db.query(JoinedCafe).filter(JoinedCafe.account_id == a.id).all()
        payload["accounts"].append({
            "naver_id": a.naver_id,
            "naver_pw": a.naver_pw or "",
            "blog_addr": getattr(a, "blog_addr", None),
            "cafes": [{"cafe_url": c.cafe_url, "board_name": c.board_name} for c in cafes],
        })

    blob = _encrypt(payload, req.password)
    token = _login(req.email, req.password)
    try:
        r = requests.post(f"{_server()}/sync/upload",
                          json={"blob": blob, "item_count": len(payload["accounts"])},
                          headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"업로드 실패: {e}")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"업로드 실패 (서버 응답 {r.status_code})")
    return {"success": True, "count": len(payload["accounts"]),
            "message": f"계정 {len(payload['accounts'])}개를 서버에 보관했습니다."}


@router.post("/download", summary="서버에 보관된 계정을 이 PC 로 가져오기(합치기)")
async def download(req: SyncRequest, db: Session = Depends(get_db),
                   current_user: dict = Depends(get_current_user)):
    uid = _uid(current_user)
    token = _login(req.email, req.password)
    try:
        r = requests.get(f"{_server()}/sync/download",
                         headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"내려받기 실패: {e}")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"내려받기 실패 (서버 응답 {r.status_code})")
    data = r.json() or {}
    if not data.get("exists"):
        raise HTTPException(status_code=404, detail="서버에 저장된 계정이 없습니다. 다른 PC 에서 먼저 올려주세요.")

    payload = _decrypt(data["blob"], req.password)
    added = updated = cafes_added = 0

    for item in payload.get("accounts", []):
        nid = (item.get("naver_id") or "").strip()
        if not nid:
            continue
        acc = db.query(NaverAccount).filter(NaverAccount.user_id == uid,
                                            NaverAccount.naver_id == nid).first()
        if acc:
            # 이 PC 에만 있는 계정은 건드리지 않는다. 같은 아이디만 갱신한다.
            if item.get("naver_pw"):
                acc.naver_pw = item["naver_pw"]
            if item.get("blog_addr") and hasattr(acc, "blog_addr"):
                acc.blog_addr = item["blog_addr"]
            updated += 1
        else:
            acc = NaverAccount(user_id=uid, naver_id=nid, naver_pw=item.get("naver_pw") or "")
            if item.get("blog_addr") and hasattr(acc, "blog_addr"):
                acc.blog_addr = item["blog_addr"]
            db.add(acc)
            db.flush()          # acc.id 를 얻어야 카페 매핑을 붙일 수 있다
            added += 1

        for c in item.get("cafes", []):
            url = (c.get("cafe_url") or "").strip()
            if not url:
                continue
            exists = db.query(JoinedCafe).filter(JoinedCafe.account_id == acc.id,
                                                 JoinedCafe.cafe_url == url).first()
            if not exists:
                db.add(JoinedCafe(account_id=acc.id, cafe_url=url,
                                  board_name=c.get("board_name") or ""))
                cafes_added += 1

    db.commit()
    msg = f"계정 {added}개 추가, {updated}개 갱신"
    if cafes_added:
        msg += f", 카페 매핑 {cafes_added}개 추가"
    return {"success": True, "added": added, "updated": updated,
            "cafes_added": cafes_added, "message": msg + "했습니다."}


@router.post("/status", summary="서버에 보관된 백업 정보(시각·개수)")
async def status(req: SyncRequest, current_user: dict = Depends(get_current_user)):
    token = _login(req.email, req.password)
    try:
        r = requests.get(f"{_server()}/sync/status",
                         headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"확인 실패: {e}")
    return r.json() if r.status_code == 200 else {"exists": False}
