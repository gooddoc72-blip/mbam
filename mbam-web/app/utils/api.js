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
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    // 리다이렉트로 끝내고, 호출부가 빈/HTML 401 body를 res.json()하다 터지지 않도록 중단
    throw new Error("UNAUTHORIZED");
  }
  return response;
};
