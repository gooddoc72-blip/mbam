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
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # 다양한 트렌디한 그라데이션 및 단색 배경 팔레트
        self.bg_colors = [
            "#FF7E5F", "#FEB47B", # Warm
            "#6A11CB", "#2575FC", # Cool
            "#11998E", "#38EF7D", # Green
            "#1E293B", "#334155"  # Dark Slate
        ]

    def generate_image(self, keyword: str, subtitle: str = "오늘의 핵심 포인트 알아보기") -> str:
        """
        키워드를 중앙에 배치한 고화질(1080x1080) 카드 뉴스 이미지를 생성하고 경로 반환
        """
        width, height = 1080, 1080
        
        # 랜덤 배경색 선택
        bg_color = random.choice(self.bg_colors)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # 폰트 설정 (Windows 맑은 고딕 기본)
        try:
            title_font = ImageFont.truetype(self.font_path, 90)
            subtitle_font = ImageFont.truetype(self.font_path, 40)
        except:
            print("[CardNews] ⚠️ 지정된 폰트를 찾을 수 없어 기본 폰트를 사용합니다.")
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            
        # 제목 중앙 정렬 계산
        text = f"[{keyword}]"
        
        # getbox is modern PIL way to get size
        try:
            bbox = draw.textbbox((0, 0), text, font=title_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            text_width, text_height = draw.textsize(text, font=title_font)
            
        x = (width - text_width) / 2
        y = (height - text_height) / 2 - 50
        
        # 그림자 효과
        draw.text((x+5, y+5), text, font=title_font, fill="#222222")
        # 메인 텍스트
        draw.text((x, y), text, font=title_font, fill="white")
        
        # 서브타이틀
        try:
            sub_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            sub_width = sub_bbox[2] - sub_bbox[0]
        except AttributeError:
            sub_width, _ = draw.textsize(subtitle, font=subtitle_font)
            
        sub_x = (width - sub_width) / 2
        sub_y = y + text_height + 60
        
        draw.text((sub_x, sub_y), subtitle, font=subtitle_font, fill="#F1F5F9")
        
        # 테두리 데코레이션
        draw.rectangle([50, 50, width-50, height-50], outline="white", width=5)
        
        # 저장
        safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '_')).replace(" ", "_")
        filename = f"cardnews_{safe_keyword}_{random.randint(1000,9999)}.jpg"
        filepath = os.path.abspath(os.path.join(self.output_dir, filename))
        
        img.save(filepath, quality=95)
        print(f"[CardNews] Auto thumbnail created: {filepath}")
        
        return filepath

if __name__ == "__main__":
    generator = CardNewsGenerator()
    path = generator.generate_image("AI 자동화 트렌드", "2024년 반드시 알아야 할 핵심 정보")
    print("Test Output:", path)
