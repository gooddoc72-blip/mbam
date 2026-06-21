import os
from fastapi import APIRouter, HTTPException
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
    if not os.path.exists(PROMPTS_PATH):
        return {}
    import json
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def write_prompts(data):
    import json
    with open(PROMPTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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

@router.get("/naver-api", response_model=NaverApiKeys)
async def get_naver_api_keys():
    env = read_env()
    return NaverApiKeys(
        customer_id=env.get("NAVER_CUSTOMER_ID", ""),
        access_license=env.get("NAVER_ACCESS_LICENSE", ""),
        secret_key=env.get("NAVER_SECRET_KEY", "")
    )

@router.post("/naver-api")
async def update_naver_api_keys(keys: NaverApiKeys):
    env_vars = {
        "NAVER_CUSTOMER_ID": keys.customer_id,
        "NAVER_ACCESS_LICENSE": keys.access_license,
        "NAVER_SECRET_KEY": keys.secret_key
    }
    write_env(env_vars)
    return {"message": "네이버 검색광고 API 키가 성공적으로 저장되었습니다."}

@router.get("/naver-dev-api", response_model=NaverDevApiKeys)
async def get_naver_dev_api_keys():
    env = read_env()
    return NaverDevApiKeys(
        client_id=env.get("NAVER_CLIENT_ID", ""),
        client_secret=env.get("NAVER_CLIENT_SECRET", "")
    )

@router.post("/naver-dev-api")
async def update_naver_dev_api_keys(keys: NaverDevApiKeys):
    env_vars = {
        "NAVER_CLIENT_ID": keys.client_id,
        "NAVER_CLIENT_SECRET": keys.client_secret
    }
    write_env(env_vars)
    
    # Reload env into os.environ
    for k, v in env_vars.items():
        if v: os.environ[k] = v
        
    return {"message": "네이버 개발자센터 API 키가 성공적으로 저장되었습니다."}

@router.get("/ai-api", response_model=AIApiKeys)
async def get_ai_api_keys():
    env = read_env()
    return AIApiKeys(
        claude_key=env.get("ANTHROPIC_API_KEY", ""),
        gemini_key=env.get("GEMINI_API_KEY", ""),
        openai_key=env.get("OPENAI_API_KEY", "")
    )

@router.post("/ai-api")
async def update_ai_api_keys(keys: AIApiKeys):
    env_vars = {
        "ANTHROPIC_API_KEY": keys.claude_key,
        "GEMINI_API_KEY": keys.gemini_key,
        "OPENAI_API_KEY": keys.openai_key
    }
    write_env(env_vars)
    
    # Reload env into os.environ so SoulRewriter uses it immediately without full restart
    for k, v in env_vars.items():
        if v: os.environ[k] = v
        
    return {"message": "AI 생성 엔진 API 키가 성공적으로 저장되었습니다."}

@router.get("/telegram-api", response_model=TelegramApiKeys)
async def get_telegram_api_keys():
    env = read_env()
    return TelegramApiKeys(
        bot_token=env.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=env.get("TELEGRAM_CHAT_ID", "")
    )

@router.post("/telegram-api")
async def update_telegram_api_keys(keys: TelegramApiKeys):
    env_vars = {
        "TELEGRAM_BOT_TOKEN": keys.bot_token,
        "TELEGRAM_CHAT_ID": keys.chat_id
    }
    write_env(env_vars)
    
    for k, v in env_vars.items():
        if v: os.environ[k] = v
        
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
    keys = ["product", "hospital", "app", "place", "service", "content_collect"]
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
    import tkinter as tk
    from tkinter import filedialog
    import asyncio
    
    def open_dialog():
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
    use_rotation: bool = Form(False)
):
    try:
        from mbam_nextgen.services.armor import ImageArmor
    except ImportError:
        pass # Handle inside

    results = []
    
    # Read all uploaded images into memory
    original_images = []
    for file in files:
        contents = await file.read()
        try:
            img = Image.open(io.BytesIO(contents)).convert("RGB")
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
        
        # Apply edits based on options
        if use_rotation:
            angle = random.uniform(0.5, 2.0)
            if random.random() > 0.5: angle = -angle
            img = img.rotate(angle, expand=False, resample=Image.BICUBIC)
            # Crop slightly to remove black edges from rotation
            w, h = img.size
            cp = int(max(w, h) * 0.02)
            img = img.crop((cp, cp, w - cp, h - cp))
            
        if use_noise:
            if random.random() > 0.3:
                noise = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.1, 0.3)))
                img = Image.blend(img, noise, alpha=0.15)
            # slight brightness/contrast
            img = ImageEnhance.Brightness(img).enhance(1 + random.uniform(-0.02, 0.02))
            img = ImageEnhance.Contrast(img).enhance(1 + random.uniform(-0.02, 0.02))
            
        if use_border:
            border_color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
            img = ImageOps.expand(img, border=5, fill=border_color)
            
        # Watermark mock
        if use_watermark:
            pass # Implement if needed
            
        # Add EXIF (mocked via ImageArmor or manually)
        try:
            from mbam_nextgen.services.armor import ImageArmor
            armor = ImageArmor(output_dir="temp")
            exif_bytes = armor._get_fake_exif()
        except:
            exif_bytes = b""
            
        # Save to buffer
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=random.randint(92, 98), exif=exif_bytes if exif_bytes else None)
        img_bytes = buf.getvalue()
        base64_str = base64.b64encode(img_bytes).decode('utf-8')
        
        orig_name = orig_dict["filename"]
        base_name = os.path.splitext(orig_name)[0]
        washed_filename = f"washed_{base_name}_{uuid.uuid4().hex[:6]}.jpg"
        
        results.append({
            "original_filename": orig_name,
            "washed_filename": washed_filename,
            "base64_data": f"data:image/jpeg;base64,{base64_str}"
        })

    return {
        "success": True,
        "results": results
    }
