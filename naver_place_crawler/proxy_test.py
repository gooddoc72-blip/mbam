# -*- coding: utf-8 -*-
"""
프록시 업체 실측 비교 스크립트 (네이버/쿠팡 대상)

사용법:
  1) 각 업체 대시보드에서 발급받은 프록시 접속정보를 아래 PROVIDERS 에 입력하고
     "enabled": True 로 켠다. (형식: http://아이디:비번@게이트웨이:포트)
  2) 터미널에서:  python proxy_test.py
  3) 결과 표를 보고 성공률/차단율/한국IP여부/속도/데이터소모(=비용)를 비교한다.

측정 항목:
  - 공인 IP / 국가 / ISP (한국 IP 맞는지, 로테이션 되는지, 통신사 무엇인지)
  - 네이버 검색 접근 성공/차단
  - 쿠팡 검색 접근 성공/차단(Access Denied·CAPTCHA 감지)
  - 응답시간, 요청당 데이터량(MB) → GB당 단가로 실제 비용 환산

주의:
  - 이 스크립트는 requests 기반의 '1차 스크리닝'입니다. 여기서 통과한 업체를
    실제 크롤러(undetected_chromedriver)에 붙여 최종 검증하세요.
  - 인증 프록시를 uc/셀레니움에 붙이려면 selenium-wire 가 필요합니다(별도 안내).
"""

import time
import requests

# ─────────────────────────────────────────────────────────────
# 1) 업체별 프록시 접속정보 입력 (대시보드에서 발급)
#    residential 로테이팅 게이트웨이는 요청마다 IP가 자동 로테이션됩니다.
# ─────────────────────────────────────────────────────────────
PROVIDERS = {
    "Decodo": {
        # 예: 한국 타겟 게이트웨이 (대시보드에서 KR 엔드포인트/포트 확인)
        "proxy": "http://USER:PASS@kr.decodo.com:10000",
        "price_per_gb": 4.0,   # 확인 필요
        "enabled": False,
    },
    "DataImpulse": {
        "proxy": "http://USER:PASS@gw.dataimpulse.com:823",
        "price_per_gb": 1.0,   # 주거용 기준, 확인 필요
        "enabled": False,
    },
    "SOAX": {
        "proxy": "http://USER:PASS@proxy.soax.com:5000",
        "price_per_gb": 3.6,   # 확인 필요
        "enabled": False,
    },
}

ITERATIONS = 20            # 업체당 반복 횟수(로테이션·성공률 표본)
TIMEOUT = 20               # 요청 타임아웃(초)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
}

# ─────────────────────────────────────────────────────────────
# 2) 테스트 대상 및 성공/차단 판정
# ─────────────────────────────────────────────────────────────
KEYWORD = "강아지 사료"


def _proxies(p):
    return {"http": p, "https": p}


def check_ip(proxy):
    """프록시를 통한 공인 IP/국가/ISP 조회 (한국 IP·로테이션 확인용)."""
    try:
        r = requests.get(
            "http://ip-api.com/json/?fields=query,countryCode,city,isp",
            proxies=_proxies(proxy), headers=HEADERS, timeout=TIMEOUT,
        )
        j = r.json()
        return j.get("query"), j.get("countryCode"), j.get("isp")
    except Exception:
        return None, None, None


def test_naver(proxy):
    url = f"https://search.naver.com/search.naver?query={requests.utils.quote(KEYWORD)}"
    try:
        r = requests.get(url, proxies=_proxies(proxy), headers=HEADERS, timeout=TIMEOUT)
        blocked = (r.status_code in (403, 429)) or ("captcha" in r.url.lower())
        ok = (r.status_code == 200) and not blocked and (len(r.content) > 5000)
        return ok, r.status_code, len(r.content)
    except Exception:
        return False, "ERR", 0


def test_coupang(proxy):
    url = f"https://www.coupang.com/np/search?q={requests.utils.quote(KEYWORD)}&page=1"
    try:
        r = requests.get(url, proxies=_proxies(proxy), headers=HEADERS, timeout=TIMEOUT)
        body = r.text[:20000]
        blocked = (
            r.status_code in (403, 429)
            or "Access Denied" in body
            or "captcha" in r.url.lower()
            or "login" in r.url.lower()
        )
        # 쿠팡 상품이 실제로 보이는지(성공 신호)
        has_products = ("search-product" in body) or ("/vp/products/" in body)
        ok = (r.status_code == 200) and not blocked and has_products
        return ok, r.status_code, len(r.content)
    except Exception:
        return False, "ERR", 0


