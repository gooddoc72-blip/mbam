import os
import glob
import random
from typing import List

class ClipGenerator:
    """
    [L2. The Clip] 15초 세로(9:16) 숏폼 클립 생성기 — V1
      구성: 인트로 카드(상호+훅 1.5s) → 리뷰 사진 최대 4장(각 3s, 켄번스 줌) → 아웃트로 카드(CTA 1.5s)
      자막: 훅/포인트/CTA 구조(clip_texts 5개), 자동 줄바꿈, 볼드 폰트
      BGM: mbam_nextgen/assets/bgm 폴더의 mp3/wav 중 랜덤 (없으면 무음)
    """

    W, H = 720, 1280           # 9:16
    FPS = 24
    PHOTO_SEC = 3.0
    CARD_SEC = 1.5
    MAX_PHOTOS = 4

    def __init__(self, output_dir: str = "mbam_nextgen/temp_clips"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.bgm_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "bgm")

    # ── 폰트 ──────────────────────────────────────────────────────────
    def _font(self, size: int, bold: bool = True):
        from PIL import ImageFont
        for name in (["malgunbd.ttf", "malgun.ttf"] if bold else ["malgun.ttf"]):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        try:
            return ImageFont.truetype("NanumGothicBold.ttf", size)
        except Exception:
            from PIL import ImageFont as _F
            return _F.load_default()

    def _wrap(self, draw, text: str, font, max_width: int) -> list:
        """픽셀 폭 기준 자동 줄바꿈 (최대 2줄, 넘치면 말줄임)."""
        words = (text or "").split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if draw.textlength(trial, font=font) <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) > 2:
            lines = lines[:2]
            lines[1] = lines[1][:12] + "…"
        return lines or [""]

    def _draw_caption(self, img, text: str):
        """하단 반투명 그라데이션 + 흰 볼드 자막(외곽선)."""
        from PIL import Image, ImageDraw
        overlay = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        # 아래로 갈수록 진해지는 그라데이션 띠 (하단 320px)
        for i in range(320):
            alpha = int(180 * (i / 320))
            d.line([(0, self.H - 320 + i), (self.W, self.H - 320 + i)], fill=(0, 0, 0, alpha))
        img = img.convert("RGBA")
        img.alpha_composite(overlay)
        d2 = ImageDraw.Draw(img)
        font = self._font(56)
        lines = self._wrap(d2, text, font, self.W - 100)
        y = self.H - 140 - (len(lines) - 1) * 70
        for line in lines:
            x = (self.W - d2.textlength(line, font=font)) / 2
            # 외곽선(가독성)
            for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
                d2.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 220))
            d2.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += 70
        return img.convert("RGB")

    def _fit_9x16(self, img, upscale: float = 1.0):
        """이미지를 9:16으로 중앙 크롭 후 (켄번스용 여유 배율 포함) 리사이즈."""
        from PIL import Image
        if img.mode != "RGB":
            img = img.convert("RGB")
        tw, th = int(self.W * upscale), int(self.H * upscale)
        ratio, target = img.width / img.height, tw / th
        if ratio > target:
            nw = int(img.height * target)
            left = (img.width - nw) // 2
            img = img.crop((left, 0, left + nw, img.height))
        else:
            nh = int(img.width / target)
            top = (img.height - nh) // 2
            img = img.crop((0, top, img.width, top + nh))
        return img.resize((tw, th), Image.Resampling.LANCZOS)

    def _card(self, main_text: str, sub_text: str = "", dark: bool = True):
        """인트로/아웃트로 카드 — 어두운 그라데이션 배경 + 큰 타이포."""
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (self.W, self.H), (15, 23, 42))
        d = ImageDraw.Draw(img)
        # 대각 그라데이션 느낌의 세로 그라데이션
        for y in range(self.H):
            t = y / self.H
            r = int(15 + (60 - 15) * t)
            g = int(23 + (18 - 23) * t)
            b = int(42 + (80 - 42) * t)
            d.line([(0, y), (self.W, y)], fill=(r, g, b))
        # 메인 텍스트(상호/CTA)
        font_main = self._font(72)
        lines = self._wrap(d, main_text, font_main, self.W - 120)
        y = self.H // 2 - len(lines) * 45 - (40 if sub_text else 0)
        for line in lines:
            x = (self.W - d.textlength(line, font=font_main)) / 2
            d.text((x, y), line, font=font_main, fill=(255, 255, 255))
            y += 92
        # 서브 텍스트(훅/부가문구)
        if sub_text:
            font_sub = self._font(46)
            for line in self._wrap(d, sub_text, font_sub, self.W - 140):
                x = (self.W - d.textlength(line, font=font_sub)) / 2
                y += 20
                d.text((x, y), line, font=font_sub, fill=(203, 213, 225))
                y += 58
        return img

    def _pick_bgm(self):
        try:
            files = []
            for ext in ("*.mp3", "*.wav", "*.m4a"):
                files += glob.glob(os.path.join(self.bgm_dir, ext))
            return random.choice(files) if files else None
        except Exception:
            return None

    # ── 메인 ──────────────────────────────────────────────────────────
    def generate_clip(self, image_paths: List[str], text_segments: List[str], output_name: str,
                      place_name: str = "") -> str:
        """사진+자막(+BGM)을 15초 세로 숏폼 MP4로 합성.
        text_segments 구조: [훅, 포인트1, 포인트2, 포인트3, CTA] (generate_place_news의 clip_texts)"""
        print(f"[Clip] V1 클립 생성: 사진 {len(image_paths)}장, 자막 {len(text_segments)}개")
        try:
            import numpy as np
            from PIL import Image
            from moviepy import ImageClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
        except ImportError as e:
            print(f"[Clip] moviepy/Pillow 미설치: {e}")
            return ""

        valid = [p for p in (image_paths or []) if p and os.path.exists(p)][:self.MAX_PHOTOS]
        if not valid:
            print("[Clip] 사용할 이미지가 없습니다.")
            return ""

        texts = [t for t in (text_segments or []) if t] or ["가게 소식"]
        hook = texts[0]
        cta = texts[-1] if len(texts) >= 2 else "지금 방문해보세요"
        points = texts[1:-1] if len(texts) >= 3 else texts

        output_path = os.path.join(self.output_dir, f"{output_name}.mp4")
        clips = []
        try:
            # 1) 인트로 카드: 상호 + 훅
            intro = self._card(place_name or hook, hook if place_name else "")
            clips.append(ImageClip(np.array(intro)).with_duration(self.CARD_SEC))

            # 2) 사진 구간: 켄번스(느린 줌 인) + 자막
            for i, p in enumerate(valid):
                with Image.open(p) as im:
                    base = self._fit_9x16(im, upscale=1.12)   # 12% 여유 → 줌 공간
                caption = points[i % len(points)]
                framed = self._draw_caption(self._center_crop(base), caption)
                big = self._draw_caption_on_big(base, caption)
                try:
                    # 느린 줌 인: 1.0 → 1.10 (지연 렌더링이라 메모리 안전)
                    photo = (ImageClip(np.array(big))
                             .with_duration(self.PHOTO_SEC)
                             .resized(lambda t: 1.0 + 0.10 * (t / self.PHOTO_SEC))
                             .with_position("center"))
                    clips.append(CompositeVideoClip([photo], size=(self.W, self.H)).with_duration(self.PHOTO_SEC))
                except Exception as ze:
                    print(f"[Clip] 줌 실패({ze}) — 정지 컷으로 대체")
                    clips.append(ImageClip(np.array(framed)).with_duration(self.PHOTO_SEC))

            # 3) 아웃트로 카드: CTA + 상호
            outro = self._card(cta, place_name)
            clips.append(ImageClip(np.array(outro)).with_duration(self.CARD_SEC))

            video = concatenate_videoclips(clips, method="compose")

            # 4) BGM (assets/bgm 에 파일이 있으면)
            bgm_path = self._pick_bgm()
            if bgm_path:
                try:
                    audio = AudioFileClip(bgm_path)
                    if audio.duration > video.duration:
                        audio = audio.subclipped(0, video.duration)
                    video = video.with_audio(audio)
                    print(f"[Clip] BGM 적용: {os.path.basename(bgm_path)}")
                except Exception as ae:
                    print(f"[Clip] BGM 적용 실패(무음 진행): {ae}")

            print(f"[Clip] 인코딩 중 → {output_path}")
            video.write_videofile(output_path, fps=self.FPS, codec="libx264",
                                  audio_codec="aac" if video.audio else None, logger=None)
            return output_path
        except Exception as e:
            print(f"[Clip] 영상 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return ""

    # 보조: 여유 배율 이미지의 중앙 720x1280 크롭 (정지 컷 폴백용)
    def _center_crop(self, big):
        left = (big.width - self.W) // 2
        top = (big.height - self.H) // 2
        return big.crop((left, top, left + self.W, top + self.H))

    # 보조: 큰(여유 배율) 이미지에 자막을 '하단 기준'으로 그려 줌 시에도 자막이 화면 안에 있게 함
    def _draw_caption_on_big(self, big, text: str):
        from PIL import Image
        # 줌은 중앙 기준 확대라, 자막을 중앙 크롭 기준 위치에 맞춰 그린 뒤 통짜로 확대되게 한다.
        # (자막도 함께 살짝 커지지만 15% 내라 시각적으로 자연스러움)
        cropped = self._center_crop(big)
        capped = self._draw_caption(cropped, text)
        out = big.copy()
        left = (big.width - self.W) // 2
        top = (big.height - self.H) // 2
        out.paste(capped, (left, top))
        return out
