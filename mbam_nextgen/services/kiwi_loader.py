"""Kiwi(형태소 분석기) 공통 로더.

kiwipiepy 는 모델 폴더 경로에 한글 등 비 ASCII 문자가 있으면 모델 파일(extract.mdl)을 열지 못하고,
환경에 따라 예외가 아니라 네이티브 충돌(0xc0000374)로 프로세스 전체를 죽인다. try/except 로 막을 수 없다.
설치형은 %LOCALAPPDATA%\\Programs\\... 에 설치되므로 Windows 사용자 이름이 한글이면 바로 걸리고,
개발 폴더(F:\\02 마케팅 프로그램\\...)에서도 같은 이유로 백엔드가 죽었다.

그래서 Kiwi() 를 만들기 '전에' 모델 경로를 검사하고, 비 ASCII 면 ProgramData 아래 영문 경로로
모델을 한 번 복사해 model_path 로 넘긴다. 그것도 안 되면 None 을 돌려 형태소 분석만 끈다(앱은 계속 동작).
"""
import os
import shutil

_cache = {"done": False, "kiwi": None}


def _is_ascii(path: str) -> bool:
    try:
        path.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _ascii_model_dir(src: str, version: str):
    """모델을 영문 경로로 복사해 그 경로를 돌려준다. 복사가 끝난 적이 있으면 재사용. 실패하면 None."""
    root = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
    dst = os.path.join(root, "MBAM", "kiwi_model", version)
    if not _is_ascii(dst):
        return None
    marker = os.path.join(dst, ".complete")
    if os.path.exists(marker):
        return dst
    tmp = dst + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp)
    shutil.rmtree(dst, ignore_errors=True)
    os.replace(tmp, dst)
    open(marker, "w").close()
    return dst


def load_kiwi():
    """Kiwi 인스턴스(프로세스당 1개 공유) 또는 None.

    클라우드 모드는 분석을 에이전트에 위임하므로 로드하지 않는다(OOM 방지).
    """
    if _cache["done"]:
        return _cache["kiwi"]
    _cache["done"] = True
    if (os.environ.get("EXECUTION_MODE", "local") or "").strip().lower() == "cloud":
        return None
    try:
        from kiwipiepy import Kiwi
        import kiwipiepy_model
        model_dir = os.path.dirname(kiwipiepy_model.__file__)
        if _is_ascii(model_dir):
            _cache["kiwi"] = Kiwi()
        else:
            version = str(getattr(kiwipiepy_model, "__version__", "") or "default")
            ascii_dir = _ascii_model_dir(model_dir, version)
            if ascii_dir:
                _cache["kiwi"] = Kiwi(model_path=ascii_dir)
            else:
                print("[kiwi] 모델 경로에 영문이 아닌 문자가 있어 형태소 분석을 끕니다:", model_dir)
    except Exception as e:
        print(f"[kiwi] 형태소 분석기 로드 실패 → 비활성화: {e}")
        _cache["kiwi"] = None
    return _cache["kiwi"]
