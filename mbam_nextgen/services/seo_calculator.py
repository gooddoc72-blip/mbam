import math
import random
import re

class SeoCalculator:
    """
    [Domain Service Layer]
    네이버 스마트플레이스 상위 노출 다차원 알고리즘 수식 계량 엔진 (N1~N4 지수)
    (Advanced Mathematical Model: Log Scaling, Temporal Decay, Wilson Score, Isolation Forest Penalty)
    """

    def __init__(self):
        # N1: Verification & Trust (영수증 검증)
        self.w1a = 0.60 # R_r: 영수증 누적 (Log)
        self.w1b = 0.25 # F_r: 영수증 최근 7일 빈도
        self.w1c = 0.15 # S_star: 윌슨 신뢰 구간 평점
        
        # N2: Engagement & Interaction (내부 탐색)
        self.w2a = 0.20 # I_f: 예상 유입률
        self.w2b = 0.40 # V_r: 리뷰/블로그 조회수 (Log)
        self.w2c = 0.20 # S_v: 저장수 최신 변화율
        self.w2d = 0.20 # T_d: 체류시간 (상대값)

        # N3: External Authority (외부 확산)
        self.w3a = 0.40 # R_b: 블로그 리뷰 수 (Log)
        self.w3b = 0.30 # V_b: 블로그 리뷰 조회수 (Log)
        self.w3c = 0.30 # C_rank: 블로그 출처 신뢰도

        # Final Weights
        self.W_fit = 0.10
        self.W_n1 = 0.35
        self.W_n2 = 0.35
        self.W_n3 = 0.20

    def wilson_score_lower_bound(self, positive: int, n: int, confidence=0.95) -> float:
        """별점 5점 비율의 윌슨 신뢰 구간 하한값 계산"""
        if n == 0:
            return 0.0
        z = 1.96
        phat = 1.0 * positive / n
        return (phat + z*z/(2*n) - z * math.sqrt((phat*(1-phat)+z*z/(4*n))/n))/(1+z*z/n)

    def temporal_decay(self, value: float, days_ago: int, is_new: bool = False) -> float:
        """시간 감쇄 함수 (7일 반감기 기준). 새로오픈 뱃지가 있으면 감쇄 방어(Boost)"""
        decay_constant = 0.1  # lambda
        if is_new:
            decay_constant = 0.02 # 신규 오픈은 과거 데이터가 없으므로 최신 데이터의 수명을 길게 유지
        return value * math.exp(-decay_constant * days_ago)

    def normalize(self, value: float, max_val: float) -> float:
        if max_val <= 0: return 0.0
        return max(0.0, min(1.0, value / max_val))

    def calculate_n1(self, reviews: int, recent_reviews: int, is_revisit: bool) -> float:
        """
        N1 [방문 검증]: 영수증 리뷰 수 기반 (Log + Wilson)
        - is_revisit이 True면 단골 충성도 가중치로 윌슨 스코어를 강제 부스팅
        """
        r_r = math.log1p(reviews) / math.log1p(10000) # Max 10,000 for scaling
        f_r = self.normalize(recent_reviews, 50.0) # 최근 7일 50개면 만점
        
        positive_est = int(reviews * 0.9)
        s_star = self.wilson_score_lower_bound(positive_est, reviews)
        
        if is_revisit:
            s_star = min(1.0, s_star + 0.15) # 재방문 뱃지의 폭발적 가중치
            
        n1 = self.w1a * r_r + self.w1b * f_r + self.w1c * s_star
        return round(max(0.0, min(1.0, n1)), 6)

    def calculate_n2(self, saves_delta: int, is_new: bool, views: int = 0) -> float:
        """
        N2 [내부 탐색]: 예상 트래픽(조회수) 및 저장수 기반
        """
        v_r = math.log1p(views) / math.log1p(50000)
        s_v = self.temporal_decay(self.normalize(saves_delta, 100.0), days_ago=1, is_new=is_new)
        
        i_f = 0.7 if is_new else 0.5 
        t_d = 0.8 if is_new else 0.6
        
        n2 = self.w2a * i_f + self.w2b * v_r + self.w2c * s_v + self.w2d * t_d
        return round(max(0.0, min(1.0, n2)), 6)

    def calculate_n3(self, blog_reviews: int, recent_blogs: int) -> float:
        """
        N3 [외부 확산]: 블로그 바이럴 지표
        """
        r_b = math.log1p(blog_reviews) / math.log1p(5000)
        v_b = math.log1p(blog_reviews * 100) / math.log1p(500000) # 가상 조회수 추정
        c_rank = self.normalize(recent_blogs, 20.0) # 최근 양질의 블로그 20개 기준
        
        n3 = self.w3a * r_b + self.w3b * v_b + self.w3c * c_rank
        return round(max(0.0, min(1.0, n3)), 6)

    def calculate_n4(self, saves_delta: int, total_saves: int, reviews_delta: int, total_reviews: int) -> float:
        """
        N4 [일상 트래픽 품질 & 성장성 지수]: 유기적인 증감량 밸런스를 측정하여 25점 만점의 가산점 부여
        """
        penalty = 1.0
        
        # 0. 평상시 성장성 (Growth Quality) 체크
        if saves_delta == 0 and reviews_delta == 0:
            penalty = 0.90 # 성장이 완전히 정체된 경우 (가벼운 패널티)
        else:
            balance = saves_delta / max(1, reviews_delta)
            if balance > 10.0:
                penalty = 0.93 # 리뷰 대비 저장이 과도하게 많은 불균형
            elif balance < 0.2:
                penalty = 0.95 # 저장 대비 리뷰가 과도하게 많은 불균형
            else:
                penalty = 1.00 # 건강한 밸런스 성장은 만점
        
        # 1. 영수증 리뷰 조작 의심: 리뷰가 단기 50건 이상 폭증했으나 저장수는 5 미만일 때
        if reviews_delta > 50 and saves_delta < 5:
            ratio = reviews_delta / max(1, total_reviews)
            if ratio > 0.1: # 전체 체급의 10% 이상 비정상 급증 시
                penalty = min(penalty, max(0.1, 1.0 - (ratio * 1.5))) 
                
        # 2. 저장수 매크로 의심: 단기간 100건 이상 폭증 시
        if saves_delta > 100:
            ratio = saves_delta / max(1, total_saves)
            if ratio > 0.05: # 본인 체급의 5% 이상 튈 때부터 서서히 감점
                p_save = max(0.3, 1.0 - (ratio * 2.5))
                penalty = min(penalty, p_save)
                
        return round(max(0.0, min(1.0, penalty)), 6)

    def calculate_n5_total_score(self, s_fit: float, n1: float, n2: float, n3: float, n4: float, is_new: bool, is_revisit: bool, rank: int = 1) -> float:
        """
        N5 [종합 랭킹 총점]: N1~N4 점수 합산 및 버프 가산점 후, 순위 기반 역산 패널티를 적용하여 1.0 이하로 정규화
        """
        # s_fit은 기존 0.6 ~ 0.9
        base_sum = n1 + n2 + n3 + n4 + s_fit
        
        if is_new:
            base_sum += 1.2 # 새로오픈 버프 (압도적 가산점)
        if is_revisit:
            base_sum += 0.5 # 재방문 많은 버프 (단골 가산점)
            
        # N1~N4(4.0) + s_fit(0.9) + new(1.2) + rev(0.5) = Max 6.6
        # 1.0을 넘지 않도록 6.8로 나누어 정규화 (항상 0.xxxxxx 형태로 출력)
        total_score = base_sum / 6.8
        
        # 순위 기반 역산 패널티 (Rank Penalty): 1위는 패널티 0%, 순위가 낮아질수록 최대 50%까지 점수 하락
        rank_penalty = max(0.5, 1.0 - (rank - 1) * 0.02)
        final_score = total_score * rank_penalty
            
        return round(min(1.0, final_score), 6)

    def analyze_1st_advantage(self, my_data: dict, top1_data: dict) -> str:
        """
        1위 매장의 점수를 역산하여 내 매장과의 가장 큰 격차(장점)를 분석하는 컨설팅 엔진
        """
        if not my_data or not top1_data:
            return "데이터가 부족하여 비교할 수 없습니다."
            
        my_n5 = my_data.get("n5", 0)
        t1_n5 = top1_data.get("n5", 0)
        
        if my_n5 >= t1_n5:
            return f"현재 매장의 종합 점수(N5: {my_n5:.2f})가 1위와 대등하거나 높습니다. 현재의 밸런스를 유지하세요!"
        
        gaps = {
            "N1 (영수증 검증/단골)": top1_data.get("n1", 0) - my_data.get("n1", 0),
            "N2 (조회수/저장/신규)": top1_data.get("n2", 0) - my_data.get("n2", 0),
            "N3 (블로그 확산/C-Rank)": top1_data.get("n3", 0) - my_data.get("n3", 0)
        }
        
        best_metric = max(gaps, key=gaps.get)
        gap_val = gaps[best_metric]
        
        if gap_val <= 0:
            return "세부 지표(N1~N3)는 1위를 앞서고 있으나, 총점(N5) 조정을 위해 최신성 또는 어뷰징 필터(N4) 점검이 필요합니다."
            
        advice = ""
        if best_metric == "N1 (영수증 검증/단골)":
            advice = "꾸준한 주간 단위 영수증 리뷰(최신성)와 '재방문' 단골 유도 마케팅이 시급합니다."
        elif best_metric == "N2 (조회수/저장/신규)":
            advice = "실제 유저들의 썸네일 클릭(유입률)과 저장하기 액션을 늘려 내부 체류시간을 확보해야 합니다."
        elif best_metric == "N3 (블로그 확산/C-Rank)":
            advice = "C-Rank 점수가 높은 우수 블로거들의 질 좋은 포스팅 확산이 절대적으로 필요합니다."
            
        return f"1위 업체는 귀하의 매장보다 **{best_metric}** 지표에서 크게 앞서 1위를 차지했습니다. 1위를 탈환하려면 {advice}"

    # =====================================================================
    # [신규 엔진] 경쟁군 2-pass 군 정규화 기반 N1~N5 산출
    #   - 고정 분모 정규화 대신 "같은 키워드 경쟁군" 내부 Min-Max 정규화
    #   - rank 역주입 제거(순환 차단), N4는 곱셈 패널티
    #   - 신규오픈 부스트는 시간감쇄 곱셈(현재 개업일 미수집 → 고정 배율)
    #   - N5_eff(부스트/현 상태 반영) vs n5_organic(실력) 분리
    #   설계: docs/place_nscore_design.md
    # =====================================================================

    def _save_bucket_mid(self, v):
        """저장수는 네이버 미공개·버킷("12,000+","~100") → 숫자만 추출(대략 하한)."""
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return max(0, int(v))
        digits = re.sub(r"[^\d]", "", str(v))
        return int(digits) if digits else 0

    def _mean_std(self, arr):
        if not arr:
            return (0.0, 0.0)
        n = len(arr)
        m = sum(arr) / n
        var = sum((x - m) ** 2 for x in arr) / n
        return (m, var ** 0.5)

    def _new_open_boost(self, p):
        """신규오픈 부스트 B(t). 개업일 미수집이라 고정 배율로 근사(추후 e^-λt로 교체)."""
        if p.get("is_new"):
            return 1.5
        if p.get("has_revisit"):
            return 1.15
        return 1.0

    def _calc_n4(self, p, rd_mean, rd_std, rkd_mean, rkd_std):
        """
        어뷰징 필터(곱셈, 0~1). 유입·저장이 미공개라 직접측정 불가 →
        '순위는 비정상 급등(z_rank↑)인데 리뷰 증감은 평범/저조(z_rev↓)' 잔차로 역추적.
        신규오픈은 면제(부스트로 동일 패턴이 정상).
        """
        if p.get("is_new"):
            return 1.0
        rank_delta = p.get("rank_delta", 0)   # +면 순위 상승(개선)
        rev_delta = p.get("rev_delta", 0)
        z_rank = (rank_delta - rkd_mean) / rkd_std if rkd_std > 1e-9 else 0.0
        z_rev = (rev_delta - rd_mean) / rd_std if rd_std > 1e-9 else 0.0
        residual = z_rank - z_rev              # 순위만 튄 정도
        m = max(0.0, min(0.9, (residual - 1.5) / 3.0))  # residual>1.5부터 의심
        return round(1.0 - m, 6)

    def score_competitors(self, places: list, keyword: str) -> list:
        """
        경쟁군 전체(places)를 받아 군 내부 정규화로 N1~N5를 채워 반환한다.
        입력 dict 필요 키: name, category, visitor_reviews, blog_reviews, saves,
                           rev_delta, blog_delta, rank_delta, is_new, has_revisit
        추가 키: n1, n2, n3, n4, n5(=eff), n5_organic
        """
        if not places:
            return places

        kw_tokens = [t for t in re.split(r"\s+", (keyword or "").strip()) if t]

        def lg(x):
            try:
                return math.log1p(max(0.0, float(x)))
            except (TypeError, ValueError):
                return 0.0

        rev_logs = [lg(p.get("visitor_reviews", 0)) for p in places]
        blog_logs = [lg(p.get("blog_reviews", 0)) for p in places]
        save_logs = [lg(self._save_bucket_mid(p.get("saves", 0))) for p in places]
        revd_logs = [lg(max(0, p.get("rev_delta", 0))) for p in places]
        blogd_logs = [lg(max(0, p.get("blog_delta", 0))) for p in places]

        def mm(a):
            return (min(a), max(a)) if a else (0.0, 0.0)

        rev_lo, rev_hi = mm(rev_logs)
        blog_lo, blog_hi = mm(blog_logs)
        save_lo, save_hi = mm(save_logs)
        revd_hi = max(revd_logs) if revd_logs else 0.0
        blogd_hi = max(blogd_logs) if blogd_logs else 0.0

        def nrm(v, lo, hi):
            if hi - lo <= 1e-9:
                return 0.5
            return max(0.0, min(1.0, (v - lo) / (hi - lo)))

        def nrm0(v, hi):  # 증감(0~hi) 정규화
            if hi <= 1e-9:
                return 0.0
            return max(0.0, min(1.0, v / hi))

        rd_mean, rd_std = self._mean_std([p.get("rev_delta", 0) for p in places])
        rkd_mean, rkd_std = self._mean_std([p.get("rank_delta", 0) for p in places])

        for i, p in enumerate(places):
            # ── N1: 플레이스 정적 품질(키워드 적합도 중심) ──
            name = p.get("name") or ""
            cat = p.get("category") or ""
            name_match = (sum(1 for t in kw_tokens if t in name) / len(kw_tokens)) if kw_tokens else 0.0
            cat_match = 1.0 if any(t in cat for t in kw_tokens) else (0.5 if cat else 0.3)
            info_quality = p.get("info_quality", 0.5)  # 소개글/사진/예약 미수집 → 중립
            n1 = round(min(1.0, 0.45 * name_match + 0.30 * cat_match + 0.25 * info_quality), 6)

            boost = self._new_open_boost(p)

            # ── N2: 내부 인기(리뷰 누적+증감, 저장 약가중) ──
            r_acc = nrm(rev_logs[i], rev_lo, rev_hi)
            r_vel = nrm0(revd_logs[i], revd_hi)
            s_acc = nrm(save_logs[i], save_lo, save_hi)
            n2_org = round(min(1.0, 0.40 * r_acc + 0.35 * r_vel + 0.25 * s_acc), 6)
            n2 = round(min(1.0, 0.40 * min(1.0, r_acc * boost) + 0.35 * min(1.0, r_vel * boost) + 0.25 * s_acc), 6)

            # ── N3: 외부 확산(블로그) ──
            b_acc = nrm(blog_logs[i], blog_lo, blog_hi)
            b_vel = nrm0(blogd_logs[i], blogd_hi)
            c_rank = p.get("c_rank", 0.5)  # C-Rank 미수집 → 중립
            n3_org = round(min(1.0, 0.45 * b_acc + 0.25 * b_vel + 0.30 * c_rank), 6)
            n3 = round(min(1.0, 0.45 * min(1.0, b_acc * boost) + 0.25 * min(1.0, b_vel * boost) + 0.30 * c_rank), 6)

            # ── N4: 어뷰징 곱셈 필터 ──
            n4 = self._calc_n4(p, rd_mean, rd_std, rkd_mean, rkd_std)

            # ── N5: 종합 (rank 미사용) ──
            n5_eff = round(min(1.0, (0.30 * n1 + 0.40 * n2 + 0.30 * n3) * n4), 6)
            n5_org = round(min(1.0, 0.30 * n1 + 0.40 * n2_org + 0.30 * n3_org), 6)  # 부스트/조작 제거

            p["n1"], p["n2"], p["n3"], p["n4"], p["n5"] = n1, n2, n3, n4, n5_eff
            p["n5_organic"] = n5_org

        return places
