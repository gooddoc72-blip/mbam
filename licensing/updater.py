"""설치본 자동 업데이트 — 바뀌는 부분(약 14MB)만 받아 교체한다.

왜 '부분 업데이트' 인가
    설치본 2.4GB 중 실제로 바뀌는 건 파이썬 소스(3.4MB)와 프론트 빌드(10.8MB)뿐이다.
    나머지(동봉 Python·Chromium·Node·node_modules 2.35GB)는 코드를 고쳐도 그대로다.
    그래서 설치본을 통째로 다시 내려받게 하지 않고 바뀐 부분만 교체한다.

언제 도는가
    런처가 서버(백엔드/프론트)를 띄우기 *전에* 한 번 확인한다.
    실행 중에 파일을 갈아끼우면 열려 있는 파일이 잠겨 실패하므로, 반드시 기동 전에 끝낸다.

안전장치
    - sha256 로 받은 파일을 검증한다(중간에 깨졌거나 엉뚱한 파일이면 중단).
    - 교체 전에 기존 폴더를 backup 으로 옮겨두고, 실패하면 되돌린다.
    - 네트워크가 안 되면 조용히 넘어간다(오프라인에서도 프로그램은 떠야 한다).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# 업데이트로 교체되는 대상. 이 목록에 없는 것(runtime, node_modules, 사용자 데이터)은 건드리지 않는다.
# 런처 파일 이름만 제품마다 다르고 나머지는 같다. 없는 파일은 _replace_target 이 그냥 건너뛰므로
# 두 제품의 런처를 함께 넣어도 서로 영향을 주지 않는다.
UPDATE_TARGETS = [
    ("mbam_nextgen", "dir"),
    ("licensing", "dir"),
    (os.path.join("mbam-web", ".next"), "dir"),
    ("cafe_launcher.py", "file"),      # 카페 전용판
    ("cafe_auth_gate.py", "file"),
    ("blog_launcher.py", "file"),      # 블로그 전용판
    ("blog_auth_gate.py", "file"),
    ("mbam_launcher.py", "file"),      # 마케팅연구소(전체판)
    ("mbam_auth_gate.py", "file"),
    ("run_backend.py", "file"),
    ("version.json", "file"),
    # 예외적으로 runtime 안의 파일 하나. 1.1.5 까지의 설치본에는 C++ 런타임(msvcp140.dll)이
    # 빠져 있어서, VC++ 재배포 패키지가 없는 깨끗한 Windows 에서는 greenlet 로드 실패로
    # 백엔드가 아예 뜨지 않는다. 이미 설치된 고객을 재설치 없이 고치려면 이것도 함께 교체해야 한다.
    # (mac 설치본에는 이 파일이 없고, 없는 항목은 _replace_target 이 그냥 건너뛴다)
    (os.path.join("runtime", "python", "msvcp140.dll"), "file"),
]

# 사용자 데이터라 업데이트가 절대 지우면 안 되는 것들(mbam_nextgen 안에 있다)
KEEP_INSIDE_TARGETS = {"profiles", "sessions", "__pycache__"}


def _read_json(path: Path) -> dict:
    # ⚠ utf-8-sig 로 읽는다. version.json 은 PowerShell 빌드 스크립트가 만드는데
    #   Set-Content -Encoding UTF8 이 BOM 을 붙이고, 그러면 utf-8 로는 JSONDecodeError 가 난다.
    #   그 경우 버전이 0.0.0 으로 잡혀 '업데이트했는데도 매번 다시 물어보는' 무한 루프가 된다.
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def local_version(app_dir: Path) -> str:
    return str(_read_json(app_dir / "version.json").get("version") or "0.0.0")


def _parse(v: str) -> tuple:
    """'1.2.10' → (1,2,10). 문자열 비교를 쓰면 1.2.10 < 1.2.9 로 잘못 판정된다."""
    out = []
    for part in str(v).split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3])


def is_newer(remote: str, local: str) -> bool:
    return _parse(remote) > _parse(local)


def fetch_manifest(server: str, product: str = "cafe", timeout: int = 8) -> dict | None:
    """서버에서 최신 버전 정보를 받아온다. 실패하면 None(= 업데이트 확인 생략)."""
    url = f"{server.rstrip('/')}/update/{product}/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MBAM-Cafe-Updater"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Update] 최신 버전 확인 실패(무시하고 계속): {e}")
        return None


def check(app_dir: Path, server: str, product: str = "cafe") -> dict | None:
    """업데이트가 있으면 manifest, 없으면 None."""
    man = fetch_manifest(server, product)
    if not man or not man.get("version") or not man.get("url"):
        return None
    cur = local_version(app_dir)
    if not is_newer(man["version"], cur):
        print(f"[Update] 최신 상태입니다 (설치 {cur} / 서버 {man['version']})")
        return None
    print(f"[Update] 새 버전 발견: {cur} → {man['version']}")
    return man


def _download(url: str, dest: Path, expect_sha256: str | None, progress=None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "MBAM-Cafe-Updater"})
    sha = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            sha.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    got = sha.hexdigest()
    if expect_sha256 and got.lower() != expect_sha256.lower():
        raise RuntimeError(f"파일 검증 실패(sha256 불일치)\n  기대: {expect_sha256}\n  실제: {got}")


def _replace_target(src_root: Path, app_dir: Path, rel: str, kind: str, backup_dir: Path) -> bool:
    """압축을 푼 것에 해당 항목이 있으면 교체한다. 교체 전 원본은 backup 으로 옮긴다."""
    src = src_root / rel
    if not src.exists():
        return False
    dst = app_dir / rel
    bak = backup_dir / rel
    bak.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        if kind == "dir":
            # ⚠ profiles/sessions(네이버 로그인 세션)는 사용자 데이터다. 통째로 옮기면 날아간다.
            #   따로 빼두었다가 새 폴더에 되돌려 놓는다.
            keep = {}
            for name in KEEP_INSIDE_TARGETS:
                p = dst / name
                if p.exists():
                    tmp = backup_dir / f"__keep__{rel.replace(os.sep, '_')}_{name}"
                    shutil.move(str(p), str(tmp))
                    keep[name] = tmp
            shutil.move(str(dst), str(bak))
            shutil.move(str(src), str(dst))
            for name, tmp in keep.items():
                shutil.move(str(tmp), str(dst / name))
            return True
        shutil.move(str(dst), str(bak))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return True


def apply(app_dir: Path, manifest: dict, progress=None) -> tuple[bool, str]:
    """업데이트를 내려받아 적용한다. (성공여부, 메시지)

    반드시 서버(백엔드/프론트)를 띄우기 전에 호출해야 한다 — 실행 중이면 파일이 잠긴다.
    """
    app_dir = Path(app_dir)
    work = Path(tempfile.mkdtemp(prefix="mbam_update_"))
    backup_dir = work / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    replaced: list[tuple[str, str]] = []
    try:
        zip_path = work / "update.zip"
        print(f"[Update] 내려받는 중: {manifest['url']}")
        _download(manifest["url"], zip_path, manifest.get("sha256"), progress)

        extract_dir = work / "new"
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)

        # 압축 안이 한 겹 더 싸여 있으면(폴더 하나만 있으면) 그 안을 쓴다.
        entries = [p for p in extract_dir.iterdir()]
        if len(entries) == 1 and entries[0].is_dir() and not (extract_dir / "version.json").exists():
            extract_dir = entries[0]

        if not (extract_dir / "version.json").exists():
            raise RuntimeError("업데이트 파일에 version.json 이 없습니다. (잘못된 패치 파일)")

        print("[Update] 파일 교체 중...")
        for rel, kind in UPDATE_TARGETS:
            if _replace_target(extract_dir, app_dir, rel, kind, backup_dir):
                replaced.append((rel, kind))
                print(f"  교체: {rel}")

        if not replaced:
            raise RuntimeError("교체할 파일이 없습니다.")

        print(f"[Update] 완료 — 버전 {manifest['version']}")
        return True, f"버전 {manifest['version']} 으로 업데이트했습니다."

    except Exception as e:
        # 되돌리기 — 이미 바꾼 것만 원위치
        print(f"[Update] 실패: {e}\n[Update] 원래 상태로 되돌립니다...")
        for rel, kind in replaced:
            try:
                dst = app_dir / rel
                bak = backup_dir / rel
                if bak.exists():
                    if dst.exists():
                        shutil.rmtree(dst, ignore_errors=True) if kind == "dir" else dst.unlink(missing_ok=True)
                    shutil.move(str(bak), str(dst))
            except Exception as e2:
                print(f"  되돌리기 실패({rel}): {e2}")
        return False, f"업데이트에 실패해 이전 상태로 되돌렸습니다.\n{e}"

    finally:
        shutil.rmtree(work, ignore_errors=True)
