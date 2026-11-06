import os
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

class NaverApiKeys(BaseModel):
    customer_id: str
    access_license: str
    secret_key: str

class NaverDevApiKeys(BaseModel):
    client_id: str
    client_secret: str

class AIApiKeys(BaseModel):
    claude_key: str
    gemini_key: str
    openai_key: str

class TelegramApiKeys(BaseModel):
    bot_token: str
    chat_id: str

PROMPTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts.json")

def read_prompts():
    import json
    # DB 우선 — 클라우드 재배포 시 prompts.json(컨테이너 파일)은 초기화되므로
    raw = db_get_settings(["BLOG_PROMPTS_JSON"]).get("BLOG_PROMPTS_JSON")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    if not os.path.exists(PROMPTS_PATH):
        return {}
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def write_prompts(data):
    import json
    db_set_settings({"BLOG_PROMPTS_JSON": json.dumps(data, ensure_ascii=False)})
    with open(PROMPTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 카페 댓글 프롬프트 저장 키.
# ⚠ 조회·저장 엔드포인트는 여기 두면 안 된다 — /api/settings 는 전체가 관리자 전용이라
#   설치형 고객(로그인 없는 local 사용자)이 접근하면 403 이 난다.
#   그래서 엔드포인트는 cafe_nurture 라우터에 두고, 저장소 키만 여기서 공유한다.
CAFE_COMMENT_PROMPT_KEY = "cafe_comment_prompt"


def read_env():
    if not os.path.exists(ENV_PATH):
        return {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    env_vars = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()
    return env_vars

def write_env(env_vars):
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = []
    
    updated = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in env_vars:
                new_lines.append(f"{key}={env_vars[key]}\n")
                updated.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    for k, v in env_vars.items():
        if k not in updated:
            new_lines.append(f"{k}={v}\n")
            
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def env_or_os(env: dict, key: str) -> str:
    """.env 파일 → os.environ 순으로 조회.
    클라우드(Railway)는 재배포 시 컨테이너 .env 가 초기화되므로, 대시보드 환경변수로
    등록한 키도 관리자 화면에 보이도록 폴백한다."""
    return env.get(key) or os.environ.get(key, "")


# ── DB 영속 설정(KV) ────────────────────────────────────────────────
# 설정 화면에서 저장한 API 키는 .env(컨테이너 파일)가 아니라 DB에 저장해야
# 재배포 후에도 유지된다. 조회 우선순위: DB > .env > os.environ
def db_get_settings(keys: list) -> dict:
    from ..database import SessionLocal, AppSetting
    try:
        db = SessionLocal()
        try:
            rows = db.query(AppSetting).filter(AppSetting.key.in_(keys)).all()
            return {r.key: r.value for r in rows if r.value}
        finally:
            db.close()
    except Exception as e:
        print(f"[settings] DB 조회 실패: {e}")
        return {}


def db_set_settings(kv: dict):
    from ..database import SessionLocal, AppSetting
    try:
        db = SessionLocal()
        try:
            for k, v in kv.items():
                row = db.query(AppSetting).filter(AppSetting.key == k).first()
                if row:
                    row.value = v
                else:
                    db.add(AppSetting(key=k, value=v))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[settings] DB 저장 실패: {e}")


# 재기동/재배포 직후 서비스들이 os.environ 으로 키를 읽으므로 DB 값을 주입한다.
HYDRATE_KEYS = [
    "NAVER_CUSTOMER_ID", "NAVER_ACCESS_LICENSE", "NAVER_SECRET_KEY",
    "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET",
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def hydrate_env_from_db():
    """DB에 저장된 설정을 os.environ 에 반영 — main.py lifespan 시작 시 호출."""
    vals = db_get_settings(HYDRATE_KEYS)
    for k, v in vals.items():
        if v:
            os.environ[k] = v
    if vals:
        print(f"[settings] DB 설정 {len(vals)}건을 환경변수로 주입했습니다.")


def resolve_keys(keys: list) -> dict:
    """설정 화면 표시용 조회 — DB > .env > os.environ."""
    env = read_env()
    dbv = db_get_settings(keys)
    return {k: (dbv.get(k) or env_or_os(env, k)) for k in keys}


def save_keys(env_vars: dict):
    """설정 저장 — DB(영속) + .env(로컬 설치형 호환) + os.environ(즉시 반영)."""
    db_set_settings(env_vars)
    write_env(env_vars)
    for k, v in env_vars.items():
        if v:
            os.environ[k] = v


@router.get("/naver-api", response_model=NaverApiKeys)
async def get_naver_api_keys():
    v = resolve_keys(["NAVER_CUSTOMER_ID", "NAVER_ACCESS_LICENSE", "NAVER_SECRET_KEY"])
    return NaverApiKeys(
        customer_id=v["NAVER_CUSTOMER_ID"],
        access_license=v["NAVER_ACCESS_LICENSE"],
        secret_key=v["NAVER_SECRET_KEY"]
    )

@router.post("/naver-api")
async def update_naver_api_keys(keys: NaverApiKeys):
    save_keys({
        "NAVER_CUSTOMER_ID": keys.customer_id,
        "NAVER_ACCESS_LICENSE": keys.access_license,
        "NAVER_SECRET_KEY": keys.secret_key
    })
    return {"message": "네이버 검색광고 API 키가 성공적으로 저장되었습니다."}

@router.get("/naver-dev-api", response_model=NaverDevApiKeys)
async def get_naver_dev_api_keys():
    v = resolve_keys(["NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"])
    return NaverDevApiKeys(
        client_id=v["NAVER_CLIENT_ID"],
        client_secret=v["NAVER_CLIENT_SECRET"]
    )

@router.post("/naver-dev-api")
async def update_naver_dev_api_keys(keys: NaverDevApiKeys):
    save_keys({
        "NAVER_CLIENT_ID": keys.client_id,
        "NAVER_CLIENT_SECRET": keys.client_secret
    })
    return {"message": "네이버 개발자센터 API 키가 성공적으로 저장되었습니다."}

@router.get("/ai-api", response_model=AIApiKeys)
async def get_ai_api_keys():
    v = resolve_keys(["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"])
    return AIApiKeys(
        claude_key=v["ANTHROPIC_API_KEY"],
        gemini_key=v["GEMINI_API_KEY"],
        openai_key=v["OPENAI_API_KEY"]
    )

@router.post("/ai-api")
async def update_ai_api_keys(keys: AIApiKeys):
    save_keys({
        "ANTHROPIC_API_KEY": keys.claude_key,
        "GEMINI_API_KEY": keys.gemini_key,
        "OPENAI_API_KEY": keys.openai_key
    })
    return {"message": "AI 생성 엔진 API 키가 성공적으로 저장되었습니다."}

@router.get("/telegram-api", response_model=TelegramApiKeys)
async def get_telegram_api_keys():
    v = resolve_keys(["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    return TelegramApiKeys(
        bot_token=v["TELEGRAM_BOT_TOKEN"],
        chat_id=v["TELEGRAM_CHAT_ID"]
    )

@router.post("/telegram-api")
async def update_telegram_api_keys(keys: TelegramApiKeys):
    save_keys({
        "TELEGRAM_BOT_TOKEN": keys.bot_token,
        "TELEGRAM_CHAT_ID": keys.chat_id
    })
    return {"message": "텔레그램 봇 연동 설정이 성공적으로 저장되었습니다."}

@router.get("/blog-prompts")
async def get_blog_prompts():
    data = read_prompts()
    
    # Legacy data conversion
    if "claude_prompt" in data and not any(k in data for k in ["product", "hospital", "app", "place", "service"]):
        legacy_data = {"claude_prompt": data.get("claude_prompt", ""), "gemini_prompt": data.get("gemini_prompt", "")}
        data = {
            "product": legacy_data.copy(),
            "hospital": legacy_data.copy(),
            "app": legacy_data.copy(),
            "place": legacy_data.copy(),
            "service": legacy_data.copy()
        }
        
    # Ensure all keys exist
    keys = ["product", "hospital", "app", "place", "service", "content_collect", "blog_daily", "blogspot", "cafe", "cafe_matjip", "tistory"]
    for k in keys:
        if k not in data:
            data[k] = {"claude_prompt": "", "gemini_prompt": ""}
            
    return data

from fastapi import Body

@router.post("/blog-prompts")
async def update_blog_prompts(prompts: dict = Body(...)):
    write_prompts(prompts)
    return {"message": "블로그 AI 프롬프트가 성공적으로 저장되었습니다."}


@router.get("/select-folder")
async def select_folder():
    """[레거시] 클라우드 백엔드에는 디스플레이·tkinter 가 없어 항상 빈 경로를 돌려준다.
    실제 폴더 선택은 내 PC 에이전트에 위임하는 POST /api/agent/pick-folder 를 사용할 것."""
    import asyncio

    def open_dialog():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(parent=root, title="이미지 폴더 선택")
        root.destroy()
        return folder

    try:
        folder = await asyncio.to_thread(open_dialog)
        return {"path": folder.replace("/", "\\") if folder else ""}
    except Exception as e:
        return {"path": ""}


class WashImagesRequest(BaseModel):
    folder_path: str

@router.post("/wash-images")
async def wash_images_endpoint(req: WashImagesRequest):
    import glob
    import os
    import sys
    
    # sys.path ?가???여 services 모듈??가져?수 ?도?처리
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_dir)
    parent_dir = os.path.dirname(backend_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
        
    try:
        from mbam_nextgen.services.armor import ImageArmor
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"ImageArmor 모듈??불러?지 못했?니?? {str(e)}")

    folder_path = req.folder_path
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        raise HTTPException(status_code=400, detail="유효?지 ?은 폴더 경로입?다.")
        
    img_paths = glob.glob(os.path.join(folder_path, "*.jpg")) +                 glob.glob(os.path.join(folder_path, "*.jpeg")) +                 glob.glob(os.path.join(folder_path, "*.png"))
                
    if not img_paths:
        return {"success": False, "total_found": 0, "success_count": 0, "fail_count": 0, "message": "이미? ?일??발견?지 못했?니??"}
        
    washed_dir = os.path.join(folder_path, "washed_images")
    armor = ImageArmor(output_dir=washed_dir)
    
    success_count = 0
    fail_count = 0
    
    for idx, img in enumerate(img_paths):
        filename = os.path.basename(img)
        # 확장자?소문자로 강제 변경?필요 ?음, 원본 ?름 ?지 (혹??washed_ 프리?스)
        washed_name = f"washed_{filename}"
        if washed_name.lower().endswith(".png"):
            washed_name = washed_name[:-4] + ".jpg" # 세탁기는 JPEG로 저장함
            
        try:
            result_path = armor.wash_image(img, washed_name)
            if result_path:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"[{filename}] ?탁 ?패: {e}")
            fail_count += 1
            
    return {
        "success": success_count > 0,
        "total_found": len(img_paths),
        "success_count": success_count,
        "fail_count": fail_count,
        "output_dir": washed_dir
    }


from fastapi import File, UploadFile, Form
import base64
import io
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import random
import uuid

@router.post("/wash-upload")
async def wash_upload_endpoint(
    files: list[UploadFile] = File(...),
    count: int = Form(10),
    use_border: bool = Form(False),
    use_noise: bool = Form(True),
    use_watermark: bool = Form(False),
    use_rotation: bool = Form(False),
    keep_original_size: bool = Form(False),   # 원본 해상도 그대로 처리(느림)
    # ── 세탁 방식 개별 선택 ────────────────────────────────────────────────
    # 예전에는 크롭·밝기·EXIF 가 선택지 없이 무조건 걸렸다. 화면에서는 어떤 처리가
    # 들어갔는지 알 수 없어, 결과가 원본과 달라 보이는 이유를 설명할 수 없었다.
    # 기본값은 예전 동작과 같게 둔다 — 체크를 건드리지 않으면 결과가 달라지지 않는다.
    use_crop: bool = Form(True),              # 가장자리 5~8% 크롭
    use_bright_contrast: bool = Form(True),   # 밝기·대비 미세변형
    use_exif: bool = Form(True),              # 촬영정보(EXIF) 교체
    use_flip: bool = Form(False),             # 좌우반전
    use_hue: bool = Form(False),              # 색조 미세이동
    use_resample: bool = Form(False),         # 리사이즈 재샘플링
    # 저장 형식 — jpeg(기본) | webp. WebP 는 같은 화질에서 용량이 25~35% 작다.
    output_format: str = Form("jpeg"),
):
    try:
        from mbam_nextgen.services.armor import ImageArmor
    except ImportError:
        pass # Handle inside

    results = []
    fmt = "webp" if (output_format or "").strip().lower() == "webp" else "jpeg"
    ext, mime = (".webp", "image/webp") if fmt == "webp" else (".jpg", "image/jpeg")

    # ⚠ 속도의 핵심 — 세탁 '전에' 한 번만 줄인다.
    #   휴대폰 사진은 보통 4000x3000(1200만 화소)이라 회전·블러·밝기보정이 전부 그 픽셀 수만큼 돈다.
    #   실측: 원본 1장 2.34초(10장 23초) → 1600px 로 줄이면 1장 0.2초 수준(10장 2초).
    #   게다가 보관함에 저장할 때 어차피 1280px 로 다시 줄이므로, 큰 걸 만들어 작게 줄이는 낭비였다.
    #   원본 화질이 꼭 필요한 경우를 위해 keep_original_size 옵션을 남겨둔다.
    MAX_SIDE = 1600

    def _fake_exif_once():
        """가짜 EXIF 생성기. 장마다 ImageArmor 를 새로 만들면 폴더 생성까지 반복된다.
        촬영일시는 armor 쪽에서 매번 새로 뽑으므로 장마다 값이 달라진다(고정값 아님)."""
        try:
            from mbam_nextgen.services.armor import ImageArmor
            return ImageArmor(output_dir="temp")._get_fake_exif()
        except Exception:
            return b""

    # 크롭 구현은 armor 한 곳에만 둔다(두 벌이 되면 한쪽만 고치는 사고가 난다).
    try:
        from mbam_nextgen.services.armor import _crop_edges
    except Exception:
        def _crop_edges(im):  # armor 를 못 불러온 경우에도 세탁 자체는 계속되게
            w, h = im.size
            base = min(w, h)
            l, t, r, b = (int(base * random.uniform(0.05, 0.08)) for _ in range(4))
            if w - l - r < 64 or h - t - b < 64:
                return im
            return im.crop((l, t, w - r, h - b))

    # Read all uploaded images into memory
    original_images = []
    for file in files:
        contents = await file.read()
        try:
            img = Image.open(io.BytesIO(contents)).convert("RGB")
            if not keep_original_size and max(img.size) > MAX_SIDE:
                img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
            original_images.append({
                "filename": file.filename,
                "img": img
            })
        except Exception as e:
            print(f"Failed to open image {file.filename}: {e}")
            
    if not original_images:
        return {"success": False, "message": "유효한 이미지가 없습니다."}

    # Generate N images circulating through the originals
    for i in range(count):
        orig_dict = original_images[i % len(original_images)]
        img = orig_dict["img"].copy()
        
        # 처리 순서 — 구도를 바꾸는 것(회전·크롭·반전·재샘플링)을 먼저 하고,
        # 픽셀 값을 건드리는 것(노이즈·밝기·색조)을 나중에 얹는다.
        # 순서가 반대면 회전으로 생긴 검은 여백에도 노이즈가 얹혀 그 자국이 남는다.
        if use_rotation:
            angle = random.uniform(0.5, 2.0)
            if random.random() > 0.5: angle = -angle
            img = img.rotate(angle, expand=False, resample=Image.BICUBIC)

        # 가장자리 크롭 5~8% — 세탁에서 가장 중요한 처리다.
        # 세탁의 목적은 지각해시(pHash)를 바꾸는 것인데, 노이즈·밝기보정·미세회전만으로는
        # pHash 거리가 0에 머물러 원본과 '같은 이미지'로 판정됐다(측정값: 노이즈만 0.2/64).
        # 크롭은 pHash 를 실제로 흔드는 유일한 저비용 처리다(5%→12, 8%→20 / 64).
        # 회전을 켰다면 이 크롭이 회전 여백까지 함께 잘라낸다.
        # ⚠ 끄면 다른 처리를 다 켜도 원본과 같은 이미지로 걸릴 수 있다(화면에도 경고를 띄운다).
        if use_crop:
            img = _crop_edges(img)

        if use_flip:
            # 좌우반전 — pHash 를 가장 크게 바꾸지만, 간판·글자가 찍힌 사진은
            # 뒤집힌 티가 바로 난다. 그래서 기본값은 꺼둔다.
            img = ImageOps.mirror(img)

        if use_resample:
            # 95~99% 로 줄였다가 원래 크기로 되돌린다.
            # 픽셀 격자가 새로 계산되면서 원본의 압축 흔적·미세 패턴이 사라진다.
            # 크기는 그대로라 보는 사람은 차이를 못 느낀다.
            w, h = img.size
            ratio = random.uniform(0.95, 0.99)
            small = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
            img = small.resize((w, h), Image.BICUBIC)

        if use_noise:
            # 체크했으면 '항상' 적용한다.
            # 예전에는 70% 확률로만 블러를 걸어, 10장 중 3장쯤은 노이즈가 빠졌다.
            # (화면 설명은 '항상 적용됨' 이라 실제 동작과 어긋났다)
            # 대신 강도를 장마다 다르게 줘서 모든 결과가 똑같이 처리된 티는 나지 않게 한다.
            noise = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.1, 0.4)))
            img = Image.blend(img, noise, alpha=random.uniform(0.10, 0.20))

        if use_bright_contrast:
            # ±2% — 사람 눈으로는 구분할 수 없는 범위다.
            # 예전에는 노이즈 옵션에 묶여 있어 따로 끌 수 없었다.
            img = ImageEnhance.Brightness(img).enhance(1 + random.uniform(-0.02, 0.02))
            img = ImageEnhance.Contrast(img).enhance(1 + random.uniform(-0.02, 0.02))

        if use_hue:
            # 색조를 255 단계 중 2~5 만큼 돌린다. 눈으로는 같은 색으로 보이지만
            # 색 히스토그램이 달라져 색 분포로 같은 사진을 찾는 검사를 피한다.
            _h, _s, _v = img.convert("HSV").split()
            shift = random.choice([-1, 1]) * random.randint(2, 5)
            _h = _h.point(lambda p: (p + shift) % 256)
            img = Image.merge("HSV", (_h, _s, _v)).convert("RGB")

        if use_border:
            border_color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
            img = ImageOps.expand(img, border=5, fill=border_color)
            
        # Watermark mock
        if use_watermark:
            pass # Implement if needed
            
        # 촬영정보(EXIF) 교체 — 촬영일시·카메라 모델을 가짜로 채운다.
        # ※ ImageArmor 를 장마다 새로 만들지 않고 위에서 한 번 만든 것을 쓴다.
        # 끄면 EXIF 없이 저장된다(원본 EXIF 가 따라붙지는 않는다 — PIL 이 다시 쓰지 않으므로).
        exif_bytes = _fake_exif_once() if use_exif else b""

        # Save to buffer
        # 품질 92~98 → 82~88. 카페 업로드용이라 육안 차이는 거의 없고 용량·시간이 크게 준다.
        # (보관함 저장 시에는 어차피 품질 80 으로 다시 압축된다)
        buf = io.BytesIO()
        # ⚠ exif=None 을 넘기면 안 된다 — PIL 이 그대로 len() 을 불러 TypeError 로 터진다.
        #   EXIF 를 끄거나 ImageArmor 를 못 불러온 경우가 여기 해당한다. 아예 넘기지 않는다.
        if fmt == "webp":
            # WebP 도 EXIF 를 담을 수 있다. 품질은 JPEG 와 같은 범위로 장마다 다르게(파일 해시 분산).
            # method=4 — 6(최고 압축)은 장당 수 초씩 걸려 대량 생성에서 너무 느리다.
            save_kwargs = {"format": "WEBP", "quality": random.randint(82, 88), "method": 4}
        else:
            save_kwargs = {"format": "JPEG", "quality": random.randint(82, 88)}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        img.save(buf, **save_kwargs)
        img_bytes = buf.getvalue()
        base64_str = base64.b64encode(img_bytes).decode('utf-8')

        orig_name = orig_dict["filename"]
        base_name = os.path.splitext(orig_name)[0]
        washed_filename = f"washed_{base_name}_{uuid.uuid4().hex[:6]}{ext}"

        results.append({
            "original_filename": orig_name,
            "washed_filename": washed_filename,
            "base64_data": f"data:{mime};base64,{base64_str}"
        })

    return {
        "success": True,
        "results": results
    }


