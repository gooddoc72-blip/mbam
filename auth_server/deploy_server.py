# -*- coding: utf-8 -*-
"""
라이선스 서버(AWS) 배포 스크립트.
초보자용 — 저장소 루트의 'deploy_aws_update.bat' 을 더블클릭하면 이 파일이 실행된다.

하는 일
  0) SSH 키 파일 권한 조정 (윈도우 기본 ssh 는 권한이 열려 있으면 접속을 거부한다)
  1) 서버의 운영 DB 백업
  2) 서버 소스 파일만 업로드  ※ license.db 는 절대 올리지 않는다
  3) 도커 컨테이너 재빌드·재시작
  4) 서버 응답 확인

[중요] 예전 배포 방식(`scp -r auth_server 서버:~/`)은 폴더를 통째로 올려서
내 PC 의 비어 있는 license.db 가 서버의 운영 DB 를 덮어썼다. 발급된 인증코드와
승인된 고객 기기가 전부 사라지는 동작이라, 지금은 파일을 하나씩 지정해서 올린다.

배치 파일이 아니라 파이썬으로 만든 이유:
  한글이 든 .bat 는 콘솔 코드페이지에 따라 글자가 깨지고 명령까지 잘못 읽힌다.
  파이썬은 출력 인코딩을 직접 맞출 수 있어 어느 PC 에서나 안전하다.
"""
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
SERVER = "ubuntu@18.209.162.250"
KEY = ROOT / "my-key.pem"
REMOTE = "~/auth_server"

# 서버로 올릴 파일 — license.db(운영 DB)는 여기에 절대 넣지 말 것
UPLOAD = [
    "server.py",
    "issue_codes.py",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
]

SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20"]
DRY = "--dry-run" in sys.argv


def step(n, total, msg):
    print(f"\n[{n}/{total}] {msg}")


def fail(msg, hint=""):
    print(f"\n  [실패] {msg}")
    if hint:
        print(f"         {hint}")
    print("\n" + "=" * 58)
    print("  배포가 중단되었습니다. 위 내용을 그대로 알려주시면 도와드립니다.")
    print("=" * 58)
    _wait()
    sys.exit(1)


def run(args, what, hint=""):
    """명령 실행. 실패하면 안내를 띄우고 종료한다."""
    if DRY:
        print("  (연습 모드) 실행하지 않음:", " ".join(str(a) for a in args)[:110])
        return ""
    try:
        r = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        fail(f"{what} — 필요한 프로그램({args[0]})을 찾을 수 없습니다.",
             "윈도우 10 이상이면 기본 설치돼 있습니다.")
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()
        fail(f"{what}", (detail[:400] + "\n         " + hint) if hint else detail[:400])
    return (r.stdout or "").strip()


def _wait():
    try:
        input("\n엔터를 누르면 창이 닫힙니다...")
    except EOFError:
        pass


def main():
    print("=" * 58)
    print("  라이선스 서버 배포")
    print(f"  대상: {SERVER}")
    if DRY:
        print("  ** 연습 모드 — 실제로는 아무것도 바꾸지 않습니다 **")
    print("=" * 58)

    if not KEY.exists():
        fail(f"접속 열쇠 파일이 없습니다: {KEY}",
             "my-key.pem 파일이 프로그램 폴더에 있어야 합니다.")

    # ── 0) 키 권한 ──
    step(0, 4, "접속 열쇠 파일 권한 확인 중...")
    # 윈도우 ssh 는 키 파일을 다른 사용자가 읽을 수 있으면 "UNPROTECTED PRIVATE KEY FILE" 로 거부한다
    subprocess.run(["icacls", str(KEY), "/inheritance:r"],
                   capture_output=True, text=True)
    subprocess.run(["icacls", str(KEY), "/grant:r", f"{Path.home().name}:(R)"],
                   capture_output=True, text=True)
    print("  완료")

    # ── 1) 백업 ──
    step(1, 4, "서버에 있는 기존 고객 자료 백업 중...")
    # updates/ 도 함께 만든다 — docker-compose 가 이 폴더를 컨테이너에 마운트한다.
    # 없으면 도커가 root 소유로 만들어 버려서 나중에 scp 로 파일을 못 올린다.
    out = run(["ssh", *SSH_OPTS, "-i", str(KEY), SERVER,
               f"mkdir -p {REMOTE} {REMOTE}/updates && if [ -f {REMOTE}/license.db ]; then "
               f"cp {REMOTE}/license.db {REMOTE}/license.db.bak.$(date +%Y%m%d_%H%M%S) && echo BACKUP_OK; "
               f"else echo NO_DB; fi"],
              "서버에 접속하지 못했습니다.",
              "인터넷 연결을 확인하세요. 그래도 안 되면 서버가 꺼져 있을 수 있습니다.")
    print("  백업 완료" if "BACKUP_OK" in out else "  기존 자료 없음 (처음 설치)")

    # ── 2) 업로드 ──
    step(2, 4, "서버 프로그램 파일 올리는 중... (고객 자료는 건드리지 않습니다)")
    files = []
    for name in UPLOAD:
        p = ROOT / "auth_server" / name
        if not p.exists():
            fail(f"보내야 할 파일이 없습니다: {p}")
        files.append(str(p))
    run(["scp", *SSH_OPTS, "-i", str(KEY), *files, f"{SERVER}:{REMOTE}/"],
        "파일 전송에 실패했습니다.", "인터넷 연결을 확인하고 다시 시도하세요.")
    print(f"  {len(files)}개 파일 전송 완료")

    # ── 3) 재시작 ──
    step(3, 4, "서버 프로그램 재시작 중... 1~2분 걸립니다. 기다려 주세요.")
    run(["ssh", *SSH_OPTS, "-i", str(KEY), SERVER,
         "cd auth_server && sudo docker compose up -d --build"],
        "서버 재시작에 실패했습니다.")
    print("  재시작 완료")

    # ── 4) 확인 ──
    step(4, 4, "서버가 정상 응답하는지 확인...")
    out = run(["ssh", *SSH_OPTS, "-i", str(KEY), SERVER,
               "sleep 3; curl -s -m 5 http://127.0.0.1:8005/health"],
              "서버 응답을 확인하지 못했습니다.")
    ok = '"ok":true' in out.replace(" ", "")

    print("\n" + "=" * 58)
    if ok or DRY:
        print("  배포가 끝났습니다.")
        print("\n  다음: '배포확인.bat' 을 실행해 [정상] 이 뜨는지 보세요.")
    else:
        print("  배포는 됐지만 서버 응답이 이상합니다.")
        print(f"  서버 응답: {out[:200]}")
        print("  '배포확인.bat' 을 실행해 상태를 확인해 주세요.")
    print("=" * 58)
    _wait()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")
        _wait()
