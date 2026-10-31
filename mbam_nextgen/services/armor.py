import os
import io
import json
import random
import hashlib
import threading
from datetime import datetime, timedelta
from PIL import Image, ImageEnhance, ImageFilter
import piexif

# 세탁 강도 — 발행 화면에서 고른다(기본 standard).
#   light    : 촬영정보(EXIF) 교체 + 재압축만. 화질 변화가 거의 없지만 pHash 는 원본과 같다.
#   standard : 미세 회전 + 가장자리 5~8% 크롭 + 미세 보정 (pHash 를 실제로 바꾸는 기본값)
#   strong   : standard + 밝기·대비·채도 ±3~4% + 크기 92~98% — 같은 사진을 여러 계정에 쓸 때
WASH_STRENGTHS = ("light", "standard", "strong")
WASH_LABELS = {"light": "약", "standard": "표준", "strong": "강"}


def normalize_strength(value) -> str:
    v = str(value or "").strip().lower()
    return v if v in WASH_STRENGTHS else "standard"


# 중복 업로드 방지 — 이 PC 에서 올린 세탁본의 지각해시(dHash)를 기억해 두고,
# 새 세탁본이 예전 것과 사실상 같은 그림이면 더 강하게 다시 세탁한다.
_REGISTRY_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "washed_hashes.json")
_REGISTRY_MAX = 3000           # 최근 이만큼만 기억(오래된 것부터 버림)
_NEAR_DUP_DISTANCE = 4         # 64비트 중 이 이하로 다르면 같은 그림으로 본다
_registry_lock = threading.Lock()


def _dhash(img: "Image.Image") -> int:
    """64비트 차이 해시 — 재압축·EXIF 교체로는 거의 안 변하고, 크롭·회전에는 변한다."""
    g = img.convert("L").resize((9, 8), Image.BILINEAR)
    px = list(g.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return bits


def _load_registry() -> list:
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_registry(entries: list):
    try:
        os.makedirs(os.path.dirname(_REGISTRY_PATH), exist_ok=True)
        tmp = _REGISTRY_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries[-_REGISTRY_MAX:], f)
        os.replace(tmp, _REGISTRY_PATH)
    except Exception as e:
        print(f"[Armor] 세탁 기록 저장 실패(무시): {e}")

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

    def __init__(self, output_dir: str = "mbam_nextgen/temp_images", strength: str = "standard"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.strength = normalize_strength(strength)   # 발행 요청마다 바꿔 쓴다(orchestrator.armor.strength)
        self.reset_stats()

    def reset_stats(self):
        """한 번의 발행에서 세탁한 결과 집계 — summary() 로 로그 한 줄을 만든다."""
        self.stats = {"count": 0, "rewashed": 0, "dup_left": 0}

    def summary(self) -> str:
        s = self.stats
        if not s["count"]:
            return ""
        msg = f"사진 {s['count']}장 세탁 완료({WASH_LABELS.get(self.strength, '표준')})"
        if s["rewashed"]:
            msg += f" — 이전에 올린 사진과 겹친 {s['rewashed']}장은 더 강하게 다시 세탁"
        if s["dup_left"]:
            msg += f" ⚠️ {s['dup_left']}장은 재세탁 후에도 이전 업로드와 비슷합니다"
        return msg

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

    def _apply(self, img: "Image.Image", strength: str) -> "Image.Image":
        """강도별 픽셀 처리. light 는 픽셀을 건드리지 않는다(EXIF·재압축은 저장 단계에서)."""
        if strength == "light":
            return img

        # 미세 회전 (무작위 방향 0.3~1.2도)
        angle = random.uniform(0.3, 1.2)
        if random.random() > 0.5: angle = -angle
        img = img.rotate(angle, expand=False, resample=Image.BICUBIC)

        # 가장자리 크롭 5~8% (회전 여백 제거 + pHash 변조)
        #   예전엔 3~6px 고정이라 1600px 이미지에서 0.3% 수준이었다.
        #   그 정도로는 pHash 거리가 0에 머물러 원본과 같은 이미지로 판정됐다.
        img = _crop_edges(img)

        # 밝기/대비 미세 조정 (standard 1% 내외 — 사람은 못 느낌, strong 3% 내외)
        amp = 0.03 if strength == "strong" else 0.01
        img = ImageEnhance.Brightness(img).enhance(1 + random.uniform(-amp, amp))
        img = ImageEnhance.Contrast(img).enhance(1 + random.uniform(-amp, amp))

        # 가우시안 노이즈 주입 (픽셀 값 미세 변조)
        if random.random() > 0.5:
            noise = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.1, 0.2)))
            img = Image.blend(img, noise, alpha=0.1)

        if strength == "strong":
            # 채도 ±4%, 크기 92~98% — 좌우 반전은 간판·메뉴 글자가 뒤집혀 쓰지 않는다
            img = ImageEnhance.Color(img).enhance(1 + random.uniform(-0.04, 0.04))
            scale = random.uniform(0.92, 0.98)
            w, h = img.size
            if min(w, h) * scale >= MIN_SIDE_AFTER_CROP:
                img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        return img

    def wash_image(self, input_path: str, output_filename: str, strength: str = None) -> str:
        level = normalize_strength(strength or self.strength)
        # 이전 업로드와 같은 그림으로 나오면 한 단계씩 강하게 다시 세탁(최대 3번)
        ladder = {"light": ["light", "standard", "strong"],
                  "standard": ["standard", "strong", "strong"],
                  "strong": ["strong", "strong", "strong"]}[level]
        try:
            with Image.open(input_path) as src:
                # 포맷 변환 (PNG/WebP -> JPEG)
                base = src.convert("RGB")

            with _registry_lock:
                known = []
                for e in _load_registry():
                    try:
                        known.append(int(e.get("h", ""), 16))
                    except Exception:
                        pass

            img, h, dup, used, attempt = None, 0, False, level, 0
            for attempt, lv in enumerate(ladder):
                img = self._apply(base.copy(), lv)
                h = _dhash(img)
                dup = any(bin(h ^ k).count("1") <= _NEAR_DUP_DISTANCE for k in known)
                used = lv
                if not dup:
                    break
            if attempt > 0:
                self.stats["rewashed"] += 1
            if dup:
                self.stats["dup_left"] += 1

            output_path = os.path.join(self.output_dir, output_filename)

            # 가짜 EXIF 주입 및 저장
            exif_bytes = self._get_fake_exif()
            q = random.randint(92, 97) if used == "light" else random.randint(94, 98)
            img.save(output_path, "JPEG", quality=q, exif=exif_bytes)

            with _registry_lock:
                entries = _load_registry()
                entries.append({"h": f"{h:016x}", "t": datetime.now().strftime("%Y-%m-%d %H:%M")})
                _save_registry(entries)

            self.stats["count"] += 1
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
