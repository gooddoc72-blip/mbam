# -*- coding: utf-8 -*-
"""
관리자용 인증코드 발급/관리 CLI  (표준 라이브러리만 사용, 추가 설치 불필요)

사용법 (라이선스 서버가 떠 있어야 함):
    set ADMIN_TOKEN=서버에_설정한_관리자_토큰
    set LICENSE_SERVER=http://내서버주소:8005     (생략 시 http://127.0.0.1:8005)

    python issue_codes.py issue --count 5 --memo "홍길동" --days 365
    python issue_codes.py list
    python issue_codes.py revoke  --code XXXX-XXXX-XXXX-XXXX
    python issue_codes.py reset   --code XXXX-XXXX-XXXX-XXXX   # PC 이전
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("LICENSE_SERVER", "http://127.0.0.1:8005").rstrip("/")
TOKEN = os.environ.get("ADMIN_TOKEN", "")


def _call(method: str, path: str, body: dict | None = None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-admin-token", TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")
        print(f"[오류 {e.code}] {detail}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[연결 실패] {BASE} 에 접속할 수 없습니다: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if not TOKEN:
        print("[안내] 환경변수 ADMIN_TOKEN 이 비어 있습니다. 서버 콘솔에 출력된 토큰을 설정하세요.", file=sys.stderr)

    ap = argparse.ArgumentParser(description="MBAM 인증코드 관리")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_issue = sub.add_parser("issue", help="코드 발급")
    p_issue.add_argument("--count", type=int, default=1)
    p_issue.add_argument("--memo", default="")
    p_issue.add_argument("--days", type=int, default=0, help="유효일수(0=무기한)")
    p_issue.add_argument("--pcs", type=int, default=1, help="PC 대수(기본 1)")

    sub.add_parser("list", help="코드 전체 목록")

    for name in ("revoke", "unrevoke", "reset"):
        pp = sub.add_parser(name)
        pp.add_argument("--code", required=True)

    # ── 계정(회원/체험) 관리 ──
    sub.add_parser("users", help="가입 계정 목록")

    p_up = sub.add_parser("upgrade", help="계정을 유료로 전환")
    p_up.add_argument("--email", required=True)
    p_up.add_argument("--days", type=int, default=365, help="유료 일수(0=무기한)")

    p_ext = sub.add_parser("extend", help="체험 기간 연장")
    p_ext.add_argument("--email", required=True)
    p_ext.add_argument("--days", type=int, default=5)

    p_blk = sub.add_parser("block", help="계정 차단")
    p_blk.add_argument("--email", required=True)

    args = ap.parse_args()

    if args.cmd == "issue":
        res = _call("POST", "/admin/issue", {
            "count": args.count, "memo": args.memo,
            "valid_days": args.days, "max_activations": args.pcs,
        })
        print(f"\n발급된 코드 {res['count']}개:")
        for c in res["issued"]:
            print("  " + c)
    elif args.cmd == "list":
        rows = _call("GET", "/admin/list")
        print(f"\n총 {len(rows)}개")
        for r in rows:
            state = "차단" if not r["is_active"] else ("활성PC:" + (r["hwid"][:12] + "…" if r["hwid"] else "미사용"))
            print(f"  {r['code']}  | {state}  | {r.get('memo') or ''}  | exp={r.get('expires_at') or '무기한'}")
    elif args.cmd in ("revoke", "unrevoke", "reset"):
        res = _call("POST", f"/admin/{args.cmd}", {"code": args.code})
        print(res.get("message", res))
    elif args.cmd == "users":
        rows = _call("GET", "/admin/users")
        print(f"\n총 {len(rows)}개 계정")
        for r in rows:
            mark = "✓" if r["allowed"] else "✗"
            print(f"  [{mark}] {r['email']:<28} {r['plan']:<7} 남은 {r['days_left']}일  "
                  f"가입={(r.get('created_at') or '')[:10]}  최근로그인={(r.get('last_login') or '-')[:10]}")
    elif args.cmd == "upgrade":
        res = _call("POST", "/admin/upgrade", {"email": args.email, "days": args.days})
        print("유료 전환:", res.get("status"))
    elif args.cmd == "extend":
        res = _call("POST", "/admin/extend_trial", {"email": args.email, "days": args.days})
        print("체험 연장:", res.get("status"))
    elif args.cmd == "block":
        res = _call("POST", "/admin/block_user", {"email": args.email})
        print(res.get("message", res))


if __name__ == "__main__":
    main()
