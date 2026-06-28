from PIL import Image, ImageDraw

def crop_blue_squircle():
    # 원본 이미지 로드
    img = Image.open('/Users/desklabs/.gemini/antigravity/brain/02d28800-c3f5-4839-a651-4952ad21e06a/crawler_app_icon_1782624041291.png').convert("RGBA")
    data = img.getdata()
    width, height = img.size
    
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    
    # 파란색 픽셀 영역(실제 아이콘 테두리) 찾기
    for y in range(height):
        for x in range(width):
            r, g, b, a = data[y * width + x]
            # 배경이 아닌, 파란색이 지배적인 픽셀만 탐지 (Blue가 Red보다 30 이상 크고, Green보다 큰 경우)
            if b > r + 30 and b > g + 10:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y

    # 탐지된 파란색 아이콘 부분만 정확히 자르기
    box = (min_x, min_y, max_x, max_y)
    cropped = img.crop(box)
    
    # 자른 아이콘에 완벽한 둥근 모서리(Squircle) 마스크 씌우기
    c_width, c_height = cropped.size
    mask = Image.new("L", (c_width, c_height), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(c_width * 0.225) # Mac 앱 아이콘 곡률
    draw.rounded_rectangle((0, 0, c_width, c_height), radius, fill=255)
    
    # 마스크 적용하여 배경을 완전 투명하게 처리
    cropped.putalpha(mask)
    
    out_path = '/Users/desklabs/Desktop/naver_place_crawler/icon_nobg.png'
    cropped.save(out_path)
    print(f"Perfectly cropped icon saved to {out_path}")

if __name__ == '__main__':
    crop_blue_squircle()
