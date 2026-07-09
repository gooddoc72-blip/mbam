import os
import time
import glob
import socket
import pandas as pd
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.driver_cache import DriverCacheManager
from history_manager import HistoryManager


def _find_cached_chromedriver():
    """이전에 받아둔 chromedriver 실행파일을 로컬 캐시(~/.wdm)에서 찾는다."""
    pattern = os.path.join(
        os.path.expanduser("~"), ".wdm", "drivers", "chromedriver",
        "**", "chromedriver*",
    )
    candidates = [
        p for p in glob.glob(pattern, recursive=True)
        if p.lower().endswith("chromedriver.exe") or os.path.basename(p) == "chromedriver"
    ]
    # 최신 버전 폴더가 가장 마지막에 오도록 정렬
    candidates.sort()
    return candidates[-1] if candidates else None


def resolve_driver_path(log=print):
    """크롬 드라이버 경로를 확보한다.

    핵심: 로컬에 이미 받아둔 드라이버가 있으면 네트워크를 아예 타지 않는다.
    (webdriver-manager는 캐시가 있어도 googlechromelabs.github.io 에서
     '크롬 버전→드라이버 버전' 매핑을 조회하려다 이 호스트에서 타임아웃이 나기 때문)
    로컬에 아무 드라이버도 없을 때만 네트워크로 최초 1회 다운로드한다.
    """
    # 1) 로컬 캐시에 드라이버가 있으면 네트워크 없이 즉시 사용 (타임아웃 원천 차단)
    cached = _find_cached_chromedriver()
    if cached:
        log("기존에 받아둔 크롬 드라이버를 사용합니다. (네트워크 확인 생략)")
        return cached

    # 2) 로컬에 없을 때만 네트워크로 다운로드 (타임아웃 30초 + 3회 재시도)
    cache_manager = DriverCacheManager(valid_range=365)
    prev_timeout = socket.getdefaulttimeout()
    for attempt in range(1, 4):
        try:
            socket.setdefaulttimeout(30)
            path = ChromeDriverManager(cache_manager=cache_manager).install()
            log("크롬 드라이버 다운로드 완료.")
            return path
        except Exception as e:
            log(f"크롬 드라이버 다운로드 재시도 {attempt}/3 중... ({e})")
            time.sleep(2)
        finally:
            socket.setdefaulttimeout(prev_timeout)

    # 3) 재시도 중 일부라도 받아졌으면 그 캐시를 사용
    cached = _find_cached_chromedriver()
    if cached:
        log("네트워크가 불안정하여, 이전에 받아둔 드라이버로 실행합니다.")
        return cached

    # 4) 캐시도 없으면 uc 내장 다운로더에 맡긴다(경로 None)
    log("드라이버 자동 준비에 실패했습니다. 내장 다운로더로 시도합니다. (인터넷 연결을 확인하세요)")
    return None
