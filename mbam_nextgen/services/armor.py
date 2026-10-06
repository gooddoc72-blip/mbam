import os
import random
import io
import hashlib
from datetime import datetime, timedelta
from PIL import Image, ImageEnhance, ImageFilter
import piexif

# 세탁 강도 — 지각해시(pHash)를 실제로 흔드는 값.
#   가장자리 크롭이 pHash 를 가장 크게 바꾼다(측정: 3%→6, 5%→12, 8%→20 / 64).
#   미세회전·노이즈·밝기보정만으로는 pHash 거리가 0에 가까워 원본과 '같은 이미지'로 판정된다.
CROP_RATIO_MIN = 0.05   # 짧은 변 기준 5%
CROP_RATIO_MAX = 0.08   # 짧은 변 기준 8%
MIN_SIDE_AFTER_CROP = 64  # 이보다 작아지면 크롭을 건너뛴다(아이콘·썸네일 보호)


def _random_shot_time() -> str:
    """최근 촬영으로 보이는 무작위 시각(EXIF 형식).

    예전에는 '2024:05:10 14:20:05' 상수를 모든 이미지에 박아 넣었다.
    ① 이 프로그램으로 만든 모든 이미지가 이 값 하나로 한 묶음이 되고,
    ② 최신성으로 노출을 다투는 글에 2년 전 촬영일이 붙는 문제가 있었다.
    """
    shot = datetime.now() - timedelta(
        days=random.randint(0, 20),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    # 새벽 촬영은 부자연스러워 08~21시로 당긴다
    if shot.hour < 8 or shot.hour > 21:
        shot = shot.replace(hour=random.randint(8, 21))
    return shot.strftime("%Y:%m:%d %H:%M:%S")


def _crop_edges(img: "Image.Image") -> "Image.Image":
    """가장자리를 5~8% 잘라낸다 — 세탁에서 pHash 를 바꾸는 핵심 처리.

    회전으로 생긴 검은 여백도 이 크롭으로 함께 사라진다.
    네 변의 비율을 조금씩 다르게 줘서 결과마다 구도가 미세하게 달라지게 한다.
    """
    w, h = img.size
    base = min(w, h)
    l, t, r, b = (int(base * random.uniform(CROP_RATIO_MIN, CROP_RATIO_MAX)) for _ in range(4))
    if w - l - r < MIN_SIDE_AFTER_CROP or h - t - b < MIN_SIDE_AFTER_CROP:
        return img  # 너무 작은 이미지는 그대로 둔다
    return img.crop((l, t, w - r, h - b))


class ImageArmor:
    """
    [L3. The Armor] - Pro Version
    이미지 픽셀 변조 및 가짜 EXIF 데이터 주입을 통해 이미지 지문을 완전히 새로 생성합니다.
    """

    def __init__(self, output_dir: str = "mbam_nextgen/temp_images"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

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

        # 촬영 시간 — 매번 새로 뽑는다(고정값 금지). 세 태그는 실제 기기처럼 같은 값으로 맞춘다.
        shot = _random_shot_time()
        exif_dict["0th"][piexif.ImageIFD.DateTime] = shot
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = shot
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = shot

        return piexif.dump(exif_dict)

    def wash_image(self, input_path: str, output_filename: str) -> str:
        try:
            with Image.open(input_path) as img:
                # 1. 포맷 변환 (PNG/WebP -> JPEG) 및 회전 보정
                img = img.convert("RGB")
                
                # 2. 미세 회전 (무작위 방향 0.3~1.2도)
                angle = random.uniform(0.3, 1.2)
                if random.random() > 0.5: angle = -angle
                img = img.rotate(angle, expand=False, resample=Image.BICUBIC)

                # 3. 가장자리 크롭 5~8% (회전 여백 제거 + pHash 변조)
                #    예전엔 3~6px 고정이라 1600px 이미지에서 0.3% 수준이었다.
                #    그 정도로는 pHash 거리가 0에 머물러 원본과 같은 이미지로 판정됐다.
                img = _crop_edges(img)

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
