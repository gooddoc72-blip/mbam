export const fetchWithAuth = async (url, options = {}) => {
  let token = null;
  if (typeof window !== "undefined") {
    // Phase 3 로그인 시 'mbam_token' 키로 저장하도록 수정됨
    token = localStorage.getItem("mbam_token");
    
    // 만약 이전 버전의 access_token이 남아있다면 호환성을 위해 체크
    if (!token) {
        token = localStorage.getItem("access_token");
    }
  }
  const headers = { ...options.headers };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const RELOAD_ONCE_KEY = "mbam_reauth_reloaded";
  const response = await fetch(url, { ...options, headers, credentials: "include" });
  if (response.ok && typeof window !== "undefined") {
    // 정상 응답이 오면 재인증 시도 표시를 지운다(다음에 진짜 만료되면 다시 한 번 시도하도록).
    try { sessionStorage.removeItem(RELOAD_ONCE_KEY); } catch (e) {}
  }
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("mbam_token");
      localStorage.removeItem("access_token");
      // 설치형(카페·블로그 전용판)에는 로그인 페이지가 없다. 토큰만 비우고 새로고침하면
      // AuthGuard 가 이 PC 전용 세션을 다시 받아온다.
      //
      // ⚠ 단, 무조건 새로고침하면 안 된다. 토큰과 무관한 이유로 401 이 나는 엔드포인트가
      //   하나라도 있으면 (새로고침 → 재요청 → 401 → 새로고침) 무한 루프가 되어
      //   화면이 계속 깜박이고 아무것도 클릭할 수 없게 된다. 실제로 그런 일이 있었다.
      //   (원인은 /api/proxy 의 교차 출처 리다이렉트로 Authorization 헤더가 벗겨진 것)
      //   그래서 새로고침은 한 번만 시도하고, 그 뒤에도 401 이면 조용히 오류로 넘긴다.
      if (process.env.NEXT_PUBLIC_PRODUCT === "cafe" || process.env.NEXT_PUBLIC_PRODUCT === "blog") {
        let already = false;
        try { already = sessionStorage.getItem(RELOAD_ONCE_KEY) === "1"; } catch (e) {}
        if (!already) {
          try { sessionStorage.setItem(RELOAD_ONCE_KEY, "1"); } catch (e) {}
          window.location.reload();
        } else {
          console.error("[auth] 재인증 후에도 401 — 새로고침을 중단합니다:", url);
        }
      } else if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    // 리다이렉트로 끝내고, 호출부가 빈/HTML 401 body를 res.json()하다 터지지 않도록 중단
    throw new Error("UNAUTHORIZED");
  }
  return response;
};

// [방법 B] 에이전트 모드 응답({mode:'agent', job_id})을 폴링해 로컬 실행 결과를 받아온다.
export const pollAgentJob = async (jobId, { tries = 100, intervalMs = 3000 } = {}) => {
  for (let i = 0; i < tries; i++) {
    await new Promise((r) => setTimeout(r, intervalMs));
    const res = await fetchWithAuth(`/api/agent/jobs/${jobId}`);
    if (!res.ok) continue;
    const info = await res.json();
    if (info.status === "done") return info.result || {};
    if (info.status === "error") throw new Error(info.error || "에이전트 작업이 실패했습니다.");
    // queued/running/not_found → 계속 대기
  }
  throw new Error("에이전트 응답 시간 초과입니다. 내 PC의 로컬 프로그램(에이전트)이 실행 중인지 확인해 주세요.");
};

// 응답이 에이전트 모드면 폴링 결과로, 아니면 그대로 반환.
export const resolveMaybeAgent = async (data, opts) => {
  if (data && data.mode === "agent" && data.job_id) {
    return await pollAgentJob(data.job_id, opts);
  }
  return data;
};
