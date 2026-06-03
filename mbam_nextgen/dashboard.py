import streamlit as st
import json, os, sys, asyncio, re, pandas as pd
from datetime import datetime, timedelta

# Streamlit Cache Reset and Hot Reload Trigger (2026-05-17 19:58)

# 서비스 클래스 임포트 (속도 최적화를 위해 최상단 이동)
from mbam_nextgen.runner import EngineRunner
from mbam_nextgen.infrastructure.db_ranking import RankingDB
from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
from mbam_nextgen.services.gov_data import GovDataCollector
from mbam_nextgen.services.seo_calculator import SeoCalculator
from mbam_nextgen.services.soul import SoulRewriter

# Naver Place MID & Keyword Auto-Collection Service
class NaverPlaceCrawler:
    """
    네이버 플레이스 MID 및 키워드 자동 수집 크롤러 (독립 프로세스 격리 엔진)
    """
    def __init__(self):
        import os
        # dashboard.py 파일 경로 기준으로 services/naver_crawler.py 경로를 빌드합니다.
        self.crawler_path = os.path.join(os.path.dirname(__file__), "services", "naver_crawler.py")
        self.log_path = os.path.join(os.path.dirname(__file__), "crawler_error.log")

    def fetch_place_by_mid(self, mid: str) -> dict:
        import subprocess
        import json
        import sys
        import traceback
        
        try:
            # sys.executable을 활용하여 현재와 동일한 가상 환경의 python 인터프리터로 독립 실행합니다.
            res = subprocess.run(
                [sys.executable, self.crawler_path, "detail", str(mid)],
                capture_output=True,
                check=True
            )
            # raw 바이트 캡처 후 안전하게 디코딩 수행 (UTF-8 우선 시도, 실패 시 CP949 폴백)
            try:
                stdout_str = res.stdout.decode("utf-8")
            except UnicodeDecodeError:
                stdout_str = res.stdout.decode("cp949", errors="ignore")
                
            data = json.loads(stdout_str)
            if data.get("success"):
                return data
            else:
                # If success is False or error present in json
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(f"[fetch_place_by_mid] Crawler returned failure JSON: {stdout_str}\n")
        except Exception as e:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[fetch_place_by_mid] Subprocess exception: {e}\n")
                f.write(traceback.format_exc() + "\n")
            print(f"[PlaceCrawler] Subprocess detail error: {e}")

        # Final fallback
        return {
            "success": False,
            "mid": mid,
            "name": "빕스 부산서면점" if mid == "11859846" else f"플레이스 매장 ({mid})",
            "category": "패밀리레스토랑",
            "visitor_reviews": 6823 if mid == "11859846" else 2450,
            "blog_reviews": 2573 if mid == "11859846" else 1050,
            "has_booking": True,
            "source": "simulated"
        }

    def search_keyword_ranking(self, keyword: str) -> list:
        import subprocess
        import json
        import sys
        import traceback

        try:
            res = subprocess.run(
                [sys.executable, self.crawler_path, "search", keyword],
                capture_output=True,
                check=True
            )
            try:
                stdout_str = res.stdout.decode("utf-8")
            except UnicodeDecodeError:
                stdout_str = res.stdout.decode("cp949", errors="ignore")
                
            data = json.loads(stdout_str)
            if isinstance(data, list):
                return data
            else:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(f"[search_keyword_ranking] Crawler returned unexpected: {stdout_str}\n")
        except Exception as e:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[search_keyword_ranking] Subprocess exception: {e}\n")
                f.write(traceback.format_exc() + "\n")
            print(f"[PlaceCrawler] Subprocess search error: {e}")

        return []

@st.cache_resource
def get_place_crawler():
    return NaverPlaceCrawler()

# ═══════════════════════════════════════
# 🛠️ 성능 최적화 (캐싱 처리)
# ═══════════════════════════════════════
@st.cache_resource
def get_runner(): return EngineRunner()

@st.cache_resource
def get_db(): return RankingDB()

@st.cache_resource
def get_analyzer(): return SeoAnalyzer()

@st.cache_resource
def get_soul(): return SoulRewriter()

@st.cache_resource
def get_seo_calculator(): return SeoCalculator()

@st.cache_resource
def get_collector(): return GovDataCollector()
if os.name == 'nt':
    import asyncio
    try:
        # Windows에서 서브프로세스(Playwright) 실행을 위해 Proactor 정책 필수
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except: pass
    
    # 콘솔 인코딩 문제 해결 (cp949 이모지 충돌 방지)
    try:
        if sys.stdout.encoding != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')
    except: pass

st.set_page_config(page_title="MBAM NextGen | SaaS Edition", layout="wide", page_icon="🚀")

# ═══════════════════════════════════════
# 🎨 SAAS PREMIUM UI DESIGN SYSTEM (최적화 - 인라인 복원)
# ═══════════════════════════════════════
def load_css():
    css_path = "mbam_nextgen/style.css"
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()
            return f"<style>{css_content}</style>"
    return ""

# 더욱 공격적인 셀렉터로 테두리 강제 적용
st.markdown("""
<style>
    /* 모든 종류의 입력 필드 외곽선 강제 적용 */
    div[data-baseweb="input"], 
    div[data-baseweb="select"], 
    div[data-baseweb="textarea"],
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox [data-baseweb="select"],
    .stNumberInput input {
        border: 1px solid #94a3b8 !important;
        border-radius: 8px !important;
        background-color: white !important;
    }
    /* --- SERP Structure List (Naver Style) --- */
    .serp-container { background: white; border-radius: 12px; border: 1px solid var(--border-color); overflow: hidden; margin-top: 1rem; }
    .serp-item { padding: 12px 20px; border-bottom: 1px solid #f1f5f9; cursor: pointer; transition: 0.2s; }
    .serp-item:hover { background: #f8fafb; }
    .serp-header { padding: 12px 20px; font-weight: 700; font-size: 0.95rem; display: flex; align-items: center; gap: 8px; }

    /* Section Colors */
    .serp-ad { background: #fffbeb; border-left: 5px solid #fbbf24; color: #92400e; }
    .serp-clip { background: #f5f3ff; border-left: 5px solid #8b5cf6; color: #5b21b6; }
    .serp-brand { background: #fff7ed; border-left: 5px solid #f97316; color: #9a3412; }
    .serp-blog { background: #f0fdf4; border-left: 5px solid #22c55e; color: #166534; }
    .serp-influencer { background: #fff7ed; border-left: 5px solid #f97316; color: #9a3412; }
    .serp-web { background: #ecfeff; border-left: 5px solid #06b6d4; color: #155e75; }
    .serp-shorts { background: #eef2ff; border-left: 5px solid #6366f1; color: #3730a3; }
    .serp-cafe { background: #fef9c3; border-left: 5px solid #eab308; color: #713f12; }
    .serp-related { background: #f0f9ff; border-left: 5px solid #0ea5e9; color: #075985; }

    .serp-sub-item { font-size: 0.85rem; color: var(--text-dim); padding: 4px 0; display: block; text-decoration: none; }
    .serp-sub-item:hover { color: var(--accent); text-decoration: underline; }
</style>
""", unsafe_allow_html=True)
st.markdown(load_css(), unsafe_allow_html=True)

# ═══════════════════════════════════════
# 세션/서비스 로드 (최적화 버전)
# ═══════════════════════════════════════
runner = get_runner()
db = get_db()
analyzer = get_analyzer()
soul = get_soul()
collector = get_collector()
seo_calc = get_seo_calculator()

# 사용자 설정 저장 파일 로드
USER_SETTINGS_PATH = "mbam_nextgen/data/user_settings.json"
os.makedirs("mbam_nextgen/data", exist_ok=True)

@st.cache_data
def load_user_settings():
    if os.path.exists(USER_SETTINGS_PATH):
        try:
            with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_user_settings():
    settings = {
        "accounts": st.session_state.accounts,
        "saved_keywords": st.session_state.saved_keywords
    }
    with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    st.cache_data.clear() # 설정 변경 시 캐시 갱신

user_settings = load_user_settings()

if "accounts" not in st.session_state:
    st.session_state.accounts = user_settings.get("accounts", [{"id": "ch_2101", "name": "메인 계정", "proxy": None}])

if "saved_keywords" not in st.session_state:
    st.session_state.saved_keywords = user_settings.get("saved_keywords", ["경제블로그", "재테크", "정부지원금", "창업"])

# ═══════════════════════════════════════
# 사이드바 (캐시플랜 스타일 프로필 적용)
# ═══════════════════════════════════════
with st.sidebar:
    # 프로필 카드
    st.markdown(f"""
    <div class="profile-box">
        <div class="user-info">
            <div class="avatar">하마</div>
            <div>
                <div class="name">김재호 대표님</div>
                <div class="email">premium_user@naver.com</div>
            </div>
        </div>
        <div class="quick-action-btn">🚀 오늘 작업 시작</div>
    </div>
    """, unsafe_allow_html=True)
    
    page = st.radio("메뉴 선택", ["🏠 대시보드", "📰 글감 수집", "📈 SEO 분석", "📈 플레이스 SEO 진단", "🛡️ 블로그 진단 & 순위", "📝 블로그", "☕ 카페", "🤝 소통 & 이웃", "👥 멀티 실행", "⚙️ 설정", "📊 로그"], label_visibility="collapsed")
    
    st.markdown("---")
    s_map = {"idle": ("엔진 대기", "chip-idle"), "running": ("자동화 가동 중", "chip-run"), "completed": ("작업 완료", "chip-ok"), "error": ("확인 필요", "chip-err")}
    lbl, cls = s_map.get(runner.status, ("대기", "chip-idle"))
    st.markdown(f'<div style="padding:0 20px;"><span class="chip {cls}">● {lbl}</span></div>', unsafe_allow_html=True)


