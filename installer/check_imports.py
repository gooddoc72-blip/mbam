"""동봉 Python 에 고객용 코드가 import 하는 패키지가 전부 있는지 검사한다 (설치형 빌드용).

    runtime\\python\\python.exe check_imports.py <페이로드 폴더>

requirements_local.txt 는 '실제로 쓰는 것만' 담은 목록이라, 코드에 새 import 를 넣고
목록에 안 넣으면 개발 PC 에서는 멀쩡하고 고객 PC 에서만 백엔드가 안 뜬다.
모듈을 실제로 import 하면 스케줄러 등이 켜지므로, 소스를 파싱해 import 이름만 모으고
find_spec 으로 존재 여부만 확인한다(코드를 실행하지 않음).

종료코드 0 = 정상, 1 = 빠진 패키지 있음.
"""
import ast
import importlib.util
import os
import sys
import warnings

# 소스 파싱 중 나는 SyntaxWarning(예: invalid escape sequence)이 stderr 로 나가면
# 빌드 스크립트(ErrorActionPreference=Stop)가 그걸 실패로 처리한다 — 검사와 무관하므로 끈다.
warnings.simplefilter("ignore")

# 고객용 코드에 import 는 있지만 동봉하지 않는 것 — 전부 쓰는 쪽이 없거나 try/except 로 감싸져 있다.
ALLOWED_MISSING = {
    "redis",      # backend/redis_queue.py — 클라우드(웹용) 전용, 설치형은 쓰지 않음
    "streamlit",  # mbam_nextgen/dashboard.py — 개발용 대시보드
    "pandas",     # 위 dashboard.py 안에서만 사용
}
TARGETS = ["mbam_nextgen", "licensing", "blog_launcher.py", "blog_auth_gate.py",
           "cafe_launcher.py", "cafe_auth_gate.py", "run_backend.py"]
SKIP_DIRS = {"__pycache__", "profiles", "sessions", "scratch", "tests",
             "temp_clips", "temp_images", "logs"}


def collect(root: str) -> dict:
    found: dict[str, str] = {}

    def scan(path: str) -> None:
        try:
            tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            return
        for n in ast.walk(tree):
            names = []
            if isinstance(n, ast.Import):
                names = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                names = [n.module]
            for name in names:
                found.setdefault(name.split(".")[0], os.path.relpath(path, root))

    for t in TARGETS:
        p = os.path.join(root, t)
        if os.path.isfile(p):
            scan(p)
        elif os.path.isdir(p):
            for d, dirs, files in os.walk(p):
                dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith("test")]
                for f in files:
                    if f.endswith(".py") and not f.startswith("test_"):
                        scan(os.path.join(d, f))
    return found


def main() -> int:
    root = os.path.abspath(sys.argv[1])
    sys.path.insert(0, root)
    local = {t.removesuffix(".py") for t in TARGETS}
    missing = []
    for name, where in sorted(collect(root).items()):
        if name in sys.stdlib_module_names or name in local or name in ALLOWED_MISSING:
            continue
        if importlib.util.find_spec(name) is None:
            missing.append(f"{name}  (예: {where})")
    if missing:
        print("동봉 Python 에 없는 패키지:")
        for m in missing:
            print("  -", m)
        print("installer\\requirements_local.txt 에 추가하고 다시 빌드하세요.")
        return 1
    print("IMPORTS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