# ─────────────────────────────────────────────────────────────
# 3) 업체별 실측 실행
# ─────────────────────────────────────────────────────────────
def run_provider(name, cfg):
    proxy = cfg["proxy"]
    print(f"\n===== [{name}] 실측 시작 ({ITERATIONS}회) =====")

    ips = set()
    kr_count = 0
    isp_samples = set()
    naver_ok = naver_total = 0
    coupang_ok = coupang_total = 0
    bytes_total = 0
    latencies = []

    for i in range(1, ITERATIONS + 1):
        t0 = time.time()

        ip, cc, isp = check_ip(proxy)
        if ip:
            ips.add(ip)
            if cc == "KR":
                kr_count += 1
            if isp:
                isp_samples.add(isp)

        n_ok, n_code, n_bytes = test_naver(proxy)
        naver_total += 1
        naver_ok += 1 if n_ok else 0
        bytes_total += n_bytes

        c_ok, c_code, c_bytes = test_coupang(proxy)
        coupang_total += 1
        coupang_ok += 1 if c_ok else 0
        bytes_total += c_bytes

        latencies.append(time.time() - t0)
        print(f"  {i:>2}/{ITERATIONS} | IP={ip or '-':<15} {cc or '?':<3} "
              f"| 네이버={'O' if n_ok else 'X'}({n_code}) "
              f"| 쿠팡={'O' if c_ok else 'X'}({c_code})")
        time.sleep(1)  # 과도한 속도 방지

    mb = bytes_total / (1024 * 1024)
    gb = mb / 1024
    price = cfg.get("price_per_gb")
    cost_note = f"${gb * price:.4f} (@${price}/GB)" if price else "-"
    avg_lat = sum(latencies) / len(latencies) if latencies else 0

    return {
        "name": name,
        "unique_ip": len(ips),
        "kr_rate": f"{kr_count}/{ITERATIONS}",
        "isp": ", ".join(list(isp_samples)[:3]) or "-",
        "naver": f"{naver_ok}/{naver_total} ({naver_ok/naver_total*100:.0f}%)",
        "coupang": f"{coupang_ok}/{coupang_total} ({coupang_ok/coupang_total*100:.0f}%)",
        "avg_latency": f"{avg_lat:.1f}s",
        "data_mb": f"{mb:.1f}MB",
        "cost": cost_note,
    }


def main():
    results = []
    for name, cfg in PROVIDERS.items():
        if not cfg.get("enabled"):
            print(f"[스킵] {name} — enabled=False (접속정보 입력 후 켜세요)")
            continue
        if "USER:PASS" in cfg["proxy"]:
            print(f"[스킵] {name} — 프록시 접속정보를 아직 안 넣었습니다.")
            continue
        try:
            results.append(run_provider(name, cfg))
        except Exception as e:
            print(f"[{name}] 실행 오류: {e}")

    if not results:
        print("\n측정된 업체가 없습니다. PROVIDERS 에 접속정보를 넣고 enabled=True 로 켜세요.")
        return

    # 결과 요약표
    print("\n\n================= 실측 요약 =================")
    cols = ["name", "unique_ip", "kr_rate", "naver", "coupang", "avg_latency", "data_mb", "cost", "isp"]
    header = ["업체", "고유IP", "한국IP", "네이버성공", "쿠팡성공", "평균지연", "데이터", "비용(추정)", "통신사/ISP"]
    print(" | ".join(header))
    print("-" * 100)
    for r in results:
        print(" | ".join(str(r[c]) for c in cols))

    print("\n판단 기준:")
    print("  - 쿠팡 성공률이 핵심(가장 까다로움). 70%+ 면 실사용 가능선.")
    print("  - 고유IP 수가 반복횟수에 근접 = 로테이션 잘 됨.")
    print("  - 한국IP 비율이 낮으면 KR 타겟팅 설정을 확인.")
    print("  - 데이터(MB)로 실제 GB당 비용을 환산해 월 예상비용 계산.")


if __name__ == "__main__":
    main()
