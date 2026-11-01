"""원고 속 '사진 표시'를 발행용 표준 마커로 통일한다(블로그·카페 공용).

사람이 쓴 원고(또는 외부 GPT 원고)는 사진 자리를 제각각 적는다:
    [이미지1: 대표이미지]   [사진3]   (사진 2)   <사진>   【사진1】   사진 4   📷 5
지금까지는 정확히 [이미지] / [이미지:N] 만 알아봐서, 나머지는 '본문에 새지 않게' 지워졌고
사진은 AI·순서 배치로 엉뚱한 자리에 들어갔다.

normalize_photo_markers() 는 이런 표시를 [이미지:N](번호 있음) / [이미지](번호 없음)로 바꾸고,
표시 바로 아래 '📁 파일명: xxx.png' 줄이 있으면 지우면서 {N: 파일명} 으로 돌려준다.
문장 속 '사진이 예쁘네요' 같은 표현은 건드리지 않는다(괄호로 감싸였거나 그 줄에 표시만 있을 때만).
"""
import os
import re

_WORD = r'(?:사진|이미지|그림|photo|img|📷|📸)'
_OPEN, _CLOSE = r'[\[\(<【〔{]', r'[\]\)>】〕}]'
# 번호 하나 또는 여러 개: 1 / 1,2 / 1, 2번 / 1~3 / 4-6 / 1·2 / 1 및 2
_SEP = r'\s*(?:,|，|/|·|및|와|과|&|~|∼|〜|-|–)\s*'
# '번' 뒤에 한글이 바로 붙으면('4번째컷') 표시가 아니라 문장이다.
_NUM = r'(?:#|no\.?|:)?\s*(\d{1,2}(?:\s*번(?![가-힣]))?(?:' + _SEP + r'\d{1,2}(?:\s*번(?![가-힣]))?)*)(?![가-힣\d])'
_DESC = r'(?:\s*[:：\-–—.]\s*[^\]\)>】〕}\n]{0,40}|\s+[^\]\)>】〕}\n]{1,20})?'

# 1) 괄호형: [사진3] (사진 2: 외관) [이미지1: 대표이미지] <사진> 【사진】 [사진 첨부]
_BRACKET_RE = re.compile(
    # 번호가 있으면 뒤에 설명을 허용, 번호가 없으면 ':설명' 이나 '첨부/삽입…' 만 — '(사진 출처: 네이버)' 같은 글은 제외
    _OPEN + r'\s*' + _WORD + r'\s*(?:' + _NUM + _DESC
    + r'|(?:\s*[:：]\s*[^\]\)>】〕}\n]{0,40})?)\s*(?:첨부|삽입|자리|위치)?\s*' + _CLOSE,
    re.I)
# 2) 줄 전체가 표시: '사진 4' '이미지3 - 메뉴판' '📷 5' '📸' '### 📸 이미지2: 외관'
_LINE_RE = re.compile(
    r'^[ \t]*(?:#+\s*)?(?:[📷📸]\s*)?(?:(?:사진|이미지|그림)\s*' + _NUM + r'|[📷📸]\s*(\d{1,2})?)' + _DESC + r'[ \t]*$',
    re.M | re.I)
# 3) 파일명 지정 줄: '📁 파일명: 백내장_대표이미지.png'
_FILE_RE = re.compile(r'^[ \t]*(?:📁\s*)?(?:파일명|파일|file(?:name)?)\s*[:：]\s*(\S[^\n]*?)\s*$', re.M | re.I)


