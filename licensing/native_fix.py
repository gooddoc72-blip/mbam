"""동봉 Python 런타임에 빠진 C++ 런타임(msvcp140.dll)을 제자리에 채워 넣는다.

왜 필요한가
    동봉 Python(python-build-standalone)은 C 런타임(vcruntime140*.dll)만 함께 오고
    C++ 런타임(msvcp140.dll)은 넣어주지 않는다. 그런데 greenlet(=playwright.async_api 가
    import 한다)·numpy·pandas·pyarrow 는 C++ 로 만들어져 이 DLL 을 요구한다.
    빌드 PC 에는 다른 프로그램이 깔아둔 VC++ 재배포 패키지 덕에 System32 에 있어서
    문제가 드러나지 않고, VC++ 재배포 패키지가 없는 깨끗한 Windows(고객 PC)에서만
    백엔드가 통째로 죽는다:
        ImportError: DLL load failed while importing _greenlet: 지정된 모듈을 찾을 수 없습니다

1.1.5 까지의 설치본을 업데이트로 고치기 위한 우회로
    업데이트는 고객 PC 에 '이미 깔려 있는' updater.py 가 수행하고, 그 교체 대상 목록에는
    runtime\\ 이 없다. 그래서 새 목록에 msvcp140.dll 을 넣어도 구버전 설치본에는 닿지 않는다.
    대신 licensing\\ 은 예전부터 교체 대상이므로, DLL 을 licensing\\runtime_fix\\ 에 실어 보내고
    런처가 그걸 runtime\\python\\ 으로 옮겨 놓는다. 한 번 옮기면 그다음부터는 정상이다.

    → 신규 설치본은 빌드 시점에 runtime\\python\\ 에 이미 들어 있어 이 함수가 할 일이 없다.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

DLL_NAME = "msvcp140.dll"


def ensure_msvc_runtime(app_dir: Path) -> str | None:
    """동봉 Python 옆에 msvcp140.dll 이 없으면 채워 넣는다.

    반환값은 로그에 남길 메시지(할 일이 없었으면 None). 어떤 경우에도 예외를 올리지 않는다 —
    이 보정이 실패한다고 프로그램 실행 자체를 막을 이유는 없다.
    """
    if sys.platform != "win32":
        return None
    try:
        py_dir = Path(app_dir) / "runtime" / "python"
        if not py_dir.is_dir():
            return None                      # 동봉 런타임을 쓰지 않는 개발 환경
        target = py_dir / DLL_NAME
        if target.exists():
            return None                      # 정상 — 신규 설치본은 여기서 끝난다

        src = Path(app_dir) / "licensing" / "runtime_fix" / DLL_NAME
        if not src.exists():
            return None
        shutil.copy2(src, target)
        return f"[NativeFix] {DLL_NAME} 을 동봉 Python 에 복구했습니다 → {target}"
    except Exception as e:
        return f"[NativeFix] 복구 실패: {e}"
