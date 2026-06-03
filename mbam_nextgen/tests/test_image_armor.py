import os
import sys
# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.armor import ImageArmor
from PIL import Image

def run_image_test():
    armor = ImageArmor()
    
    # 1. 테스트용 더미 이미지 생성 (이미지가 없을 경우 대비)
    test_img_path = "mbam_nextgen/tests/test_source.jpg"
    if not os.path.exists(test_img_path):
        dummy = Image.new('RGB', (800, 600), color=(random_color := (100, 150, 200)))
        dummy.save(test_img_path)
        print(f"[Test] 샘플 이미지 생성됨: {test_img_path}")

    # 2. 원본 해시 확인
    original_hash = armor.get_file_hash(test_img_path)
    print(f"\n[원본] 해시: {original_hash}")

    # 3. 세척 실행 (3번 반복하여 매번 다른지 확인)
    for i in range(1, 4):
        output_file = f"washed_test_{i}.jpg"
        washed_path = armor.wash_image(test_img_path, output_file)
        new_hash = armor.get_file_hash(washed_path)
        
        # EXIF 정보 확인
        with Image.open(washed_path) as img:
            info = img._getexif()
            # 271: Make, 272: Model
            make = info.get(271) if info else "Unknown"
            model = info.get(272) if info else "Unknown"
        
        print(f"[변조 {i}] 해시: {new_hash} (기기: {make} {model})")
        if original_hash == new_hash:
            print("⚠️ 경고: 해시값이 변하지 않았습니다!")
        else:
            print("✅ 성공: 해시값이 완전히 변경되었습니다.")

if __name__ == "__main__":
    run_image_test()
