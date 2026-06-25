# -*- coding: utf-8 -*-
"""
설치 시 1회 실행 — JWT_SECRET / ENV_CIPHER_KEY 가 없으면 생성해 .env 에 영구 저장.
이 키들은 로그인 토큰 서명·계정 비밀번호 암호화에 쓰이므로 한 번 정해지면 바뀌면 안 됩니다.
(기존 PC의 DB/계정을 그대로 쓰려면 원본 PC의 JWT_SECRET / ENV_CIPHER_KEY 값을 .env 에 그대로 복사하세요.)
"""
import os
import secrets
from pathlib import Path

ENV = Path(__file__).resolve().parent / ".env"


def load_existing_keys(text):
    keys = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        keys[k.strip()] = v.strip()
    return keys


def main():
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    existing = load_existing_keys(text)
    lines = text.splitlines()
    added = []

    def ensure(name, gen):
        # .env 에도 없고 시스템 환경변수에도 없으면 새로 생성
        if existing.get(name) or os.environ.get(name):
            return
        lines.append(f"{name}={gen()}")
        added.append(name)

    ensure("JWT_SECRET", lambda: secrets.token_urlsafe(48))

    def gen_cipher():
        try:
            from cryptography.fernet import Fernet
            return Fernet.generate_key().decode()
        except Exception:
            return secrets.token_urlsafe(32)

    ensure("ENV_CIPHER_KEY", gen_cipher)

    if added:
        content = "\n".join(lines).rstrip("\n") + "\n"
        ENV.write_text(content, encoding="utf-8")
        print(f"[보안키] 새로 생성해 .env 에 저장: {', '.join(added)}")
        print("        (이 .env 는 백업해 두세요. 분실 시 기존 계정 비밀번호 복호화 불가)")
    else:
        print("[보안키] JWT_SECRET / ENV_CIPHER_KEY 이미 설정됨 — 변경 없음")


if __name__ == "__main__":
    main()