# ===================== 이미지 보관함 (세탁 후 저장 → 발행 재사용) =====================
from fastapi import Depends
import glob as _glob
from ..auth import get_current_user

SAVED_IMAGES_ROOT = os.path.join(os.getcwd(), "saved_images")


def _user_lib_dir(current_user: dict) -> str:
    uid = (current_user or {}).get("sub") or "anon"
    safe = "".join(c for c in str(uid) if c.isalnum() or c in "._-@") or "anon"
    d = os.path.join(SAVED_IMAGES_ROOT, safe)
    os.makedirs(d, exist_ok=True)
    return d


# 보관함 용량 가드레일
LIB_MAX_FILES = 30      # 계정당 최대 보관 장수 (초과 시 오래된 것부터 삭제)
LIB_TTL_DAYS = 14       # 저장 후 N일 지나면 자동 삭제
LIB_MAX_DIM = 1280      # 저장 시 긴 변 최대 px (이보다 크면 리사이즈)
LIB_QUALITY = 80        # 저장 JPEG 품질


def _compress_jpeg(raw_bytes: bytes) -> bytes:
    """저장 용량 절감: 긴 변 LIB_MAX_DIM 이하로 리사이즈 + 품질 LIB_QUALITY로 재인코딩."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail((LIB_MAX_DIM, LIB_MAX_DIM), Image.LANCZOS)  # 더 클 때만 축소(비율 유지)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=LIB_QUALITY, optimize=True)
    return buf.getvalue()


def _cleanup_lib(d: str):
    """14일 경과분 삭제 + 30장 상한 유지(오래된 것부터)."""
    import time
    try:
        now = time.time()
        for p in _glob.glob(os.path.join(d, "*.jpg")):
            try:
                if now - os.path.getmtime(p) > LIB_TTL_DAYS * 86400:
                    os.remove(p)
            except Exception:
                pass
        files = sorted(_glob.glob(os.path.join(d, "*.jpg")), key=os.path.getmtime)
        if len(files) > LIB_MAX_FILES:
            for p in files[:len(files) - LIB_MAX_FILES]:
                try:
                    os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass


class WashSaveRequest(BaseModel):
    images: list  # base64 data URL 목록 (세탁 결과)


@router.post("/wash-library/save", summary="세탁한 이미지를 내 보관함에 저장")
async def wash_library_save(req: WashSaveRequest, current_user: dict = Depends(get_current_user)):
    d = _user_lib_dir(current_user)
    saved = 0
    for data_url in (req.images or []):
        try:
            b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
            raw = base64.b64decode(b64)
            raw = _compress_jpeg(raw)  # 용량 절감(리사이즈+품질↓)
            fn = f"lib_{uuid.uuid4().hex[:10]}.jpg"
            with open(os.path.join(d, fn), "wb") as f:
                f.write(raw)
            saved += 1
        except Exception as e:
            print(f"[wash-library] 저장 실패: {e}")
    _cleanup_lib(d)  # 30장 상한 + 14일 만료 유지
    return {"success": True, "saved": saved, "folder": d, "max_files": LIB_MAX_FILES, "ttl_days": LIB_TTL_DAYS}


@router.get("/wash-library", summary="내 이미지 보관함 목록")
async def wash_library_list(current_user: dict = Depends(get_current_user)):
    d = _user_lib_dir(current_user)
    _cleanup_lib(d)  # 조회 시점에도 만료/상한 정리
    items = []
    for p in sorted(_glob.glob(os.path.join(d, "*.jpg")), key=os.path.getmtime, reverse=True):
        try:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            items.append({"filename": os.path.basename(p), "base64_data": f"data:image/jpeg;base64,{b64}"})
        except Exception:
            pass
    return {"success": True, "folder": d, "items": items, "max_files": LIB_MAX_FILES, "ttl_days": LIB_TTL_DAYS}


@router.delete("/wash-library/{filename}", summary="보관함 이미지 삭제")
async def wash_library_delete(filename: str, current_user: dict = Depends(get_current_user)):
    d = _user_lib_dir(current_user)
    safe = os.path.basename(filename)  # path traversal 방지
    p = os.path.abspath(os.path.join(d, safe))
    if os.path.exists(p) and os.path.commonpath([os.path.abspath(d), p]) == os.path.abspath(d):
        try:
            os.remove(p)
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}
    return {"success": False, "message": "파일을 찾을 수 없습니다."}


class WashStageRequest(BaseModel):
    filenames: list  # 발행에 사용할 보관함 파일명 목록


@router.post("/wash-library/stage", summary="선택한 보관함 이미지를 발행용 임시 폴더로 복사")
async def wash_library_stage(req: WashStageRequest, current_user: dict = Depends(get_current_user)):
    import shutil
    src_dir = _user_lib_dir(current_user)
    dst_dir = os.path.join(os.getcwd(), "temp_uploaded_images", uuid.uuid4().hex)
    os.makedirs(dst_dir, exist_ok=True)
    copied = 0
    for fn in (req.filenames or []):
        safe = os.path.basename(fn)  # path traversal 방지
        sp = os.path.abspath(os.path.join(src_dir, safe))
        if os.path.exists(sp) and os.path.commonpath([os.path.abspath(src_dir), sp]) == os.path.abspath(src_dir):
            try:
                shutil.copy2(sp, os.path.join(dst_dir, safe))
                copied += 1
            except Exception as e:
                print(f"[wash-stage] 복사 실패: {e}")
    return {"success": True, "folder": dst_dir, "count": copied}
