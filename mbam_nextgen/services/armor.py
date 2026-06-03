import os
import random
import io
import hashlib
from PIL import Image, ImageEnhance, ImageFilter
import piexif

class ImageArmor:
    """
    [L3. The Armor] - Pro Version
    이미지 픽셀 변조 및 가짜 EXIF 데이터 주입을 통해 이미지 지문을 완전히 새로 생성합니다.
    """
    
    def __init__(self, output_dir: str = "mbam_nextgen/temp_images"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def _get_fake_exif(self):
        """최신 스마트폰 기기 정보를 담은 가짜 EXIF 데이터를 생성합니다."""
        devices = [
            {"make": "Apple", "model": "iPhone 15 Pro"},
            {"make": "Samsung", "model": "SM-S928N"}, # Galaxy S24 Ultra
            {"make": "Apple", "model": "iPhone 14"},
        ]
        dev = random.choice(devices)
        
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        exif_dict["0th"][piexif.ImageIFD.Make] = dev["make"]
        exif_dict["0th"][piexif.ImageIFD.Model] = dev["model"]
        exif_dict["0th"][piexif.ImageIFD.Software] = "iOS 17.4" if "iPhone" in dev["model"] else "Android 14"
        
        # 촬영 시간 (현재 시간 기준 무작위)
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = "2024:05:10 14:20:05"
        
        return piexif.dump(exif_dict)

    def wash_image(self, input_path: str, output_filename: str) -> str:
        try:
            with Image.open(input_path) as img:
                # 1. 포맷 변환 (PNG/WebP -> JPEG) 및 회전 보정
                img = img.convert("RGB")
                
                # 2. 미세 회전 (무작위 방향 0.1~0.5도)
                angle = random.uniform(0.1, 0.5)
                if random.random() > 0.5: angle = -angle
                img = img.rotate(angle, expand=False, resample=Image.BICUBIC)
                
                # 3. 미세 크롭 (회전 후 여백 제거 및 해시 변조)
                w, h = img.size
                cp = random.randint(3, 6)
                img = img.crop((cp, cp, w - cp, h - cp))
                
                # 4. 밝기/대비 미세 조정 (인간은 못 느끼는 1% 내외)
                img = ImageEnhance.Brightness(img).enhance(1 + random.uniform(-0.01, 0.01))
                img = ImageEnhance.Contrast(img).enhance(1 + random.uniform(-0.01, 0.01))
                
                # 5. 가우시안 노이즈 주입 (픽셀 값 미세 변조)
                if random.random() > 0.5:
                    noise = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.1, 0.2)))
                    img = Image.blend(img, noise, alpha=0.1)

                output_path = os.path.join(self.output_dir, output_filename)
                
                # 6. 가짜 EXIF 주입 및 저장
                exif_bytes = self._get_fake_exif()
                img.save(output_path, "JPEG", quality=random.randint(94, 98), exif=exif_bytes)
                
                return output_path
        except Exception as e:
            print(f"[Armor] 에러: {e}")
            raise RuntimeError(f"이미지 보안 세척 실패: {e}")

    def get_file_hash(self, path: str) -> str:
        """파일의 MD5 해시값을 계산합니다."""
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()
