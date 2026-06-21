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
        # 1. Gemini Init (New SDK)
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        if genai and self.gemini_key:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
        else:
            self.gemini_client = None

        # 2. Claude Init
        self.claude_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic and self.claude_key:
            self.claude_client = anthropic.AsyncAnthropic(api_key=self.claude_key)
        else:
            self.claude_client = None

        # 3. OpenAI Init
        self.openai_key = os.getenv("OPENAI_API_KEY")
        if openai and self.openai_key:
            self.openai_client = openai.AsyncOpenAI(api_key=self.openai_key)
        else:
            self.openai_client = None

    async def rewrite_for_blog(self, raw_data: str, keyword: str, provider: str = None,
                               post_purpose: str = None, promo_type: str = None, distribution_mode: str = None, api_key: str = None,
                               prompt_category: str = None) -> str:
        target_provider = (provider or self.provider).lower()
        prompt = self._get_blog_prompt(target_provider, raw_data, keyword, post_purpose, promo_type, distribution_mode, prompt_category)

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

    def _get_blog_prompt(self, target_provider, raw_data, keyword, post_purpose=None, promo_type=None, distribution_mode=None, prompt_category=None):
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
        # prompts.json 은 mbam_nextgen/ 아래에 있음 (settings.py 저장 경로와 일치시켜야 커스텀 프롬프트가 적용됨)
        prompts_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts.json")
        if os.path.exists(prompts_path):
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
            return custom_prompt.replace("{keyword}", str(keyword)).replace("{raw_data}", str(raw_data)).replace("{combined_text}", str(raw_data)).replace("{tone_guide}", str(tone_guide)).replace("{length_guide}", str(length_guide)).replace("{special_guide}", str(special_guide))
        
        # 기본 프롬프트에 첨부파일이 있다면 추가

        return f"""
        당신은 네이버 블로그 전문 파워블로거이자 마케팅 전문가입니다.
        아래의 정보를 바탕으로 블로그 포스팅 원고를 작성해주세요.

        [기본 정보]
        - 타겟(핵심) 키워드: {keyword}
        - 참고 데이터: {raw_data}

        [작성 가이드라인]
        1. 어조: {tone_guide}
        2. 분량 및 구조: {length_guide}
        3. 마크다운 기호 금지: 별표(*), 물결표(~), 샵(#) 등 마크다운 기호를 절대 사용하지 마세요. (단, 해시태그에는 샵 허용)
        4. 이모지 금지: 글에 어떠한 이모지(아이콘)도 절대 사용하지 마세요.
        5. 이미지 삽입 위치 지정: 내용이 전환되거나 문단이 끝나는 적절한 위치(본문 사이사이)에 `[이미지]` 라는 특수 태그를 3~5회 정도 삽입하세요.
        6. 해시태그 추가: 본문 작성이 모두 끝난 후, 맨 마지막 줄에는 이 글과 관련된 검색용 해시태그를 5개 내외로 작성해 주세요. (예: `#해시태그1 #해시태그2`)
        {special_guide}
        {ref_injection}
        
        첫 줄에 반드시 '[제목] 클릭하고 싶어지는 매력적인 제목' 형식으로 제목을 작성하고, 그 다음 줄부터 본문을 작성해주세요.
        """

    async def generate_content(self, prompt: str) -> str:
        """자유 형식의 프롬프트를 처리 (가용한 첫 번째 AI 사용)"""
        if self.gemini_client:
            return await self._call_gemini_client(self.gemini_client, prompt)
        elif self.claude_client:
            return await self._call_claude_client(self.claude_client, prompt)
        elif self.openai_client:
            return await self._call_openai_client(self.openai_client, prompt)
        raise RuntimeError("사용 가능한 AI 클라이언트가 없습니다. 환경변수(.env)에 API 키를 설정해주세요.")

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
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            raise e

    async def _call_openai_client(self, client, prompt: str) -> str:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

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
            if target_provider == "gemini" and self.gemini_client:
                result_text = await self._call_gemini(prompt)
            elif target_provider == "claude" and self.claude_client:
                result_text = await self._call_claude(prompt)
            elif target_provider == "openai" and self.openai_client:
                result_text = await self._call_openai(prompt)
            else:
                result_text = await self._call_gemini(prompt) # fallback
            
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

    async def generate_place_news(self, place_name: str, reviews: list, theme: str = "🌟 고객 극찬 릴레이 (방문 후기형)") -> dict:
        """
        플레이스 리뷰를 분석하여 스마트플레이스 새소식 원고와 클립 영상용 텍스트를 생성합니다.
        선택된 테마(theme)에 따라 프롬프트 조건을 다르게 적용합니다.
        """
        if not self.gemini_client:
            return {"title": "소식 제목", "content": "AI 설정이 필요합니다.", "clip_texts": ["리뷰 분석", "소식"]}
            
        print(f"[SoulRewriter] '{place_name}' 리뷰 분석 및 소식 원고 생성 중... (테마: {theme})")
        reviews_text = "\n".join([f"- {r}" for r in reviews[:30]]) # Limit to 30 to avoid token limits
        
        # 테마에 따른 추가 프롬프트 가이드라인
        theme_guide = ""
        if "고객 극찬" in theme:
            theme_guide = "리뷰에 나타난 고객들의 찐 반응과 칭찬(맛, 친절도 등)을 집중적으로 어필하고, 고객들에게 감사함을 표하는 감동적인 후기 위주로 작성하세요."
        elif "차별점" in theme:
            theme_guide = "리뷰에서 언급된 우리 매장만의 특별한 메뉴, 시설, 서비스 등 독보적인 차별 포인트를 찾아내어 전문적이고 자랑스럽게 강조하는 글로 작성하세요."
        elif "베스트 포토" in theme:
            theme_guide = "고객들이 예쁘게 찍어준 사진이나 시각적 매력, 분위기 등을 상상하며 감각적이고 트렌디하게 묘사하는 글로 작성하세요. 사진 찍기 좋은 곳이라는 점을 강조하세요."
        else:
            theme_guide = "고객들의 긍정적인 평가를 종합하여 매력적인 소개 글로 작성하세요."
            
        prompt = f"""
당신은 네이버 스마트플레이스 마케팅 전문가입니다.
다음은 우리 가게('{place_name}')를 방문한 고객들의 실제 최근 리뷰들입니다:

{reviews_text}

이 리뷰들을 분석하여 작성할 글의 컨셉은 다음과 같습니다:
[{theme}]
{theme_guide}

[작성 조건]
1. 제목은 클릭하고 싶게 만들 것. (이모지 및 특수기호 사용 금지)
2. 본문은 정해진 테마({theme})에 맞춰서, 리뷰 내용을 자연스럽게 언급하며 친근한 톤으로 작성할 것.
3. 클립 숏폼 영상에 들어갈 짧은 자막 텍스트 5개(각 15자 이내)를 추출할 것.

아래 JSON 형식으로만 응답해주세요:
{{
  "title": "소식 제목",
  "content": "본문 내용",
  "clip_texts": ["자막1", "자막2", "자막3", "자막4", "자막5"]
}}
"""
        try:
            result = await self._call_gemini(prompt)
            import json, re
            json_str = re.sub(r'```json\s*|```', '', result).strip()
            data = json.loads(json_str)
            return data
        except Exception as e:
            print(f"[SoulRewriter] AI 소식 생성 실패: {e}")
            return {"title": "소식 업데이트", "content": f"{place_name}의 새로운 소식입니다.", "clip_texts": ["환영합니다", "감사합니다"]}
