# -*- coding: utf-8 -*-
"""
네이버 카페 마케팅 프로그램 전용 아이콘(cafe.ico) 생성기.

디자인 의도
  - 제품 정체성: 커피잔 = '네이버 카페', 색은 사이드바 브랜드 색 계열
  - 16px 에서도 읽혀야 하므로 형태를 크고 단순하게 (잔 몸통 · 손잡이 · 받침)
  - 김(steam)은 작은 크기에서 뭉개지므로 32px 이상에서만 그린다

실행:
    python make_cafe_icon.py --preview        # 시안 비교 PNG 생성(파일 안 건드림)
    python make_cafe_icon.py --variant A      # 고른 안으로 installer/cafe.ico 생성
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
#  A: 브랜드 녹색(사이드바 #16a34a 계열) 배경 + 흰 커피잔
#  B: 네이버 그린(#03C75A) 배경 + 흰 커피잔 — 네이버 서비스 느낌을 강조
#  C: 흰 배경 + 녹색 커피잔 + 녹색 테두리 — 밝은 작업표시줄에서 또렷
#  D: A 와 같은 색이되 김을 빼서 가장 단순 — 작은 크기에서 제일 또렷
VARIANTS = {
    "A": {"bg_top": (34, 176, 90),  "bg_bot": (18, 138, 70),  "fg": (255, 255, 255), "ring": None, "steam": True},
    "B": {"bg_top": (16, 214, 106), "bg_bot": (3, 175, 80),   "fg": (255, 255, 255), "ring": None, "steam": True},
    "C": {"bg_top": (255, 255, 255), "bg_bot": (238, 246, 240), "fg": (19, 145, 76), "ring": (19, 145, 76), "steam": True},
    "D": {"bg_top": (34, 176, 90),  "bg_bot": (18, 138, 70),  "fg": (255, 255, 255), "ring": None, "steam": False},
}


def _vertical_gradient(size, top, bottom):
    grad = Image.new("RGB", (1, size))
    px = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return grad.resize((size, size), Image.NEAREST)


def _steam_curve(d, cx, y0, y1, amp, width, fill):
    """올라가는 김 — 완만한 사인 곡선. 지그재그(«««)나 쉼표로 안 보이게 세로로 길게 뽑고
    양 끝을 원으로 막아 둥근 캡을 만든다(PIL line 은 캡이 각지다)."""
    pts = []
    steps = 48
    for i in range(steps + 1):
        t = i / steps
        y = y1 + (y0 - y1) * t
        x = cx + amp * math.sin(t * math.pi * 2.0)
        pts.append((x, y))
    d.line(pts, fill=fill, width=width, joint="curve")
    r = width / 2
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def draw_master(v: dict, detail: str) -> Image.Image:
    """detail: 'full'(김+받침) | 'plain'(받침만) | 'mini'(잔만, 크게)"""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    radius = int(S * 0.22)

    # ── 배경: 둥근 사각형 + 세로 그라데이션 ──
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)
    img.paste(_vertical_gradient(S, v["bg_top"], v["bg_bot"]).convert("RGBA"), (0, 0), mask)

    d = ImageDraw.Draw(img)
    fg = v["fg"] + (255,)

    # 밝은 배경 안은 테두리를 둘러 경계를 만든다
    if v["ring"]:
        d.rounded_rectangle([16, 16, S - 17, S - 17], radius=radius - 10,
                            outline=v["ring"] + (255,), width=32)

    # 작은 크기에서는 잔만 크게 그려 형태가 살아남게 한다
    if detail == "mini":
        cup_top, cup_bot = 330, 700
        cup_l, cup_r = 210, 640
        hcx, hcy, hr, hw = 690, 470, 128, 66
        rim_h = 46
    else:
        cup_top, cup_bot = 400, 690
        cup_l, cup_r = 245, 645
        hcx, hcy, hr, hw = 700, 520, 118, 56
        rim_h = 40

    # ── 손잡이(링) 먼저 → 잔 몸통이 왼쪽을 덮는다 ──
    d.ellipse([hcx - hr, hcy - hr, hcx + hr, hcy + hr], outline=fg, width=hw)

    # ── 잔 몸통: 아래로 살짝 좁아지고 바닥은 둥글게 ──
    inset = int((cup_r - cup_l) * 0.10)
    body_bot_l, body_bot_r = cup_l + inset, cup_r - inset
    d.polygon([(cup_l, cup_top), (cup_r, cup_top),
               (body_bot_r, cup_bot - 40), (body_bot_l, cup_bot - 40)], fill=fg)
    d.rounded_rectangle([body_bot_l, cup_bot - 110, body_bot_r, cup_bot], radius=70, fill=fg)
    # 잔 입구 — 타원으로 두께감
    d.ellipse([cup_l, cup_top - rim_h, cup_r, cup_top + rim_h], fill=fg)

    # ── 받침: 납작한 타원 (막대로 안 보이게) ──
    if detail in ("full", "plain"):
        d.ellipse([170, 742, 770, 838], fill=fg)

    # ── 김: 부드러운 사인 곡선 2줄 ──
    if detail == "full" and v.get("steam", True):
        _steam_curve(d, 372, 140, 336, 30, 42, fg)
        _steam_curve(d, 516, 170, 336, 30, 42, fg)

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
    out = HERE / "cafe.ico"
    frames[0].save(out, format="ICO", sizes=[(s, s) for s in SIZES], append_images=frames[1:])
    print(f"생성: {out}   (시안 {variant} / {', '.join(str(s) for s in SIZES)}px)")
    return out


def build_iconset(variant: str) -> Path:
    """macOS .icns 재료(.iconset 폴더) 생성. 뒤이어 iconutil 이 .icns 로 묶는다.

    맥은 Retina 때문에 1x/2x 쌍이 필요하고 파일 이름 규칙이 정해져 있다
    (icon_16x16.png / icon_16x16@2x.png ...). 하나라도 빠지면 iconutil 이 거부한다.
    Windows 용 cafe.ico 와 같은 그림을 써야 두 버전이 같은 제품으로 보인다.
    """
    out = HERE / "cafe.iconset"
    out.mkdir(exist_ok=True)
    # (표기 크기, 실제 픽셀, 파일명 접미사)
    for base in (16, 32, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            px = base * scale
            render(variant, px).save(out / f"icon_{base}x{base}{suffix}.png")
    print(f"생성: {out}   (시안 {variant} / 10개 PNG)")
    print("  다음: iconutil -c icns cafe.iconset -o cafe.icns")
    return out


def build_preview() -> Path:
    """시안 3개 × 실제 크기 비교 시트. 확대본도 같이 보여 형태를 확인한다."""
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

    p = HERE / "cafe_icon_preview.png"
    sheet.save(p)
    print(f"시안 미리보기: {p}")
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="시안 비교 PNG만 생성")
    ap.add_argument("--variant", choices=list(VARIANTS), help="이 시안으로 cafe.ico 생성")
    ap.add_argument("--iconset", choices=list(VARIANTS),
                    help="이 시안으로 macOS 용 cafe.iconset 생성 (.icns 재료)")
    a = ap.parse_args()
    if a.preview or not (a.variant or a.iconset):
        build_preview()
    if a.variant:
        build_ico(a.variant)
    if a.iconset:
        build_iconset(a.iconset)
