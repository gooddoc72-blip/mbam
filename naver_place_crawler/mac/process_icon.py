from PIL import Image, ImageDraw

def process_icon():
    img_path = '/Users/desklabs/.gemini/antigravity/brain/02d28800-c3f5-4839-a651-4952ad21e06a/crawler_app_icon_1782624041291.png'
    img = Image.open(img_path).convert("RGBA")
    
    data = img.getdata()
    width, height = img.size
    
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = data[y * width + x]
            # 하얀색 배경이 아닌 픽셀 찾기 (그림자 포함)
            if r < 245 or g < 245 or b < 245:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
                
    # 아이콘 영역 크롭
    padding = 2
    box = (max(0, min_x - padding), max(0, min_y - padding), min(width, max_x + padding), min(height, max_y + padding))
    cropped = img.crop(box)
    
    # Mac 스타일의 둥근 모서리(Squircle) 마스크 생성
    c_width, c_height = cropped.size
    mask = Image.new("L", (c_width, c_height), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(c_width * 0.225) # Mac 앱 아이콘의 일반적인 곡률 반경
    draw.rounded_rectangle((0, 0, c_width, c_height), radius, fill=255)
    
    # 마스크 적용하여 배경 투명하게 만들기
    cropped.putalpha(mask)
    
    out_path = '/Users/desklabs/Desktop/naver_place_crawler/icon_transparent.png'
    cropped.save(out_path)
    print(f"Successfully created transparent icon at {out_path}")

if __name__ == "__main__":
    process_icon()
