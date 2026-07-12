from PIL import Image

def remove_white_bg():
    # 원본 이미지 불러오기
    img = Image.open('/Users/desklabs/.gemini/antigravity/brain/02d28800-c3f5-4839-a651-4952ad21e06a/crawler_app_icon_1782624041291.png').convert("RGBA")
    data = img.getdata()
    
    new_data = []
    for item in data:
        # R,G,B가 240 이상인 밝은 하얀색 계열은 모두 투명(Alpha=0)으로 변경
        if item[0] > 240 and item[1] > 240 and item[2] > 240:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
            
    img.putdata(new_data)
    
    # 투명하지 않은 실제 그림 부분만 꽉 차게 잘라내기(Crop)
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        
    # 결과 저장
    img.save('/Users/desklabs/Desktop/naver_place_crawler/icon_nobg.png')

if __name__ == '__main__':
    remove_white_bg()
