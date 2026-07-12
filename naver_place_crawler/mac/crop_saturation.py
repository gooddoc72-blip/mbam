from PIL import Image, ImageDraw

def find_icon_bounds():
    img = Image.open('/Users/desklabs/.gemini/antigravity/brain/02d28800-c3f5-4839-a651-4952ad21e06a/crawler_app_icon_1782624041291.png').convert("RGB")
    width, height = img.size
    cx, cy = width // 2, height // 2
    pixels = img.load()
    
    # 1. 왼쪽으로 스캔 (무채색 배경이 나올 때까지)
    left = cx
    while left > 0:
        r, g, b = pixels[left, cy]
        if max(r,g,b) - min(r,g,b) < 15: # RGB 차이가 거의 없는 무채색(회색 캔버스) 감지
            break
        left -= 1
        
    # 2. 오른쪽으로 스캔
    right = cx
    while right < width - 1:
        r, g, b = pixels[right, cy]
        if max(r,g,b) - min(r,g,b) < 15:
            break
        right += 1
        
    # 3. 위로 스캔
    top = cy
    while top > 0:
        r, g, b = pixels[cx, top]
        if max(r,g,b) - min(r,g,b) < 15:
            break
        top -= 1
        
    # 4. 아래로 스캔
    bottom = cy
    while bottom < height - 1:
        r, g, b = pixels[cx, bottom]
        if max(r,g,b) - min(r,g,b) < 15:
            break
        bottom += 1

    # 정확한 아이콘 경계로 크롭
    # (그림자가 캔버스에 퍼져있을 수 있으므로 약간 안쪽으로 2픽셀 조여줌)
    box = (left+2, top+2, right-2, bottom-2)
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
    print(f"Perfectly cropped bounds: {box}")

if __name__ == '__main__':
    find_icon_bounds()
