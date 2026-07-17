import os
import asyncio
from typing import List, Optional
from dotenv import load_dotenv

# Explicitly load .env from mbam_nextgen directory
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

# 최신 구글 제미나이 SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

# Optional imports for other AI support
try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

class SoulRewriter:
    """
    [L2. The Soul] - Multi-AI Support (Updated for google-genai)
    """
    
    def __init__(self, provider: str = "gemini"):
        self.provider = provider.lower()
        self._init_clients()

    def _init_clients(self):
        # BYOK: 요청 사용자(설치형 고객)의 키가 있으면 그 키, 없으면 서버 .env 키(웹/시스템).
        try:
            from mbam_nextgen.services.ai_keys import get_ai_keys
            _uk = get_ai_keys()
        except Exception:
            _uk = {}

        # 1. Gemini Init (New SDK)
        self.gemini_key = _uk.get("gemini_key") or os.getenv("GEMINI_API_KEY")
        if genai and self.gemini_key:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
        else:
            self.gemini_client = None

        # 2. Claude Init
        self.claude_key = _uk.get("claude_key") or os.getenv("ANTHROPIC_API_KEY")
        if anthropic and self.claude_key:
            self.claude_client = anthropic.AsyncAnthropic(api_key=self.claude_key)
        else:
            self.claude_client = None

        # 3. OpenAI Init
        self.openai_key = _uk.get("openai_key") or os.getenv("OPENAI_API_KEY")
        if openai and self.openai_key:
            self.openai_client = openai.AsyncOpenAI(api_key=self.openai_key)
        else:
            self.openai_client = None

    async def rewrite_for_blog(self, raw_data: str, keyword: str, provider: str = None,
                               post_purpose: str = None, promo_type: str = None, distribution_mode: str = None, api_key: str = None,
                               prompt_category: str = None, custom_prompt: str = None,
                               long_tail: str = None, title_main: str = None) -> str:
        target_provider = (provider or self.provider).lower()
        prompt = self._get_blog_prompt(target_provider, raw_data, keyword, post_purpose, promo_type, distribution_mode, prompt_category, custom_prompt, long_tail=long_tail, title_main=title_main)

        if target_provider == "gemini":
            if api_key and genai:
                temp_client = genai.Client(api_key=api_key)
                return await self._call_gemini_client(temp_client, prompt)
            elif self.gemini_client:
                return await self._call_gemini_client(self.gemini_client, prompt)

        elif target_provider == "claude":
            try:
                if api_key and anthropic:
                    temp_client = anthropic.AsyncAnthropic(api_key=api_key)
                    return await self._call_claude_client(temp_client, prompt)
                elif self.claude_client:
                    return await self._call_claude_client(self.claude_client, prompt)
            except Exception as e:
                print(f"⚠️ Claude API failed ({e}), falling back to Gemini.")
                if self.gemini_client:
                    return await self._call_gemini_client(self.gemini_client, prompt)
                raise

        elif target_provider == "openai":
            if api_key and openai:
                temp_client = openai.AsyncOpenAI(api_key=api_key)
                return await self._call_openai_client(temp_client, prompt)
            elif self.openai_client:
                return await self._call_openai_client(self.openai_client, prompt)

        # 설정 오류는 raise — 호출자(orchestrator)가 폴백 처리. string 반환 시 본문에 그대로 게시됨
        raise RuntimeError(f"{target_provider} 엔진 미설정 (API 키 없음 또는 라이브러리 미설치)")

    def _get_blog_prompt(self, target_provider, raw_data, keyword, post_purpose=None, promo_type=None, distribution_mode=None, prompt_category=None, custom_prompt_text=None, long_tail=None, title_main=None):
        # 검색량 기반 '메인+롱테일' 제목 지시(있을 때만). title_main = 원본(깨끗한) 메인 키워드
        _main_kw = (str(title_main).strip() if title_main else "") or (str(keyword).splitlines()[0].strip() if keyword else "")
        _lt = str(long_tail).strip() if long_tail else ""
        _has_lt = bool(_lt) and _lt.replace(" ", "") != _main_kw.replace(" ", "")
        if _has_lt:
            title_seo_block = (
                "[제목 규칙 — 검색량 기반 SEO]\n"
                f"        - 메인 키워드 '{_main_kw}'를 제목 맨 앞쪽에 배치\n"
                f"        - 롱테일 키워드 '{_lt}'를 제목에 자연스럽게 함께 녹여 '메인+롱테일' 조합으로 완성\n"
                "        - 전체 32자 이내, 숫자·기간·경험 등 클릭 유발 요소 1개 포함\n"
                "        - 이모지·특수기호 금지, 키워드 억지 나열 금지(하나의 자연스러운 문장/구로)"
            )
            title_seo_inline = f" (제목엔 메인 키워드 '{_main_kw}'를 앞쪽에, 롱테일 키워드 '{_lt}'를 자연스럽게 함께 포함)"
        else:
            title_seo_block = (
                "[제목 규칙 — SEO]\n"
                "        - 타겟 키워드를 제목 앞쪽에 배치하고, 25자 이내로 작성\n"
                "        - 숫자·기간·경험 등 클릭 유발 요소를 1개 포함 (예: \"3가지\", \"일주일 써보니\")\n"
                "        - 이모지·특수기호 금지"
            )
            title_seo_inline = ""
        # 1. 포스팅 목적 (Tone & Manner)
        if post_purpose == "intro":
            tone_guide = "객관적이고 전문적인 어조로 매장이나 상품의 장점을 소개하는 '홍보/소개' 글로 작성해주세요. (3인칭 관찰자 혹은 브랜드 에디터 시점)"
        elif post_purpose == "info":
            tone_guide = "독자에게 유용한 지식을 전달하는 '정보 제공성' 글로 작성해주세요. (전문적이고 신뢰감 있는 톤, 지나친 홍보나 과장된 감정표현 자제)"
        else: # 기본값은 review
            tone_guide = "직접 다녀오거나 사용해본 것처럼 생생하고 감성적인 '내돈내산 체험 후기' 느낌으로 작성해주세요. (1인칭 시점, 경험 중심)"

        # 2. 배포 방식 (분량 및 구조)
        if distribution_mode == "mass":
            length_guide = "분량은 800~1,000자 이내로 짧고 간결하게 작성하세요. 서론을 짧게 하고 핵심만 빠르게 전달하세요."
        else: # 기본값은 normal
            length_guide = "분량은 1,500자 이상으로 길고 상세하게 작성하세요. [도입부(공감/후킹) - 본문(상세 설명/장점) - 마무리(추천/요약)]의 탄탄한 구조를 갖추세요."

        # 3. 홍보 카테고리 (특별 가이드라인)
        special_guide = ""
        if promo_type == "hospital":
            special_guide = """
            [★중요: 의료법 준수 지침★]
            - '최고', '유일', '보장', '완치', '전문' 등의 과장되거나 절대적인 표현은 의료법 위반이므로 절대 사용하지 마세요.
            - 부작용이 있을 수 있다는 점이나 개인차가 있다는 뉘앙스를 자연스럽게 포함하세요.
            - 감정적인 과한 칭찬보다는 객관적인 시설, 친절도, 위치, 진료 과목 중심의 정보 전달에 집중하세요.
            """
        elif promo_type == "product":
            special_guide = "- 제품의 스펙, 디자인, 활용도, 가성비 등을 중심으로 작성하고, 글 하단에 구매를 유도하는 자연스러운 멘트를 포함하세요."
        elif promo_type == "place":
            special_guide = "- 매장의 위치(접근성), 주차 여부, 분위기, 시그니처 메뉴/서비스 등을 강조하고, 방문을 유도하세요."

        # 4. Check Custom Prompts
        custom_prompt = ""
        ref_injection = ""
        # 주입된 커스텀 프롬프트(예: 클라우드가 매일 자동배포 잡 payload로 실어 보낸 blog_daily 프롬프트)가
        # 있으면 로컬 prompts.json 대신 그것을 사용 — 에이전트 PC에 로컬 파일이 없어도 관리자 설정이 적용된다.
        prompts_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts.json")
        if custom_prompt_text and str(custom_prompt_text).strip():
            custom_prompt = str(custom_prompt_text)
        elif os.path.exists(prompts_path):
            import json
            try:
                with open(prompts_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 카테고리 선택: 명시적 prompt_category(예: 글감수집 content_collect) 우선,
                    # 없으면 홍보 카테고리(promo_type), 그것도 없으면 레거시 단일 프롬프트
                    if prompt_category and isinstance(data.get(prompt_category), dict):
                        cat_data = data.get(prompt_category, {})
                    elif "claude_prompt" in data and not any(k in data for k in ["product", "hospital", "app", "place", "service", "content_collect"]):
                        cat_data = data
                    else:
                        cat_data = data.get(promo_type, {}) if promo_type else {}
                    
                    if target_provider == "claude":
                        custom_prompt = cat_data.get("claude_prompt", "")
                    elif target_provider == "gemini":
                        custom_prompt = cat_data.get("gemini_prompt", "")
                        
                    ref_files = []
                    if "reference_file_content" in cat_data and cat_data["reference_file_content"]:
                        ref_files.append({"name": cat_data.get("reference_file_name", "reference.txt"), "content": cat_data["reference_file_content"]})
                    
                    if "reference_files" in cat_data:
                        ref_files.extend(cat_data["reference_files"])
                        
                    if ref_files:
                        docs = []
                        for i, file in enumerate(ref_files, 1):
                            docs.append(f'<document index="{i}">\n<source>{file.get("name", "document")}</source>\n<document_content>\n{file.get("content", "")}\n</document_content>\n</document>')
                        
                        docs_str = "\n".join(docs)
                        ref_injection = f"\n\n[프로젝트 첨부 지식/가이드라인]\n<documents>\n{docs_str}\n</documents>\n\n★중요★ 위 <documents> 태그에 포함된 파일의 내용을 완벽하게 숙지하고 가장 우선적으로 참고하여 원고를 작성하세요."
                        
                    if ref_injection and custom_prompt.strip():
                        custom_prompt += ref_injection
            except Exception as e:
                pass

        if custom_prompt.strip():
            if "{keyword}" not in custom_prompt:
                custom_prompt += "\n\n위 가이드라인에 따라 아래의 타겟 키워드로 블로그 원고를 작성해주세요.\n\n[기본 정보]\n- 타겟(핵심) 키워드: {keyword}\n- 참고 데이터: {raw_data}\n\n[작성 가이드라인]\n1. 어조: {tone_guide}\n2. 분량 및 구조: {length_guide}\n3. 마크다운 기호 금지: 별표(*), 물결표(~), 샵(#) 등 마크다운 기호를 절대 사용하지 마세요. (단, 해시태그에는 샵 허용)\n4. 이모지 금지: 글에 어떠한 이모지(아이콘)도 절대 사용하지 마세요.\n5. 이미지 삽입 위치 지정: 내용이 전환되거나 문단이 끝나는 적절한 위치(본문 사이사이)에 `[이미지]` 라는 특수 태그를 3~5회 정도 삽입하세요.\n6. 해시태그 추가: 본문 작성이 모두 끝난 후, 맨 마지막 줄에는 이 글과 관련된 검색용 해시태그를 5개 내외로 작성해 주세요. (예: `#해시태그1 #해시태그2`)\n{special_guide}\n\n첫 줄에 반드시 '[제목] 클릭하고 싶어지는 매력적인 제목' 형식으로 제목을 작성하고, 그 다음 줄부터 본문을 작성해주세요."
            if _has_lt:
                custom_prompt += f"\n\n[제목 필수 규칙] 첫 줄 제목은 메인 키워드 '{_main_kw}'를 앞쪽에 두고, 롱테일 키워드 '{_lt}'를 자연스럽게 함께 녹여 '메인+롱테일' 조합으로 작성하세요(전체 32자 이내, 억지 나열 금지)."
            return custom_prompt.replace("{keyword}", str(keyword)).replace("{raw_data}", str(raw_data)).replace("{combined_text}", str(raw_data)).replace("{tone_guide}", str(tone_guide)).replace("{length_guide}", str(length_guide)).replace("{special_guide}", str(special_guide))
        
        # 기본 프롬프트에 첨부파일이 있다면 추가

        return f"""
        당신은 네이버 블로그 전문 파워블로거이자 상위노출 SEO 전문가입니다.
        아래의 정보를 바탕으로 블로그 포스팅 원고를 작성해주세요.

        [기본 정보]
        - 타겟(핵심) 키워드: {keyword}
        - 참고 데이터: {raw_data}

        {title_seo_block}

        [본문 구조 — 반드시 이 순서로]
        1) 서론: 독자의 상황에 공감하는 도입 3~4문장 (첫 문단에 타겟 키워드 1회 자연 포함)
        2) 본문: 소제목 3~4개로 단락 구분. 각 소제목 아래 구체적 내용 (경험·수치·예시 포함)
        3) 결론: 핵심 요약 + 독자 행동 유도(방문·구매·저장 등) 한 문장

        [SEO 키워드 규칙]
        - 타겟 키워드를 본문 전체에 5~7회 자연스럽게 삽입 (같은 문장 반복 금지)
        - 소제목에도 타겟 또는 연관 키워드를 최소 2회 포함

        [작성 가이드라인]
        1. 어조: {tone_guide}
        2. 분량 및 구조: {length_guide}
        3. 마크다운 기호 금지: 별표(*), 물결표(~), 샵(#) 등 마크다운 기호를 절대 사용하지 마세요. (단, 해시태그에는 샵 허용)
        4. 이모지 금지: 글에 어떠한 이모지(아이콘)도 절대 사용하지 마세요.
        5. 이미지 삽입 위치 지정: 내용이 전환되거나 문단이 끝나는 적절한 위치(본문 사이사이)에 `[이미지]` 라는 특수 태그를 3~5회 정도 삽입하세요.
        6. 해시태그 추가: 본문 작성이 모두 끝난 후, 맨 마지막 줄에는 이 글과 관련된 검색용 해시태그를 5개 내외로 작성해 주세요. (예: `#해시태그1 #해시태그2`)
        7. 금지 표현: "~에 대해 알아보겠습니다", "이상으로 ~를 마치겠습니다" 등 기계적인 상투 문구, 같은 어미 3회 연속 반복
        {special_guide}
        {ref_injection}

        첫 줄에 반드시 '[제목] 클릭하고 싶어지는 매력적인 제목' 형식으로 제목을 작성하고, 그 다음 줄부터 본문을 작성해주세요.
        """

    async def describe_image(self, image_paths: list, keyword: str = "") -> str:
        """첨부 이미지를 비전으로 분석해 원고 작성용 '글감(핵심 정보)'을 한국어로 정리.
        Gemini 우선(재시도) → 실패 시 Claude 비전 폴백. 글감수집 없이 이미지+키워드로 원고 작성 시 사용."""
        import os
        valid = [p for p in (image_paths or [])[:4] if p and os.path.exists(p)]
        if not valid:
            return ""
        kw = (keyword or "").strip()
        instruction = (
            f"다음 이미지를 보고 '{kw}' 주제의 네이버 블로그/카페 글을 쓰기 위한 핵심 정보를 한국어로 정리해줘.\n"
            if kw else
            "다음 이미지를 보고 네이버 블로그/카페 글을 쓰기 위한 핵심 정보를 한국어로 정리해줘.\n"
        ) + "- 이미지에 실제로 보이는 사실만 객관적으로(상품/장면/특징/문구/숫자 등).\n- 추측·과장 금지. 보이지 않는 정보는 적지 말 것.\n- 글 작성에 바로 쓸 수 있게 항목별로 간결히."

        # 1) Gemini 비전 (503/429 등 일시 오류 시 재시도)
        if self.gemini_client:
            try:
                from PIL import Image
                parts = [instruction]
                for p in valid:
                    try:
                        parts.append(Image.open(p))
                    except Exception:
                        continue
                if len(parts) > 1:
                    for attempt in range(3):
                        try:
                            response = await asyncio.to_thread(
                                self.gemini_client.models.generate_content,
                                model="gemini-2.5-flash",
                                contents=parts,
                            )
                            if response.text:
                                return response.text
                        except Exception as e:
                            msg = str(e)
                            print(f"[Soul] Gemini 비전 시도{attempt+1} 실패: {msg[:120]}")
                            if any(k in msg for k in ("503", "429", "UNAVAILABLE", "high demand", "overloaded")) and attempt < 2:
                                await asyncio.sleep(2.5 * (attempt + 1))
                                continue
                            break
            except Exception as e:
                print(f"[Soul] Gemini 비전 준비 실패: {e}")

        # 2) Claude 비전 폴백
        if self.claude_client:
            try:
                import base64
                blocks = []
                for p in valid:
                    ext = os.path.splitext(p)[1].lower()
                    media = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}.get(ext, "image/jpeg")
                    with open(p, "rb") as f:
                        b64 = base64.standard_b64encode(f.read()).decode("utf-8")
                    blocks.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}})
                blocks.append({"type": "text", "text": instruction})
                resp = await self.claude_client.messages.create(
                    model="claude-opus-4-8",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": blocks}],
                )
                txt = resp.content[0].text if resp.content else ""
                if txt:
                    print("[Soul] Claude 비전 폴백 성공")
                    return txt
            except Exception as e:
                print(f"[Soul] Claude 비전 폴백 실패: {e}")

        return ""

    async def generate_matjip_with_photos(self, source_data: str, image_paths: list, place_name: str = "",
                                          keyword: str = "", sub_keywords: list = None) -> str:
        """[맛집] 사진 + 리뷰를 한 모델에 함께 주고, 사진에 맞는 자리에 [이미지] 마커를 넣은
        방문 후기(카페글)를 한 번에 생성. 사진을 '직접 본 모델이 글도 쓰므로' 사진↔글이 정확히 맞는다.
        keyword=메인 키워드(제목·본문 SEO), sub_keywords=서브(연관) 키워드(본문에 자연스럽게 녹임).
        Claude(비전+작성) 우선 → 실패 시 Gemini(비전+작성) → 사진 없이 텍스트 생성 순 폴백."""
        import os
        # 폴더 사진을 최대한 활용(예: 17장). 사진마다 [이미지] 마커를 매칭해 본문에 분산 배치.
        MAX_MATJIP_PHOTOS = 20
        valid = [p for p in (image_paths or [])[:MAX_MATJIP_PHOTOS] if p and os.path.exists(p)]
        n = len(valid)
        place = (place_name or keyword or "맛집").strip()
        main_kw = (keyword or place_name or "").strip()
        subs = [s.strip() for s in (sub_keywords or []) if s and str(s).strip()][:5]
        kw_rule = ""
        if main_kw:
            kw_rule += f"- 메인 키워드 '{main_kw}'를 제목 앞쪽과 본문에 자연스럽게 포함(본문 최소 2~3회, 억지 반복 금지).\n"
        if subs:
            kw_rule += f"- 서브(연관) 키워드 [{', '.join(subs)}]를 본문에 자연스럽게 녹이세요(나열식 금지).\n"
        rules = (
            f"당신은 '{place}'을(를) 실제로 다녀온 손님입니다. 아래 [참고 리뷰]를 사실 근거로 "
            f"내돈내산 1인칭 방문 후기(네이버 카페용)를 자연스럽게 작성하세요.\n"
            + (f"사진이 {n}장 첨부돼 있습니다(순서대로 1~{n}번).\n"
               f"규칙:\n- 각 사진을 실제로 보고, 그 사진 내용을 이야기하는 문단 '바로 뒤'에 '[이미지]' 마커를 넣으세요. "
               f"총 {n}개, 첨부 사진 순서대로.\n" if n else "규칙:\n")
            + kw_rule
            + "- 소제목은 '■ 소제목' 형식. 마크다운(**, ~~) 금지, 이모지 3개 이하.\n"
              "- 800~1300자. 사진에 안 보이는 내용은 리뷰 근거로만.\n"
              "- 첫 줄은 '제목: ...' 형식으로 시작.\n\n"
            + f"[참고 리뷰]\n{source_data or ''}"
        )
        # 사진을 여러 장(최대 20) 보내므로 요청 크기·토큰이 커지지 않게 긴 변 1568px·JPEG로 다운스케일해 base64 인코딩.
        def _downscale_jpeg_b64(path, max_side=1568, quality=85):
            import io, base64
            from PIL import Image
            im = Image.open(path)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            w, h = im.size
            if max(w, h) > max_side:
                if w >= h:
                    im = im.resize((max_side, max(1, round(h * max_side / w))), Image.LANCZOS)
                else:
                    im = im.resize((max(1, round(w * max_side / h)), max_side), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=quality)
            return base64.standard_b64encode(buf.getvalue()).decode("utf-8")

        # 1) Claude 비전+작성 (한 번의 호출로 사진 보고 바로 작성)
        if self.claude_client and valid:
            try:
                blocks = []
                for p in valid:
                    try:
                        b64 = _downscale_jpeg_b64(p)
                    except Exception:
                        import base64
                        with open(p, "rb") as f:
                            b64 = base64.standard_b64encode(f.read()).decode("utf-8")
                    blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
                blocks.append({"type": "text", "text": rules})
                resp = await self.claude_client.messages.create(
                    model="claude-opus-4-8", max_tokens=6000,
                    messages=[{"role": "user", "content": blocks}])
                txt = resp.content[0].text if resp.content else ""
                if txt:
                    return txt
            except Exception as e:
                print(f"[Soul] 맛집 Claude 비전+작성 실패 → Gemini 폴백: {e}")
        # 2) Gemini 비전+작성 폴백
        if self.gemini_client and valid:
            try:
                from PIL import Image
                parts = [rules] + [Image.open(p) for p in valid]
                resp = await asyncio.to_thread(
                    self.gemini_client.models.generate_content, model="gemini-2.5-flash", contents=parts)
                if resp.text:
                    return resp.text
            except Exception as e:
                print(f"[Soul] 맛집 Gemini 비전+작성 실패: {e}")
        # 3) 사진 없이라도 텍스트 생성(폴백)
        return await self.generate_content(rules)

    async def generate_content(self, prompt: str) -> str:
        """자유 형식의 프롬프트를 처리. Gemini→Claude→OpenAI 순으로 폴백한다.
        (Gemini 레이트리밋·빈응답·안전필터로 한 provider가 실패해도 다음 provider로 이어가
        글감 수집/원고 생성이 끊기지 않도록 함.)"""
        attempts = [
            ("Gemini", self.gemini_client, self._call_gemini_client),
            ("Claude", self.claude_client, self._call_claude_client),
            ("OpenAI", self.openai_client, self._call_openai_client),
        ]
        errors = []
        for name, client, caller in attempts:
            if not client:
                continue
            try:
                return await caller(client, prompt)
            except Exception as e:
                errors.append(f"{name}: {e}")
                print(f"[Soul] {name} 생성 실패 → 다음 provider 폴백: {e}")
        if errors:
            raise RuntimeError("모든 AI provider 실패 (" + " | ".join(errors) + ")")
        raise RuntimeError("사용 가능한 AI 클라이언트가 없습니다. 설정에서 API 키를 저장해주세요.")

    # 세 메서드 모두 예외를 raise — 호출자(orchestrator)가 retry/폴백 결정.
    # 예외를 string으로 swallow하면 "Gemini Error: 401" 같은 텍스트가 그대로 블로그 본문이 됨.
    async def _call_gemini_client(self, client, prompt: str) -> str:
        # Run sync generate_content in a thread pool to avoid async event loop locks on Windows/Streamlit
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text
        if not text:
            # 안전필터 차단·빈 part 시 .text는 None → 호출자가 retry/폴백하도록 raise
            raise RuntimeError("Gemini가 빈 응답을 반환했습니다 (안전필터 차단 또는 빈 결과).")
        return text

    async def _call_claude_client(self, client, prompt: str) -> str:
        try:
            response = await client.messages.create(
                model="claude-opus-4-8",
                max_tokens=8000,  # 1,500자 이상 장문(한글)은 토큰 소모가 커서 2500이면 문장 중간에 잘림
                messages=[{"role": "user", "content": prompt}],
            )
            # 토큰 상한에 걸려 잘린 경우 경고 — 잘린 원고가 그대로 발행되는 것을 진단하기 위함
            if getattr(response, "stop_reason", None) == "max_tokens":
                print("[Soul] ⚠️ Claude 응답이 max_tokens 상한에 걸려 잘렸습니다. max_tokens 상향이 필요할 수 있습니다.")
            return response.content[0].text
        except Exception as e:
            raise e

    async def _call_openai_client(self, client, prompt: str) -> str:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    async def _dissect_ai_call(self, target_provider: str, prompt: str) -> str:
        """본문 해부(카페/블로그) 공용 AI 호출: 지정 provider 우선, 없으면 가용한 첫 클라이언트로 폴백."""
        if target_provider == "gemini" and self.gemini_client:
            return await self._call_gemini_client(self.gemini_client, prompt)
        if target_provider == "claude" and self.claude_client:
            return await self._call_claude_client(self.claude_client, prompt)
        if target_provider == "openai" and self.openai_client:
            return await self._call_openai_client(self.openai_client, prompt)
        # 지정 provider 클라이언트가 없으면 가용한 것으로 폴백
        if self.gemini_client:
            return await self._call_gemini_client(self.gemini_client, prompt)
        if self.claude_client:
            return await self._call_claude_client(self.claude_client, prompt)
        if self.openai_client:
            return await self._call_openai_client(self.openai_client, prompt)
        raise RuntimeError("사용 가능한 AI 클라이언트가 없습니다 (API 키 확인)")

    async def generate_cafe_post(
        self,
        main_keyword: str,
        sub_keywords: list,
        reference_text: str = "",
        post_style: str = "후기",
        provider: str = None
    ) -> str:
        """카페글 전용 생성"""
        target_provider = (provider or self.provider).lower()
        prompt = self._get_cafe_prompt(main_keyword, sub_keywords, reference_text, post_style)
        if target_provider == "gemini" and self.gemini_client:
            return await self._call_gemini_client(self.gemini_client, prompt)
        elif target_provider == "claude" and self.claude_client:
            return await self._call_claude_client(self.claude_client, prompt)
        elif target_provider == "openai" and self.openai_client:
            return await self._call_openai_client(self.openai_client, prompt)
        raise RuntimeError(f"{target_provider} 엔진 미설정 (API 키 확인)")

    def _get_cafe_prompt(self, main_keyword, sub_keywords, reference_text, post_style):
        sub_str = ", ".join(sub_keywords) if sub_keywords else "없음"
        style_map = {
            "후기": "실제 경험한 사람처럼 솔직하고 생생하게. 내돈내산 느낌, 장단점 포함.",
            "정보": "친절하고 상세하게 정보를 전달. 핵심을 먼저 말하고 부연 설명.",
            "추천": "열정적이고 설득력 있게. 추천 이유를 구체적으로.",
            "질문/토론": "카페 회원들과 소통하는 느낌으로. 경험 공유 + 의견 요청.",
        }
        style_guide = style_map.get(post_style, "자연스럽고 친근하게.")
        ref_part = f"\n\n[참고 분석 자료]\n{reference_text[:1500]}" if reference_text else ""

        lines = [
            "당신은 네이버 카페 활성 회원입니다. 아래 조건으로 카페 게시글을 작성해주세요.",
            "",
            "[작성 조건]",
            f"- 글 유형: {post_style} ({style_guide})",
            f"- 메인 키워드: {main_keyword} (제목과 본문에 자연스럽게, 최소 3회)",
            f"- 서브 키워드: {sub_str} (본문에 자연스럽게 분산 배치)",
            "- 분량: 600~1200자 (공백 포함)",
            "- 형식: 카페글 특유의 구어체, 줄바꿈 활용, 마크다운(별표, 물결표) 및 이모지 사용 금지",
            ref_part,
            "",
            "[출력 형식]",
            "제목: (메인키워드 포함 35자 이내 제목)",
            "",
            "---",
            "",
            "(본문 내용)",
        ]
        return "\n".join(lines)

    async def analyze_cafe_cheat_keys(self, keyword: str, text: str, provider: str = None) -> dict:
        """카페 상위노출 글의 4대 로직 + 작성자 영향력(5번) 분석 (JSON 리턴 보장)"""
        target_provider = (provider or self.provider).lower()
        
        prompt = f"""당신은 네이버 카페 알고리즘(RCON, SCQA, D.I.A+ 등)을 완벽하게 해부하는 국내 최고의 SEO 전문가이자 데이터 분석가입니다.
사용자가 제공한 [타겟 키워드]와 [카페 글 본문]을 바탕으로 아래 5가지 항목을 낱낱이 분석하여 **반드시 JSON 포맷**으로만 응답하세요. 마크다운 백틱(```json)이나 다른 설명은 절대 넣지 마세요.

[입력 데이터]
- 타겟 키워드: {keyword}
- 카페 글 본문:
{text[:4000]} # 토큰 제한 방지

[분석 기준 (5가지)]
1. rcon (제목 및 문맥 정합성 분석): 메인/서브 키워드가 서론에 어떻게 주입되었고, 사용자 의도(스마트블록 타겟)에 맞는지.
2. scqa (SCQA+MPC 프레임워크 분석): 서론에 상황-문제-질문-답변 구조가 있는지, 본문에 표/리스트/H태그가 구조적으로 쓰였는지.
3. dia (D.I.A+ 경험 데이터 분석): 작성자의 실제 1차 경험(오리지널리티)과 체류시간을 높이는 휴먼 터치가 어떻게 배치되었는지.
4. chain (커뮤니티 상호작용 및 Chain Score 분석): 글의 문맥이 회원들의 자연스러운 댓글 소통을 유도하도록(질문 던지기 등) 기획되었는지.
5. author_power (작성자 영향력 추정): 이 글의 서술 방식, 호응 유도 패턴, 전문성 깊이를 볼 때 이 작성자가 해당 카페에서 어느 정도의 네임드(활동 지수)를 가진 사람일지 추정(예: '단순 정보 공유 뉴비', '커뮤니티 여론 주도 핵심 멤버', '홍보 목적의 서브 계정' 등).

[출력 포맷 (반드시 아래 구조의 순수 JSON으로만 출력)]
{{
    "rcon": {{"score": 85, "title": "RCON 및 문맥 정합성", "analysis": "분석내용..."}},
    "scqa": {{"score": 90, "title": "SCQA+MPC 프레임워크", "analysis": "분석내용..."}},
    "dia": {{"score": 80, "title": "D.I.A+ 경험 데이터 지수", "analysis": "분석내용..."}},
    "chain": {{"score": 75, "title": "커뮤니티 소통(Chain) 로직", "analysis": "분석내용..."}},
    "author_power": {{"score": 88, "title": "작성자 영향력 (지수) 추정", "analysis": "분석내용..."}}
}}
"""
        
        try:
            result_text = await self._dissect_ai_call(target_provider, prompt)

            import json, re
            json_str = re.sub(r'```json\s*|```', '', result_text).strip()
            return json.loads(json_str)
        except Exception as e:
            # Fallback mock data in case of error
            return {
                "rcon": {"score": 0, "title": "RCON 및 문맥 정합성", "analysis": f"AI 분석 오류: {e}"},
                "scqa": {"score": 0, "title": "SCQA+MPC 프레임워크", "analysis": "분석 실패"},
                "dia": {"score": 0, "title": "D.I.A+ 경험 데이터 지수", "analysis": "분석 실패"},
                "chain": {"score": 0, "title": "커뮤니티 소통(Chain) 로직", "analysis": "분석 실패"},
                "author_power": {"score": 0, "title": "작성자 영향력 (지수) 추정", "analysis": "분석 실패"}
            }

    async def analyze_blog_seo_keys(self, keyword: str, text: str, provider: str = None) -> dict:
        """네이버 블로그 상위노출 글의 5대 로직 분석 (JSON 리턴 보장).
        카페 분석과 동일한 5개 키(rcon/scqa/dia/chain/author_power)를 쓰되,
        블로그(C-Rank·D.I.A+·이웃 상호작용) 관점으로 제목/분석을 채운다.
        → 프론트 카드 렌더(data.title 사용)는 카페와 동일 컴포넌트로 처리된다."""
        target_provider = (provider or self.provider).lower()

        prompt = f"""당신은 네이버 블로그 검색 알고리즘(C-Rank, D.I.A+, 스마트블록)을 완벽하게 해부하는 국내 최고의 블로그 SEO 전문가입니다.
사용자가 제공한 [타겟 키워드]와 [블로그 글 본문]을 바탕으로 아래 5가지 항목을 낱낱이 분석하여 **반드시 JSON 포맷**으로만 응답하세요. 마크다운 백틱(```json)이나 다른 설명은 절대 넣지 마세요.

[입력 데이터]
- 타겟 키워드: {keyword}
- 블로그 글 본문:
{text[:4000]} # 토큰 제한 방지

[분석 기준 (5가지)]
1. rcon (C-Rank·검색의도 정합성): 메인/서브 키워드가 제목과 서론에 자연스럽게 주입되었는지, 해당 키워드의 검색의도(정보형/후기형/구매형 스마트블록)에 본문 주제가 정확히 부합하는지.
2. scqa (본문 구조·가독성): 서론 후킹이 있는지, 소제목/리스트/표/이미지가 구조적으로 배치되어 가독성과 체류시간을 높이는지.
3. dia (D.I.A+ 경험·오리지널리티): 작성자의 실제 1차 경험(직접 촬영한 사진·실사용·방문)과 다른 글과 차별되는 오리지널리티, 체류시간을 높이는 휴먼 터치가 어떻게 배치되었는지.
4. chain (이웃·공감·댓글 유도): 글이 이웃·공감·댓글 등 블로그 내 자연스러운 상호작용(질문 던지기, 공감 유도)을 일으키도록 기획되었는지.
5. author_power (블로그 지수·작성자 신뢰도 추정): 이 글의 서술 방식, 전문성 깊이, 정보의 밀도를 볼 때 작성자의 블로그 지수 수준(예: '준최적화 생활 블로거', '해당 주제 전문 최적화 블로거', '협찬·홍보 위주 블로거' 등)과 주제 전문성을 추정.

[출력 포맷 (반드시 아래 구조의 순수 JSON으로만 출력)]
{{
    "rcon": {{"score": 85, "title": "C-Rank·검색의도 정합성", "analysis": "분석내용..."}},
    "scqa": {{"score": 90, "title": "본문 구조·가독성(체류시간)", "analysis": "분석내용..."}},
    "dia": {{"score": 80, "title": "D.I.A+ 경험·오리지널리티", "analysis": "분석내용..."}},
    "chain": {{"score": 75, "title": "이웃·공감·댓글 유도력", "analysis": "분석내용..."}},
    "author_power": {{"score": 88, "title": "블로그 지수·작성자 신뢰도 추정", "analysis": "분석내용..."}}
}}
"""

        try:
            result_text = await self._dissect_ai_call(target_provider, prompt)

            import json, re
            json_str = re.sub(r'```json\s*|```', '', result_text).strip()
            return json.loads(json_str)
        except Exception as e:
            return {
                "rcon": {"score": 0, "title": "C-Rank·검색의도 정합성", "analysis": f"AI 분석 오류: {e}"},
                "scqa": {"score": 0, "title": "본문 구조·가독성(체류시간)", "analysis": "분석 실패"},
                "dia": {"score": 0, "title": "D.I.A+ 경험·오리지널리티", "analysis": "분석 실패"},
                "chain": {"score": 0, "title": "이웃·공감·댓글 유도력", "analysis": "분석 실패"},
                "author_power": {"score": 0, "title": "블로그 지수·작성자 신뢰도 추정", "analysis": "분석 실패"},
            }

    async def generate_place_news(self, place_name: str, reviews: list, theme: str = "🌟 고객 극찬 릴레이 (방문 후기형)") -> dict:
        """
        플레이스 리뷰를 분석하여 스마트플레이스 새소식 원고와 클립 영상용 텍스트를 생성합니다.
        선택된 테마(theme)에 따라 프롬프트 조건을 다르게 적용합니다.
        """
        if not (self.claude_client or self.gemini_client or self.openai_client):
            return {"title": "소식 제목", "content": "AI 설정이 필요합니다.", "clip_texts": ["리뷰 분석", "소식"]}
            
        print(f"[SoulRewriter] '{place_name}' 리뷰 분석 및 소식 원고 생성 중... (테마: {theme})")
        reviews_text = "\n".join([f"- {r}" for r in reviews[:30]]) # Limit to 30 to avoid token limits
        
        # 테마에 따른 소재 가이드라인 (글 구조는 공통, 인용·포인트의 소재만 달라짐)
        theme_guide = ""
        if "고객 극찬" in theme:
            theme_guide = "인용할 리뷰는 맛·친절·만족감 등 '찐 반응' 위주로 고르고, 매장 포인트는 고객들이 가장 많이 칭찬한 한 가지를 꼽아 감사 인사와 함께 강조하세요."
        elif "차별점" in theme:
            theme_guide = "인용할 리뷰는 우리 매장만의 특별한 메뉴·시설·서비스가 언급된 것으로 고르고, 매장 포인트는 다른 곳에 없는 독보적 차별점 한 가지를 전문적으로 설명하세요."
        elif "베스트 포토" in theme:
            theme_guide = "인용할 리뷰는 비주얼·분위기·사진 관련 반응 위주로 고르고, 매장 포인트는 '사진 찍기 좋은 포인트' 한 가지를 감각적으로 묘사하세요."
        else:
            theme_guide = "고객들의 긍정 평가 중 가장 인상적인 것들을 골라 인용하고, 매장의 대표 강점 한 가지를 강조하세요."

        prompt = f"""
당신은 네이버 스마트플레이스 '새소식' 작성 전문가입니다. 사장님이 직접 쓰는 것처럼 씁니다.
다음은 우리 가게('{place_name}')를 방문한 고객들의 실제 최근 리뷰들입니다:

{reviews_text}

작성 컨셉: [{theme}]
{theme_guide}

[본문 구조 — 반드시 이 순서로]
1) 첫 줄 훅: 15자 내외로 시선을 끄는 한 문장 (질문형 또는 감탄형)
2) 리뷰 인용 2~3개: 리뷰를 그대로 복사하지 말고 자연스럽게 각색해 "~라는 후기를 남겨주셨어요"처럼 소개
3) 매장 포인트 1개: 위 컨셉에 맞는 우리 매장의 강점 한 가지를 구체적으로
4) 마무리 CTA: 방문·예약을 부드럽게 유도하는 한 문장 + 감사 인사

[작성 규칙]
- 분량: 본문 300~500자 (스마트플레이스 새소식 적정 길이)
- 어조: 사장님 1인칭 존댓말, 과장 없이 진솔하게
- 제목: 클릭하고 싶게, 이모지·특수기호 금지, 25자 이내
- 금지: 리뷰 원문 통째 복사(닉네임 등 개인정보 노출 금지), "최고·1위·유일·보장" 등 절대적 표현, 이모지 남발(본문 전체 3개 이하)

[클립 자막 — 15초 숏폼 영상 구조에 맞춰 정확히 5개]
- 1번: 오프닝 훅 (본문 첫 줄 훅과 같은 맥락, 12자 이내)
- 2~4번: 리뷰/강점 포인트 3개 (각 15자 이내)
- 5번: CTA (예: "지금 방문해보세요", 12자 이내)

[해시태그]
- 지역+업종, 대표메뉴, 분위기 등으로 5개 (# 포함, 공백 없이)

아래 JSON 형식으로만 응답해주세요:
{{
  "title": "소식 제목",
  "content": "본문 내용",
  "clip_texts": ["오프닝 훅", "포인트1", "포인트2", "포인트3", "CTA"],
  "hashtags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5"]
}}
"""
        try:
            # Claude 메인 → 없으면 Gemini/OpenAI 폴백
            result = await self._dissect_ai_call("claude", prompt)
            import json, re
            s = re.sub(r'```json\s*|```', '', result or '').strip()
            m = re.search(r'\{.*\}', s, re.DOTALL)   # 프로즈에 감싸여 와도 JSON 객체만 추출
            if m:
                s = m.group(0)
            data = json.loads(s)
            # 해시태그는 본문 끝에 붙여 저장/발행 흐름 어디서든 함께 노출되게 함
            tags = data.get("hashtags") or []
            if isinstance(tags, list) and tags:
                data["content"] = (data.get("content") or "").rstrip() + "\n\n" + " ".join(str(t) for t in tags)
            return data
        except Exception as e:
            print(f"[SoulRewriter] AI 소식 생성 실패: {e}")
            return {"title": "소식 업데이트", "content": f"{place_name}의 새로운 소식입니다.", "clip_texts": ["환영합니다", "감사합니다"]}

    # ══════════════════════════════════════════════════════════════════
    # 🎨 나노바나나(Gemini 이미지) 자동 생성
    #   1) generate_blog_image_prompts: 본문 → 영문 이미지 프롬프트 N개(JSON)
    #   2) generate_images: 프롬프트별 → PNG 저장(경로 리스트)
    # ══════════════════════════════════════════════════════════════════
    async def generate_blog_image_prompts(self, title: str, content: str, keyword: str,
                                          category: str = None, n: int = 5) -> List[str]:
        """블로그 본문을 바탕으로 나노바나나(Gemini 이미지)용 영문 프롬프트 N개를 생성.
        병원 카테고리는 의료 이미지 공식(실사/일러스트/상담)을 주입. JSON 배열로 파싱."""
        n = max(1, min(int(n or 5), 5))
        body = (content or "")[:4000]
        if (category or "").lower() == "hospital":
            style_guide = (
                "This is a MEDICAL (hospital) blog. Produce a 5-image set with these roles in order: "
                "1) HERO/thumbnail: a Korean patient (age/gender fitting the topic) expressing the symptom, "
                "with a translucent red circle graphic overlay on the affected area, bright clean background, photorealistic, trustworthy. "
                "2) ANATOMY/cause: a clean medical illustration of the relevant anatomy, soft pastel colors, white background, educational vector style. "
                "3) SELF-CARE/stretch: a Korean person demonstrating a safe stretch or management action, natural lighting, instructional photo. "
                "4) CONSULTATION: a Korean patient consulting a doctor in a white coat in a bright modern clinic, photorealistic. "
                "5) POSITIVE ENDING: a healthy Korean person doing a bright everyday activity, optimistic mood, photorealistic. "
                "Strictly: no text/letters/numbers/watermark rendered in the image, no blood or graphic wounds, "
                "no real celebrities, no brand logos, safe-for-work."
            )
        elif (category or "").lower() in ("product", "shopping", "product_scene"):
            style_guide = (
                "This is a PRODUCT REVIEW blog. Produce LIFESTYLE/CONTEXT staging images that set the mood and "
                "usage scene for the product CATEGORY — NOT a recreation of the specific branded product. "
                "Examples: the item in cozy daily use, a tasteful flat-lay on a wooden desk, warm interior scene, "
                "hands using it in natural daylight, magazine editorial mood, soft shadows, inviting warm tone. "
                "Do NOT recreate the exact branded product, packaging, or logos; keep any product shape generic/blurred. "
                "Strictly: no text/letters/numbers/watermark, no brand logos, no identifiable real faces in focus, safe-for-work."
            )
        else:
            style_guide = (
                "Produce photorealistic, clean, blog-friendly images, one matching each major section of the post. "
                "Strictly: no text/letters/numbers/watermark rendered in the image, no brand logos, "
                "no identifiable real people/celebrities, safe-for-work."
            )
        prompt = f"""You are an art director writing prompts for an AI image generator (Google "nano banana" / Gemini image model).
Blog topic keyword: "{keyword}"
Blog title: {title}
Blog body (Korean, for context only):
\"\"\"{body}\"\"\"

{style_guide}

Rules for each prompt:
- One self-contained English paragraph, 30-60 words, describing a concrete scene (subject, action, setting, lighting, style).
- End every prompt with: "no text, no watermark, high quality."
- Do not number the prompts inside their text.

Return ONLY a JSON array of exactly {n} strings and nothing else.
Example: ["a photorealistic ... no text, no watermark, high quality.", "..."]"""
        raw = await self._dissect_ai_call("claude", prompt)
        import json, re
        s = re.sub(r'```json\s*|```', '', raw or '').strip()
        m = re.search(r'\[.*\]', s, re.DOTALL)
        if m:
            s = m.group(0)
        prompts: List[str] = []
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                prompts = [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            # 파싱 실패 시 줄 단위 폴백(30자 이상 라인만)
            for ln in (raw or "").splitlines():
                ln = ln.strip().strip('-"').strip()
                if len(ln) > 30:
                    prompts.append(ln)
        return prompts[:n]

    async def generate_images(self, prompts: List[str], out_dir: str,
                              filename_prefix: str = "ai_img") -> List[str]:
        """나노바나나(gemini-2.5-flash-image)로 프롬프트별 이미지를 생성해 PNG로 저장, 경로 리스트 반환.
        Gemini 클라이언트가 없거나(키 없음) part가 비면 해당 이미지는 건너뜀(예외 대신 부분 성공)."""
        if not self.gemini_client or not genai:
            print("[SoulRewriter] 이미지 생성 불가: Gemini 클라이언트 없음(GEMINI_API_KEY 확인)")
            return []
        os.makedirs(out_dir, exist_ok=True)
        paths: List[str] = []
        for idx, p in enumerate(prompts):
            if not p or not p.strip():
                continue
            try:
                resp = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model="gemini-2.5-flash-image",
                    contents=[p],
                )
                saved = None
                cand = (resp.candidates or [None])[0]
                if cand and cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        inline = getattr(part, "inline_data", None)
                        if inline and inline.data:
                            fp = os.path.join(out_dir, f"{filename_prefix}_{idx+1}.png")
                            with open(fp, "wb") as f:
                                f.write(inline.data)
                            saved = fp
                            break
                if saved:
                    paths.append(saved)
                    print(f"[SoulRewriter] 이미지 생성 {idx+1}/{len(prompts)} → {saved}")
                else:
                    print(f"[SoulRewriter] 이미지 part 없음 (프롬프트 {idx+1}, 안전필터 가능성)")
            except Exception as e:
                print(f"[SoulRewriter] 이미지 생성 실패 {idx+1}: {e}")
        return paths