def normalize_photo_markers(text: str):
    """원고의 사진 표시를 표준 마커로 바꾼다.

    반환: (바뀐 원고, info)
      info = {"numbered": 번호 있는 표시 수, "plain": 번호 없는 표시 수,
              "human": 표준이 아닌(사람이 쓴) 표시 수, "max_no": 가장 큰 번호,
              "filenames": {번호: 파일명}}
    """
    info = {"numbered": 0, "plain": 0, "human": 0, "max_no": 0, "filenames": {}}
    if not text:
        return text, info

    def _nums(spec):
        """'1,2' '1~3' '4-6' '1번, 2번' → [1, 2] / [1, 2, 3] / [4, 5, 6] / [1, 2]"""
        out = []
        for a, rng, b in re.findall(r'(\d{1,2})(?:\s*번)?(?:\s*(~|∼|〜|-|–)\s*(\d{1,2}))?', spec):
            a = int(a)
            if rng and b and a <= int(b) <= a + 20:
                out += list(range(a, int(b) + 1))
            else:
                out.append(a)
                if b:
                    out.append(int(b))
        return out

    def _std(no):
        nums = _nums(no) if no else []
        if nums:
            info["numbered"] += len(nums)
            info["max_no"] = max([info["max_no"]] + nums)
            # 한 자리에 여러 장이면 연달아 넣는다(사진1,2 → 사진1 다음 바로 사진2)
            return "\n".join(f"[이미지:{n}]" for n in nums)
        info["plain"] += 1
        return "[이미지]"

    def _bracket(m):
        raw = m.group(0)
        if re.fullmatch(r'\[이미지\]', raw):          # AI 가 쓰는 표준 표시 — 사람 표시로 세지 않는다
            return _std(None)
        if not re.fullmatch(r'\[이미지\s*:\s*\d{1,2}\]', raw):
            info["human"] += 1
        return _std(m.group(1))

    def _line(m):
        info["human"] += 1
        return _std(m.group(1) or m.group(2))

    out = _BRACKET_RE.sub(_bracket, text)
    out = _LINE_RE.sub(_line, out)

    # 표시 바로 아래 파일명 줄 → {번호: 파일명} 으로 기억하고 본문에서는 지운다.
    lines, last_no = out.split("\n"), None
    kept = []
    for ln in lines:
        mk = re.search(r'\[이미지(?::(\d+))?\]', ln)
        if mk:
            last_no = int(mk.group(1)) if mk.group(1) else None
        fm = _FILE_RE.match(ln)
        if fm:
            if last_no:
                info["filenames"][last_no] = fm.group(1).strip()
            continue
        if ln.strip():
            if not mk:
                last_no = None
        kept.append(ln)
    out = re.sub(r'\n{3,}', '\n\n', "\n".join(kept))
    return out, info


def honors_markers(info: dict) -> bool:
    """표시대로 넣어야 하는 원고인가 — 번호가 있거나 사람이 쓴 사진 표시가 있으면 그렇다.
    (AI 가 그냥 찍은 [이미지] 만 있으면 '사진 배치' 설정을 따른다)"""
    return bool(info and (info.get("numbered") or info.get("human")))


def order_files_by_markers(files: list, info: dict) -> list:
    """폴더 사진(이름순)을 표시 번호에 맞춘다: '파일명' 지정이 있으면 그 파일을 그 번호 자리로."""
    files = list(files or [])
    names = {os.path.basename(f).lower(): f for f in files}
    stems = {os.path.splitext(os.path.basename(f))[0].lower(): f for f in files}
    for no, fname in sorted((info or {}).get("filenames", {}).items()):
        key = os.path.basename(fname).lower()
        path = names.get(key) or stems.get(os.path.splitext(key)[0])
        if not path or no < 1:
            continue
        cur = files.index(path)
        if no - 1 < len(files):
            files[cur], files[no - 1] = files[no - 1], files[cur]
    return files


def analyze_photo_plan(text: str, info: dict, n_photos: int) -> list:
    """글을 쓰기 전에 사진 표시를 점검해 경고 문구 목록을 돌려준다.
    - 사진 표시처럼 보이는데 인식 못 한 줄(예: '사진1번째컷')
    - 원고에 표시가 없는 폴더 사진 번호 / 표시는 있는데 폴더에 없는 번호"""
    warns = []
    for ln in (text or "").split("\n"):
        s = ln.strip()
        if "[이미지" in s:
            continue
        if re.search(r'(사진|이미지|📷|📸)\s*\d', s) and len(s) <= 40:
            warns.append(f"사진 표시로 보이지만 인식하지 못한 줄: '{s}'")
    used = set(int(n) for n in re.findall(r'\[이미지:(\d+)\]', text or ""))
    plain = len(re.findall(r'\[이미지\]', text or ""))
    missing = sorted(n for n in used if n > n_photos)
    if missing:
        warns.append(f"원고에는 사진 {missing}번 표시가 있지만 폴더 사진은 {n_photos}장뿐입니다")
    if n_photos and used:
        unused = [n for n in range(1, n_photos + 1) if n not in used][plain:]
        if unused:
            warns.append(f"폴더 사진 중 {unused}번은 원고에 표시가 없어 넣지 않습니다")
    return warns
