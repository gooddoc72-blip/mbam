import aiohttp
import asyncio
import re
import json
import base64
from bs4 import BeautifulSoup

def replace_seo_analyzer():
    old_content = open('mbam_nextgen/services/seo_analyzer.py', encoding='utf-8').read()
    
    new_func = """    async def analyze_multiple_urls(self, urls: list) -> dict:
        \"\"\"네이버 블로그/카페 URL을 병렬(동시) 수집 및 분석 (API 기반 고속 통신)\"\"\"
        import aiohttp
        from bs4 import BeautifulSoup
        import asyncio
        import re
        import json
        import base64
        
        results = {}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://search.naver.com/"
        }

        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as session:
            semaphore = asyncio.Semaphore(5)
            
            async def process_url(raw_url):
                async with semaphore:
                    try:
                        url = raw_url
                        
                        # 리다이렉트 추적 (in.naver.com 등 단축/리다이렉트 URL 대비)
                        if "in.naver.com" in url or "naver.me" in url:
                            try:
                                async with session.get(url, allow_redirects=True) as r:
                                    url = str(r.url)
                            except Exception:
                                pass

                        is_cafe = "cafe.naver.com" in url
                        is_blog = "blog.naver.com" in url
                        blog_id = "미상"
                        
                        raw_text = ""
                        html_source = ""
                        title_str = "제목 없음"
                        
                        if is_blog:
                            match = re.search(r'blog\.naver\.com/([^/]+)/(\d+)', url)
                            if not match:
                                query_match = re.search(r'blogId=([^&]+).*logNo=(\d+)', url)
                                if query_match:
                                    blog_id, log_no = query_match.group(1), query_match.group(2)
                                else:
                                    return raw_url, {"error": "블로그 메인(홈) 주소입니다. 개별 포스팅 주소가 필요합니다."}
                            else:
                                blog_id, log_no = match.group(1), match.group(2)
                                
                            post_view_url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
                            async with session.get(post_view_url) as resp:
                                if resp.status != 200:
                                    return raw_url, {"error": f"블로그 본문을 가져올 수 없습니다. (상태코드: {resp.status})"}
                                html = await resp.text()
                                if "해당 블로그가 비공개 상태이거나" in html or "존재하지 않는" in html:
                                    return raw_url, {"error": "비공개이거나 삭제된 게시글입니다."}
                                
                                html_source = html
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # 블로그 제목 추출
                                title_el = soup.select_one('.se-title-text, .pcol1, .se_title, head > title')
                                if title_el:
                                    title_str = title_el.get_text(strip=True).replace(' : 네이버 블로그', '')
                                
                                content_div = soup.select_one('.se-main-container, #postViewArea')
                                if not content_div:
                                    return raw_url, {"error": "본문 영역(.se-main-container)을 찾을 수 없습니다."}
                                raw_text = content_div.get_text(separator='\\n', strip=True)
                                
                        elif is_cafe:
                            club_id = None
                            article_id = None
                            
                            art_match = re.search(r'art=[^.]+\\.[^.]+\\.([^.]+)', url)
                            if art_match:
                                payload = art_match.group(1)
                                payload += '=' * (-len(payload) % 4)
                                try:
                                    data = json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
                                    article_id = data.get('articleId')
                                except Exception:
                                    try:
                                        data = json.loads(base64.b64decode(payload).decode('utf-8'))
                                        article_id = data.get('articleId')
                                    except Exception:
                                        pass
                                    
                            if not article_id:
                                cafe_match = re.search(r'/cafes/(\\d+)/articles/(\\d+)', url)
                                if cafe_match:
                                    club_id, article_id = cafe_match.group(1), cafe_match.group(2)
                                else:
                                    aid_match = re.search(r'articleid=(\\d+)', url.lower()) or re.search(r'/(\\d+)$', url)
                                    cid_match = re.search(r'clubid=(\\d+)', url.lower())
                                    if aid_match: article_id = aid_match.group(1)
                                    if cid_match: club_id = cid_match.group(1)
                            
                            if not club_id and article_id:
                                async with session.get(url) as resp:
                                    redirect_html = await resp.text()
                                    cid_match = re.search(r'clubid=(\\d+)', redirect_html.lower())
                                    if cid_match:
                                        club_id = cid_match.group(1)
                                        
                            if not club_id or not article_id:
                                return raw_url, {"error": "카페 게시글의 clubid 또는 articleid를 추출할 수 없습니다."}
                                
                            api_url = f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{club_id}/articles/{article_id}"
                            async with session.get(api_url) as resp:
                                if resp.status != 200:
                                    return raw_url, {"error": f"카페 본문을 가져올 수 없습니다. (상태코드: {resp.status})"}
                                api_data = await resp.json()
                                if 'article' not in api_data.get('result', {}):
                                    return raw_url, {"error": api_data.get('result', {}).get('reason', '비공개이거나 삭제된 게시글입니다.')}
                                
                                article_data = api_data['result']['article']
                                title_str = article_data.get('subject', '제목 없음')
                                html_source = article_data.get('contentHtml', '')
                                
                                soup = BeautifulSoup(html_source, 'html.parser')
                                raw_text = soup.get_text(separator='\\n', strip=True)
                                
                                member_key = article_data.get('writer', {}).get('memberKey')
                                if member_key:
                                    blog_id = member_key
                                    
                        else:
                            return raw_url, {"error": "지원되지 않는 URL 형식입니다. (네이버 블로그/카페만 지원)"}
                            
                        if not raw_text:
                            return raw_url, {"error": "본문 내용이 비어있습니다."}
                            
                        cleaned_text = self.clean_text(raw_text)
                        rule_props = self.extract_rule_based_properties(cleaned_text)
                        
                        soup = BeautifulSoup(html_source, 'html.parser')
                        img_count = len(soup.find_all('img'))
                        link_count = len(soup.find_all('a'))
                        table_count = len(soup.find_all('table'))
                        h_tag_count = len(soup.find_all(['h2', 'h3', 'h4']))
                        
                        total_char = len(cleaned_text)
                        char_count = len(cleaned_text.replace(" ", ""))
                        space_count = cleaned_text.count(" ")
                        sentence_count = len(re.findall(r'[.!?]+', cleaned_text)) or 1
                        ko_char = len(re.findall(r'[가-힣]', cleaned_text))
                        en_char = len(re.findall(r'[A-Za-z]', cleaned_text))
                        num_char = len(re.findall(r'\\d', cleaned_text))
                        
                        if len(cleaned_text) < 50:
                            return raw_url, {"error": "본문이 너무 짧습니다."}
                            
                        cafe_author_info = {}
                        if is_cafe:
                            cafe_author_info = {'club_id': club_id, 'member_hash': blog_id}
                            
                        blog_info = {}
                        if blog_id and blog_id != "미상" and not is_cafe:
                            blog_info = await self.fetch_blog_stats_by_id(blog_id)
                            
                        return raw_url, {
                            "blog_id": blog_id,
                            "blog_info": blog_info,
                            "cafe_author_info": cafe_author_info,
                            "title": title_str,
                            "char_count": char_count,
                            "total_char": total_char,
                            "space_count": space_count,
                            "img_count": img_count,
                            "link_count": link_count,
                            "table_count": table_count,
                            "h_tag_count": h_tag_count,
                            "sentence_count": sentence_count,
                            "ko_char": ko_char,
                            "en_char": en_char,
                            "num_char": num_char,
                            "rule_properties": rule_props,
                            "text_sample": cleaned_text[:200] + "...",
                            "full_text": cleaned_text,
                            "top_keywords": [],
                            "main_keyword": "",
                            "sub_keywords": [],
                            "text_type": "네이버 카페" if is_cafe else "네이버 블로그",
                            "type_color": "#7c3aed" if is_cafe else "#16a34a",
                            "source": "네이버 카페" if is_cafe else "네이버 블로그",
                        }
                    except Exception as e:
                        return raw_url, {"error": f"분석 중 오류: {str(e)}"}

            tasks = [process_url(u) for u in urls]
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in completed:
                if isinstance(res, Exception):
                    continue
                raw_url, result = res
                results[raw_url] = result
                
        return results"""

    pattern = re.compile(r'    async def analyze_multiple_urls\(self, urls: list\) -> dict:.*?        return results\n', re.DOTALL)
    if pattern.search(old_content):
        replaced_content = pattern.sub(lambda m: new_func + '\n', old_content)
        with open('mbam_nextgen/services/seo_analyzer.py', 'w', encoding='utf-8') as f:
            f.write(replaced_content)
        print('SUCCESSFULLY REPLACED!')
    else:
        print('COULD NOT FIND PATTERN')

if __name__ == "__main__":
    replace_seo_analyzer()
