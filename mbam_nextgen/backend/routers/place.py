from fastapi import APIRouter, HTTPException, Depends
from mbam_nextgen.backend.quota import consume_generation_quota
from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.backend.database import get_db
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
import re

import subprocess

def fetch_place_by_mid_cli(mid):
    crawler_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "services", "naver_crawler.py")
    try:
        result = subprocess.run(["python", crawler_path, "detail", str(mid)], capture_output=True, text=True, check=True)
        output = result.stdout
        start_idx = output.find('{')
        end_idx = output.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            return json.loads(output[start_idx:end_idx])
        return json.loads(output)
    except Exception as e:
        return {"error": str(e)}

def fetch_place_coords_cli(mid):
    """대상 매장(MID)의 실제 좌표를 가져온다. 실패 시 None."""
    crawler_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "services", "naver_crawler.py")
    try:
        result = subprocess.run(["python", crawler_path, "coords", str(mid)], capture_output=True, text=True, check=True, timeout=30)
        output = result.stdout
        start_idx = output.find('{')
        end_idx = output.rfind('}') + 1
        data = json.loads(output[start_idx:end_idx]) if start_idx != -1 and end_idx > start_idx else {}
        if data.get("success") and data.get("gps"):
            return data
        return None
    except Exception:
        return None

def search_keyword_ranking_cli(keyword, limit=300, gps=None):
    crawler_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "services", "naver_crawler.py")
    try:
        args = ["python", crawler_path, "search", keyword, "--limit", str(limit)]
        if gps:
            args.extend(["--gps", gps])
        # 300위 전체 수집은 콜드스타트/네이버 지연 시 45초를 넘길 수 있어 여유있게 90초.
        result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=90)
        output = result.stdout
        start_idx = output.find('[')
        end_idx = output.rfind(']') + 1
        if start_idx != -1 and end_idx > start_idx:
            return json.loads(output[start_idx:end_idx])
        return json.loads(output)
    except Exception as e:
        return {"error": str(e)}
from mbam_nextgen.services.seo_calculator import SeoCalculator
from mbam_nextgen.services.place_service import PlaceService
from mbam_nextgen.infrastructure.database import DatabaseManager

db_manager = DatabaseManager()

router = APIRouter()
calculator = SeoCalculator()