class CrawlerEngine:
    def __init__(self, log_callback=None):
        self.log = log_callback if log_callback else print
        self.results = []
        self.is_running = False
        self.driver = None
        self.history_manager = HistoryManager()

    def stop(self):
        self.is_running = False
        # 브라우저를 즉시 강제종료하면 백업 로직이 실행되지 못하고 에러로 튕깁니다.
        # 따라서 플래그만 False로 변경하여, 반복문이 안전하게 체크포인트를 저장하고 
        # 스스로 브라우저를 닫도록 유도합니다.

    def crawl_naver_place(self, keywords, use_ip_change=False, resume_checkpoint=None, max_pages=1):
        self.is_running = True
        self.results = resume_checkpoint.get("results", []) if resume_checkpoint else []
        
        try:
            options = uc.ChromeOptions()
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            # 드라이버 확보(캐시 우선 + 재시도 + 오프라인 폴백)
            driver_path = resolve_driver_path(self.log)

            # 다운로드된 올바른 드라이버 경로를 undetected-chromedriver에 주입 (강제 패치)
            # 쿠팡에서도 동일하게 적용
            self.driver = uc.Chrome(options=options, driver_executable_path=driver_path)
            self.driver.set_page_load_timeout(30)
            wait = WebDriverWait(self.driver, 10)

            for idx, keyword in enumerate(keywords):
                if not self.is_running:
                    return
                    
                # 작업 인덱스 저장
                from checkpoint_manager import CheckpointManager
                CheckpointManager.save_checkpoint("place", keywords, idx, position=0, results=self.results)
                    
                if use_ip_change and idx > 0:
                    self.log(f"[{keyword}] 검색 전 IP 변경 대기 중...")
                    import ip_changer
                    ip_changer.toggle_airplane_mode(log=self.log)

                self.log(f"[{keyword}] 네이버 플레이스 검색 중...")
                
                try:
                    self.log("로봇 탐지 방어를 위해 사람처럼 검색창에 타이핑을 시도합니다...")
                    import random
                    from selenium.webdriver.common.keys import Keys
                    
                    self.driver.get("https://map.naver.com/p/")
                    time.sleep(3)
                    try:
                        search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.input_search")))
                        search_box.clear()
                        for char in keyword:
                            search_box.send_keys(char)
                            time.sleep(random.uniform(0.1, 0.2))
                        time.sleep(0.5)
                        search_box.send_keys(Keys.ENTER)
                        time.sleep(4)
                    except Exception as e:
                        self.log(f"검색창 입력 실패, 기존 주소창 방식으로 우회합니다: {e}")
                        self.driver.get(f"https://map.naver.com/p/search/{keyword}")
                        time.sleep(4) # 로딩 대기
                    
                    # IP 차단 및 CAPTCHA 감지
                    current_url = self.driver.current_url
                    page_source = self.driver.page_source
                    if "nid.naver.com" in current_url or "captcha" in current_url.lower() or "보안절차" in page_source or "robot" in page_source.lower():
                        self.log("⚠️ 네이버에 의해 IP 차단 또는 보안 절차(CAPTCHA)가 감지되었습니다. 작업을 중단하고 현재 시점을 저장합니다.")
                        from checkpoint_manager import CheckpointManager
                        CheckpointManager.save_checkpoint("place", keywords, idx, position=collected if 'collected' in locals() else 0, results=self.results)
                        self.is_running = False
                        return
                    
                    # searchIframe으로 이동
                    try:
                        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe")))
                    except:
                        self.log("검색 목록 프레임을 찾을 수 없습니다. (구조 변경 의심)")
                        continue
                        
                    # 아이템 리스트 찾기
                    items = self.driver.find_elements(By.CSS_SELECTOR, "li.VLTHu, li.tzwk0, li.UEzoS, li.YwYLL, li.hYhmy")
                    if not items:
                        items = self.driver.find_elements(By.XPATH, "//li[descendant::*[contains(@class, 'place_bluelink') or contains(@class, 'TYaxT') or contains(@class, 'title')]]")
                    count = len(items)
                    
                    if count == 0:
                        self.log(f"[{keyword}] 검색 결과가 없습니다.")
                        self.driver.switch_to.default_content()
                        continue
                        
                    self.log(f"[{keyword}] {count}개의 검색 결과를 찾았습니다. 상세 수집을 시작합니다.")
                    page_limit = max_pages * 50 # 페이지 당 대략 50개 아이템
                    self.log(f"[{keyword}] 설정된 최대 {max_pages}페이지(약 {page_limit}개) 단위로 수집 및 체크포인트를 설정합니다.")

                    collected = 0
                    i = 0
                    if resume_checkpoint and idx == 0:
                        target_skip = resume_checkpoint.get("position", 0)
                        if target_skip > 0:
                            self.log(f"[{keyword}] 이전 작업에서 {target_skip}개의 아이템을 수집했습니다. 중복을 방지하기 위해 해당 위치로 스크롤하여 직행합니다...")
                            collected = target_skip
                            i = target_skip
                    
                    while collected < page_limit:
                        if not self.is_running:
                            from checkpoint_manager import CheckpointManager
                            self.log(f"[{keyword}] 수집 중지됨. 현재 위치({collected}개)를 저장합니다.")
                            CheckpointManager.save_checkpoint("place", keywords, idx, position=collected, results=self.results)
                            return
                            
                        # 아이템 다시 찾기 (Stale Element 방지)
                        items = self.driver.find_elements(By.CSS_SELECTOR, "li.VLTHu, li.tzwk0, li.UEzoS, li.YwYLL, li.hYhmy")
                        if not items:
                            items = self.driver.find_elements(By.XPATH, "//li[descendant::*[contains(@class, 'place_bluelink') or contains(@class, 'TYaxT') or contains(@class, 'title')]]")
                        
                        if i >= len(items):
                            # 아이템이 모자라면 스크롤을 내려서 추가 로드 시도
                            if items:
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", items[-1])
                                time.sleep(1.5)
                                new_items = self.driver.find_elements(By.CSS_SELECTOR, "li.VLTHu, li.tzwk0, li.UEzoS, li.YwYLL, li.hYhmy")
                                if not new_items:
                                    new_items = self.driver.find_elements(By.XPATH, "//li[descendant::*[contains(@class, 'place_bluelink') or contains(@class, 'TYaxT') or contains(@class, 'title')]]")
                                if len(new_items) == len(items):
                                    break # 더 이상 로드 안됨
                                items = new_items
                            else:
                                break
                                
                        item = items[i]
                        i += 1
                        
                        # 리스트에서 가게 클릭
                        try:
                            try:
                                # 아이템 내부에서 확실한 제목 텍스트나 링크를 찾음 (의원/병원용 클래스 추가)
                                click_target = item.find_element(By.CSS_SELECTOR, ".place_bluelink, .TYaxT, .YwYLL, .YwYbM, span[class^='title'], div[class^='title']")
                            except:
                                try:
                                    click_target = item.find_element(By.CSS_SELECTOR, "a")
                                except:
                                    click_target = item # 못 찾으면 전체 item을 클릭
                                
                            place_name = click_target.text.strip()
                            if not place_name:
                                place_name = "Unknown"
                            unique_id = f"naver_place_{keyword}_{place_name}"
                            
                            # 중복 스킵 로직
                            if self.history_manager.is_collected(unique_id):
                                continue
                                
                            # 스크롤해서 화면 중앙에 오게 하기
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", click_target)
                            time.sleep(1.0)
                            
                            # 일반적인 클릭 우선 시도 (React 이벤트 정상 트리거용), 실패시 JS 클릭
                            try:
                                click_target.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", click_target)
                                
                            # 상세 프레임이 열릴 때까지 여유있게 대기
                            time.sleep(1.5)
                        except Exception as e:
                            self.log(f"[{i}번째] 클릭 오류: {e}")
                            continue
                                
                        # 상세 프레임으로 전환
                        self.driver.switch_to.default_content()
                        try:
                            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "entryIframe")))
                        except:
                            self.log(f"[{i}번째] 상세 정보 프레임을 찾을 수 없습니다.")
                            self.driver.switch_to.default_content()
                            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe")))
                            continue
                            
                        # "홈" 탭으로 강제 이동 (사진 탭 등으로 잘못 들어간 경우 방지)
                        try:
                            time.sleep(0.5)
                            home_tab = self.driver.find_element(By.XPATH, "//a[@role='tab' and .//span[text()='홈']]")
                            self.driver.execute_script("arguments[0].click();", home_tab)
                            time.sleep(1) # 탭 전환 후 렌더링 대기
                        except:
                            pass

                        data = {
                            "키워드": keyword, 
                            "수집시간": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "상호명": "N/A",
                            "대표키워드": "N/A",
                            "업종": "N/A",
                            "업체 주소": "N/A",
                            "안심번호": "N/A",
                            "홈페이지": "N/A",
                            "SNS": "N/A",
                            "이메일": "N/A",
                            "방문자리뷰수": "N/A",
                            "블로그 리뷰수": "N/A",
                            "고유번호": "N/A",
                            "플레이스URL": "N/A",
                            "소개내용": "N/A"
                        }
                        
                        # 1. 가장 완벽한 추출법: Apollo State (내부 데이터베이스) 직접 파싱
                        try:
                            # SPA 렌더링 및 데이터베이스 로드를 위한 능동적 대기 (최대 8초)
                            apollo_json_str = None
                            for _ in range(16):
                                apollo_json_str = self.driver.execute_script("return window.__APOLLO_STATE__ ? JSON.stringify(window.__APOLLO_STATE__) : null;")
                                if apollo_json_str and "PlaceDetailBase:" in apollo_json_str:
                                    break
                                time.sleep(0.5)
                                
                            if apollo_json_str:
                                import json
                                apollo_state = json.loads(apollo_json_str)
                                
                                place_base = None
                                for key, val in apollo_state.items():
                                    if key.startswith("PlaceDetailBase:"):
                                        place_base = val
                                        break
                                        
                                if place_base:
                                    data["상호명"] = place_base.get("name", "N/A")
                                    data["업종"] = place_base.get("category", "N/A")
                                    
                                    # 대표키워드 (MicroReviews 활용 또는 keywords 필드)
                                    keywords_list = place_base.get("keywords", [])
                                    if not keywords_list:
                                        if place_base.get("microReviews"):
                                            data["대표키워드"] = ", ".join(place_base["microReviews"])
                                    elif place_base.get("keywords"):
                                        data["대표키워드"] = ", ".join(place_base["keywords"])
                                    
                                    desc = place_base.get("description")
                                    if not desc:
                                        root_query = apollo_state.get("ROOT_QUERY", {})
                                        root_query_detail = {}
                                        for k, v in root_query.items():
                                            if k.startswith("placeDetail") and isinstance(v, dict):
                                                root_query_detail = v
                                                break
                                        for k, v in root_query_detail.items():
                                            if isinstance(k, str) and k.startswith("description"):
                                                desc = v
                                                break
                                    data["소개내용"] = desc if desc else "N/A"
                                    
                                    # 주소 (도로명 우선, 없으면 지번)
                                    road = place_base.get("roadAddress", "")
                                    jibun = place_base.get("address", "")
                                    data["업체 주소"] = road if road else jibun if jibun else "N/A"
                                    
                                    # 전화번호
                                    v_phone = place_base.get("virtualPhone", "")
                                    phone = place_base.get("phone", "")
                                    data["안심번호"] = v_phone if v_phone else phone if phone else "N/A"
                                    
                                    data["방문자리뷰수"] = str(place_base.get("visitorReviewsTotal", "N/A"))
                                    data["블로그 리뷰수"] = str(place_base.get("cafeBlogReviewsTotal", "N/A"))
                                    
                                    # 고유번호 및 URL
                                    pid = str(place_base.get("id", "N/A"))
                                    data["고유번호"] = pid
                                    if pid != "N/A":
                                        data["플레이스URL"] = f"https://m.place.naver.com/restaurant/{pid}"
                                    # SNS
                                    urls = place_base.get("urls", [])
                                    homepaths = place_base.get("homepaths", [])
                                    all_urls = []
                                    if urls and isinstance(urls, list):
                                        all_urls.extend([u.get("url", u) for u in urls if isinstance(u, dict) or isinstance(u, str)])
                                    if homepaths and isinstance(homepaths, list):
                                        all_urls.extend([u.get("url", u) for u in homepaths if isinstance(u, dict) or isinstance(u, str)])
                                        
                                    root_query = apollo_state.get("ROOT_QUERY", {})
                                    root_query_detail = {}
                                    for k, v in root_query.items():
                                        if k.startswith("placeDetail") and isinstance(v, dict):
                                            root_query_detail = v
                                            break
                                    
                                    homepages = root_query_detail.get("homepages", {})
                                    if isinstance(homepages, dict):
                                        repr_url = homepages.get("repr", {}).get("url")
                                        if repr_url: all_urls.append(repr_url)
                                        for etc in homepages.get("etc", []):
                                            if isinstance(etc, dict) and etc.get("url"): all_urls.append(etc.get("url"))
                                        
                                    sns_list = []
                                    homepage_list = []
                                    for u in all_urls:
                                        u_str = str(u)
                                        if any(sns in u_str for sns in ["instagram.com", "facebook.com", "twitter.com", "youtube.com", "blog.naver.com"]):
                                            sns_list.append(u_str)
                                        elif u_str.startswith("http") and "m.place.naver.com" not in u_str:
                                            homepage_list.append(u_str)
                                            
                                    if sns_list:
                                        data["SNS"] = ", ".join(list(set(sns_list)))
                                    if homepage_list:
                                        data["홈페이지"] = ", ".join(list(set(homepage_list)))
                                        
                                    if desc:
                                        import re
                                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', desc)
                                        if emails:
                                            data["이메일"] = ", ".join(list(set(emails)))
                                        
                        except Exception as e:
                            self.log(f"Apollo 데이터 파싱 오류: {e}")

                        # 2. 누락된 핵심 데이터가 있을 경우 2차 텍스트 정규식으로 복구 (Fallback)
                        try:
                            if data["안심번호"] == "N/A" or data["업체 주소"] == "N/A" or data["상호명"] == "N/A":
                                body_html = self.driver.page_source
                                clean_text = re.sub(r'<[^>]+>', ' ', body_html)
                                clean_text_compact = re.sub(r'\s+', ' ', clean_text)
                                
                                if data["안심번호"] == "N/A":
                                    phone_match = re.search(r'0\d{1,3}-\d{3,4}-\d{4}', clean_text)
                                    if phone_match:
                                        data["안심번호"] = phone_match.group(0)
                                        
                                if data["업체 주소"] == "N/A":
                                    addr_match = re.search(r'((?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)\s+[가-힣]+(?:시|군|구)\s+[가-힣0-9]+(?:로|길|동)\s*\d*(?:번길)?\s*\d*(?:\s+\d+층)?)', clean_text_compact)
                                    if addr_match:
                                        data["업체 주소"] = addr_match.group(1).strip()
                                        
                                if data["이메일"] == "N/A":
                                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', clean_text)
                                    if emails:
                                        data["이메일"] = ", ".join(list(set(emails)))
                                        
                                if data["상호명"] in ["N/A", "네이버지도", "네이버 지도"]:
                                    try:
                                        title_elem = self.driver.find_element(By.CSS_SELECTOR, "div > span.Fc1rA, span.GHAhO, span[class^='title'], div[class^='title'], h2, h3")
                                        if title_elem.text and "네이버" not in title_elem.text:
                                            data["상호명"] = title_elem.text
                                    except:
                                        pass
                                        
                                if data["소개내용"] == "N/A" or data["SNS"] == "N/A":
                                    try:
                                        # 홈 탭으로 강제 이동
                                        try:
                                            home_tab = self.driver.find_element(By.XPATH, "//a[@role='tab' and .//span[contains(text(), '홈')]]")
                                            self.driver.execute_script("arguments[0].click();", home_tab)
                                            time.sleep(1.5)
                                        except: pass
                                        
                                        if data["소개내용"] == "N/A":
                                            desc_elems = self.driver.find_elements(By.CSS_SELECTOR, "div.zPf8m, span.zPf8m, div.O8qbU, div[class*='desc'], span[class*='desc']")
                                            for d in desc_elems:
                                                text = d.text.strip()
                                                if text and len(text) > 5 and not any(kw in text for kw in ["리뷰", "블로그", "검색", "네이버", "별점"]):
                                                    data["소개내용"] = text
                                                    break
                                                    
                                        if data["SNS"] == "N/A":
                                            sns_links = []
                                            for a in self.driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                                                href = a.get_attribute("href")
                                                if href and any(domain in href for domain in ["instagram.com", "facebook.com", "twitter.com", "youtube.com"]):
                                                    sns_links.append(href)
                                            if sns_links:
                                                data["SNS"] = ", ".join(list(set(sns_links)))
                                    except:
                                        pass
                                        
                        except Exception as e:
                            pass

                        self.log(f"수집 완료: {data['상호명']} | {data['업체 주소']} | 리뷰 {data['방문자리뷰수']}")
                        
                        unique_id = f"naver_place_{keyword}_{data['상호명']}"
                        self.history_manager.add_collected(unique_id)
                        
                        self.results.append(data)
                        collected += 1
                        
                        if collected >= page_limit:
                            from checkpoint_manager import CheckpointManager
                            self.log(f"[{keyword}] {page_limit}개 수집 완료. 봇 탐지 방지를 위해 여기서 일시 정지하며, 현재 위치({collected}개)를 메모리에 저장합니다.")
                            CheckpointManager.save_checkpoint("place", keywords, idx, position=collected, results=self.results)
                            return
                            
                        # 다시 searchIframe으로 돌아가기 위해 메인으로 먼저 빠져나옴
                        self.driver.switch_to.default_content()
                        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe")))
                        time.sleep(1)
                        
                except Exception as e:
                    self.log(f"[{keyword}] 검색 중 오류 발생: {e}")
                    
                self.driver.switch_to.default_content()
                
            # 체크포인트 지우지 않음 (무한 이어하기 지원)
        except Exception as e:
            self.log(f"크롤러 엔진 실행 중 치명적 오류: {e}")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
        if self.results:
            self.save_excel("naver_place_results.xlsx")

    def crawl_naver_shopping(self, keywords, use_ip_change=False):
        self.log("네이버 쇼핑 판매자 크롤링 로직은 추후 확장이 가능하도록 뼈대만 잡아두었습니다.")
        pass

    def _interruptible_sleep(self, seconds):
        """중지 요청에 빠르게 반응하도록 0.5초 단위로 쪼개어 대기한다."""
        end = seconds
        slept = 0.0
        while slept < end and self.is_running:
            time.sleep(min(0.5, end - slept))
            slept += 0.5

    def _build_coupang_driver(self):
        """쿠팡용 크롬 드라이버를 새로 생성한다. (재시작 시 재사용)"""
        options = uc.ChromeOptions()
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--start-maximized')
        options.add_argument('--accept-lang=ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7')
        driver_path = resolve_driver_path(self.log)
        driver = uc.Chrome(options=options, driver_executable_path=driver_path)
        driver.set_page_load_timeout(30)  # 상세페이지가 오래 매달리는 것 방지
        return driver

    def _coupang_is_blocked(self):
        """쿠팡 차단(Akamai) 여부를 확인한다."""
        try:
            title = self.driver.title
            source = self.driver.page_source
            return ("Access Denied" in title or 
                    "사용권한이 없습니다" in title or 
                    "사용권한이 없습니다" in source or
                    "edgesuite" in source)
        except Exception:
            return False

    def _coupang_type_search(self, keyword, wait):
        """홈에서 검색창에 사람처럼 타이핑해 검색결과 1페이지로 진입한다. 성공 시 True."""
        import random
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        
        try:
            self.driver.get("https://www.coupang.com/")
            time.sleep(random.uniform(3.5, 5.5))  # 검색창 로딩 여유
            
            # Access Denied 인지 확인
            if self._coupang_is_blocked():
                self.log("홈 접속 시 쿠팡 차단(Access Denied) 감지됨. 검색창 입력을 중단합니다.")
                return False
                
            # 팝업 오버레이 우회를 위해 clickable 대신 presence 사용 + 대체 선택자 추가
            search_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#headerSearchKeyword, input[name='q'], input[type='search']")))
            self.driver.execute_script("arguments[0].click();", search_box)
            time.sleep(random.uniform(0.3, 0.7))
            
            search_box.clear()
            self.driver.execute_script("arguments[0].value = '';", search_box)
            
            for char in keyword:
                search_box.send_keys(char)
                time.sleep(random.uniform(0.08, 0.25))
            time.sleep(random.uniform(0.4, 0.9))
            
            search_box.send_keys(Keys.ENTER)
            time.sleep(random.uniform(2.5, 4.0))
            
            # 검색(엔터) 직후 차단 페이지(Access Denied)로 넘어갔는지 확인
            if self._coupang_is_blocked():
                self.log("검색 실행 직후 쿠팡 차단(Access Denied) 감지됨. 진행을 중단합니다.")
                return False
                
            return True
        except Exception as e:
            self.log(f"검색창 입력 실패: {type(e).__name__}")
            return False

    def _coupang_goto_page(self, keyword, page, wait):
        """검색결과에서 목표 페이지로 '사람처럼' 이동한다.

        핵심: 쿠팡은 np/search?...&page=N URL을 직접 치고 들어오는 딥링크를 봇으로 보고
        빈 결과를 내려준다(1페이지는 검색창 타이핑이라 통과, 2페이지+ URL 직행은 0개).
        따라서 검색창으로 1페이지에 먼저 진입한 뒤, 하단 페이지네이션의 해당 번호를
        실제로 클릭해 이동한다. 클릭 대상을 못 찾으면 URL 폴백(호출부에서 처리)을 위해 False.
        """
        import random
        # 검색결과 페이지가 아니면(상세페이지 등) 먼저 검색으로 1페이지 진입
        try:
            cur = self.driver.current_url or ""
        except Exception:
            cur = ""
        if "/np/search" not in cur:
            if not self._coupang_type_search(keyword, wait):
                return False
        # 목표가 1페이지면 검색 직후 상태로 충분
        if page <= 1:
            return True
        # 페이지네이션이 하단에 있으므로 스크롤 후, href에 page=N 이 담긴 앵커를 클릭
        try:
            from urllib.parse import urlparse, parse_qs
            from selenium.webdriver.common.by import By
            target = str(page)
            link = None
            
            # 자연스러운 스크롤(Smooth Scroll)로 지연 로딩(Lazy Load) 유도
            # 단번에 맨 밑으로 내리면 IntersectionObserver가 트리거되지 않거나 봇으로 의심받음
            scroll_height = self.driver.execute_script("return document.body.scrollHeight")
            current_scroll = 0
            
            for attempt in range(15): # 최대 15번 찔끔찔끔 스크롤
                scroll_step = random.randint(600, 1000)
                current_scroll += scroll_step
                self.driver.execute_script(f"window.scrollTo(0, {current_scroll});")
                time.sleep(random.uniform(0.5, 1.2))
                
                # 1순위: a 태그나 button 태그 중 텍스트가 정확히 일치하는 것 찾기
                elements = self.driver.find_elements(By.CSS_SELECTOR, "a, button, .btn-page")
                for el in elements:
                    try:
                        text = el.text.strip()
                        if text == target:
                            link = el
                            break
                        href = el.get_attribute("href") or ""
                        if "page=" in href and parse_qs(urlparse(href).query).get("page", [None])[0] == target:
                            link = el
                            break
                    except Exception:
                        continue
                        
                if link:
                    break
                
                # 만약 이미 맨 밑까지 왔는데도 못 찾았다면 조금 더 기다려봄
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if current_scroll >= new_height:
                    time.sleep(1.0)
                    # 맨 끝 도달 시 약간 위로 올렸다가 다시 내리는 것도 봇 회피에 좋음
                    self.driver.execute_script("window.scrollBy(0, -500);")
                    time.sleep(0.5)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.0)
                    
            if not link:
                self.log(f"{page}페이지 링크를 찾을 수 없습니다. (스크롤 후에도 페이지네이션 미발견)")
                return False
                
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
            time.sleep(random.uniform(0.5, 1.0))
            
            try:
                link.click()
            except:
                self.driver.execute_script("arguments[0].click();", link)
                
            time.sleep(random.uniform(2.5, 4.0))
            return True
        except Exception as e:
            self.log(f"{page}페이지 이동(페이지네이션 클릭) 실패: {e}")
            return False

    def _coupang_scroll_to_bottom(self):
        """페이지 끝까지 부드럽게 스크롤하여 지연 로딩된 모든 상품을 불러옵니다."""
        import random
        current_scroll = 0
        for _ in range(12):
            scroll_step = random.randint(600, 1000)
            current_scroll += scroll_step
            self.driver.execute_script(f"window.scrollTo(0, {current_scroll});")
            time.sleep(random.uniform(0.5, 1.0))
            
            # 맨 밑에 도달했는지 확인
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if current_scroll >= new_height:
                time.sleep(1.0)
                self.driver.execute_script("window.scrollBy(0, -500);")
                time.sleep(0.5)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.0)
                break
        return True

    def _coupang_session_reset(self, use_ip_change, restart_browser=True):
        """차단 낙인이 찍힌 세션을 통째로 갈아준다: IP 변경 + 브라우저 재시작 + 홈 워밍업.

        Akamai는 _abck 쿠키뿐 아니라 localStorage/sessionStorage의 센서 데이터에도
        봇 판정을 심어둔다. delete_all_cookies()만으로는 이 지문이 남으므로,
        브라우저를 완전히 종료(quit)하고 새 프로필로 다시 띄워 "완전히 새로운 사람"이 된다.
        홈을 먼저 방문해 정상 쿠키/센서를 새로 발급받은 뒤 복귀한다.
        """
        import random
        if use_ip_change:
            import ip_changer
            changed = ip_changer.toggle_airplane_mode(log=self.log)
            if not changed:
                self.log("⚠️ IP가 바뀌지 않았습니다. 휴대폰 테더링 연결 상태를 확인하세요.")

        if restart_browser:
            # 브라우저 완전 재시작 — 쿠키+localStorage+세션지문까지 통째로 폐기
            try:
                if self.driver:
                    self.driver.quit()
            except Exception:
                pass
            self.driver = None
            try:
                self.driver = self._build_coupang_driver()
                self.log("브라우저를 완전히 새로 띄웠습니다. (쿠키·저장소·세션지문 초기화)")
            except Exception as e:
                self.log(f"⚠️ 브라우저 재시작 실패: {e}")
                return False
        else:
            try:
                self.driver.delete_all_cookies()
                self.log("차단 판정이 담긴 쿠키를 삭제했습니다. (세션 초기화)")
            except Exception as e:
                self.log(f"쿠키 삭제 실패(무시하고 진행): {e}")

        # 홈 워밍업 — 검색 없이 곧장 상세로 가지 않도록 정상 세션을 먼저 확보
        try:
            self.driver.get("https://www.coupang.com/")
            time.sleep(random.uniform(2, 4))
        except Exception:
            pass
        return True

    def _collect_coupang_detail(self, prod, use_ip_change):
        """상품 상세 페이지에서 판매자 정보를 수집해 prod에 채운다.

        반환값: True = 수집 완료(정보가 없어도 페이지는 정상 열람),
                False = 차단으로 페이지 자체를 못 봄(재시도 필요, prod는 저장하면 안 됨)
        """
        import random
        if self.driver is None:
            return False  # 이전 재시작 실패 등으로 드라이버가 없으면 저장 금지
        seller_name = "N/A"
        seller_contact = "N/A"
        seller_address = "N/A"
        seller_email = "N/A"
        seller_bizno = "N/A"

        try:
            # 봇 차단 방지를 위한 랜덤 딜레이
            time.sleep(random.uniform(1.5, 3.5))

            # 현재(검색결과) 창의 핸들을 기억해둠
            main_window = self.driver.current_window_handle
            
            # 새 탭으로 상세페이지 열기 (검색결과 페이지 유지)
            self.driver.execute_script(f"window.open('{prod['상품URL']}', '_blank');")
            
            # 새로 열린 탭으로 포커스 이동
            for handle in self.driver.window_handles:
                if handle != main_window:
                    self.driver.switch_to.window(handle)
                    break

            # 페이지 로드 후 자연스러운 스크롤
            time.sleep(random.uniform(1.0, 2.0))
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
            time.sleep(random.uniform(0.5, 1.0))

            # Access Denied → 세션 리셋(IP+브라우저 재시작+워밍업) 후 같은 상품 1회 재시도
            if self._coupang_is_blocked():
                self.log("  [경고] 쿠팡 접근 차단됨(Access Denied). IP 변경+브라우저 재시작 후 재시도합니다...")
                try:
                    self.driver.close()
                    self.driver.switch_to.window(main_window)
                except:
                    pass
                if not self._coupang_session_reset(use_ip_change) or self.driver is None:
                    return False  # 재시작 실패 — 저장하지 않고 재시도 큐로
                # 재시작했으므로 창이 1개뿐임. 다시 새 탭으로 시도
                main_window = self.driver.current_window_handle
                self.driver.execute_script(f"window.open('{prod['상품URL']}', '_blank');")
                for handle in self.driver.window_handles:
                    if handle != main_window:
                        self.driver.switch_to.window(handle)
                        break
                time.sleep(random.uniform(2, 4))
                if self._coupang_is_blocked():
                    try:
                        self.driver.close()
                        self.driver.switch_to.window(main_window)
                    except:
                        pass
                    return False

            import bs4
            detail_soup = bs4.BeautifulSoup(self.driver.page_source, 'html.parser')

            for th in detail_soup.find_all('th'):
                th_text = th.get_text(strip=True).replace(" ", "").lower()
                td = th.find_next_sibling('td')
                if td:
                    td_text = td.get_text(strip=True)
                    if "상호/대표자" in th_text or "판매자상호" in th_text or "상호명" in th_text:
                        seller_name = td_text
                    elif "사업장소재지" in th_text or "주소" in th_text:
                        seller_address = td_text
                    elif "e-mail" in th_text or "이메일" in th_text:
                        seller_email = td_text
                    elif "연락처" in th_text or "전화번호" in th_text:
                        seller_contact = td_text
                    elif "사업자번호" in th_text or "사업자등록번호" in th_text:
                        seller_bizno = td_text

            if seller_name == "N/A":
                seller_info_div = detail_soup.select_one("div.seller-info, div.prod-sell-info")
                if seller_info_div:
                    text = seller_info_div.get_text(" ", strip=True)
                    if "판매자:" in text:
                        text = text.split("판매자:")[1].split("다른 판매자")[0].strip()
                        seller_name = text
                    elif "쿠팡(주)" in text or "로켓그로스" in text:
                        seller_name = text

            if prod["로켓배송여부"] == "O" and seller_name == "N/A":
                seller_name = "쿠팡(주) 또는 로켓그로스"

        except Exception as detail_e:
            self.log(f"상세 페이지 수집 오류: {detail_e}")
            
        finally:
            # 상세 수집이 끝났거나 오류가 났으면 현재 탭(상세)을 닫고 원래 창(검색목록)으로 복귀
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(main_window)
            except Exception as e:
                self.log(f"탭 닫기 오류(무시): {e}")

        prod["판매자명"] = seller_name
        prod["판매자 연락처"] = seller_contact
        prod["주소"] = seller_address
        prod["이메일"] = seller_email
        prod["사업자번호"] = seller_bizno
        return True

    def crawl_coupang(self, keywords, use_ip_change=False, resume_checkpoint=None, rounds=1, pages_per_round=1):
        self.is_running = True
        self.results = resume_checkpoint.get("results", []) if resume_checkpoint else []

        try:
            rounds = int(rounds)
        except (TypeError, ValueError):
            rounds = 1
        if rounds < 1:
            rounds = 1

        try:
            pages_per_round = int(pages_per_round)
        except (TypeError, ValueError):
            pages_per_round = 1
        if pages_per_round < 1:
            pages_per_round = 1

        MAX_PAGE = 200  # 쿠팡 페이지네이션 안전 상한

        from checkpoint_manager import CheckpointManager

        try:
            self.driver = self._build_coupang_driver()

            for idx, keyword in enumerate(keywords):
                if not self.is_running:
                    return

                # 작업 인덱스 저장
                CheckpointManager.save_checkpoint("coupang", keywords, idx, position=1, results=self.results)

                if use_ip_change and idx > 0:
                    self.log(f"[{keyword}] 검색 전 IP 변경 시도...")
                    import ip_changer
                    ip_changer.toggle_airplane_mode(log=self.log)

                # 페이지 커서: 회차가 바뀌어도 초기화하지 않고 멈춘 지점에서 계속 이어간다.
                page = 1
                if resume_checkpoint and idx == 0:
                    page = resume_checkpoint.get("position", 1)
                    if page > 1:
                        self.log(f"[{keyword}] 이전 작업에서 멈춘 위치로 직행합니다. ({page}페이지부터 재개)")

                try:
                    for round_num in range(1, rounds + 1):
                        if not self.is_running:
                            self.log(f"[{keyword}] 수집 중지됨. 현재 위치({page}페이지)를 저장합니다.")
                            CheckpointManager.save_checkpoint("coupang", keywords, idx, position=page, results=self.results)
                            return

                        end_page = page + pages_per_round - 1
                        self.log(f"===== [{keyword}] {round_num}/{rounds}회차 수집 시작 ({page}~{end_page}페이지, {pages_per_round}페이지 분량) =====")
                        products = []
                        round_start_len = len(self.results)

                        while page <= end_page and page <= MAX_PAGE:
                            if not self.is_running:
                                self.log(f"[{keyword}] 수집 중지됨. 현재 위치({page}페이지)를 저장합니다.")
                                CheckpointManager.save_checkpoint("coupang", keywords, idx, position=page, results=self.results)
                                return
                            import random
                            from urllib.parse import quote
                            # 드라이버가 재시작됐을 수 있으므로 wait을 현재 드라이버에 매번 새로 묶는다.
                            wait = WebDriverWait(self.driver, 15)

                            if page == 1:
                                self.log(f"[{keyword}] 로봇 탐지 방어를 위해 사람처럼 검색창에 타이핑을 시도합니다...")
                                if not self._coupang_type_search(keyword, wait):
                                    # 검색창 실패 시에만 URL 폴백(홈 워밍업 경유)
                                    self.log(f"[{keyword}] 검색창 입력 실패 → 홈 워밍업 후 검색 URL로 우회합니다.")
                                    try:
                                        self.driver.get("https://www.coupang.com/")
                                        time.sleep(random.uniform(2.0, 3.5))
                                    except Exception:
                                        pass
                                    self.driver.get(f"https://www.coupang.com/np/search?q={quote(keyword)}&page={page}")
                                    time.sleep(random.uniform(2.5, 4.0))
                            else:
                                # 2페이지+ 는 검색창→페이지네이션 클릭으로 사람처럼 이동한다.
                                # (URL 직행 딥링크는 쿠팡이 빈 결과를 주므로 반드시 클릭 이동)
                                self.log(f"[{keyword}] 쿠팡 {page}페이지로 이동합니다... (검색→페이지네이션 클릭)")
                                if not self._coupang_goto_page(keyword, page, wait):
                                    self.log(f"[{keyword}] 페이지네이션 클릭 실패 → 검색 세션 확보 후 URL 폴백")
                                    self._coupang_type_search(keyword, wait)  # 정상 세션 먼저 확보
                                    self.driver.get(f"https://www.coupang.com/np/search?q={quote(keyword)}&page={page}")
                                    time.sleep(random.uniform(2.5, 4.0))

                            # IP 차단 및 CAPTCHA 감지
                            current_url = self.driver.current_url
                            page_source = self.driver.page_source
                            if "captcha" in current_url.lower() or "login" in current_url.lower() or "Access Denied" in page_source or "사용권한이 없습니다" in page_source:
                                self.log("⚠️ 쿠팡에 의해 IP 차단 또는 보안 절차(CAPTCHA)가 감지되었습니다.")
                                if use_ip_change:
                                    self.log("IP를 변경하고 새 세션에서 현재 페이지를 다시 시도합니다...")
                                    self._rotate_mobile_ip()
                                    self._coupang_session_reset(use_ip_change=True, restart_browser=True)
                                    continue # 같은 페이지 번호로 다시 루프 시도
                                else:
                                    self.log("IP 자동 변경 옵션이 꺼져 있어 작업을 중단하고 현재 시점을 저장합니다.")
                                    CheckpointManager.save_checkpoint("coupang", keywords, idx, position=page, results=self.results)
                                    self.is_running = False
                                    return

                            self.log(f"[{keyword}] {page}페이지의 모든 상품을 불러오기 위해 화면을 스크롤합니다...")
                            self._coupang_scroll_to_bottom()

                            # 상품 목록 추출 (기존 DOM과 신규 Next.js DOM 모두 지원, BeautifulSoup 활용)
                            import bs4
                            soup = bs4.BeautifulSoup(self.driver.page_source, 'html.parser')

                            items = soup.select("li.search-product")
                            if not items:
                                items = soup.select("li[class*='ProductUnit']")
                            if not items:
                                a_tags = soup.select("a[href*='/vp/products/']")
                                if a_tags:
                                    items = []
                                    for a in a_tags:
                                        parent = a.find_parent('li')
                                        if parent and parent not in items:
                                            items.append(parent)

                            if not items:
                                try:
                                    self.log(f"[{keyword}] 검색 결과가 없거나 차단되었습니다. (현재 주소: {self.driver.current_url}) 검색창으로 재진입 후 재시도합니다...")
                                except Exception:
                                    self.log(f"[{keyword}] 검색 결과가 없거나 차단되었습니다. 재시도합니다...")
                                time.sleep(3)
                                # 단순 refresh 대신, 사람처럼 검색창→페이지네이션으로 다시 진입한다.
                                self._coupang_goto_page(keyword, page, wait)
                                time.sleep(3)

                                soup = bs4.BeautifulSoup(self.driver.page_source, 'html.parser')
                                items = soup.select("li.search-product")
                                if not items:
                                    items = soup.select("li[class*='ProductUnit']")
                                if not items:
                                    a_tags = soup.select("a[href*='/vp/products/']")
                                    if a_tags:
                                        items = []
                                        for a in a_tags:
                                            parent = a.find_parent('li')
                                            if parent and parent not in items:
                                                items.append(parent)

                            self.log(f"[{keyword}] {page}페이지에서 {len(items)}개의 상품을 찾았습니다.")

                            new_found = 0
                            for item in items:
                                if not self.is_running: break
                                try:
                                    # 상품명 (신/구 DOM 호환)
                                    name_elem = item.select("div.name, div[class*='ProductUnit_productName']")
                                    if not name_elem: continue
                                    p_name = name_elem[0].get_text(strip=True)

                                    # 로켓배송 여부 (텍스트나 이미지 src에 rocket 포함)
                                    is_rocket = "X"
                                    if item.select("img.badge.rocket, span.badge.rocket, span.badge.roket"):
                                        is_rocket = "O"
                                    else:
                                        html_text = str(item).lower()
                                        if 'rocket' in html_text or '로켓배송' in html_text or '로켓그로스' in html_text:
                                            is_rocket = "O"

                                    # 평점
                                    rating_elem = item.select("em.rating")
                                    rating = rating_elem[0].get_text(strip=True) if rating_elem else "N/A"
                                    if rating == "N/A":
                                        # 신규 DOM
                                        aria_elems = item.select("div[aria-label]")
                                        for a_el in aria_elems:
                                            lbl = a_el.get("aria-label", "")
                                            if lbl and lbl.replace('.', '', 1).isdigit():
                                                rating = lbl
                                                break

                                    # 리뷰수
                                    review_elem = item.select("span.rating-total-count")
                                    review_count = "N/A"
                                    if review_elem:
                                        review_count = review_elem[0].get_text(strip=True).replace("(", "").replace(")", "")
                                    else:
                                        # 신규 DOM: 괄호 안의 숫자 찾기
                                        match = re.search(r'\((\d+)\)', item.get_text())
                                        if match:
                                            review_count = match.group(1)

                                    # 상품 링크
                                    link_elem = item.select("a.search-product-link, a[href*='/vp/products/']")
                                    if not link_elem: continue
                                    p_link = link_elem[0].get("href", "")
                                    if p_link and not p_link.startswith("http"):
                                        p_link = "https://www.coupang.com" + p_link

                                    import urllib.parse as urlparse
                                    parsed = urlparse.urlparse(p_link)
                                    qs = urlparse.parse_qs(parsed.query)
                                    clean_query = []
                                    if 'itemId' in qs: clean_query.append('itemId=' + qs['itemId'][0])
                                    if 'vendorItemId' in qs: clean_query.append('vendorItemId=' + qs['vendorItemId'][0])
                                    clean_p_link = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{'&'.join(clean_query)}"

                                    # 이력 매니저 중복 검사 (이미 수집한 상품은 건너뛰어 회차가 이어지도록 함)
                                    if self.history_manager.is_collected(clean_p_link):
                                        continue

                                    new_found += 1

                                    products.append({
                                        "키워드": keyword,
                                        "수집시간": time.strftime("%Y-%m-%d %H:%M:%S"),
                                        "상품명": p_name,
                                        "로켓배송여부": is_rocket,
                                        "평점": rating,
                                        "리뷰수": review_count,
                                        "판매자명": "N/A",
                                        "판매자 연락처": "N/A",
                                        "주소": "N/A",
                                        "이메일": "N/A",
                                        "사업자번호": "N/A",
                                        "상품URL": clean_p_link
                                    })

                                except Exception as e:
                                    pass

                                if not self.is_running: break

                            if not items:
                                break  # 더 이상 상품이 없으면 종료
                            page += 1

                        if not products:
                            self.log(f"[{keyword}] {round_num}회차: 더 이상 수집할 새 상품이 없습니다. 이 키워드를 종료합니다.")
                            break

                        self.log(f"[{keyword}] {round_num}회차 - 새로운 상품 총 {len(products)}개의 상세 수집을 시작합니다.")

                        import random
                        retry_queue = []
                        for i, prod in enumerate(products):
                            if not self.is_running: break

                            # 자동 IP 변경 (IP 차단 방지) — IP만 바꾸면 Akamai 쿠키/저장소 낙인이
                            # 따라오므로 브라우저를 완전히 재시작하고 홈 워밍업까지 수행한다.
                            if use_ip_change and i > 0 and i % 20 == 0:
                                self.log("안전한 수집을 위해 IP를 변경하고 브라우저를 재시작합니다... (USB 테더링)")
                                self._coupang_session_reset(use_ip_change)
                                time.sleep(5)

                            self.log(f"[{keyword}] {i+1}/{len(products)} 상품 상세 정보 수집 중...")

                            if self._collect_coupang_detail(prod, use_ip_change):
                                # 수집 성공 시 이력에 추가
                                self.history_manager.add_collected(prod["상품URL"])
                                self.results.append(prod)
                            else:
                                self.log("  [경고] 재시도에도 차단 상태입니다. 이 상품은 회차 말미에 다시 시도합니다.")
                                retry_queue.append(prod)

                            # 사람처럼 보이는 체류 간격: 상품마다 5~15초 랜덤(가우시안 중심 8초),
                            # 8개마다 20~40초 '지능형 휴식'을 넣어 기계적 등간격 리듬을 깬다.
                            if self.is_running and i < len(products) - 1:
                                if (i + 1) % 8 == 0:
                                    rest = random.uniform(20, 40)
                                    self.log(f"  자연스러운 패턴을 위해 {rest:.0f}초 쉬어갑니다...")
                                else:
                                    rest = min(15, max(5, random.gauss(8, 2.5)))
                                self._interruptible_sleep(rest)

                        # ---- 차단으로 밀린 상품 재시도 (회차 말미 1회) ----
                        if retry_queue and self.is_running:
                            self.log(f"[{keyword}] 차단으로 밀린 상품 {len(retry_queue)}개를 재시도합니다. (세션 초기화 후 잠시 대기)")
                            self._coupang_session_reset(use_ip_change)
                            time.sleep(10)
                            still_blocked = 0
                            for j, prod in enumerate(retry_queue):
                                if not self.is_running: break
                                self.log(f"[{keyword}] 재시도 {j+1}/{len(retry_queue)} 상품 상세 정보 수집 중...")
                                if self._collect_coupang_detail(prod, use_ip_change):
                                    self.history_manager.add_collected(prod["상품URL"])
                                    self.results.append(prod)
                                else:
                                    still_blocked += 1
                            if still_blocked:
                                self.log(f"[{keyword}] {still_blocked}개 상품은 끝내 차단으로 수집하지 못했습니다. (수집 이력에 남기지 않으므로 다음 실행 때 다시 수집됩니다)")

                        # ---- 이번 회차 마무리: 결과 저장 + 체크포인트 갱신 ----
                        round_items = self.results[round_start_len:]
                        if round_items:
                            fname = f"coupang_{keyword}_{round_num}회차_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
                            self.save_excel(fname, data=round_items)
                        CheckpointManager.save_checkpoint("coupang", keywords, idx, position=page, results=self.results)
                        self.log(f"[{keyword}] {round_num}/{rounds}회차 완료 — {len(round_items)}건 저장 (누적 {len(self.results)}건). 다음 회차는 {page}페이지부터 이어갑니다.")

                        # 회차 사이 대기/IP 변경 (봇 탐지 방지)
                        if round_num < rounds and self.is_running:
                            if use_ip_change:
                                self.log("다음 회차 전 IP를 변경하고 세션을 초기화합니다... (USB 테더링)")
                                self._coupang_session_reset(use_ip_change)
                                time.sleep(5)
                            else:
                                import random
                                wait_s = random.uniform(5, 10)
                                self.log(f"봇 탐지 방지를 위해 {wait_s:.0f}초 대기 후 다음 회차를 이어갑니다...")
                                time.sleep(wait_s)

                except Exception as ex:
                    self.log(f"[{keyword}] 수집 중 에러: {ex}")

            # 체크포인트 지우지 않음 (무한 이어하기 지원)
            self.log("모든 쿠팡 크롤링이 완료되었습니다.")

        except Exception as e:
            self.log(f"크롤러 초기화/실행 오류: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
            self.is_running = False

    def _get_desktop_dir(self):
        """실제 바탕화면 폴더를 찾는다.

        OneDrive 백업이 켜진 PC는 바탕화면이 ~/OneDrive/바탕 화면 등으로 옮겨져
        ~/Desktop 이 존재하지 않을 수 있으므로 여러 후보를 검사한다.
        """
        home = os.path.expanduser("~")
        candidates = [
            os.path.join(home, "Desktop"),
            os.path.join(home, "OneDrive", "Desktop"),
            os.path.join(home, "OneDrive", "바탕 화면"),
            os.path.join(home, "바탕 화면"),
        ]
        onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
        if onedrive:
            candidates.insert(0, os.path.join(onedrive, "Desktop"))
            candidates.insert(1, os.path.join(onedrive, "바탕 화면"))

        for path in candidates:
            if os.path.isdir(path):
                return path
        # 어떤 후보도 없으면 홈 폴더에 저장(최소한 실패는 않도록)
        return home

    def save_excel(self, filename, data=None):
        try:
            rows = data if data is not None else self.results
            if not rows:
                self.log("저장할 수집 데이터가 없어 엑셀 파일을 만들지 않았습니다.")
                return

            df = pd.DataFrame(rows)
            desktop_path = self._get_desktop_dir()
            save_path = os.path.join(desktop_path, filename)

            try:
                df.to_excel(save_path, index=False)
            except PermissionError:
                # 같은 파일을 Excel로 열어둔 경우 → 시간표시된 다른 이름으로 저장
                base, ext = os.path.splitext(filename)
                alt_name = f"{base}_{time.strftime('%Y%m%d_%H%M%S')}{ext}"
                save_path = os.path.join(desktop_path, alt_name)
                df.to_excel(save_path, index=False)
                self.log("기존 파일이 열려 있어 새 이름으로 저장했습니다. (열려 있는 엑셀을 닫아주세요)")

            self.log(f"데이터 엑셀 저장 완료: {save_path}")
        except Exception as e:
            self.log(f"엑셀 저장 실패: {e}")
            self.log("(엑셀 파일이 열려 있거나 저장 폴더 접근 권한을 확인해주세요)")
