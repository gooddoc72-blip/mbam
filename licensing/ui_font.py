# -*- coding: utf-8 -*-
"""
tkinter 창에 쓸 OS 별 한글 폰트.

'맑은 고딕' 은 Windows 전용이다. 맥에는 없으므로 Tk 가 기본 폰트로 대체하는데,
그 기본 폰트가 한글 자소를 못 그려서 인증창·제어창의 글자가 네모(□)로 나온다.
고객이 처음 보는 화면이라 여기서 깨지면 프로그램이 고장 난 것으로 보인다.

쓰는 곳: cafe_auth_gate.py, cafe_launcher.py, licensing/update_prompt.py
"""
import sys

if sys.platform == "darwin":
    # macOS 10.11+ 기본 한글 서체. 없으면 Tk 가 AppleGothic 으로 내려간다.
    _KO = "Apple SD Gothic Neo"
    _MONO = "Menlo"
elif sys.platform == "win32":
    _KO = "맑은 고딕"
    _MONO = "Consolas"
else:
    _KO = "NanumGothic"
    _MONO = "DejaVu Sans Mono"


def ko(size: int, weight: str = None):
    """한글 UI 폰트 튜플. tkinter 의 font= 에 그대로 넣는다."""
    return (_KO, size, weight) if weight else (_KO, size)


def mono(size: int, weight: str = None):
    """기기번호처럼 자릿수를 맞춰 보여줄 때 쓰는 고정폭 폰트."""
    return (_MONO, size, weight) if weight else (_MONO, size)