def _save_to_int(v):
    """저장수 버킷("12,000+","~100")에서 숫자만 추출. 없으면 0."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return max(0, int(v))
    digits = re.sub(r"[^\d]", "", str(v))
    return int(digits) if digits else 0

class TrackRequest(BaseModel):
    mid: str
    keyword: str
    name: str

class FetchMidRequest(BaseModel):
    mid: str

class HistoryRequest(BaseModel):
    target_mid: str
    keyword: str

class ScoreRequest(BaseModel):
    mid: str
    store_name: str
    keyword: str
    current_rank: int
    saves: int
    visitor_reviews: int
    blog_reviews: int
    category: str
    has_booking: bool

    baseline_saves: int
    baseline_visitor_reviews: int
    baseline_blog_reviews: int
    baseline_rank: int
    baseline_has_booking: bool

@router.post("/fetch-mid")
def fetch_mid(request: FetchMidRequest,
              current_user: dict = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """
    네이버 플레이스 MID를 기반으로 실시간 업체 정보를 스크래핑합니다.
    [방법 B] cloud 모드면 job 적재 → 로컬 에이전트가 집 IP로 실행.
    """
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        job_id = jobsvc.enqueue_job(db, current_user.get("sub"), "place_fetch_mid", {"mid": request.mid})
        return {"mode": "agent", "job_id": job_id}
    try:
        res = fetch_place_by_mid_cli(request.mid)
        # naver_crawler.py returns a dict with 'name', 'category', 'success' (maybe), etc.
        if "error" in res:
            raise HTTPException(status_code=400, detail=res.get("error", "정보를 가져오는데 실패했습니다."))
        # ensure success field is present for frontend
        res["success"] = True
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/track-rank")
async def track_place_rank(request: TrackRequest):
    """새로 개발된 Playwright 봇 기반 순위 추적 (SaaS DB에 저장됨)"""
    try:
        # PlaceService가 비동기 Playwright를 사용
        place_bot = PlaceService(db_manager)
        result = await place_bot.check_place_rank(place_name=request.name, keyword=request.keyword)
        if result.get("success"):
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to track rank"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze")
def analyze_place(request: ScoreRequest):
    """
    SeoCalculator를 활용하여 N1, N2, N3 지수를 계산하고, 병목 진단 및 해결책 리포트를 생성합니다.
    """
    try:
        # N2 지표 계산용
        metrics_payload = {
            "s_fit": 0.8,
            "s_save": min(1.0, request.saves / 50000.0),
            "s_rec": min(1.0, request.visitor_reviews / 10000.0),
            "s_blog": min(1.0, request.blog_reviews / 5000.0),
            "s_stay": 0.7,
            "m_recent": 0.5,
            "s_func": 1.0 if request.has_booking else 0.5
        }
        
        c_match = 1.0
        k_brand = 0.9 if request.store_name in request.keyword else 0.6
        k_desc = 0.8
        b_status = 1.0

        n1 = calculator.calculate_n1(c_match, k_brand, k_desc, b_status)
        n2 = calculator.calculate_n2(metrics_payload)
        
        # 순위 기반 M_dist
        m_dist = 1.0 if request.current_rank <= 5 else max(0.2, 1.0 - (request.current_rank * 0.05))
        c_is_new = ("새로오픈" in request.store_name)
        n3 = calculator.calculate_n3(n2, m_dist, a_personal=0.05, a_category=0.1, is_new=c_is_new)

        # 델타 (증감량) 계산
        saves_delta = request.saves - request.baseline_saves
        visitor_reviews_delta = request.visitor_reviews - request.baseline_visitor_reviews
        blog_reviews_delta = request.blog_reviews - request.baseline_blog_reviews
        
        abusing_result = calculator.analyze_abusing(
            views=1000, # 가상의 유입량
            saves=request.saves,
            reviews=request.visitor_reviews,
            saves_delta=saves_delta,
            reviews_delta=visitor_reviews_delta,
            night_traffic_spike=False
        )
        
        top3_avg = {
            "n2": 0.538,
            "save_raw": 1500,
            "rec_raw": 500,
            "blog_raw": 300,
            "recent_raw": 50,
            "func_raw": 1.0
        }
        top10_avg = {
            "n2": 0.512,
            "save_raw": 800,
            "rec_raw": 200,
            "blog_raw": 150,
            "recent_raw": 30,
            "func_raw": 0.8
        }
        my_metrics_raw = {
            "save_raw": request.saves,
            "rec_raw": request.visitor_reviews,
            "blog_raw": request.blog_reviews,
            "recent_raw": saves_delta,
            "func_raw": 1.0 if request.has_booking else 0.0
        }
        
        proposal = calculator.generate_proposal(
            store_name=request.store_name,
            keyword=request.keyword,
            current_rank=request.current_rank,
            my_metrics=my_metrics_raw,
            top3_avg=top3_avg,
            top10_avg=top10_avg,
            my_n1=n1,
            my_n2=n2,
            my_n3=n3
        )
        
        report = proposal["proposal_text"]
        
        return {
            "scores": {
                "n1": n1,
                "n2": n2,
                "n3": n3
            },
            "abusing": abusing_result,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

import json
import os
import sqlite3
from datetime import datetime
from pydantic import BaseModel

class KeywordAnalysisRequest(BaseModel):
    keyword: str
    target_mid: str
    compare_days: int = 1
    force_refresh: bool = True

def run_place_analysis(keyword: str, target_mid: str, compare_days: int = 1, force_refresh: bool = True):
    """
    300위 심층 분석 핵심 로직. (API와 자동화 스케줄러 양쪽에서 공통 사용)
    """
    # 오전/오후 순위 변동을 실시간으로 반영하기 위해 무조건 강제 새로고침 적용
    force_refresh = True
    
    # 0. Check DB for today's snapshot to skip crawling
    today_str = datetime.now().strftime("%Y-%m-%d")
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ranking.db")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 테이블이 없으면 생성 방어를 위해 기본 쿼리 실패 시 예외 처리
    cached_competitors = None
    try:
        c.execute("SELECT snapshot_json FROM place_rank_history WHERE keyword=? AND date=? ORDER BY id DESC LIMIT 1", (keyword, today_str))
        row = c.fetchone()
        if row and row[0]:
            import json
            parsed = json.loads(row[0])
            if parsed and len(parsed) >= 20:
                cached_competitors = [{"mid": p["mid"], "name": p["name"], "cat": p["category"], "rec": p["visitor_reviews"], "blog": p["blog_reviews"], "save": p["saves"], "rec_d": p.get("c_rec_d", 0), "blog_d": p.get("c_blog_d", 0), "is_new": p.get("is_new", False), "has_revisit": p.get("has_revisit", False), "local_rank": p.get("local_rank")} for p in parsed if p.get("rank", 400) < 400]
    except Exception as e:
        pass
    finally:
        conn.close()

    # 강제 새로고침 시 캐시 무시하고 재크롤
    if force_refresh:
        cached_competitors = None

    # 1. 300개 매장 수집 (스크롤) - 캐시가 없으면 실행
    if cached_competitors:
        competitors = cached_competitors
    else:
        # 전국 통합 크롤러 (Crawler A)
        competitors = search_keyword_ranking_cli(keyword, limit=400)

        # 내 매장 기준 로컬 크롤러 (Crawler B - 위치 기반 순위)
        # 플레이스 순위는 검색자 위치로 개인화되므로, 대상 매장의 '실제 좌표'를 기준점으로 사용.
        # (이전: 전포동 더미 좌표 하드코딩 → 매장이 다른 지역이면 로컬 순위가 부정확)
        target_coords = fetch_place_coords_cli(target_mid)
        competitors_local = None
        if target_coords and target_coords.get("gps"):
            competitors_local = search_keyword_ranking_cli(keyword, limit=400, gps=target_coords["gps"])
        else:
            print(f"[place] 대상 매장({target_mid}) 좌표를 찾지 못해 로컬 순위는 생략합니다.")

        # 에러 처리
        if isinstance(competitors, dict) and "error" in competitors:
            raise Exception(f"크롤러 에러: {competitors['error']}")
        if not isinstance(competitors, list):
            raise Exception(f"크롤러 응답 오류: {competitors}")

        # 로컬 순위 병합
        if isinstance(competitors_local, dict) and "error" in competitors_local:
            print(f"LOCAL CRAWLER ERROR: {competitors_local['error']}")
            # For debugging, we inject the error into the first competitor's name
            if competitors:
                competitors[0]["name"] = f"[ERR] {competitors_local['error'][:20]} {competitors[0]['name']}"

        if isinstance(competitors_local, list):
            local_map = {str(c.get("mid")): idx + 1 for idx, c in enumerate(competitors_local)}
            for c in competitors:
                mid_str = str(c.get("mid"))
                c["local_rank"] = local_map.get(mid_str, None)
        
    # 2. 내 매장 상세 정보 수집 (타겟이 검색 결과에 이미 있다면 불필요한 크롤링 생략하여 속도 최적화)
    target_comp = next((c for c in competitors if str(c["mid"]).strip() == str(target_mid).strip()), None)
    if target_comp:
        target_info = {
            "name": target_comp.get("name", ""),
            "category": target_comp.get("cat", "음식점"),
            "visitor_reviews": target_comp.get("rec", 0),
            "blog_reviews": target_comp.get("blog", 0),
            "has_booking": True
        }
    else:
        target_info = fetch_place_by_mid_cli(target_mid)
        if isinstance(target_info, dict) and "error" in target_info and target_info.get("success") is False:
            pass # 에러가 나도 기본값으로 진행
    
    # 2.5 DB에서 과거 데이터(prev_map) 선제적 조회 (최신 증감량 계산용)
    from datetime import timedelta
    compare_target_date = (datetime.now() - timedelta(days=compare_days)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # 테이블이 아직 없을 수 있음(최초 분석/데이터 초기화 직후) → 없으면 과거데이터 없이 진행
    prev_row = None
    try:
        c.execute("SELECT snapshot_json FROM place_rank_history WHERE keyword=? AND date<=? ORDER BY date DESC LIMIT 1", (keyword, compare_target_date))
        prev_row = c.fetchone()
        if not prev_row:
            c.execute("SELECT snapshot_json FROM place_rank_history WHERE keyword=? ORDER BY date ASC LIMIT 1", (keyword,))
            prev_row = c.fetchone()
    except sqlite3.OperationalError:
        prev_row = None

    prev_map = {}
    if prev_row and prev_row[0]:
        import json
        try:
            prev_places = json.loads(prev_row[0])
            prev_map = {str(p["mid"]): p for p in prev_places}
        except:
            pass
    conn.close()

    # 3. 400개 매장에 대해 점수 계산 및 내 매장 순위 찾기
    target_rank = 400
    places_data = []
    
    # 가상의 Top 3 / Top 10 평균
    top3_avg = {"n2": 0.538, "save_raw": 1500, "rec_raw": 500, "blog_raw": 300, "recent_raw": 50, "func_raw": 1.0}
    
    for idx, comp in enumerate(competitors):
        rank = idx + 1
        
        # 내 매장인지 확인 (MID 일치, 상세 스크래핑 이름 일치, 혹은 입력값이 이름인 경우 대비)
        t_mid = str(target_mid).strip()
        c_mid = str(comp["mid"]).strip()
        
        t_name = target_info.get("name", "").replace(" ", "").lower()
        c_name_check = str(comp["name"]).replace(" ", "").lower()
        t_mid_as_name = t_mid.replace(" ", "").lower()
        
        is_target = (c_mid == t_mid) or (t_name and t_name == c_name_check) or (t_mid_as_name and t_mid_as_name in c_name_check)
        
        if is_target:
            target_rank = rank
            my_rec = target_info.get("visitor_reviews", 0)
            my_blog = target_info.get("blog_reviews", 0)
            if my_blog == 0: my_blog = int(my_rec * 0.45)
            my_save = _save_to_int(target_info.get("saves", 0))
            has_booking = target_info.get("has_booking", False)
            c_name = target_info.get("name", comp.get("name", ""))
            c_cat = target_info.get("category", comp.get("cat", ""))
        else:
            my_rec = comp.get("rec", 100)
            my_blog = comp.get("blog", 0)
            if my_blog == 0: my_blog = int(my_rec * 0.35)
            my_save = _save_to_int(comp.get("save", 0))  # 저장수=버킷, 숫자만(없으면 0)
            has_booking = True if rank < 50 else False
            c_name = comp.get("name", "")
            c_cat = comp.get("cat", "")
            
        c_is_new = comp.get("is_new", False) or ("새로오픈" in c_name)
        c_has_revisit = comp.get("has_revisit", False)
            
        # Extract crawler's random deltas for fallback
        c_rec_d = comp.get("rec_d", 0)
        c_blog_d = comp.get("blog_d", 0)
        
        # 실제 증감(velocity) 및 순위 변동 (군 정규화/어뷰징 잔차용). 과거 스냅샷 없으면 0(데이터 축적 중).
        pmid = str(comp["mid"]).strip()
        if pmid in prev_map:
            prev_p = prev_map[pmid]
            real_rec_d = my_rec - prev_p.get("visitor_reviews", my_rec)
            real_blog_d = my_blog - prev_p.get("blog_reviews", my_blog)
            rank_delta = prev_p.get("rank", rank) - rank  # +면 순위 상승(개선)
        else:
            real_rec_d = 0
            real_blog_d = 0
            rank_delta = 0

        c_local_rank = comp.get("local_rank")

        places_data.append({
            "rank": rank,
            "local_rank": c_local_rank,
            "mid": comp["mid"],
            "name": c_name,
            "category": c_cat,
            "visitor_reviews": my_rec,
            "blog_reviews": my_blog,
            "saves": my_save,
            "rev_delta": real_rec_d,
            "blog_delta": real_blog_d,
            "rank_delta": rank_delta,
            "is_target": is_target,
            "c_rec_d": c_rec_d,
            "c_blog_d": c_blog_d,
            "is_new": c_is_new,
            "has_revisit": c_has_revisit
        })
        
    # 내 매장이 수집된 경쟁사 목록(Top N)에 없는 경우, 표 맨 아래에 표시하기 위해 강제 추가
    if target_rank == 400:
        my_rec = target_info.get("visitor_reviews", 0)
        my_blog = target_info.get("blog_reviews", 0)
        my_save = _save_to_int(target_info.get("saves", 0))
        c_name = target_info.get("name", "내 매장 (순위 밖)")

        c_local_rank = local_map.get(str(target_mid), None) if 'local_map' in locals() else None

        places_data.append({
            "mid": target_mid,
            "name": c_name,
            "category": target_info.get("category", "카테고리"),
            "visitor_reviews": my_rec,
            "blog_reviews": my_blog,
            "saves": my_save,
            "rev_delta": 0,
            "blog_delta": 0,
            "rank_delta": 0,
            "rank": 400,
            "local_rank": c_local_rank,
            "is_target": True,
            "is_new": False,
            "has_revisit": False
        })

    # ── N1~N5 산출: 경쟁군 전체 기준 2-pass 군 정규화 (rank 순환 제거, N4 곱셈) ──
    places_data = calculator.score_competitors(places_data, keyword)

    # 내 매장의 순위/저장수 히스토리 DB 기록
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ranking.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS place_rank_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mid TEXT,
            keyword TEXT,
            rank INTEGER,
            saves INTEGER,
            visitor_reviews INTEGER DEFAULT 0,
            blog_reviews INTEGER DEFAULT 0,
            date TEXT,
            n1 REAL DEFAULT 0,
            n2 REAL DEFAULT 0,
            n3 REAL DEFAULT 0,
            n4 REAL DEFAULT 1.0,
            n5 REAL DEFAULT 0,
            snapshot_json TEXT
        )
    ''')
    try: c.execute("ALTER TABLE place_rank_history ADD COLUMN n1 REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE place_rank_history ADD COLUMN n2 REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE place_rank_history ADD COLUMN n3 REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE place_rank_history ADD COLUMN n4 REAL DEFAULT 1.0")
    except: pass
    try: c.execute("ALTER TABLE place_rank_history ADD COLUMN n5 REAL DEFAULT 0")
    except: pass
    conn.commit()
    conn.close()
    
    target_saves = 0
    target_rec = 0
    target_blog = 0
    target_n1 = 0
    target_n2 = 0
    target_n3 = 0
    target_n4 = 1.0
    target_n5 = 0
    for p in places_data:
        if p["is_target"]:
            target_saves = p["saves"]
            target_rec = p["visitor_reviews"]
            target_blog = p["blog_reviews"]
            target_n1 = p["n1"]
            target_n2 = p["n2"]
            target_n3 = p["n3"]
            target_n4 = p["n4"]
            target_n5 = p["n5"]
            break
            
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Calculate deltas with specific past snapshot based on compare_days
    from datetime import timedelta
    compare_target_date = (datetime.now() - timedelta(days=compare_days)).strftime("%Y-%m-%d")
    
    for p in places_data:
        pmid = str(p["mid"])
        if pmid in prev_map:
            prev_p = prev_map[pmid]
            p["delta_rank"] = prev_p["rank"] - p["rank"] # + means improved rank
            p["delta_saves"] = p["saves"] - prev_p.get("saves", p["saves"])
            p["delta_visitor_reviews"] = p["visitor_reviews"] - prev_p.get("visitor_reviews", p["visitor_reviews"])
            p["delta_blog_reviews"] = p["blog_reviews"] - prev_p.get("blog_reviews", p["blog_reviews"])
            p["delta_n1"] = p["n1"] - prev_p.get("n1", p["n1"])
            p["delta_n2"] = p["n2"] - prev_p.get("n2", p["n2"])
            p["delta_n3"] = p["n3"] - prev_p.get("n3", p["n3"])
            p["delta_n5"] = p["n5"] - prev_p.get("n5", p["n5"])
        else:
            p["delta_rank"] = 0
            p["delta_saves"] = 0
            p["delta_visitor_reviews"] = 0
            p["delta_blog_reviews"] = 0
            p["delta_n1"] = 0.0
            p["delta_n2"] = 0.0
            p["delta_n3"] = 0.0
            p["delta_n5"] = 0.0
        # (가짜 random 증감 주입 제거 — 데이터 없으면 0으로 표기)
            
    import json
    snapshot_json = json.dumps(places_data, ensure_ascii=False)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    c.execute("INSERT INTO place_rank_history (mid, keyword, rank, saves, visitor_reviews, blog_reviews, date, n1, n2, n3, n4, n5, snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (target_mid, keyword, target_rank, target_saves, target_rec, target_blog, today_str, target_n1, target_n2, target_n3, target_n4, target_n5, snapshot_json))
    conn.commit()
    
    # ---------------------------------------------------------
    # Track 2: 딥 퀄리티 크롤러 백그라운드 실행 트리거
    # ---------------------------------------------------------
    import threading
    from mbam_nextgen.services.deep_crawler import run_deep_crawl_for_keyword
    
    # 별도 스레드에서 실행하여 API 응답(1~3초)에 영향을 주지 않음
    threading.Thread(target=run_deep_crawl_for_keyword, args=(keyword, 30)).start()
    
    # 이전 히스토리 조회
    c.execute("SELECT date, rank, saves, visitor_reviews, blog_reviews, n1, n2, n3, n4, n5 FROM place_rank_history WHERE mid=? AND keyword=? ORDER BY date ASC", (target_mid.strip(), keyword))
    history_rows = c.fetchall()
    conn.close()
    
    history_data = []
    for r in history_rows:
        history_data.append({
            "date": r[0][-5:], # MM-DD
            "rank": r[1],
            "saves": r[2],
            "visitor_reviews": r[3] or 0,
            "blog_reviews": r[4] or 0,
            "n1": r[5] or 0,
            "n2": r[6] or 0,
            "n3": r[7] or 0,
            "n4": r[8] if r[8] is not None else 1.0,
            "n5": r[9] or 0
        })

    return {
        "success": True,
        "keyword": keyword,
        "target_mid": target_mid,
        "target_rank": target_rank,
        "places": places_data,
        "history": history_data
    }

@router.post("/analyze-keyword")
def analyze_keyword(request: KeywordAnalysisRequest,
                    current_user: dict = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """
    300위 심층 분석용 통합 API
    [방법 B] cloud 모드면 job 적재 → 로컬 에이전트가 집 IP로 실행.
    """
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        job_id = jobsvc.enqueue_job(db, current_user.get("sub"), "place_analyze", {
            "keyword": request.keyword, "target_mid": request.target_mid,
            "compare_days": request.compare_days, "force_refresh": request.force_refresh,
        })
        return {"mode": "agent", "job_id": job_id}
    try:
        return run_place_analysis(request.keyword, request.target_mid, request.compare_days, request.force_refresh)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/track")
def track_place(req: TrackRequest):
    """
    특정 키워드와 MID 조합을 관심 목록(DB)에 추가합니다.
    """
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ranking.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute("INSERT OR REPLACE INTO tracked_places (mid, keyword, name) VALUES (?, ?, ?)", 
                  (req.mid.strip(), req.keyword.strip(), req.name.strip()))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "성공적으로 저장되었습니다."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/tracked")
def get_tracked_places():
    """
    저장된 관심 매장 목록을 반환합니다.
    """
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ranking.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 테이블이 존재하는지 확인 (만약 없는 상태에서 호출될 경우 대비)
        c.execute('''
            CREATE TABLE IF NOT EXISTS tracked_places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mid TEXT NOT NULL,
                keyword TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(mid, keyword)
            )
        ''')
        c.execute("SELECT mid, keyword, name, created_at FROM tracked_places ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        
        tracked = []
        for r in rows:
            tracked.append({
                "mid": r[0],
                "keyword": r[1],
                "name": r[2],
                "created_at": r[3]
            })
            
        return {"success": True, "tracked": tracked}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/history")
def get_place_history(req: HistoryRequest):
    """
    특정 키워드/MID에 대한 DB 기록 (순위 변동, 저장수 등) 히스토리를 반환합니다.
    """
    try:
        import sqlite3
        import os
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ranking.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # 테이블이 아직 없으면(분석 이력 없음) 빈 히스토리로 응답
        try:
            c.execute("SELECT date, rank, saves, visitor_reviews, blog_reviews, n1, n2, n3, n4, n5, snapshot_json FROM place_rank_history WHERE mid=? AND keyword=? ORDER BY date ASC",
                      (req.target_mid.strip(), req.keyword.strip()))
            rows = c.fetchall()
        except sqlite3.OperationalError:
            rows = []
        conn.close()
        
        history_data = []
        latest_rank = 0
        latest_places = []
        for r in rows:
            history_data.append({
                "date": r[0][-5:],
                "rank": r[1],
                "saves": r[2],
                "visitor_reviews": r[3] or 0,
                "blog_reviews": r[4] or 0,
                "n1": r[5] or 0,
                "n2": r[6] or 0,
                "n3": r[7] or 0,
                "n4": r[8] if r[8] is not None else 1.0,
                "n5": r[9] or 0
            })
            latest_rank = r[1]
            if r[10]:
                import json
                try:
                    latest_places = json.loads(r[10])
                except:
                    pass
            
        # 1위 매장 역산 분석 (Comparative Analyzer)
        top1_data = None
        target_data = None
        for p in latest_places:
            if p["rank"] == 1:
                top1_data = p
            if p["is_target"]:
                target_data = p
                
        advantage_report = "분석 불가능"
        if top1_data and target_data:
            advantage_report = calculator.analyze_1st_advantage(target_data, top1_data)
            
        # 최종 결과 반환
        report = f"'{req.keyword}' 분석 완료!\n- 순위: {latest_rank}위\n- 영수증 검증 점수(N1): {target_data['n1'] if target_data else 0:.4f}\n\n💡 **[AI 1위 역산 컨설팅]**\n{advantage_report}"
            
        return {
            "success": True,
            "keyword": req.keyword,
            "target_mid": req.target_mid,
            "target_rank": latest_rank,
            "places": latest_places,
            "history": history_data,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PlaceNewsGenerateRequest(BaseModel):
    place_url: str
    place_name: str

class PlaceNewsScheduleRequest(BaseModel):
    place_url: str
    place_name: str
    interval_weeks: int

class FetchReviewsRequest(BaseModel):
    place_url: str

class GenerateWithThemeRequest(BaseModel):
    place_name: str
    reviews: list
    image_paths: list
    theme: str

@router.post("/news/fetch-reviews")
async def fetch_place_reviews_api(req: FetchReviewsRequest):
    """
    Step 1: 1주일치 리뷰 및 사진 크롤링만 수행하여 반환
    """
    try:
        from mbam_nextgen.services.place_review_service import PlaceReviewService
        pr_service = PlaceReviewService()
        review_data = await pr_service.collect_reviews(req.place_url)
        
        if not review_data.get("success"):
            return {"success": False, "error": review_data.get("error")}
            
        reviews = review_data.get("reviews", [])
        image_paths = review_data.get("image_paths", [])
        
        if not reviews:
            return {"success": False, "error": "최근 리뷰를 찾을 수 없습니다."}
            
        return {
            "success": True, 
            "reviews": reviews,
            "image_paths": image_paths
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/news/generate-with-theme")
async def generate_with_theme_api(req: GenerateWithThemeRequest, _q: dict = Depends(consume_generation_quota)):
    """
    Step 2: 수집된 리뷰와 선택된 테마를 기반으로 AI 원고 및 영상 생성
    """
    try:
        from mbam_nextgen.services.soul import SoulRewriter
        from mbam_nextgen.services.clip import ClipGenerator
        import uuid
        
        # 1. AI 분석 및 원고 생성 (테마 적용)
        soul = SoulRewriter()
        ai_result = await soul.generate_place_news(req.place_name, req.reviews, req.theme)
        
        # 2. 클립 영상 생성
        clip_gen = ClipGenerator()
        clip_name = f"clip_{uuid.uuid4().hex[:8]}"
        clip_texts = ai_result.get("clip_texts", ["리뷰 소식"])
        clip_path = clip_gen.generate_clip(req.image_paths, clip_texts, clip_name)
        
        # 3. DB 저장
        from mbam_nextgen.backend.database import SessionLocal, PlaceNewsHistory
        db = SessionLocal()
        history = PlaceNewsHistory(
            schedule_id="manual",
            generated_text=f"[{req.theme}]\n제목: {ai_result.get('title')}\n\n{ai_result.get('content')}",
            clip_path=clip_path,
            status="pending"
        )
        db.add(history)
        db.commit()
        history_id = history.id
        db.close()
        
        return {
            "success": True, 
            "ai_result": ai_result, 
            "clip_path": clip_path,
            "history_id": history_id
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/news/generate")
async def generate_place_news_api(req: PlaceNewsGenerateRequest, _q: dict = Depends(consume_generation_quota)):
    """
    1. 리뷰 크롤링
    2. AI 원고 생성
    3. 클립 영상 생성
    """
    try:
        from mbam_nextgen.services.place_review_service import PlaceReviewService
        from mbam_nextgen.services.soul import SoulRewriter
        from mbam_nextgen.services.clip import ClipGenerator
        import uuid
        
        # 1. 리뷰 수집
        pr_service = PlaceReviewService()
        review_data = await pr_service.collect_reviews(req.place_url)
        
        if not review_data.get("success"):
            return {"success": False, "error": review_data.get("error")}
            
        reviews = review_data.get("reviews", [])
        image_paths = review_data.get("image_paths", [])
        
        if not reviews:
            return {"success": False, "error": "최근 리뷰를 찾을 수 없습니다."}
            
        # 2. AI 분석 및 원고 생성
        soul = SoulRewriter()
        ai_result = await soul.generate_place_news(req.place_name, reviews)
        
        # 3. 클립 영상 생성
        clip_gen = ClipGenerator()
        clip_name = f"clip_{uuid.uuid4().hex[:8]}"
        clip_texts = ai_result.get("clip_texts", ["리뷰 소식"])
        clip_path = clip_gen.generate_clip(image_paths, clip_texts, clip_name)
        
        # DB 저장 (스케줄이 없더라도 History에 임시 저장 가능하도록 처리)
        from mbam_nextgen.backend.database import SessionLocal, PlaceNewsHistory
        db = SessionLocal()
        # Create a dummy or standalone history record
        history = PlaceNewsHistory(
            schedule_id="manual",
            generated_text=f"제목: {ai_result.get('title')}\n\n{ai_result.get('content')}",
            clip_path=clip_path,
            status="pending"
        )
        db.add(history)
        db.commit()
        history_id = history.id
        db.close()
        
        return {
            "success": True, 
            "ai_result": ai_result, 
            "clip_path": clip_path,
            "history_id": history_id
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/news/schedule")
def save_place_news_schedule(req: PlaceNewsScheduleRequest):
    try:
        from mbam_nextgen.backend.database import SessionLocal, PlaceNewsSchedule
        db = SessionLocal()
        
        sch = db.query(PlaceNewsSchedule).filter(PlaceNewsSchedule.place_url == req.place_url).first()
        if not sch:
            sch = PlaceNewsSchedule(
                place_url=req.place_url,
                place_name=req.place_name,
                interval_weeks=req.interval_weeks
            )
            db.add(sch)
        else:
            sch.interval_weeks = req.interval_weeks
            sch.place_name = req.place_name
            
        db.commit()
        db.close()
        return {"success": True, "message": "스케줄이 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/schedule")
def get_place_news_schedules():
    try:
        from mbam_nextgen.backend.database import SessionLocal, PlaceNewsSchedule
        db = SessionLocal()
        schedules = db.query(PlaceNewsSchedule).all()
        res = []
        for s in schedules:
            res.append({
                "id": s.id,
                "place_url": s.place_url,
                "place_name": s.place_name,
                "interval_weeks": s.interval_weeks,
                "last_run_time": s.last_run_time
            })
        db.close()
        return {"success": True, "schedules": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/history")
def get_place_news_history():
    try:
        from mbam_nextgen.backend.database import SessionLocal, PlaceNewsHistory, PlaceNewsSchedule
        db = SessionLocal()
        
        # Join to get place name
        histories = db.query(PlaceNewsHistory, PlaceNewsSchedule.place_name)\
                      .outerjoin(PlaceNewsSchedule, PlaceNewsHistory.schedule_id == PlaceNewsSchedule.id)\
                      .order_by(PlaceNewsHistory.created_at.desc())\
                      .limit(50).all()
                      
        res = []
        for h, place_name in histories:
            res.append({
                "id": h.id,
                "place_name": place_name or "수동생성",
                "generated_text": h.generated_text,
                "clip_path": h.clip_path,
                "status": h.status,
                "created_at": h.created_at
            })
        db.close()
        return {"success": True, "history": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
