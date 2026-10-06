# -*- coding: utf-8 -*-
"""
블로그 마케팅 프로그램 전용 아이콘(blog.ico) 생성기.

디자인 의도
  - 제품 정체성: 종이(글) + 펜 = '블로그 글쓰기', 색은 사이드바 브랜드 색(파랑) 계열
  - 카페판(녹색 커피잔)과 작업표시줄에서 한눈에 구분돼야 한다 → 색과 형태를 모두 다르게
  - 16px 에서도 읽혀야 하므로 형태를 크고 단순하게

실행:
    python make_blog_icon.py --preview        # 시안 비교 PNG 생성(파일 안 건드림)
    python make_blog_icon.py --variant A      # 고른 안으로 installer/blog.ico 생성
"""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

# .ico 에 넣을 크기들 (윈도우가 상황에 맞게 골라 쓴다)
SIZES = [256, 128, 64, 48, 32, 24, 16]
S = 1024          # 마스터 캔버스 크기

# ── 시안별 색 ─────────────────────────────────────────────
#  A: 브랜드 파랑(사이드바 #2563eb 계열) 배경 + 흰 종이·펜
#  B: 진한 남색 배경 — 어두운 작업표시줄에서 카페판(녹색)과 대비가 크다
#  C: 흰 배경 + 파란 종이·펜 + 파란 테두리 — 밝은 작업표시줄에서 또렷
#  D: A 와 같은 색이되 글줄을 빼서 가장 단순 — 작은 크기에서 제일 또렷
VARIANTS = {
    "A": {"bg_top": (59, 130, 246), "bg_bot": (29, 78, 216),  "fg": (255, 255, 255), "ring": None, "lines": True},
    "B": {"bg_top": (37, 99, 235),  "bg_bot": (23, 37, 84),   "fg": (255, 255, 255), "ring": None, "lines": True},
    "C": {"bg_top": (255, 255, 255), "bg_bot": (238, 243, 254), "fg": (37, 99, 235), "ring": (37, 99, 235), "lines": True},
    "D": {"bg_top": (59, 130, 246), "bg_bot": (29, 78, 216),  "fg": (255, 255, 255), "ring": None, "lines": False},
}


def _vertical_gradient(size, top, bottom):
    grad = Image.new("RGB", (1, size))
    px = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return grad.resize((size, size), Image.NEAREST)


def _pen(d, fg, cap_fill, x0, y0, length, width):
    """오른쪽 위에서 왼쪽 아래로 내려오는 펜 (몸통 + 삼각 촉).

    ⚠ 방향은 반드시 '왼쪽 아래'다. 오른쪽 아래로 그리면 1024 캔버스를 넘어가
      작은 크기에서 모서리 쐐기 모양으로 잘려 나온다(처음에 그렇게 만들어 봤다).
    45도로 고정하는 이유는 작은 크기에서 계단현상이 가장 적어서다.
    """
    dx, dy = -math.cos(math.radians(45)), math.sin(math.radians(45))
    nx, ny = -dy, dx                       # 몸통 두께 방향(수직)
    hw = width / 2
    x1, y1 = x0 + dx * length, y0 + dy * length      # 촉 쪽 끝
    d.polygon([
        (x0 + nx * hw, y0 + ny * hw), (x0 - nx * hw, y0 - ny * hw),
        (x1 - nx * hw, y1 - ny * hw), (x1 + nx * hw, y1 + ny * hw),
    ], fill=fg)
    # 촉 — 몸통 끝에서 뾰족하게
    tip = width * 1.15
    d.polygon([
        (x1 + nx * hw, y1 + ny * hw), (x1 - nx * hw, y1 - ny * hw),
        (x1 + dx * tip, y1 + dy * tip),
    ], fill=fg)
    # 손잡이 끝 마감 — 얇게 잘라 '펜 뚜껑' 느낌
    d.polygon([
        (x0 + nx * hw, y0 + ny * hw), (x0 - nx * hw, y0 - ny * hw),
        (x0 - nx * hw + dx * width * 0.5, y0 - ny * hw + dy * width * 0.5),
        (x0 + nx * hw + dx * width * 0.5, y0 + ny * hw + dy * width * 0.5),
    ], fill=cap_fill)


