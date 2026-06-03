import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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

class BlogPrompts(BaseModel):
    claude_prompt: str
    gemini_prompt: str

PROMPTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts.json")

def read_prompts():
    if not os.path.exists(PROMPTS_PATH):
        return {"claude_prompt": "", "gemini_prompt": ""}
    import json
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {"claude_prompt": "", "gemini_prompt": ""}

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

@router.get("/blog-prompts", response_model=BlogPrompts)
async def get_blog_prompts():
    data = read_prompts()
    return BlogPrompts(
        claude_prompt=data.get("claude_prompt", ""),
        gemini_prompt=data.get("gemini_prompt", "")
    )

@router.post("/blog-prompts")
async def update_blog_prompts(prompts: BlogPrompts):
    write_prompts({
        "claude_prompt": prompts.claude_prompt,
        "gemini_prompt": prompts.gemini_prompt
    })
    return {"message": "블로그 AI 프롬프트가 성공적으로 저장되었습니다."}
