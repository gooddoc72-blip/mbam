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
  const response = await fetch(url, { ...options, headers, credentials: "include" });
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("mbam_token");
      localStorage.removeItem("access_token");
      if (window.location.pathname !== "/login") {
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
