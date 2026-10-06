# -*- coding: utf-8 -*-
"""업데이트 패키지를 라이선스 서버에 올린다.

루트의 '업데이트_서버에올리기.bat' 을 더블클릭하면 이 파일이 실행된다.

하는 일
  1) installer/output/updates 에서 최신 패키지와 정보 파일을 찾는다
  2) 서버의 ~/auth_server/updates/ 로 올린다 (도커가 이 폴더를 컨테이너에 마운트한다)
  3) 서버가 새 버전을 제대로 알려주는지 확인한다

※ 서버 프로그램 자체를 고쳤을 때는 이 스크립트가 아니라 '배포하기'(deploy_server.py)를 쓴다.
   이건 고객이 받을 업데이트 파일만 올리는 용도다.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
SERVER = "ubuntu@18.209.162.250"
KEY = ROOT / "my-key.pem"
REMOTE = "~/auth_server/updates"
UPDATES_DIR = ROOT / "installer" / "output" / "updates"
PUBLIC_URL = "https://license.blocklab.co.kr"

SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20"]


def fail(msg, hint=""):
    print(f"\n  [실패] {msg}")
    if hint:
        print(f"         {hint}")
    input("\n엔터를 누르면 창이 닫힙니다...")
    sys.exit(1)


def run(args, what, hint=""):
    try:
        r = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        fail(f"{what} — 필요한 프로그램({args[0]})을 찾을 수 없습니다.")
    if r.returncode != 0:
        fail(what, ((r.stderr or r.stdout or "").strip()[:400] + ("\n         " + hint if hint else "")))
    return (r.stdout or "").strip()


def main():
    print("=" * 58)
    print("  업데이트 파일 올리기")
    print(f"  대상: {SERVER}:{REMOTE}")
    print("=" * 58)

    if not KEY.exists():
        fail(f"접속 열쇠 파일이 없습니다: {KEY}")
    if not UPDATES_DIR.exists():
        fail(f"업데이트 폴더가 없습니다: {UPDATES_DIR}",
             "installer\\업데이트_패키지_만들기.ps1 을 먼저 실행하세요.")

    # 제품 선택 — 인자로 주거나(예: upload_update.py mbam), 없으면 가장 최근에 만든 것.
    #   cafe = 카페 마케팅 / mbam = 마케팅연구소
    product = (sys.argv[1].strip().lower() if len(sys.argv) > 1 else "")
    if product:
        manifest_path = UPDATES_DIR / f"{product}-latest.json"
        if not manifest_path.exists():
            fail(f"{product}-latest.json 이 없습니다.",
                 f"installer\\업데이트_패키지_만들기.ps1 -Product {product} 를 먼저 실행하세요.")
    else:
        cands = sorted(UPDATES_DIR.glob("*-latest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not cands:
            fail("올릴 버전 정보 파일(*-latest.json)이 없습니다.",
                 "installer\\업데이트_패키지_만들기.ps1 을 먼저 실행하세요.")
        manifest_path = cands[0]
        product = manifest_path.name.replace("-latest.json", "")
        if len(cands) > 1:
            others = ", ".join(c.name.replace("-latest.json", "") for c in cands)
            print(f"  ※ 여러 제품이 있어 가장 최근 것을 올립니다: {product}")
            print(f"     (지정하려면: upload_update.py <제품명>  —  {others})")

    man = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    version = man.get("version")
    zip_name = str(man.get("url", "")).rsplit("/", 1)[-1]
    zip_path = UPDATES_DIR / zip_name
    if not zip_path.exists():
        fail(f"패키지 파일이 없습니다: {zip_path}")

    size_mb = round(zip_path.stat().st_size / 1024 / 1024, 1)
    print(f"\n  제품      : {product}")
    print(f"  올릴 버전 : {version}")
    print(f"  파일      : {zip_name} ({size_mb} MB)")
    print(f"  변경 내용 : {man.get('notes') or '(없음)'}")

    # ── 키 권한 (윈도우 기본 ssh 는 권한이 열려 있으면 거부한다) ──
    subprocess.run(["icacls", str(KEY), "/inheritance:r"], capture_output=True, text=True)
    subprocess.run(["icacls", str(KEY), "/grant:r", f"{Path.home().name}:(R)"],
                   capture_output=True, text=True)

    print("\n[1/3] 서버 폴더 준비...")
    run(["ssh", *SSH_OPTS, "-i", str(KEY), SERVER, f"mkdir -p {REMOTE}"],
        "서버에 접속하지 못했습니다.", "인터넷 연결을 확인하세요.")
    print("  완료")

    # ⚠ 패키지(zip)를 먼저 올리고 정보 파일(json)을 나중에 올린다.
    #   순서가 반대면, 정보 파일만 올라간 순간 고객이 '새 버전 있음'을 보고
    #   아직 없는 파일을 받으러 와 404 가 난다.
    print("\n[2/3] 파일 전송...")
    run(["scp", *SSH_OPTS, "-i", str(KEY), str(zip_path), f"{SERVER}:{REMOTE}/"],
        "패키지 전송에 실패했습니다.")
    print(f"  {zip_name} 완료")
    run(["scp", *SSH_OPTS, "-i", str(KEY), str(manifest_path), f"{SERVER}:{REMOTE}/"],
        "버전 정보 전송에 실패했습니다.")
    print(f"  {manifest_path.name} 완료")

    print("\n[3/3] 서버 응답 확인...")
    try:
        with urllib.request.urlopen(f"{PUBLIC_URL}/update/{product}/latest", timeout=15) as resp:
            got = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        fail(f"서버 확인에 실패했습니다: {e}",
             "파일은 올라갔을 수 있습니다. 서버가 재시작 중이면 잠시 뒤 다시 확인하세요.")

    print("\n" + "=" * 58)
    if got.get("version") == version:
        print(f"  올리기 완료 — 서버가 버전 {version} 을 안내하고 있습니다.")
        print("\n  고객이 프로그램을 껐다 켜면 업데이트 안내가 뜹니다.")
    else:
        print("  파일은 올라갔지만 서버 응답이 예상과 다릅니다.")
        print(f"  기대: {version} / 서버: {got.get('version')}")
        print("  서버가 아직 재시작 중일 수 있습니다. 1분 뒤 다시 실행해 보세요.")
    print("=" * 58)
    input("\n엔터를 누르면 창이 닫힙니다...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류: {e}")
        input("\n엔터를 누르면 창이 닫힙니다...")
