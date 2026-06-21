import os
import random
from PIL import Image, ImageDraw, ImageFont

class CardNewsGenerator:
    """
    [Domain Service] AI 카드 뉴스 썸네일 자동 생성기
    사용자가 이미지를 제공하지 않았을 때 블로그/카페 포스팅용 임시 이미지를 생성합니다.
    """
    
    def __init__(self, font_path: str = "C:/Windows/Fonts/malgun.ttf"):
        self.font_path = font_path
        self.output_dir = "mbam_nextgen/generated_images"
        os.makedirs(self.output_dir, exist_ok=True)
            
        # 다양한 트렌디한 그라데이션 및 단색 배경 팔레트
        self.bg_colors = [
            "#FF7E5F", "#FEB47B", # Warm
            "#6A11CB", "#2575FC", # Cool
            "#11998E", "#38EF7D", # Green
            "#1E293B", "#334155"  # Dark Slate
        ]

    def _text_w(self, draw, text, font):
        try:
            b = draw.textbbox((0, 0), text, font=font)
            return b[2] - b[0], b[3] - b[1]
        except AttributeError:
            return draw.textsize(text, font=font)

    def _wrap(self, draw, text, font, max_width):
        """글자 단위로 max_width 안에 들어가도록 줄바꿈(한글 대응)."""
        lines, cur = [], ""
        for ch in text:
            test = cur + ch
            w, _ = self._text_w(draw, test, font)
            if w <= max_width or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines

    def generate_image(self, keyword: str, subtitle: str = "오늘의 핵심 포인트 알아보기") -> str:
        """
        제목을 중앙에 배치한 고화질(1080x1080) 카드 뉴스 이미지를 생성하고 경로 반환.
        제목이 길면 자동 줄바꿈한다.
        """
        width, height = 1080, 1080

        bg_color = random.choice(self.bg_colors)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        try:
            title_font = ImageFont.truetype(self.font_path, 90)
            subtitle_font = ImageFont.truetype(self.font_path, 40)
        except Exception:
            print("[CardNews] ⚠️ 지정된 폰트를 찾을 수 없어 기본 폰트를 사용합니다.")
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()

        # 제목 (대괄호 래핑) — 길면 자동 줄바꿈
        text = f"[{keyword}]"
        max_text_w = width - 160
        lines = self._wrap(draw, text, title_font, max_text_w)
        _, line_h = self._text_w(draw, "가", title_font)
        line_gap = 24
        block_h = len(lines) * line_h + (len(lines) - 1) * line_gap
        y = (height - block_h) / 2 - 40

        for line in lines:
            lw, _ = self._text_w(draw, line, title_font)
            x = (width - lw) / 2
            draw.text((x + 5, y + 5), line, font=title_font, fill="#222222")  # 그림자
            draw.text((x, y), line, font=title_font, fill="white")
            y += line_h + line_gap

        # 서브타이틀 (길면 줄바꿈)
        sub_y = y + 40
        for sline in self._wrap(draw, subtitle, subtitle_font, max_text_w):
            sw, sh = self._text_w(draw, sline, subtitle_font)
            sx = (width - sw) / 2
            draw.text((sx, sub_y), sline, font=subtitle_font, fill="#F1F5F9")
            sub_y += sh + 12

        draw.rectangle([50, 50, width - 50, height - 50], outline="white", width=5)

        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).replace(" ", "_")[:20] or "card"
        filename = f"cardnews_{safe_keyword}_{random.randint(1000,9999)}.jpg"
        filepath = os.path.abspath(os.path.join(self.output_dir, filename))

        img.save(filepath, quality=95)
        print(f"[CardNews] Auto thumbnail created: {filepath}")
        return filepath

    def _extract_headings(self, content: str) -> list:
        """원고의 H태그(소제목) 추출. '[소제목] 텍스트' 형식 우선."""
        import re
        if not content:
            return []
        heads = re.findall(r'^\s*\[소제목\]\s*(.+?)\s*$', content, flags=re.MULTILINE)
        return [h.strip() for h in heads if h.strip()]

    def _extract_points(self, content: str, n: int):
        """폴백: 본문에서 카드 부제로 쓸 짧은 핵심 문구 n개 추출."""
        import re
        if not content:
            return []
        parts = re.split(r'[\n.!?]+', content)
        seen, points = set(), []
        for p in parts:
            s = p.strip().strip('-•*~#[]() ').strip()
            if 4 <= len(s) <= 24 and s not in seen:
                seen.add(s)
                points.append(s)
            if len(points) >= n:
                break
        return points

    def generate_card_set(self, title: str, content: str = "", count: int = 5, max_cards: int = 9) -> list:
        """
        제목/본문으로 카드 뉴스 세트를 생성하고 경로 리스트 반환.
        ★ 원고의 H태그(소제목)에 맞춰: 1장은 표지, 그 다음은 [소제목]별로 1장씩.
        소제목이 없으면 기존 방식(핵심 문구/일반 문구)으로 count장 생성.
        """
        heads = self._extract_headings(content)
        paths = []
        # 표지
        paths.append(self.generate_image(title, subtitle="핵심 포인트 정리"))
        if heads:
            # H태그(소제목)별 카드
            for h in heads[:max_cards - 1]:
                paths.append(self.generate_image(title, subtitle=h))
            print(f"[CardNews] 카드 세트 {len(paths)}장 생성 (H태그 {len(heads)}개 기준)")
        else:
            count = max(1, count)
            points = self._extract_points(content, count - 1)
            generic = ["핵심 포인트 정리", "꼭 알아두세요", "한눈에 보기", "이것만 기억하세요", "마무리 체크"]
            for i in range(count - 1):
                sub = points[i] if i < len(points) else generic[i % len(generic)]
                paths.append(self.generate_image(title, subtitle=sub))
            print(f"[CardNews] 카드 세트 {len(paths)}장 생성 (소제목 없음 → 폴백)")
        return paths

if __name__ == "__main__":
    generator = CardNewsGenerator()
    path = generator.generate_image("AI 자동화 트렌드", "2024년 반드시 알아야 할 핵심 정보")
    print("Test Output:", path)
