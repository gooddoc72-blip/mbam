from PIL import Image, ImageDraw

def find_symmetric_bounds():
    img = Image.open('/Users/desklabs/.gemini/antigravity/brain/02d28800-c3f5-4839-a651-4952ad21e06a/crawler_app_icon_1782624041291.png').convert("RGB")
    width, height = img.size
    cx, cy = width // 2, height // 2
    pixels = img.load()
    
    # 1. 왼쪽으로 스캔 (완벽하게 작동했음)
    left = cx
    while left > 0:
        r, g, b = pixels[left, cy]
        if max(r,g,b) - min(r,g,b) < 15:
            break
        left -= 1
        
    # 2. 오른쪽으로 스캔 (완벽하게 작동했음)
    right = cx
    while right < width - 1:
        r, g, b = pixels[right, cy]
        if max(r,g,b) - min(r,g,b) < 15:
            break
        right += 1

    # 좌우 너비를 구함
    icon_size = right - left
    
    # 좌우 너비와 똑같은 길이의 "완벽한 정사각형"을 정중앙(cx, cy) 기준으로 생성
    # 아래쪽 그림자에 속지 않도록 강제로 정사각형으로 오려냄
    box = (left + 2, cy - (icon_size // 2) + 2, right - 2, cy + (icon_size // 2) - 2)
    
    img = img.convert("RGBA")
    cropped = img.crop(box)
    
    # Mac 전용 둥근 모서리 마스크 적용
    c_width, c_height = cropped.size
    mask = Image.new("L", (c_width, c_height), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(c_width * 0.225)
    draw.rounded_rectangle((0, 0, c_width, c_height), radius, fill=255)
    
    cropped.putalpha(mask)
    
    out_path = '/Users/desklabs/Desktop/naver_place_crawler/icon_nobg.png'
    cropped.save(out_path)
    print(f"Symmetric perfectly cropped bounds: {box}")

if __name__ == '__main__':
    find_symmetric_bounds()
