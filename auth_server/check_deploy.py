# -*- coding: utf-8 -*-
"""
라이선스 서버가 제대로 배포됐는지 확인하는 스크립트.
초보자용 — 저장소 루트의 '배포확인.bat' 을 더블클릭하면 이 파일이 실행된다.

확인하는 것
  1) 서버가 살아 있는지
  2) '제품별 기기 승인'(카페판용) 기능이 들어간 새 버전인지
  3) 관리자 토큰이 아직 기본 예시값인지 (보안 경고)

서버에 아무것도 새로 만들지 않는다(읽기만 한다). 그래서 몇 번을 돌려도 안전하다.

판별 원리
  새 버전의 GET /admin/devices 는 각 기기에 'product' 항목을 같이 준다.
  예전 버전은 그 항목이 아예 없다. 이 차이로 버전을 가른다.
  (예전 버전은 product 를 보내도 무시하고 기존 devices 표만 보기 때문에,
   '등록해 보고 응답을 보는' 방식으로는 두 버전을 구분할 수 없다)
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 배포확인.bat 이 chcp 65001(UTF-8) 로 콘솔을 바꾼 뒤 이 파일을 실행한다.
# 콘솔 코드페이지가 다른 환경에서도 한글이 깨지거나 죽지 않도록 맞춰 준다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SERVER = "https://license.blocklab.co.kr"
DEFAULT_TOKEN = "change-this-admin-token"

OK, NG, WARN = "  [정상]", "  [문제]", "  [주의]"


def admin_token() -> str:
    """admin_tool.py 에 적힌 관리자 토큰을 그대로 읽어 쓴다(토큰을 바꿔도 따라간다)."""
    p = Path(__file__).resolve().parent.parent / "admin_tool.py"
    try:
        m = re.search(r'^ADMIN_TOKEN\s*=\s*["\'](.+?)["\']', p.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    except Exception:
        pass
    return DEFAULT_TOKEN


def get(path, token=None):
    req = urllib.request.Request(SERVER + path)
    if token:
        req.add_header("x-admin-token", token)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def main():
    print("=" * 60)
    print("  라이선스 서버 배포 확인")
    print(f"  대상: {SERVER}")
    print("=" * 60)
    problems = []
    token = admin_token()

    # ── 1) 서버 생존 ──
    print("\n[1/3] 서버가 켜져 있는지 확인...")
    try:
        get("/health")
        print(OK, "서버가 응답합니다.")
    except Exception as e:
        print(NG, f"서버에 연결할 수 없습니다: {e}")
        print("       → 서버가 꺼져 있거나 인터넷이 안 되는 상태입니다.")
        return _end(["서버 연결 실패"])

    # ── 2) 새 버전인지 ──
    print("\n[2/3] 카페판용 '제품별 기기 승인' 기능이 들어갔는지 확인...")
    rows = None
    try:
        rows = get("/admin/devices", token=token)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(NG, "관리자 토큰이 서버와 다릅니다.")
            print("       → admin_tool.py 의 ADMIN_TOKEN 과 서버 docker-compose.yml 의 값이")
            print("         같은지 확인하세요.")
            problems.append("관리자 토큰 불일치")
        else:
            print(NG, f"확인 실패 (HTTP {e.code})")
            problems.append("버전 확인 실패")
    except Exception as e:
        print(NG, f"확인 실패: {e}")
        problems.append("버전 확인 실패")

    if rows is not None:
        if not rows:
            print(WARN, "등록된 기기가 하나도 없어 버전을 판별할 수 없습니다.")
            print("       → 카페 프로그램에서 [승인 요청]을 한 번 한 뒤 다시 실행해 주세요.")
            problems.append("버전 판별 불가(등록 기기 없음)")
        elif any("product" in r for r in rows):
            print(OK, "새 버전이 올라가 있습니다. (카페 설치본 배포 가능)")
            n_cafe = sum(1 for r in rows if r.get("product") == "cafe")
            n_old = sum(1 for r in rows if not r.get("product"))
            print(f"       등록 기기: 카페판 {n_cafe}대 / 기존(크롤러 등) {n_old}대")
        else:
            print(NG, "아직 예전 버전입니다. 배포가 반영되지 않았습니다.")
            print("       → deploy_aws_update.bat 을 실행해 서버를 올려주세요.")
            print("       → 이 상태로 카페 설치본을 배포하면, 크롤러로 승인된 PC가")
            print("         카페 프로그램까지 그냥 열립니다.")
            problems.append("서버가 예전 버전")

    # ── 3) 관리자 토큰 안전성 ──
    print("\n[3/3] 관리자 토큰이 안전한지 확인...")
    if token == DEFAULT_TOKEN:
        print(WARN, "관리자 토큰이 기본 예시값(change-this-admin-token)입니다.")
        print("       → 이 값을 아는 사람은 누구나 고객 기기를 승인·차단하고")
        print("         인증코드를 발급할 수 있습니다.")
        print("       → 배포 가이드 5항을 보고 바꾸시길 권합니다.")
        problems.append("관리자 토큰이 기본값")
    else:
        print(OK, "기본값이 아닌 토큰을 쓰고 있습니다.")

    return _end(problems)


def _end(problems):
    print("\n" + "=" * 60)
    if not problems:
        print("  결과: 모두 정상입니다. 카페 설치본을 배포하셔도 됩니다.")
    else:
        print("  결과: 확인이 필요한 항목이 있습니다")
        for p in problems:
            print(f"        - {p}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")
    try:
        input("\n엔터를 누르면 창이 닫힙니다...")
    except EOFError:
        pass   # 자동 실행(입력 없는 환경)에서는 그냥 끝낸다