# ═══════════════════════════════════════
# 🏠 대시보드 (캐시플랜 상단 메트릭 적용)
# ═══════════════════════════════════════
if page == "🏠 대시보드":
    st.markdown('<div class="ph"><div><h1>전체 현황</h1><p>오늘까지 완료된 자동화 미션과 성과를 확인하세요</p></div></div>', unsafe_allow_html=True)
    
    logs = runner.get_logs()
    sc = 0
    for l in logs:
        res = l.get("result", {})
        if isinstance(res, dict) and res.get("success"):
            sc += 1
        elif isinstance(res, list):
            if any(item.get("success") for item in res if isinstance(item, dict)):
                sc += 1
    
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        ("총 등록 계정", f"{len(st.session_state.accounts)}개", "Active"),
        ("오늘 실행 미션", f"{len(logs)}건", f"+{len(logs)} today"),
        ("성공적인 작업", f"{sc}건", "Success Rate High"),
        ("대기 중인 예약", "0건", "All clear")
    ]
    for col, (lbl, val, sub) in zip([c1,c2,c3,c4], cards):
        with col:
            st.markdown(f'<div class="m-card"><div class="lbl">{lbl}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("#### 📋 최근 실행 기록")
    if logs:
        for log in logs[:5]:
            r = log.get("result", {})
            if isinstance(r, list):
                # 멀티 실행인 경우 첫 번째 계정 정보 표시
                main_r = r[0] if r else {}
                acc_id = f"멀티 ({len(r)}개)"
                kw = main_r.get("keyword", "N/A")
                ok = all(item.get("success") for item in r if isinstance(item, dict))
            else:
                acc_id = r.get("account_id", "N/A")
                kw = r.get("keyword", "N/A")
                ok = r.get("success", False)
            
            chip = '<span class="chip chip-ok">✅ 성공</span>' if ok else '<span class="chip chip-err">❌ 실패</span>'
            st.markdown(f'''<div class="log-row">
                <span style="color:var(--text-main);font-weight:600;">{acc_id}</span>
                <span style="color:var(--text-dim);">{kw}</span>
                <span style="color:var(--text-dim);font-size:0.8rem;">{log.get("timestamp","")}</span>
                {chip}
            </div>''', unsafe_allow_html=True)
    else:
        st.info("아직 실행 기록이 없습니다. 블로그 또는 카페 포스팅을 시작해 보세요!")

# ═══════════════════════════════════════
# 📝 블로그
# ═══════════════════════════════════════
elif page == "📝 블로그":
    st.markdown('<div class="ph"><h1>블로그 포스팅</h1><p>네이버 블로그에 AI 원고를 자동으로 작성합니다</p></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<div class="s-card"><h3>📌 기본 설정</h3>', unsafe_allow_html=True)
        acc_ids = [a["id"] for a in st.session_state.accounts]
        sel_acc = st.selectbox("계정", acc_ids)
        default_kw = st.session_state.get("selected_gov", {}).get("title", "정부지원금") if st.session_state.get("selected_gov") else "정부지원금"
        kw = st.text_input("키워드", value=default_kw)
        if st.session_state.get("selected_gov"):
            st.caption(f"📰 선택된 글감: {st.session_state.selected_gov.get('title', '')}")
        ca, cb = st.columns(2)
        with ca: sp_mode = st.selectbox("타이핑 모드", ["slow","normal","fast"], index=1)
        with cb: sp_mult = st.slider("속도 배수", 0.3, 3.0, 0.5, 0.1)
        use_img = st.checkbox("🖼️ 이미지 첨부", value=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with c2:
        st.markdown('<div class="s-card"><h3>📤 발행 설정</h3>', unsafe_allow_html=True)
        pub = st.radio("발행 방식", ["수동", "즉시 발행", "예약 발행"])
        pub_map = {"수동": "none", "즉시 발행": "now", "예약 발행": "schedule"}
        s_date = s_time = None
        if pub == "예약 발행":
            s_date = st.date_input("날짜", value=datetime.now() + timedelta(days=1))
            s_time = st.time_input("시간", value=datetime.strptime("10:00", "%H:%M").time())
        st.markdown('</div>', unsafe_allow_html=True)
        
        with st.expander("🔒 프록시 (선택)"):
            proxy = st.text_input("프록시 URL", placeholder="socks5://user:pass@host:port") or None
    
    st.markdown("")
    if st.button("🚀 블로그 포스팅 실행", use_container_width=True, disabled=runner.is_running()):
        if not sel_acc:
            st.error("❌ 계정을 선택해주세요.")
        else:
            runner.run_blog({
                "account_id": sel_acc,
                "keyword": kw,
                "publish_mode": pub_map[pub],
                "speed_mode": sp_mode,
                "speed_multiplier": sp_mult,
                "proxy": proxy,
                "test_image": "mbam_nextgen/test_image.jpg" if use_img else None,
                "schedule_date": str(s_date) if s_date else None,
                "schedule_time": str(s_time) if s_time else None,
            })
            st.success("🚀 엔진이 시작되었습니다! 잠시 후 브라우저가 나타납니다.")
            st.rerun()

# ═══════════════════════════════════════
# ☕ 카페
# ═══════════════════════════════════════
elif page == "☕ 카페":
    st.markdown('<div class="ph"><h1>카페 포스팅</h1><p>네이버 카페에 AI 원고를 자동으로 작성합니다</p></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<div class="s-card"><h3>📌 카페 설정</h3>', unsafe_allow_html=True)
        acc_ids = [a["id"] for a in st.session_state.accounts]
        sel_acc = st.selectbox("계정", acc_ids, key="cf_acc")
        cafe_id = st.text_input("카페 ID", placeholder="예: joonggonara")
        board = st.text_input("게시판", placeholder="예: 자유게시판")
        kw = st.text_input("키워드", value="정부지원금", key="cf_kw")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="s-card"><h3>⚡ 실행 옵션</h3>', unsafe_allow_html=True)
        sp_mode = st.selectbox("타이핑 모드", ["slow","normal","fast"], index=1, key="cf_sp")
        sp_mult = st.slider("속도 배수", 0.3, 3.0, 0.5, 0.1, key="cf_m")
        auto_sub = st.checkbox("✅ 자동 등록", value=False)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("")
    if st.button("☕ 카페 포스팅 실행", use_container_width=True, disabled=runner.is_running()):
        runner.run_cafe({"account_id": sel_acc, "cafe_id": cafe_id, "board_name": board, "keyword": kw, "speed_mode": sp_mode, "speed_multiplier": sp_mult, "auto_submit": auto_sub, "proxy": None})
        st.success("☕ 카페 엔진이 실행되었습니다!")
        st.rerun()

# ═══════════════════════════════════════
# 🤝 소통 & 이웃
# ═══════════════════════════════════════
elif page == "🤝 소통 & 이웃":
    st.markdown('<div class="ph"><h1>블로그 소통 및 이웃 관리</h1><p>타겟 키워드 유저들과 자동으로 소통하며 블로그를 키웁니다</p></div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<div class="s-card"><h3>🎯 타겟팅 설정</h3>', unsafe_allow_html=True)
        acc_ids = [a["id"] for a in st.session_state.accounts]
        sel_acc = st.selectbox("실행 계정", acc_ids)
        
        # 소통 키워드 관리 (현장에서 즉시 수정/추가)
        kw_list = st.session_state.saved_keywords
        c_sel, c_add = st.columns([3, 1])
        with c_sel:
            sel_kw = st.selectbox("소통 키워드 선택", kw_list + ["직접 입력"] if kw_list else ["직접 입력"])
        
        with c_add:
            st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
            if sel_kw != "직접 입력" and st.button("🗑️", help="선택한 키워드 삭제"):
                st.session_state.saved_keywords.remove(sel_kw)
                save_user_settings()
                st.rerun()

        if sel_kw == "직접 입력":
            c_in, c_save = st.columns([3, 1])
            with c_in:
                new_kw = st.text_input("새 키워드 입력", placeholder="예: 경제블로그")
            with c_save:
                st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
                if st.button("➕", help="키워드 리스트에 추가"):
                    if new_kw and new_kw not in st.session_state.saved_keywords:
                        st.session_state.saved_keywords.append(new_kw)
                        save_user_settings()
                        st.rerun()
            kw = new_kw
        else:
            kw = sel_kw
            
        limit = st.slider("최대 작업 수", 1, 30, 5)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with c2:
        st.markdown('<div class="s-card"><h3>⚙️ 소통 옵션</h3>', unsafe_allow_html=True)
        do_like = st.checkbox("❤️ 공감 누르기", value=True)
        do_comment = st.checkbox("💬 댓글 달기 (AI 자동생성)", value=True)
        c_msg = st.text_area("댓글 메시지 (비워두면 AI 자동생성)", value="", placeholder="블로그 잘 보고 갑니다! 자주 소통해요 :)")
        do_neighbor = st.checkbox("🤝 서로이웃 신청", value=True)
        n_msg = st.text_area("이웃 신청 메시지", value="포스팅 잘 보고 갑니다! 서로이웃 하고 소통하며 지내요 :)")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 소통 자동화 시작", use_container_width=True, disabled=runner.is_running()):
        if not kw:
            st.error("❌ 소통할 키워드를 입력하거나 선택해주세요.")
        else:
            runner.run_engagement({
                "account_id": sel_acc,
                "keyword": kw,
                "limit": limit,
                "do_like": do_like,
                "do_comment": do_comment,
                "comment_msg": c_msg,
                "do_neighbor": do_neighbor,
                "neighbor_msg": n_msg,
                "proxy": None
            })
            st.success(f"🚀 {sel_acc} 계정으로 '{kw}' 소통 작업을 시작합니다!")
            st.rerun()

    st.markdown("---")
    st.markdown('<div class="s-card"><h3>🎯 소통 키워드 관리</h3>', unsafe_allow_html=True)
    new_kw_m = st.text_input("새 키워드 추가", placeholder="예: 맛집탐방, 일상", key="m_new_kw")
    if st.button("추가", key="m_add_kw"):
        if new_kw_m and new_kw_m not in st.session_state.saved_keywords:
            st.session_state.saved_keywords.append(new_kw_m)
            save_user_settings()
            st.rerun()
    
    st.markdown("##### 현재 저장된 키워드")
    cols = st.columns(3)
    for i, k in enumerate(st.session_state.saved_keywords):
        with cols[i % 3]:
            st.markdown(f"""
            <div style="background:#f8fafb; padding:8px 12px; border-radius:8px; display:flex; justify-content:space-between; align-items:center; border:1px solid var(--border-color); margin-bottom:8px;">
                <span style="font-size:0.9rem;">{k}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("삭제", key=f"m_del_kw_{i}"):
                st.session_state.saved_keywords.pop(i)
                save_user_settings()
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════
# 👥 멀티 실행
# ═══════════════════════════════════════
elif page == "👥 멀티 실행":
    st.markdown('<div class="ph"><h1>멀티 계정 실행</h1><p>여러 계정을 순차 실행하여 대량 포스팅합니다</p></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="s-card"><h3>🎯 공통 설정</h3>', unsafe_allow_html=True)
    kw = st.text_input("공통 키워드", value="정부지원금")
    c1, c2 = st.columns(2)
    with c1: pub = st.selectbox("발행 방식", ["none","now","schedule"], key="mp")
    with c2: sp = st.slider("속도 배수", 0.3, 3.0, 0.5, 0.1, key="ms")
    c3, c4 = st.columns(2)
    with c3: mn = st.number_input("최소 대기(초)", value=180, min_value=30, step=30)
    with c4: mx = st.number_input("최대 대기(초)", value=600, min_value=60, step=60)
    
    use_tether = st.checkbox("📱 USB 테더링 IP 자동 전환", value=False, help="계정 전환 시마다 휴대폰 비행기 모드를 토글하여 IP를 바꿉니다.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("#### 실행할 계정")
    sel = []
    for acc in st.session_state.accounts:
        if st.checkbox(f"🦛 {acc['id']} ({acc.get('name','')})", value=True, key=f"m_{acc['id']}"):
            sel.append(acc)
    
    st.markdown("")
    if st.button(f"🚀 {len(sel)}개 계정 순차 실행", use_container_width=True, disabled=runner.is_running() or not sel):
        accs = [{"id": a["id"], "keyword": kw, "publish_mode": pub, "proxy": a.get("proxy")} for a in sel]
        runner.run_multi(accs, {
            "speed_mode": "normal", 
            "speed_multiplier": sp, 
            "min_delay": mn, 
            "max_delay": mx,
            "use_tethering": use_tether
        })
        st.success(f"🚀 {len(sel)}개 계정 실행 시작!")
        st.rerun()

# ═══════════════════════════════════════
# ⚙️ 설정
# ═══════════════════════════════════════
elif page == "⚙️ 설정":
    st.markdown('<div class="ph"><h1>설정</h1><p>계정, 프록시, API 키를 관리합니다</p></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="s-card"><h3>👤 계정 관리</h3>', unsafe_allow_html=True)
    for i, acc in enumerate(st.session_state.accounts):
        c1, c2, c3, c4 = st.columns([3,2,3,1])
        with c1: st.session_state.accounts[i]["id"] = st.text_input("ID", value=acc["id"], key=f"ai_{i}")
        with c2: st.session_state.accounts[i]["name"] = st.text_input("별칭", value=acc.get("name",""), key=f"an_{i}")
        with c3: st.session_state.accounts[i]["proxy"] = st.text_input("프록시", value=acc.get("proxy") or "", key=f"ap_{i}") or None
        with c4:
            st.markdown("")
            if st.button("🗑️", key=f"d_{i}"):
                st.session_state.accounts.pop(i); save_user_settings(); st.rerun()
    if st.button("➕ 계정 추가"):
        st.session_state.accounts.append({"id": "", "name": "", "proxy": None}); save_user_settings(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown('<div class="s-card"><h3>📱 USB 테더링 설정</h3>', unsafe_allow_html=True)
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.write("안드로이드 휴대폰을 USB로 연결하고 'USB 디버깅'을 켜주세요.")
    with col_t2:
        if st.button("장치 연결 확인", use_container_width=True):
            from mbam_nextgen.infrastructure.tethering import TetheringManager
            tm = TetheringManager()
            ok, devs = tm.check_device()
            if ok:
                st.success(f"연결됨: {devs[0]}")
            else:
                st.error("인식된 장치 없음")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # env 먼저 로드
    env_path = "mbam_nextgen/.env"
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if "=" in line: k,v = line.strip().split("=",1); env[k] = v
    
    st.markdown('<div class="s-card"><h3>🤖 AI 모델 선택</h3>', unsafe_allow_html=True)
    ai_models = ["Gemini 2.5 Flash", "Claude (Anthropic)", "ChatGPT (OpenAI)"]
    current_model = env.get("AI_MODEL", "Gemini 2.5 Flash")
    sel_model = st.selectbox("원고 생성에 사용할 AI", ai_models, index=ai_models.index(current_model) if current_model in ai_models else 0)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="s-card"><h3>🔑 API 키 관리</h3>', unsafe_allow_html=True)
    
    gk = st.text_input("Gemini API Key", value=env.get("GEMINI_API_KEY",""), type="password")
    ck = st.text_input("Claude API Key (Anthropic)", value=env.get("CLAUDE_API_KEY",""), type="password")
    ok = st.text_input("OpenAI API Key (ChatGPT)", value=env.get("OPENAI_API_KEY",""), type="password")
    
    st.markdown("---")
    gdk = st.text_input("공공데이터포털 API Key (선택)", value=env.get("GOV_DATA_API_KEY",""), type="password", help="data.go.kr에서 무료 발급")
    
    if st.button("💾 전체 저장"):
        save_user_settings() # 계정 및 키워드 저장
        with open(env_path, "w") as f:
            f.write(f"AI_MODEL={sel_model}\n")
            if gk: f.write(f"GEMINI_API_KEY={gk}\n")
            if ck: f.write(f"CLAUDE_API_KEY={ck}\n")
            if ok: f.write(f"OPENAI_API_KEY={ok}\n")
            if gdk: f.write(f"GOV_DATA_API_KEY={gdk}\n")
        st.success("✅ 모든 설정이 저장되었습니다!")
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════
# 📊 로그
# ═══════════════════════════════════════
elif page == "📊 로그":
    st.markdown('<div class="ph"><h1>실행 로그</h1><p>자동화 엔진의 실행 기록을 확인합니다</p></div>', unsafe_allow_html=True)
    logs = runner.get_logs(limit=50)
    if logs:
        for log in logs:
            r = log.get("result", {})
            # 결과가 리스트(멀티 계정)인지 사전(단일 계정)인지 확인
            if isinstance(r, list):
                ok = any(item.get("success") for item in r if isinstance(item, dict))
                label = f"👥 멀티 계정 실행 ({len(r)}건)"
                keyword = r[0].get("keyword", "N/A") if r else "N/A"
                acc_id = "Multi"
            else:
                ok = r.get("success", False) if isinstance(r, dict) else False
                label = f"{r.get('account_id','N/A')}" if isinstance(r, dict) else "Unknown"
                keyword = r.get("keyword", "N/A") if isinstance(r, dict) else "N/A"
                acc_id = label

            with st.expander(f"{'✅' if ok else '❌'} {label} | {keyword} | {log.get('timestamp','')}"):
                st.json(r)
    else:
        st.info("아직 실행 기록이 없습니다.")

# ═══════════════════════════════════════
# 📰 글감 수집
# ═══════════════════════════════════════
elif page == "📰 글감 수집":
    st.markdown('<div class="ph"><h1>글감 수집</h1><p>매일 오전 9시 전체 자동 수집 | 현재는 캐시된 데이터를 즉시 활용합니다</p></div>', unsafe_allow_html=True)

    # 왼쪽 카테고리 / 오른쪽 데이터 구조
    col_cat, col_data = st.columns([1, 4])

    with col_cat:
        st.markdown("#### 📂 카테고리")
        selected_cat = st.radio("분류", list(collector.CATEGORIES.keys()), label_visibility="collapsed")
        
        # 전체 시스템 동기화 상태 확인
        sched_file = "mbam_nextgen/data/scheduler_state.json"
        full_sync_time = "기록 없음"
        if os.path.exists(sched_file):
            try:
                with open(sched_file, "r") as f:
                    data = json.load(f)
                    st_time = data.get("last_success", "")
                    if st_time:
                        full_sync_time = datetime.fromisoformat(st_time).strftime("%m-%d %H:%M")
            except: pass
            
        st.markdown(f"""
        <div style="background:#f1f5f9; padding:12px; border-radius:10px; margin: 10px 0; border: 1px solid var(--border-color);">
            <div style="font-size:0.7rem; color:var(--text-dim); text-transform:uppercase;">전체 시스템 동기화</div>
            <div style="font-size:0.9rem; font-weight:700; color:var(--accent);">{full_sync_time}</div>
        </div>
        """, unsafe_allow_html=True)
        
        last_sync = collector.get_cache_time(selected_cat)
        st.markdown(f"""
        <div style="background:white; padding:12px; border-radius:10px; margin: 10px 0; border: 1px solid var(--border-color);">
            <div style="font-size:0.7rem; color:var(--text-dim); text-transform:uppercase;">선택 카테고리 업데이트</div>
            <div style="font-size:0.85rem; font-weight:600;">{last_sync}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("🔄 현재 항목 실시간 수집", use_container_width=True):
            with st.spinner(f"{selected_cat} 데이터 수집 중..."):
                loop = asyncio.new_event_loop()
                data = loop.run_until_complete(collector.fetch_data(selected_cat))
                loop.close()
                collector.save_cache(selected_cat, data)
                st.success(f"✅ {len(data)}건 수집 완료!")
                st.rerun()
        
        st.caption(f"마지막 수집: {collector.get_cache_time(selected_cat)}")

    with col_data:
        st.markdown(f"### 📋 {selected_cat} 목록")
        
        # 검색바
        c_search, c_btn, c_reset = st.columns([3, 1, 1])
        with c_search: search_query = st.text_input("검색어", placeholder="강좌명, 기관명 등 검색...", label_visibility="collapsed")
        with c_btn: st.button("검색", use_container_width=True)
        with c_reset: st.button("초기화", use_container_width=True)

        items = collector.load_cache(selected_cat) or collector.SAMPLE_DATA
        filtered_items = [i for i in items if i.get("category") == selected_cat]
        if search_query:
            filtered_items = [i for i in filtered_items if search_query.lower() in str(i).lower()]

        filtered_items.sort(key=lambda x: x.get("priority", 99))

        if not filtered_items:
            st.info(f"'{selected_cat}' 카테고리에 데이터가 없습니다. 수집 버튼을 눌러주세요.")
        else:
            for item in filtered_items:
                source = item.get("source", "-")
                deadline = item.get("deadline", "상시")
                priority_val = item.get("priority", 99)
                
                priority_badge = ""
                if priority_val == 1: priority_badge = "🆕[최신/혜택] "
                elif priority_val == 2: priority_badge = "🔥[트렌드] "
                elif priority_val == 3: priority_badge = "🚨[긴급성] "
                
                extra_info = ""
                if "professor" in item: extra_info += f" | 교수: {item['professor']}"
                if "region" in item: extra_info += f" | 지역: {item['region']}"

                with st.expander(f"{priority_badge}📌 {item['title']} ({source}){extra_info} | {deadline}"):
                    st.markdown(f"**기관**: {source}")
                    if "target" in item: st.markdown(f"**대상**: {item['target']}")
                    if "amount" in item: st.markdown(f"**지원내용**: {item['amount']}")
                    
                    st.markdown("---")
                    bc, cc = st.columns(2)
                    with bc:
                        if st.button(f"📝 블로그 작성", key=f"blog_{item['id']}"):
                            st.session_state.selected_gov = item
                            st.success(f"'{item['title']}' 주제로 블로그 작성을 준비합니다.")
                    with cc:
                        if st.button(f"☕ 카페 작성", key=f"cafe_{item['id']}"):
                            st.session_state.selected_gov = item
                            st.success(f"'{item['title']}' 주제로 카페 작성을 준비합니다.")

# ═══════════════════════════════════════
# 📈 SEO 분석
# ═══════════════════════════════════════
elif page == "📈 SEO 분석":
    st.markdown('<div class="ph"><h1>SEO 상위노출 분석</h1><p>타겟 키워드 경쟁 데이터를 정밀 분석하여 우승 공식을 도출합니다</p></div>', unsafe_allow_html=True)
    
    # 상태 관리 초기화
    if "seo_keyword" not in st.session_state: st.session_state.seo_keyword = ""
    if "seo_results" not in st.session_state: st.session_state.seo_results = None
    if "serp_struct" not in st.session_state: st.session_state.serp_struct = None
    if "selected_urls" not in st.session_state: st.session_state.selected_urls = []
    if "batch_analysis_results" not in st.session_state: st.session_state.batch_analysis_results = {}
    if "cafe_generated_post" not in st.session_state: st.session_state.cafe_generated_post = ""

    kw_input = st.text_input("분석 키워드", value=st.session_state.seo_keyword, placeholder="예: 부산맛집, 전포동맛집")
    
    if st.button("🚀 분석 시작", use_container_width=True):
        if kw_input:
            with st.spinner(f"'{kw_input}' 검색 환경 및 경쟁 데이터 분석 중..."):
                st.session_state.seo_keyword = kw_input
                st.session_state.selected_urls = []
                st.session_state.batch_analysis_results = {}
                try:
                    loop = asyncio.new_event_loop()
                    st.session_state.serp_struct = loop.run_until_complete(analyzer.analyze_serp_structure(kw_input))
                    st.session_state.seo_results = loop.run_until_complete(analyzer.analyze_keyword(kw_input))
                    loop.close()
                except Exception as e:
                    st.error(f"분석 중 오류 발생: {e}")
                st.rerun()
    
    if st.session_state.serp_struct:
        res = st.session_state.seo_results
        st.markdown("---")
        
        # 월간 조회수 표시 (메인 키워드)
        main_vol = next((v for v in res.get("kw_volumes", []) if v['keyword'] == st.session_state.seo_keyword), None) if res else None
        if main_vol:
            st.markdown(f"""
            <div style="background:#f0fdf4; padding:12px 20px; border-radius:10px; border:1px solid #22c55e; margin-bottom:20px; display:flex; gap:20px; align-items:center;">
                <span style="font-size:1.1rem; font-weight:700; color:#166534;">🔍 {st.session_state.seo_keyword}</span>
                <span style="color:#15803d; font-weight:600;">월검색 <span style="font-size:1.3rem;">{main_vol['total']:,}</span></span>
                <span style="background:#dcfce7; color:#166534; padding:4px 10px; border-radius:20px; font-size:0.8rem; font-weight:700;">경쟁 보통</span>
            </div>
            """, unsafe_allow_html=True)
        

        # ─── 기간별 블로그 포스팅 수 분석 섹션 ───────────────────────────
        with st.expander("📊 기간별 블로그 포스팅 수 분석", expanded=False):
            st.markdown("#### 📊 키워드별 블로그 포스팅 수 (기간 설정)")
            from datetime import date, timedelta

            bc_col1, bc_col2, bc_col3 = st.columns([2, 1, 1])
            with bc_col1:
                bc_keyword = st.text_input(
                    "분석 키워드",
                    value=st.session_state.get("seo_keyword", ""),
                    placeholder="예: 인천공항 주차대행",
                    key="bc_keyword_input"
                )
            with bc_col2:
                bc_preset = st.selectbox(
                    "기간 선택",
                    ["직접 입력", "최근 1주", "최근 1개월", "최근 3개월", "최근 6개월", "최근 1년"],
                    key="bc_preset_select"
                )
            with bc_col3:
                bc_run = st.button("🔍 포스팅 수 조회", use_container_width=True, key="bc_run_btn", type="primary")

            # 날짜 범위 계산
            today = date.today()
            preset_map = {
                "최근 1주":   (today - timedelta(weeks=1),    today),
                "최근 1개월": (today - timedelta(days=30),    today),
                "최근 3개월": (today - timedelta(days=90),    today),
                "최근 6개월": (today - timedelta(days=180),   today),
                "최근 1년":   (today - timedelta(days=365),   today),
            }

            if bc_preset == "직접 입력":
                dc1, dc2 = st.columns(2)
                with dc1:
                    bc_start = st.date_input("시작일", value=today - timedelta(days=30), key="bc_start_date")
                with dc2:
                    bc_end = st.date_input("종료일", value=today, key="bc_end_date")
            else:
                bc_start, bc_end = preset_map[bc_preset]
                st.caption(f"📅 기간: {bc_start.strftime('%Y.%m.%d')} ~ {bc_end.strftime('%Y.%m.%d')}")

            if bc_run and bc_keyword:
                with st.spinner(f"'{bc_keyword}' 블로그 포스팅 수 수집 중..."):
                    try:
                        loop = asyncio.new_event_loop()
                        bc_result = loop.run_until_complete(
                            analyzer.get_blog_post_count(
                                keyword=bc_keyword,
                                start_date=bc_start.strftime("%Y%m%d"),
                                end_date=bc_end.strftime("%Y%m%d"),
                            )
                        )
                        loop.close()
                        st.session_state["bc_result"] = bc_result
                    except Exception as e:
                        st.error(f"조회 오류: {e}")

            if st.session_state.get("bc_result"):
                bcr = st.session_state["bc_result"]

                if bcr.get("error"):
                    st.error(f"수집 오류: {bcr['error']}")
                else:
                    # 핵심 지표
                    bc_m1, bc_m2, bc_m3 = st.columns(3)
                    total = bcr.get("total_count", 0)
                    days = (bc_end - bc_start).days or 1

                    # 경쟁 강도 판정
                    if total < 1000:        difficulty, diff_color = "낮음 (공략 용이)", "#10b981"
                    elif total < 10000:     difficulty, diff_color = "보통", "#f59e0b"
                    elif total < 100000:    difficulty, diff_color = "높음", "#f97316"
                    else:                   difficulty, diff_color = "매우 높음 (레드오션)", "#ef4444"

                    bc_m1.metric("📝 총 포스팅 수", f"{total:,}개")
                    bc_m2.metric("📅 일평균 포스팅", f"{total // days:,}개/일")
                    bc_m3.metric("🏁 수집 방법", bcr.get("method", "—"))

                    st.markdown(
                        f'<div style="background:{diff_color}22;border:1px solid {diff_color};'
                        f'padding:10px 16px;border-radius:10px;margin:10px 0;">'
                        f'<span style="color:{diff_color};font-weight:700;font-size:0.95rem;">'
                        f'⚔️ 경쟁 강도: {difficulty}</span>'
                        f'<span style="color:#64748b;font-size:0.82rem;margin-left:10px;">'
                        f'(기간 내 블로그 포스팅 수 기준)</span></div>',
                        unsafe_allow_html=True
                    )

                    # 추이 차트
                    trend = bcr.get("trend", [])
                    if trend and len(trend) > 1:
                        import pandas as pd
                        df_trend = pd.DataFrame(trend)
                        if "count" in df_trend.columns and "period" in df_trend.columns:
                            st.markdown("**📈 기간별 포스팅 수 추이**")
                            st.bar_chart(df_trend.set_index("period")["count"])

                    # 최근 포스팅 샘플
                    recent = bcr.get("recent_posts", [])
                    if recent:
                        st.markdown("**📋 최근 포스팅 샘플**")
                        for rp in recent[:5]:
                            rp_title = rp.get("title", "")[:55]
                            rp_url = rp.get("url", "")
                            rp_date = rp.get("date", "")
                            rp_blogger = rp.get("blogger", "")
                            st.markdown(
                                f'<div style="padding:8px 12px;background:#f8fafc;border-radius:8px;'
                                f'border-left:3px solid #6366f1;margin-bottom:6px;">'
                                f'<a href="{rp_url}" target="_blank" style="color:#1e293b;text-decoration:none;font-weight:600;">{rp_title}</a>'
                                f'<span style="color:#94a3b8;font-size:0.78rem;margin-left:8px;">{rp_date} · {rp_blogger}</span>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

                    # CSV 다운로드
                    import io, csv
                    buf = io.StringIO()
                    w = csv.writer(buf)
                    w.writerow(["키워드", "시작일", "종료일", "총포스팅수", "일평균", "경쟁강도"])
                    w.writerow([bc_keyword, str(bc_start), str(bc_end), total, total//days, difficulty])
                    if trend:
                        w.writerow([])
                        w.writerow(["기간", "포스팅수"])
                        for t in trend:
                            w.writerow([t.get("period",""), t.get("count",0)])
                    st.download_button(
                        "⬇️ 결과 CSV 다운로드",
                        data=buf.getvalue().encode("utf-8-sig"),
                        file_name=f"blog_count_{bc_keyword}_{bc_start}.csv",
                        mime="text/csv",
                        key="bc_dl_csv"
                    )
        # ─────────────────────────────────────────────────────────────────


        col_serp, col_detail = st.columns([1, 1.2])
        
        with col_serp:
            st.markdown("#### 🧩 키워드 웹 구조 분석")
            st.markdown('<div class="serp-container">', unsafe_allow_html=True)
            for si, s in enumerate(st.session_state.serp_struct.get("sections", [])):
                s_type = s['type']  # 한글 타입명 그대로 사용
                icon_map = {
                    "AD": "📢", "클립": "🎥", "브랜드": "💎",
                    "블로그": "📝", "인플루언서": "👤", "카페인기글": "☕",
                    "뉴스": "📰", "웹문서": "🌐", "동영상": "📺",
                    "쇼핑": "🛒", "지식iN": "💡", "플레이스": "📍", "일반": "📌"
                }
                css_map = {
                    "AD": "ad", "클립": "clip", "브랜드": "brand",
                    "블로그": "blog", "인플루언서": "influencer", "카페인기글": "cafe",
                    "뉴스": "web", "웹문서": "web", "동영상": "shorts",
                    "쇼핑": "web", "지식iN": "web", "플레이스": "web", "일반": "web"
                }
                icon = icon_map.get(s_type, "📌")
                css_cls = css_map.get(s_type, "web")
                cnt = s.get('count', len(s.get('items', [])))
                st.markdown(f'<div class="serp-header serp-{css_cls}">{icon} {s["title"]} <span style="font-size:0.75rem;opacity:0.7;margin-left:6px;">({cnt})</span></div>', unsafe_allow_html=True)
                for ii, item in enumerate(s.get("items", [])):
                    is_selected = item['url'] in st.session_state.selected_urls
                    check_icon = "✅" if is_selected else "⬜"
                    # 섹션 인덱스(si) + 아이템 인덱스(ii) 조합으로 key 고유성 보장
                    btn_key = f"sel_{si}_{ii}"
                    if st.button(f"{check_icon} {item['text'][:35]}...", key=btn_key, use_container_width=True):
                        if item['url'] in st.session_state.selected_urls:
                            st.session_state.selected_urls.remove(item['url'])
                        else:
                            st.session_state.selected_urls.append(item['url'])
                        st.rerun()
            
            st.markdown('<div class="serp-header serp-related">💡 함께 많이 찾는 검색어</div>', unsafe_allow_html=True)
            for rk in st.session_state.serp_struct.get("related", []):
                if st.button(f"🔍 {rk}", key=f"rk_{rk}", use_container_width=True):
                    st.session_state.seo_keyword = rk
                    st.session_state.serp_struct = None
                    st.session_state.seo_results = None
                    st.session_state.selected_urls = []
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ── 분석 버튼 (선택 항목이 있으면 항상 표시) ──
            if st.session_state.selected_urls:
                sel_count = len(st.session_state.selected_urls)
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);'
                    f'padding:10px 16px;border-radius:10px;margin:10px 0;text-align:center;">'
                    f'<span style="color:white;font-weight:700;">체크 {sel_count}개 선택됨</span></div>',
                    unsafe_allow_html=True
                )
                col_btn_a, col_btn_b = st.columns(2)
                with col_btn_a:
                    if st.button("🔬 선택 포스팅 분석", type="primary", use_container_width=True, key="do_analyze_btn"):
                        with st.spinner(f"{sel_count}개 포스팅 수집 및 분석 중..."):
                            try:
                                loop = asyncio.new_event_loop()
                                texts_for_ai = []
                                valid_metrics = []
                                urls_to_fetch = [u for u in st.session_state.selected_urls if u not in st.session_state.batch_analysis_results]
                                if urls_to_fetch:
                                    new_results = loop.run_until_complete(analyzer.analyze_multiple_urls(urls_to_fetch))
                                    st.session_state.batch_analysis_results.update(new_results)

                                def enrich_detail(detail):
                                    if "error" in detail or not detail.get("full_text"):
                                        return detail
                                    if "total_char" not in detail:
                                        full_text = detail["full_text"]
                                        detail["total_char"] = len(full_text)
                                        detail["space_count"] = full_text.count(" ")
                                        detail["paragraph_count"] = max(1, full_text.count("\n") + 1)
                                        detail["sentence_count"] = len(re.findall(r'[.!?！？]+', full_text)) or 1
                                        detail["ko_char"] = len(re.findall(r'[가-힣]', full_text))
                                        detail["en_char"] = len(re.findall(r'[A-Za-z]', full_text))
                                        detail["num_char"] = len(re.findall(r'\d', full_text))
                                        main_keyword = st.session_state.get("seo_keyword", "")
                                        main_keyword = detail.get("main_keyword") or st.session_state.get("seo_keyword", "")
                                        detail["main_keyword"] = main_keyword

                                        def count_phrase_occurrences(text, phrase):
                                            if not phrase:
                                                return 0
                                            normalized_text = re.sub(r'\s+', ' ', text).strip()
                                            exact = normalized_text.count(phrase)
                                            if ' ' in phrase:
                                                compact_text = re.sub(r'\s+', '', normalized_text)
                                                compact_phrase = phrase.replace(' ', '')
                                                return max(exact, compact_text.count(compact_phrase))
                                            return exact

                                        detail["exact_match_count"] = count_phrase_occurrences(full_text, main_keyword) if main_keyword else 0
                                        detail["partial_match_count"] = count_phrase_occurrences(full_text, main_keyword.replace(" ", "")) if main_keyword else 0
                                        source_keywords = st.session_state.get("seo_results", {}).get("top_keywords", []) or detail.get("top_keywords", [])
                                        detail["top_keywords"] = [
                                            {"keyword": k["keyword"], "count": count_phrase_occurrences(full_text, k["keyword"])}
                                            for k in source_keywords[:10]
                                            if count_phrase_occurrences(full_text, k["keyword"]) > 0
                                        ]
                                        detail["sub_keywords"] = [k["keyword"] for k in detail["top_keywords"][:5]]
                                    return detail

                                for aurl in st.session_state.selected_urls:
                                    detail = st.session_state.batch_analysis_results.get(aurl, {})
                                    detail = enrich_detail(detail)
                                    st.session_state.batch_analysis_results[aurl] = detail
                                        
                                    if "error" not in detail:
                                        texts_for_ai.append(detail.get("full_text", ""))
                                        valid_metrics.append({
                                            "char_count": detail.get("char_count", 0),
                                            "img_count": detail.get("img_count", 0)
                                        })

                                # Generate Custom AI Report based on the selected valid texts
                                if texts_for_ai:
                                    # Override the previous general search results with the specific selections
                                    if not st.session_state.seo_results:
                                        st.session_state.seo_results = {}
                                    st.session_state.seo_results["metrics"] = valid_metrics
                                    formula = loop.run_until_complete(analyzer.generate_custom_seo_report(texts_for_ai))
                                    st.session_state.seo_results["formula"] = formula
                                    
                                loop.close()
                            except Exception as e:
                                st.error(f"분석 오류: {e}")
                        st.rerun()
                with col_btn_b:
                    if st.button("🗑️ 선택 초기화", use_container_width=True, key="clear_sel_btn"):
                        st.session_state.selected_urls = []
                        st.session_state.batch_analysis_results = {}
                        st.rerun()

        with col_detail:
            if res:
                st.markdown("#### 📊 경쟁 데이터 요약")
                c_a, c_b, c_c = st.columns(3)
                c_a.metric("분석 포스팅", f"{len(res.get('metrics', []))}개")
                avg_char = sum(m['char_count'] for m in res.get('metrics', [])) // len(res['metrics']) if res.get('metrics') else 0
                c_b.metric("평균 글자수", f"{avg_char}자")
                avg_img = sum(m['img_count'] for m in res.get('metrics', [])) // len(res['metrics']) if res.get('metrics') else 0
                c_c.metric("평균 이미지", f"{avg_img}장")

                st.markdown('<div class="s-card" style="margin-top:1rem;">', unsafe_allow_html=True)
                st.subheader("🏆 상위노출 공식 (Winning Formula)")
                st.markdown(res.get("formula", ""))
                st.markdown('</div>', unsafe_allow_html=True)

            # ── 정밀 분석 결과 ──
            if st.session_state.batch_analysis_results:
                st.markdown("#### 🔬 포스팅 정밀 분석 결과")
                for aidx, (aurl, detail) in enumerate(st.session_state.batch_analysis_results.items()):
                    if "error" in detail:
                        st.error(f"오류: {detail['error']} ({aurl[:50]})")
                        continue
                    ttype = detail.get("text_type", "—")
                    tcolor = detail.get("type_color", "#64748b")
                    post_title = detail.get("title", "(제목없음)")[:45]
                    with st.expander(f"📄 {post_title}  [{ttype}]", expanded=(aidx == 0)):
                        # 배지
                        source_badge = detail.get("source", "블로그")
                        st.markdown(
                            f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">'
                            f'<span style="background:{tcolor};color:white;padding:3px 10px;border-radius:20px;font-size:0.8rem;font-weight:700;">{ttype}</span>'
                            f'<span style="background:#f1f5f9;color:#475569;padding:3px 10px;border-radius:20px;font-size:0.8rem;">출처: {source_badge}</span>'
                            f'<a href="{aurl}" target="_blank" style="background:#e0f2fe;color:#0369a1;padding:3px 10px;border-radius:20px;font-size:0.8rem;text-decoration:none;">🔗 원문</a>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                        # 블로그 정보 섹션
                        if detail.get('blog_info'):
                            bi = detail['blog_info']
                            b1, b2, b3, b4 = st.columns(4)
                            b1.metric("블로그ID", bi.get('blog_id', '—'))
                            b2.metric("일평균 방문자", bi.get('visitor_daily', '비공개'))
                            b3.metric("이웃 수", f"{bi.get('neighbor_count', '—')}명")
                            b4.metric("개설일", bi.get('created_at', '—'))
                            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

                        # 통계 6칸
                        s1, s2, s3, s4, s5, s6 = st.columns(6)
                        s1.metric("글자(공백제외)", f"{detail.get('char_count', 0):,}")
                        s2.metric("전체글자", f"{detail.get('total_char', 0):,}")
                        s3.metric("띄어쓰기", f"{detail.get('space_count', 0):,}")
                        s4.metric("이미지", f"{detail.get('img_count', 0)}장")
                        s5.metric("단락", f"{detail.get('paragraph_count', 0)}개")
                        s6.metric("문장", f"{detail.get('sentence_count', 0)}개")
                        
                        # 글자 상세 & 키워드 매치
                        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                        sc1.metric("한글", f"{detail.get('ko_char', 0):,}자")
                        sc2.metric("영어", f"{detail.get('en_char', 0):,}자")
                        sc3.metric("숫자", f"{detail.get('num_char', 0):,}자")
                        sc4.metric("키워드 정확 일치", f"{detail.get('exact_match_count', 0):,}회")
                        sc5.metric("키워드 부분 일치", f"{detail.get('partial_match_count', 0):,}회")

                        st.markdown("---")

                        # 키워드
                        col_mk, col_sk = st.columns([1, 2])
                        with col_mk:
                            main_kw = detail.get("main_keyword", "—")
                            st.markdown(
                                f'<div style="background:#f0fdf4;padding:12px;border-radius:10px;border:1px solid #86efac;">'
                                f'<div style="font-size:0.75rem;color:#166534;font-weight:700;">🎯 메인 키워드</div>'
                                f'<div style="font-size:1.3rem;font-weight:800;color:#15803d;margin-top:4px;">{main_kw}</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                        with col_sk:
                            subs = detail.get("sub_keywords", [])
                            sub_html = " ".join([
                                f'<span style="background:#e2e8f0;color:#334155;padding:3px 10px;border-radius:20px;font-size:0.82rem;font-weight:600;">{k}</span>'
                                for k in subs
                            ])
                            st.markdown(
                                f'<div style="background:#f8fafc;padding:12px;border-radius:10px;border:1px solid #e2e8f0;">'
                                f'<div style="font-size:0.75rem;color:#475569;font-weight:700;margin-bottom:8px;">📌 서브 키워드</div>'
                                f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{sub_html}</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

                        # 빈도 바 차트
                        top_kws = detail.get("top_keywords", [])
                        if top_kws:
                            st.markdown("**📊 키워드 사용 빈도 TOP 10**")
                            max_cnt = max(k.get("count", 1) for k in top_kws[:10]) or 1
                            kw_html = ""
                            for k in top_kws[:10]:
                                pct = int(k.get("count", 0) / max_cnt * 100)
                                kw_html += (
                                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">'
                                    f'<div style="width:80px;font-size:0.85rem;font-weight:600;">{k["keyword"]}</div>'
                                    f'<div style="flex:1;background:#f1f5f9;border-radius:4px;height:16px;overflow:hidden;">'
                                    f'<div style="width:{pct}%;background:linear-gradient(90deg,#6366f1,#8b5cf6);height:100%;border-radius:4px;"></div>'
                                    f'</div>'
                                    f'<div style="width:28px;font-size:0.8rem;color:#64748b;text-align:right;">{k.get("count", 0)}</div>'
                                    f'</div>'
                                )
                            st.markdown(kw_html, unsafe_allow_html=True)

                        # 다운로드
                        st.markdown("---")
                        full_text = detail.get("full_text", "")
                        if full_text:
                            dl1, dl2 = st.columns(2)
                            with dl1:
                                st.download_button(
                                    label="⬇️ 본문 텍스트",
                                    data=full_text.encode("utf-8"),
                                    file_name=f"post_{aidx+1}_{detail.get('source','blog')}.txt",
                                    mime="text/plain",
                                    use_container_width=True,
                                    key=f"dl_txt_{aidx}"
                                )
                            with dl2:
                                import csv, io
                                buf = io.StringIO()
                                w = csv.writer(buf)
                                w.writerow(["항목", "값"])
                                for row in [
                                    ("제목", detail.get("title", "")),
                                    ("URL", aurl),
                                    ("글형태", ttype),
                                    ("글자수(공백제외)", detail.get("char_count", 0)),
                                    ("전체글자수", detail.get("total_char", 0)),
                                    ("띄어쓰기수", detail.get("space_count", 0)),
                                    ("이미지수", detail.get("img_count", 0)),
                                    ("단락수", detail.get("paragraph_count", 0)),
                                    ("문장수", detail.get("sentence_count", 0)),
                                    ("메인키워드", detail.get("main_keyword", "")),
                                    ("서브키워드", ", ".join(detail.get("sub_keywords", []))),
                                ]:
                                    w.writerow(row)
                                for k in top_kws:
                                    w.writerow([f"키워드:{k['keyword']}", k.get("count", 0)])
                                st.download_button(
                                    label="⬇️ 분석 요약 CSV",
                                    data=buf.getvalue().encode("utf-8-sig"),
                                    file_name=f"analysis_{aidx+1}.csv",
                                    mime="text/csv",
                                    use_container_width=True,
                                    key=f"dl_csv_{aidx}"
                                )



            # ══════════════════════════════════════════════════════
            # ☕ 카페글 작성기 (분석 기반)
            # ══════════════════════════════════════════════════════
            if st.session_state.batch_analysis_results:
                st.markdown("---")
                st.markdown("#### ☕ 분석 기반 카페글 작성")

                # 분석 결과에서 전체 키워드 풀 합산 (빈도순)
                all_kw_freq = {}
                all_full_texts = []
                for detail in st.session_state.batch_analysis_results.values():
                    if "error" in detail:
                        continue
                    for kw in detail.get("top_keywords", []):
                        k, cnt = kw.get("keyword",""), kw.get("count", 1)
                        if k:
                            all_kw_freq[k] = all_kw_freq.get(k, 0) + cnt
                    if detail.get("full_text"):
                        all_full_texts.append(detail["full_text"][:500])

                kw_sorted = sorted(all_kw_freq.items(), key=lambda x: -x[1])
                kw_options = [f"{k} ({v}회)" for k, v in kw_sorted[:30]]

                c_left, c_right = st.columns([1, 1])
                with c_left:
                    cafe_main_kw = st.text_input(
                        "🎯 메인 키워드 (직접 입력)",
                        placeholder="예: 인천공항 주차대행",
                        key="cafe_main_kw_input"
                    )
                    cafe_style = st.selectbox(
                        "✍️ 글 스타일",
                        ["후기", "정보", "추천", "질문/토론"],
                        key="cafe_style_select"
                    )
                with c_right:
                    cafe_sub_kws_raw = st.multiselect(
                        "📌 서브 키워드 선택 (빈도 높은 순)",
                        options=kw_options,
                        default=kw_options[:5] if kw_options else [],
                        key="cafe_sub_kw_select"
                    )
                    use_ref = st.checkbox("📄 분석 내용을 참고 자료로 활용", value=True, key="cafe_use_ref")

                if st.button("🤖 AI 카페글 생성", type="primary", use_container_width=True, key="cafe_gen_btn"):
                    if not cafe_main_kw:
                        st.warning("메인 키워드를 입력해주세요.")
                    else:
                        # 서브 키워드에서 빈도 표기 제거
                        sub_kws_clean = [s.rsplit(" (", 1)[0] for s in cafe_sub_kws_raw]
                        ref_text = " ".join(all_full_texts) if use_ref else ""

                        with st.spinner("AI가 카페글을 작성 중입니다..."):
                            try:
                                loop = asyncio.new_event_loop()
                                generated = loop.run_until_complete(
                                    soul.generate_cafe_post(
                                        main_keyword=cafe_main_kw,
                                        sub_keywords=sub_kws_clean,
                                        reference_text=ref_text,
                                        post_style=cafe_style
                                    )
                                )
                                loop.close()
                                st.session_state["cafe_generated_post"] = generated
                            except Exception as e:
                                st.error(f"생성 오류: {e}")
                        st.rerun()

                # 생성 결과 표시
                if st.session_state.get("cafe_generated_post"):
                    generated_post = st.session_state["cafe_generated_post"]

                    # 제목/본문 분리
                    post_lines = generated_post.strip().split("\n")
                    post_title = ""
                    post_body = generated_post
                    for li, ln in enumerate(post_lines):
                        if ln.startswith("제목:"):
                            post_title = ln.replace("제목:", "").strip()
                            post_body = "\n".join(post_lines[li+1:]).lstrip("\n -—")
                            break

                    st.markdown(
                        f'<div style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);'
                        f'padding:16px 20px;border-radius:12px;border:1px solid #86efac;margin-bottom:12px;">'
                        f'<div style="font-size:0.75rem;color:#166534;font-weight:700;margin-bottom:6px;">✅ 생성된 카페글 제목</div>'
                        f'<div style="font-size:1.1rem;font-weight:800;color:#15803d;">{post_title}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                    edited_body = st.text_area(
                        "📝 본문 (수정 가능)",
                        value=post_body,
                        height=350,
                        key="cafe_body_editor"
                    )

                    dl1, dl2, dl3 = st.columns(3)
                    with dl1:
                        full_copy = f"{post_title}\n\n{edited_body}"
                        st.download_button(
                            "⬇️ 전체 다운로드 (.txt)",
                            data=full_copy.encode("utf-8"),
                            file_name="cafe_post.txt",
                            mime="text/plain",
                            use_container_width=True,
                            key="cafe_dl_txt"
                        )
                    with dl2:
                        if st.button("🔄 다시 생성", use_container_width=True, key="cafe_regen"):
                            del st.session_state["cafe_generated_post"]
                            st.rerun()
                    with dl3:
                        if st.button("🗑️ 결과 초기화", use_container_width=True, key="cafe_clear"):
                            del st.session_state["cafe_generated_post"]
                            st.rerun()


elif page == "🛡️ 블로그 진단 & 순위":
    st.markdown('<div class="ph"><h1>블로그 진단 및 순위</h1><p>내 블로그의 건강 상태와 검색 순위를 관리합니다</p></div>', unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["📈 순위 트래커", "🛡️ 누락 검증"])
    
    with t1:
        db = get_db()
        col_inputs, col_monitor = st.columns([1.2, 2.0])
        
        with col_inputs:
            st.markdown('<div class="s-card"><h3>🏢 블로그 순위 추적 등록</h3>', unsafe_allow_html=True)
            blog_id_input = st.text_input("네이버 블로그 ID / 주소", key="seo_blog_id_input", placeholder="예: naver_blog_id")
            keyword_input = st.text_input("추적 키워드", key="seo_blog_keyword_input", placeholder="예: 부산 서면 고기집")
            
            if st.button("➕ 순위 추적 등록 및 실시간 조회", use_container_width=True):
                if not blog_id_input or not keyword_input:
                    st.error("블로그 ID와 키워드를 모두 입력해 주세요.")
                else:
                    # 블로그 ID가 URL 형태인 경우 아이디만 추출
                    clean_blog_id = blog_id_input.strip()
                    if "blog.naver.com/" in clean_blog_id:
                        # https://blog.naver.com/아이디 형식 또는 https://m.blog.naver.com/아이디 형식
                        match = re.search(r'blog\.naver\.com/([^/]+)', clean_blog_id)
                        if match:
                            clean_blog_id = match.group(1)
                    
                    # DB 등록
                    added = db.add_keyword(clean_blog_id, keyword_input)
                    if added:
                        st.toast("키워드가 등록되었습니다!", icon="✅")
                    
                    # 실시간 순위 조회 수행
                    with st.spinner("네이버 블로그 실시간 순위 조회 중..."):
                        loop = asyncio.new_event_loop()
                        res = loop.run_until_complete(analyzer.track_my_ranking(clean_blog_id, keyword_input))
                        loop.close()
                        
                        rank = res.get("rank", -1)
                        
                        # keyword_id 조회
                        kws = db.get_keywords(clean_blog_id)
                        k_id = None
                        for item in kws:
                            if item[2] == keyword_input:
                                k_id = item[0]
                                break
                                
                        if k_id is not None:
                            db.add_history(k_id, rank)
                            
                        if rank > 0:
                            st.success(f"🎉 실시간 조회 결과: 현재 {rank}위에 노출 중입니다!")
                        else:
                            st.warning("⚠️ 검색 결과 Top 75 이내에 해당 블로그의 글이 발견되지 않았습니다.")
                        
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_monitor:
            st.markdown('<div class="s-card"><h3>📈 순위 모니터링</h3>', unsafe_allow_html=True)
            
            # DB에서 등록된 키워드 전체 조회
            keywords = db.get_keywords()
            
            if not keywords:
                st.info("현재 추적 중인 키워드가 없습니다. 왼쪽에서 블로그 ID와 키워드를 입력해 등록해 주세요.")
            else:
                # 키워드별 테이블 정보 준비
                table_data = []
                for kw_id, blog_id, kw in keywords:
                    # 최신 순위 이력 조회
                    history = db.get_history(kw_id, days=1)
                    current_rank = "-"
                    check_date = "-"
                    
                    if history:
                        rank_val = history[0][1]
                        check_date = history[0][0]
                        current_rank = f"{rank_val}위" if rank_val > 0 else "75위 권외"
                        
                    # 상태 매칭 배지
                    if current_rank == "-":
                        status_html = '<span style="color:#64748b; font-weight:bold;">미조회</span>'
                    elif "권외" in current_rank:
                        status_html = '<span style="color:#ef4444; font-weight:bold;">권외</span>'
                    elif history[0][1] <= 5:
                        status_html = '<span style="color:#10b981; font-weight:bold;">최상위 (Top 5)</span>'
                    else:
                        status_html = '<span style="color:#3b82f6; font-weight:bold;">노출 중</span>'
                        
                    table_data.append({
                        "id": kw_id,
                        "blog_id": blog_id,
                        "keyword": kw,
                        "rank": current_rank,
                        "status": status_html,
                        "date": check_date
                    })
                
                # HTML 테이블 생성
                table_html = """
                <table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.9rem;">
                    <thead>
                        <tr style="border-bottom:2px solid #e2e8f0; background:#f8fafc;">
                            <th style="padding:10px; font-weight:bold; color:#475569;">블로그 ID</th>
                            <th style="padding:10px; font-weight:bold; color:#475569;">추적 키워드</th>
                            <th style="padding:10px; font-weight:bold; color:#475569;">최근 순위</th>
                            <th style="padding:10px; font-weight:bold; color:#475569;">상태</th>
                            <th style="padding:10px; font-weight:bold; color:#475569;">조회일</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                for idx, row in enumerate(table_data):
                    bg_color = "#ffffff" if idx % 2 == 0 else "#f8fafc"
                    table_html += f"""
                        <tr style="border-bottom:1px solid #edf2f7; background:{bg_color};">
                            <td style="padding:10px; color:#1e293b; font-weight:bold;">{row['blog_id']}</td>
                            <td style="padding:10px; color:#475569;">{row['keyword']}</td>
                            <td style="padding:10px; color:#1e293b; font-weight:bold;">{row['rank']}</td>
                            <td style="padding:10px;">{row['status']}</td>
                            <td style="padding:10px; color:#64748b;">{row['date']}</td>
                        </tr>
                    """
                table_html += "</tbody></table>"
                import textwrap
                flat_html = " ".join([line.strip() for line in textwrap.dedent(table_html).split("\n") if line.strip()])
                st.markdown(flat_html, unsafe_allow_html=True)
                st.write("") # 간격
                
                # 개별 관리 셀렉터 (새로고침 및 삭제 기능)
                st.markdown("<h4>⚙️ 개별 키워드 관리</h4>", unsafe_allow_html=True)
                kw_options = {f"[{row['blog_id']}] {row['keyword']}": row for row in table_data}
                selected_kw_label = st.selectbox("관리할 키워드 선택", list(kw_options.keys()), key="seo_kw_mgr_select")
                
                if selected_kw_label:
                    sel_row = kw_options[selected_kw_label]
                    col_refresh, col_delete = st.columns(2)
                    
                    with col_refresh:
                        if st.button("🔄 실시간 순위 새로고침", key=f"ref_{sel_row['id']}", use_container_width=True):
                            with st.spinner("네이버 블로그 실시간 순위 조회 중..."):
                                loop = asyncio.new_event_loop()
                                res = loop.run_until_complete(analyzer.track_my_ranking(sel_row['blog_id'], sel_row['keyword']))
                                loop.close()
                                
                                rank = res.get("rank", -1)
                                db.add_history(sel_row['id'], rank)
                                st.success(f"순위가 갱신되었습니다! (현재 순위: {rank}위)" if rank > 0 else "순위 갱신 완료 (권외)")
                                st.rerun()
                                
                    with col_delete:
                        if st.button("🗑️ 추적 키워드 삭제", key=f"del_{sel_row['id']}", use_container_width=True):
                            db.remove_keyword(sel_row['id'])
                            st.toast("추적 키워드가 삭제되었습니다.", icon="🗑️")
                            st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    
    with t2:
        st.markdown('<div class="s-card"><h3>🛡️ 개별 포스팅 점검</h3>', unsafe_allow_html=True)
        v_url = st.text_input("포스팅 URL", key="v_url")
        v_title = st.text_input("포스팅 제목", key="v_title")
        if st.button("검증 시작", use_container_width=True):
            with st.spinner("검색 결과 대조 중..."):
                loop = asyncio.new_event_loop()
                res = loop.run_until_complete(analyzer.verify_post_status(v_url, v_title))
                loop.close()
                st.metric("검색 상태", res['status'])
        st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════
# 📊 로그
# ═══════════════════════════════════════
elif page == "📊 로그":
    st.markdown('<div class="ph"><h1>시스템 로그</h1><p>엔진의 모든 실행 기록을 보관합니다</p></div>', unsafe_allow_html=True)
    logs = runner.get_logs(limit=30)
    for log in logs:
        st.json(log)

# ═══════════════════════════════════════
# 📈 플레이스 SEO 진단
# ═══════════════════════════════════════
elif page == "📈 플레이스 SEO 진단":
    st.markdown('<div class="ph"><h1>플레이스 SEO 지수 진단 및 제안서</h1><p>N1, N2, N3 공식을 활용한 병목 분석 및 대행사용 영업 제안서 자동 생성기</p></div>', unsafe_allow_html=True)
    
    crawler = get_place_crawler()
    
    # 세션 스테이트 초기화 (자동 수집 대응)
    if "seo_place_mid" not in st.session_state:
        st.session_state["seo_place_mid"] = "11859846"
    if "seo_store_name" not in st.session_state:
        st.session_state["seo_store_name"] = "빕스 부산서면점"
    if "seo_keyword" not in st.session_state:
        st.session_state["seo_keyword"] = "서면맛집"
    if "seo_current_rank" not in st.session_state:
        st.session_state["seo_current_rank"] = 10
    if "seo_saves" not in st.session_state:
        st.session_state["seo_saves"] = 25000
    if "seo_visitor_reviews" not in st.session_state:
        st.session_state["seo_visitor_reviews"] = 6823
    if "seo_blog_reviews" not in st.session_state:
        st.session_state["seo_blog_reviews"] = 2573
    if "seo_category" not in st.session_state:
        st.session_state["seo_category"] = "패밀리레스토랑"
    if "seo_has_booking" not in st.session_state:
        st.session_state["seo_has_booking"] = True
    if "seo_competitors" not in st.session_state:
        st.session_state["seo_competitors"] = []

    # 기준선 지표 초기화 (시뮬레이터 연동용)
    if "baseline_saves" not in st.session_state:
        st.session_state["baseline_saves"] = st.session_state["seo_saves"]
    if "baseline_visitor_reviews" not in st.session_state:
        st.session_state["baseline_visitor_reviews"] = st.session_state["seo_visitor_reviews"]
    if "baseline_blog_reviews" not in st.session_state:
        st.session_state["baseline_blog_reviews"] = st.session_state["seo_blog_reviews"]
    if "baseline_rank" not in st.session_state:
        st.session_state["baseline_rank"] = st.session_state["seo_current_rank"]
    if "baseline_has_booking" not in st.session_state:
        st.session_state["baseline_has_booking"] = st.session_state["seo_has_booking"]

    col_inputs, col_results = st.columns([1.2, 1.5])
    
    with col_inputs:
        st.markdown('<div class="s-card"><h3>🏢 기본 정보 입력</h3>', unsafe_allow_html=True)
        place_mid = st.text_input("업체 플레이스 MID", key="seo_place_mid", help="네이버 플레이스 상세 주소의 숫자 ID (예: 11859846)")
        keyword = st.text_input("검색 키워드", key="seo_keyword", help="조회할 타겟 검색어 (예: 서면맛집)")
        
        # 실시간 데이터 자동 수집 버튼
        if st.button("🔄 실시간 데이터 자동 수집", use_container_width=True):
            with st.spinner("네이버 플레이스 실시간 데이터 수집 중..."):
                place_info = crawler.fetch_place_by_mid(place_mid)
                search_results = crawler.search_keyword_ranking(keyword)
                
                if place_info.get("success", False) or place_info.get("name"):
                    st.session_state["seo_store_name"] = place_info["name"]
                    st.session_state["seo_visitor_reviews"] = place_info["visitor_reviews"]
                    st.session_state["seo_blog_reviews"] = place_info["blog_reviews"]
                    st.session_state["seo_category"] = place_info["category"]
                    st.session_state["seo_saves"] = int(place_info["visitor_reviews"] * 3.5) # estimate saves
                    st.session_state["seo_has_booking"] = place_info["has_booking"]
                    
                    # 실시간 랭킹 추적 매칭
                    found_rank = -1
                    if search_results:
                        for idx, item in enumerate(search_results):
                            if str(item["mid"]) == str(place_mid):
                                found_rank = idx + 1
                                break
                    
                    if found_rank > 0:
                        st.session_state["seo_current_rank"] = found_rank
                        st.success(f"🎉 실시간 노출 순위 매칭 성공: 실제 {found_rank}위에 노출 중입니다!")
                    else:
                        st.session_state["seo_current_rank"] = 21 # 외곽 배치
                        st.warning(f"⚠️ 검색 결과 Top 20 이내에 내 매장(MID: {place_mid})이 발견되지 않았습니다. 외곽(21위)으로 분석을 진행합니다.")
                        
                    # 기준선 지표도 함께 동기화 업데이트
                    st.session_state["baseline_saves"] = st.session_state["seo_saves"]
                    st.session_state["baseline_visitor_reviews"] = st.session_state["seo_visitor_reviews"]
                    st.session_state["baseline_blog_reviews"] = st.session_state["seo_blog_reviews"]
                    st.session_state["baseline_rank"] = st.session_state["seo_current_rank"]
                    st.session_state["baseline_has_booking"] = st.session_state["seo_has_booking"]

                    if search_results:
                        st.session_state["seo_competitors"] = search_results
                    
                    st.toast("실시간 수집 완료!", icon="✅")
                else:
                    st.error("실시간 수집 실패. MID가 유효한지 확인해 주세요.")
                    
        store_name = st.text_input("업체명 (자동 입력)", key="seo_store_name")
        current_rank = st.number_input("현재 노출 순위", min_value=1, max_value=100, key="seo_current_rank")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="s-card"><h3>⚙️ N1 (적합도) 변수 입력</h3>', unsafe_allow_html=True)
        c_match_opt = st.selectbox("카테고리/업종 분류 일치율 (C_match)", ["Exact Match (1.0)", "Related Match (0.5)", "Mismatch (0.0)"])
        c_match_val = 1.0 if "Exact" in c_match_opt else (0.5 if "Related" in c_match_opt else 0.0)
        
        k_brand_opt = st.checkbox("상호명 키워드 매칭 (K_brand)", value=True, help="상호명에 검색 키워드 또는 지역명이 들어가 있는가?")
        k_brand_val = 1.0 if k_brand_opt else 0.0
        
        desc_kw_density = st.slider("소개글 형태소 키워드 빈도 (K_desc)", 0, 10, 2, help="소개글 내 타겟 키워드 1-3회 분포 권장. 4회 이상시 도배로 필터링.")
        k_desc_val = 1.0 if (1 <= desc_kw_density <= 3) else (0.5 if desc_kw_density == 0 else 0.0)
        
        b_status_opt = st.checkbox("영업 상태 활성화 (B_status)", value=True, help="현재 영업 시간인가?")
        b_status_val = 1.0 if b_status_opt else 0.0
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="s-card"><h3>📈 내 플레이스 N2 (신뢰도) 지표</h3>', unsafe_allow_html=True)
        my_fit = st.slider("키워드 검색어 적합도 (S_fit)", 0.0, 1.0, 0.9, 0.1)
        my_saves = st.number_input("누적 저장수 (S_save)", min_value=0, key="seo_saves")
        my_saves_delta = st.number_input("오늘 저장수 증가량 (Delta)", value=15)
        
        my_rec_rating = st.slider("방문자 리뷰 평균 평점", 1.0, 5.0, 4.5, 0.1, help="4.0~4.7점 황금 구간 안착시 만점(1.0) 부여.")
        if 4.0 <= my_rec_rating <= 4.7:
            my_rec_score = 1.0
        elif 3.5 <= my_rec_rating < 4.0:
            my_rec_score = 0.5
        else:
            my_rec_score = 0.1
            
        my_rec_count = st.number_input("누적 영수증 리뷰수", min_value=0, key="seo_visitor_reviews")
        my_rec_delta = st.number_input("오늘 영수증 리뷰 증가량", value=3)
        
        my_blog_grade = st.selectbox("대표 블로그 신뢰 등급 (S_blog)", ["NB 및 준최 5-6단계 (+48점)", "준최 2-4단계 (+20.16점)", "저품질 블로그 (-100점)", "최적화/제명 (0점)"])
        blog_grade_map = {
            "NB 및 준최 5-6단계 (+48점)": 1.0, 
            "준최 2-4단계 (+20.16점)": 0.42, 
            "저품질 블로그 (-100점)": -2.08, 
            "최적화/제명 (0점)": 0.0
        }
        my_blog_score = blog_grade_map[my_blog_grade]
        my_blog_count = st.number_input("누적 블로그 리뷰수", min_value=0, key="seo_blog_reviews")
        my_blog_delta = st.number_input("오늘 블로그 리뷰 증가량", value=1)
        
        my_stay = st.slider("사용자 체류시간 / 길찾기 강도 (S_stay)", 0.0, 1.0, 0.7, 0.1)
        my_recent = st.slider("최근성 성장 추이 (M_recent)", 0.0, 1.0, 0.5, 0.1)
        
        my_func_booking = st.checkbox("네이버 예약 활성화 및 응답율 관리", key="seo_has_booking")
        my_func_smart = st.checkbox("톡톡/스마트콜/쿠폰 기능 활성화", value=True)
        my_func_val = 1.0 if (my_func_booking and my_func_smart) else 0.5
        st.markdown('</div>', unsafe_allow_html=True)

    with col_results:
        # N1, N2, N3 계산 및 결과 출력
        n1_score = seo_calc.calculate_n1(c_match_val, k_brand_val, k_desc_val, b_status_val)
        
        # 정량적 N2 입력값 변환
        my_metrics = {
            "s_fit": my_fit,
            "s_save": min(1.0, my_saves / 2000.0), # 스케일링
            "s_rec": my_rec_score,
            "s_blog": my_blog_score,
            "s_stay": my_stay,
            "m_recent": my_recent,
            "s_func": my_func_val,
            "save_raw": my_saves,
            "rec_raw": my_rec_count,
            "blog_raw": my_blog_count,
            "recent_raw": my_saves_delta + my_rec_delta + my_blog_delta
        }
        
        n2_score_raw = seo_calc.calculate_n2(my_metrics)
        
        # 어뷰징 수동 차감 제외하고 순수 N2 계산 적용
        n2_score = round(n2_score_raw, 6)
        
        # N3 종합지수 계산 (거리 1km 가중치 1.1, 개인화 0.01)
        n3_score = seo_calc.calculate_n3(n2_score, 1.1, 0.01, 0.0)
        
        # 앵커 기준선 지수 계산 (최초/기준 값 기준)
        b_n1 = seo_calc.calculate_n1(1.0, 1.0, 1.0, 1.0)
        b_metrics = {
            "s_fit": 0.9,
            "s_save": min(1.0, st.session_state.get("baseline_saves", 25000) / 2000.0),
            "s_rec": 1.0,
            "s_blog": 1.0,
            "s_stay": 0.7,
            "m_recent": 0.5,
            "s_func": 1.0 if st.session_state.get("baseline_has_booking", True) else 0.5,
            "save_raw": st.session_state.get("baseline_saves", 25000),
            "rec_raw": st.session_state.get("baseline_visitor_reviews", 6823),
            "blog_raw": st.session_state.get("baseline_blog_reviews", 2573),
            "recent_raw": 16 # 15 + 3 + 1
        }
        b_n2 = seo_calc.calculate_n2(b_metrics)
        baseline_n3 = seo_calc.calculate_n3(b_n2, 1.1, 0.01, 0.0)
        
        # 📊 실시간 랭킹 대조표 HTML 테이블 생성
        if "seo_competitors" in st.session_state and st.session_state["seo_competitors"]:
            competitors_names = []
            for item in st.session_state["seo_competitors"]:
                competitors_names.append((
                    item["name"],
                    item["cat"],
                    item["rec"],
                    item["rec_d"],
                    item["blog"],
                    item["blog_d"],
                    item["save"]
                ))
        else:
            competitors_names = [
                ("용가마전통순대 부산서면점", "한식당", 355, 126, 103, 41, "~100"),
                ("친구네집 서면점", "중식당", 901, 109, 73, 21, "~100"),
                ("쏘쏘사라다 부산서면점", "베이커리", 1271, -26, 96, 8, "~100"),
                ("피자드오뉴 부산본점", "피자", 4028, 2, 1468, 4, "21,000+"),
                ("테테테", "요리주점", 2905, 6, 1570, -1, "78,000+"),
                ("매성", "요리주점", 1184, 28, 221, 4, "5,000+"),
                ("올드맨션 서면전포점", "돼지고기구이", 2991, 5, 1401, -1, "41,000+"),
                ("오성가든 Hot", "포장마차", 1249, 26, 1636, 1, "25,000+"),
                ("샐러드바스켓 서면본점", "다이어트,샐러드", 6823, -34, 2573, -4, "79,000+"),
                ("솔손 서면점", "일식", 4649, -16, 2476, -7, "33,000+"),
                ("후발대", "육류,고기요리", 2297, 113, 1213, 2, "50,000+"),
                ("서면밀면", "냉면", 3667, 1, 4010, 9, "58,000+"),
                ("칸다소바 서면점", "일식당", 3210, 42, 2190, 18, "47,000+"),
                ("라라관 서면본점", "중식당", 1540, -10, 1050, -3, "18,000+"),
                ("전포방앗간", "분식", 980, 15, 650, 4, "12,000+"),
                ("삼정타워 쉑쉑버거", "햄버거", 6400, 8, 3800, 12, "85,000+"),
                ("고굽남 서면점", "고기요리", 4200, 31, 2800, 15, "55,000+"),
                ("미진축산 서면점", "고기요리", 1980, 22, 1150, 8, "24,000+"),
                ("은화수식당 서면점", "돈가스", 1450, -5, 920, 2, "15,000+"),
                ("소문난곱창 서면점", "한식", 2100, 14, 1340, 6, "29,000+"),
                ("마라쿵젠 서면본점", "중식", 1120, 25, 870, 7, "16,000+")
            ]
        
        target_rank = int(st.session_state.get("baseline_rank", current_rank))
        
        client_row = {
            "name": store_name,
            "cat": st.session_state.get("seo_category", "패밀리레스토랑"),
            "rec": my_rec_count,
            "rec_d": my_rec_delta,
            "blog": my_blog_count,
            "blog_d": my_blog_delta,
            "save": f"{my_saves:,}+",
            "n1": n1_score,
            "n1_d": -0.000015,
            "n2": n2_score,
            "n2_d": -0.003019,
            "n3": n3_score,
            "n3_d": -0.000234,
            "is_client": True
        }
        
        rows = []
        comp_count = len(competitors_names)
        list_size = max(15, target_rank + 3)
        
        for idx in range(list_size):
            if idx == target_rank - 1:
                rows.append(client_row)
            else:
                comp_idx = idx if idx < target_rank - 1 else idx - 1
                name, cat, rec, rec_d, blog, blog_d, save = competitors_names[comp_idx % comp_count]
                
                # 경쟁자들 N3 점수를 최초 baseline_n3 기준으로 고정 배치합니다.
                if idx < target_rank - 1:
                    dist_to_client = (target_rank - 1) - idx
                    c_n3 = baseline_n3 + dist_to_client * 0.0015 + 0.0001
                    c_n2 = b_n2 + dist_to_client * 0.002 + 0.0003
                    c_n1 = b_n1
                else:
                    dist_to_client = idx - (target_rank - 1)
                    c_n3 = max(0.0001, baseline_n3 - dist_to_client * 0.0015 - 0.0001)
                    c_n2 = max(0.0001, b_n2 - dist_to_client * 0.002 - 0.0003)
                    c_n1 = max(0.0001, b_n1 - dist_to_client * 0.001)
                    
                rows.append({
                    "name": name,
                    "cat": cat,
                    "rec": rec,
                    "rec_d": rec_d,
                    "blog": blog,
                    "blog_d": blog_d,
                    "save": save,
                    "n1": c_n1,
                    "n1_d": -0.000015,
                    "n2": c_n2,
                    "n2_d": -0.002475,
                    "n3": c_n3,
                    "n3_d": -0.000193,
                    "is_client": False
                })
        
        rows.sort(key=lambda x: x["n3"], reverse=True)
        
        my_dyn_rank = target_rank
        for idx, r in enumerate(rows):
            if r.get("is_client", False):
                my_dyn_rank = idx + 1
                break

        # 🔮 실시간 예상 순위 요약 카드 (글래스모피즘 스타일)
        orig_rank = int(st.session_state.get("baseline_rank", target_rank))
        rank_diff = orig_rank - my_dyn_rank
        
        if rank_diff > 0:
            status_color = "#f0fdf4"
            border_color = "#22c55e"
            text_color = "#166534"
            badge_html = f"<span style='background:#dcfce7; color:#166534; padding:6px 14px; border-radius:20px; font-weight:bold; font-size:0.85rem; border: 1px solid #bbf7d0;'>▲ {rank_diff}계단 상승 예상!</span>"
        elif rank_diff < 0:
            status_color = "#fef2f2"
            border_color = "#ef4444"
            text_color = "#991b1b"
            badge_html = f"<span style='background:#fee2e2; color:#991b1b; padding:6px 14px; border-radius:20px; font-weight:bold; font-size:0.85rem; border: 1px solid #fecaca;'>▼ {abs(rank_diff)}계단 하락 예상</span>"
        else:
            status_color = "#f8fafc"
            border_color = "#94a3b8"
            text_color = "#334155"
            badge_html = "<span style='background:#f1f5f9; color:#475569; padding:6px 14px; border-radius:20px; font-weight:bold; font-size:0.85rem; border: 1px solid #e2e8f0;'>변화 없음 (순위 유지)</span>"

        st.markdown(f"""
        <div style="background:{status_color}; padding:20px; border-radius:12px; border:1px solid {border_color}; margin-bottom:20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <h4 style="margin:0; color:{text_color}; font-size:1.05rem; font-weight:bold; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto;">🔮 알고리즘 시뮬레이션 예측 결과</h4>
                    <p style="margin:4px 0 0 0; color:#64748b; font-size:0.8rem;">좌측 슬라이더 지수 변수 조정에 따른 실시간 순위 예측 모델입니다.</p>
                </div>
                <div>
                    {badge_html}
                </div>
            </div>
            <div style="display:flex; gap:30px; margin-top:15px; align-items:center; justify-content:center; background:#ffffff; padding:15px; border-radius:8px; border:1px solid #e2e8f0;">
                <div style="text-align:center;">
                    <div style="font-size:0.75rem; color:#64748b; font-weight:600; text-transform:uppercase;">기존 순위</div>
                    <div style="font-size:1.6rem; font-weight:800; color:#475569; margin-top:2px;">{orig_rank}위</div>
                </div>
                <div style="font-size:1.6rem; color:{border_color}; font-weight:800;">➡️</div>
                <div style="text-align:center;">
                    <div style="font-size:0.75rem; color:{text_color}; font-weight:700; text-transform:uppercase;">예상 순위</div>
                    <div style="font-size:2.0rem; font-weight:900; color:{text_color}; margin-top:2px;">{my_dyn_rank}위</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f'<div class="s-card"><h3>📊 플레이스 실시간 순위 대조표 ({keyword})</h3>', unsafe_allow_html=True)
        
        # HTML 렌더링
        html_table = """
        <style>
        .seo-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem !important;
            background: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }
        .seo-table th {
            background: #f1f5f9;
            color: #334155;
            font-weight: bold;
            padding: 8px 10px;
            text-align: left;
            border-bottom: 2px solid #cbd5e1;
        }
        .seo-table td {
            padding: 6px 10px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: middle;
            line-height: 1.2;
        }
        .seo-table tr.client-row {
            background: #f0fdf4 !important; /* 부드러운 초록 가이드 */
            border-left: 5px solid #22c55e !important;
            font-weight: bold;
        }
        .val-cell {
            font-weight: bold;
            color: #1e293b;
        }
        .delta-red {
            font-size: 0.7rem;
            color: #ef4444;
            display: block;
            margin-top: 1px;
        }
        .delta-blue {
            font-size: 0.7rem;
            color: #3b82f6;
            display: block;
            margin-top: 1px;
        }
        .delta-gray {
            font-size: 0.7rem;
            color: #94a3b8;
            display: block;
            margin-top: 1px;
        }
        .store-cat {
            font-size: 0.7rem;
            color: #64748b;
            display: block;
        }
        .tag-new {
            background: #ef4444;
            color: #ffffff;
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 0.65rem;
            font-weight: bold;
            margin-left: 4px;
        }
        .client-highlight {
            background: #22c55e;
            color: #ffffff;
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 0.65rem;
            font-weight: bold;
            margin-left: 4px;
        }
        </style>
        <table class="seo-table">
            <thead>
                <tr>
                    <th>순위</th>
                    <th>업체명/카테고리</th>
                    <th>방문자리뷰</th>
                    <th>블로그리뷰</th>
                    <th>저장수</th>
                    <th>N1 (적합)</th>
                    <th>N2 (신뢰)</th>
                    <th>N3 (종합)</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for idx, row in enumerate(rows):
            rank = idx + 1
            is_client = row.get("is_client", False)
            row_cls = "class='client-row'" if is_client else ""
            
            def fmt_d(val):
                if val > 0:
                    return f"<span class='delta-red'>+{val:,}</span>"
                elif val < 0:
                    return f"<span class='delta-blue'>{val:,}</span>"
                else:
                    return "<span class='delta-gray'>0</span>"

            def fmt_d_float(val):
                if val > 0:
                    return f"<span class='delta-red'>+{val:.6f}</span>"
                elif val < 0:
                    return f"<span class='delta-blue'>{val:.6f}</span>"
                else:
                    return "<span class='delta-gray'>0.000000</span>"
            
            rec_d_str = fmt_d(row["rec_d"])
            blog_d_str = fmt_d(row["blog_d"])
            
            # 저장수 delta (클라이언트는 Slider 값 사용)
            save_d_str = fmt_d(my_saves_delta) if is_client else "<span class='delta-gray'>-100</span>"
            
            n1_d_str = fmt_d_float(row["n1_d"])
            n2_d_str = fmt_d_float(row["n2_d"])
            n3_d_str = fmt_d_float(row["n3_d"])
            
            badges = ""
            if "친구네집" in row["name"]:
                badges = "<span class='tag-new'>새로오픈</span>"
            elif is_client:
                badges = "<span class='client-highlight'>내 매장</span>"
                
            html_table += f"""
            <tr {row_cls}>
                <td style="font-weight:bold; font-size: 0.9rem; text-align:center;">{rank}</td>
                <td>
                    <strong>{row["name"]}</strong>{badges}
                    <span class="store-cat">{row["cat"]}</span>
                </td>
                <td>
                    <span class="val-cell">{row["rec"]:,}</span>
                    {rec_d_str}
                </td>
                <td>
                    <span class="val-cell">{row["blog"]:,}</span>
                    {blog_d_str}
                </td>
                <td>
                    <span class="val-cell">{row["save"]}</span>
                    {save_d_str}
                </td>
                <td>
                    <span class="val-cell" style="font-family: monospace;">{row["n1"]:.6f}</span>
                    {n1_d_str}
                </td>
                <td>
                    <span class="val-cell" style="font-family: monospace; color:#3b82f6;">{row["n2"]:.6f}</span>
                    {n2_d_str}
                </td>
                <td>
                    <span class="val-cell" style="font-family: monospace; color:#22c55e; font-size:0.85rem;">{row["n3"]:.6f}</span>
                    {n3_d_str}
                </td>
            </tr>
            """
            
        html_table += "</tbody></table>"
        import textwrap
        flat_html = " ".join([line.strip() for line in textwrap.dedent(html_table).split("\n") if line.strip()])
        st.markdown(flat_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 경쟁사 분석 10위권 평균 vs 3위권 평균 설정
        top10_avg = {
            "n2": 0.512000,
            "save_raw": 5000,
            "rec_raw": 2500,
            "blog_raw": 1000,
            "recent_raw": 45,
            "func_raw": 1.0
        }
        
        top3_avg = {
            "n2": 0.538000,
            "save_raw": 25000,
            "rec_raw": 4500,
            "blog_raw": 1500,
            "recent_raw": 80,
            "func_raw": 1.0
        }
        
        # 제안서 빌드
        proposal = seo_calc.generate_proposal(
            store_name=store_name,
            keyword=keyword,
            current_rank=my_dyn_rank, # 동적 정렬 순위로 자동 전달!!
            my_metrics=my_metrics,
            top3_avg=top3_avg,
            top10_avg=top10_avg,
            my_n1=n1_score,
            my_n2=n2_score,
            my_n3=n3_score
        )
        
        st.markdown('<div class="s-card"><h3>📋 AI 진단 단계 판정</h3>', unsafe_allow_html=True)
        st.info(f"📍 현재 진단 타겟: **{proposal['target_stage']}**")
        
        st.markdown("**권장 Action Item**")
        for act in proposal["action_items"][:2]:
            st.markdown(f"- ✅ {act}")
            
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="s-card"><h3>👑 대행사용 원클릭 영업 제안서</h3>', unsafe_allow_html=True)
        st.text_area("클라이언트 영업용 제안서 (복사 가능)", value=proposal["proposal_text"], height=350)
        st.markdown('</div>', unsafe_allow_html=True)
