import pytest
from fastapi.testclient import TestClient
from mbam_nextgen.backend.main import app

client = TestClient(app)

def test_login_success():
    """올바른 자격 증명으로 로그인 시 JWT 토큰이 발급되는지 검증"""
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["plan_type"] == "pro"

def test_login_failure():
    """잘못된 비밀번호 입력 시 401 Unauthorized 반환 검증"""
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrong_password"
    })
    
    assert response.status_code == 401
    assert response.json()["detail"] == "아이디 또는 비밀번호가 올바르지 않습니다."

def test_protected_route_with_token():
    """JWT 토큰을 포함한 요청이 보호된 라우트(/me)에 접근 가능한지 검증"""
    # 1. 로그인하여 토큰 획득
    login_res = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testuser123"
    })
    token = login_res.json()["access_token"]
    
    # 2. 획득한 토큰으로 /me 엔드포인트 접근
    me_res = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "testuser"
    assert me_data["plan_type"] == "basic"
    assert me_data["credits"] == 100

def test_protected_route_without_token():
    """토큰 없이 보호된 라우트 접근 시 403 Forbidden 검증"""
    response = client.get("/api/auth/me")
    assert response.status_code == 403