def _pen_with_halo(d, fg, halo, x0, y0, length, width):
    """펜과 종이가 같은 흰색이라 맞닿으면 한 덩어리로 보인다.
    배경색으로 한 겹 두껍게 먼저 깔아 경계를 만든다."""
    _pen(d, halo, halo, x0, y0, length, width + 56)
    _pen(d, fg, halo, x0, y0, length, width)


def draw_master(v: dict, detail: str) -> Image.Image:
    """detail: 'full'(종이+글줄+펜) | 'plain'(종이+펜) | 'mini'(펜만, 크게)"""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    radius = int(S * 0.22)

    # ── 배경: 둥근 사각형 + 세로 그라데이션 ──
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)
    img.paste(_vertical_gradient(S, v["bg_top"], v["bg_bot"]).convert("RGBA"), (0, 0), mask)

    d = ImageDraw.Draw(img)
    fg = v["fg"] + (255,)
    bg_mid = tuple(round((v["bg_top"][i] + v["bg_bot"][i]) / 2) for i in range(3)) + (255,)

    # 밝은 배경 안은 테두리를 둘러 경계를 만든다
    if v["ring"]:
        d.rounded_rectangle([16, 16, S - 17, S - 17], radius=radius - 10,
                            outline=v["ring"] + (255,), width=32)

    # 작은 크기에서는 펜만 크게 그려 형태가 살아남게 한다
    if detail == "mini":
        _pen(d, fg, bg_mid, 830, 175, 515, 205)
        return img

    # ── 종이 ──
    page = [190, 170, 650, 750]
    d.rounded_rectangle(page, radius=52, fill=fg)

    # ── 글줄 (배경색으로 파넣어 '글이 적힌 종이'로 읽히게) ──
    if detail == "full" and v.get("lines", True):
        x0, x1 = page[0] + 80, page[2] - 80
        y = page[1] + 118
        for ratio in (1.0, 1.0, 0.58):
            d.rounded_rectangle([x0, y, x0 + (x1 - x0) * ratio, y + 48],
                                radius=24, fill=bg_mid)
            y += 122

    # ── 펜: 오른쪽 위에서 내려와 종이 오른쪽 아래를 짚는다 ──
    _pen_with_halo(d, fg, bg_mid, 890, 395, 285, 150)
    return img


def render(variant: str, size: int) -> Image.Image:
    """크기별로 디테일을 줄인다 — 작은 아이콘에서 뭉개지지 않게."""
    if size >= 48:
        detail = "full"
    elif size >= 32:
        detail = "plain"
    else:
        detail = "mini"
    v = VARIANTS[variant]
    return draw_master(v, detail).resize((size, size), Image.LANCZOS)


def build_ico(variant: str) -> Path:
    frames = [render(variant, s) for s in SIZES]
    out = HERE / "blog.ico"
    frames[0].save(out, format="ICO", sizes=[(s, s) for s in SIZES], append_images=frames[1:])
    print(f"생성: {out}   (시안 {variant} / {', '.join(str(s) for s in SIZES)}px)")
    return out


def build_preview() -> Path:
    """시안 × 실제 크기 비교 시트. 확대본도 같이 보여 형태를 확인한다."""
    show = [256, 64, 48, 32, 24, 16]
    pad, gap, row_gap, label_w = 28, 26, 28, 130
    row_h = max(show)
    w = label_w + pad * 2 + sum(show) + gap * (len(show) - 1)
    h = pad * 2 + (row_h + row_gap) * len(VARIANTS)
    sheet = Image.new("RGB", (w, h), (245, 247, 250))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 20)
        small = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 14)
    except Exception:
        font = small = ImageFont.load_default()

    y = pad
    for name in VARIANTS:
        d.text((pad, y + row_h // 2 - 10), f"시안 {name}", fill=(30, 41, 59), font=font)
        x = label_w + pad
        for s in show:
            f = render(name, s)
            sheet.paste(f, (x, y + (row_h - s) // 2), f)
            d.text((x, y + row_h + 6), f"{s}px", fill=(100, 116, 139), font=small)
            x += s + gap
        y += row_h + row_gap

    p = HERE / "blog_icon_preview.png"
    sheet.save(p)
    print(f"시안 미리보기: {p}")
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="시안 비교 PNG만 생성")
    ap.add_argument("--variant", choices=list(VARIANTS), help="이 시안으로 blog.ico 생성")
    a = ap.parse_args()
    if a.preview or not a.variant:
        build_preview()
    if a.variant:
        build_ico(a.variant)
