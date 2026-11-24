"use client";
import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { HOME_PATH } from "../utils/product";

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // URL에 token 파라미터가 있으면 (소셜 로그인 콜백으로 리다이렉트된 경우)
    const token = searchParams.get("token");
    if (token) {
      localStorage.setItem("mbam_token", token);
      router.push(HOME_PATH);
      return;
    }
    // 소셜 로그인 실패로 돌아온 경우(?error=...) — 예전에는 아무 표시 없이 로그인 화면만 다시 떠서 원인을 알 수 없었다
    const err = searchParams.get("error");
    if (err) {
      const NAMES = { google: "구글", kakao: "카카오", naver: "네이버" };
      const [prov, ...rest] = err.split("_");
      const kind = rest.join("_");
      const who = NAMES[prov] || "소셜";
      const MSG = {
        not_configured: `${who} 로그인이 아직 준비되지 않았습니다. 이메일로 로그인하거나 다른 방법을 이용해 주세요.`,
        token_failed: `${who} 인증 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.`,
        user_failed: `${who} 계정 정보를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.`,
        json_failed: `${who} 응답을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.`,
      };
      setError(err === "invalid_state"
        ? "로그인 시간이 지났거나 다른 창에서 시작된 요청입니다. 다시 시도해 주세요."
        : MSG[kind] || "소셜 로그인에 실패했습니다. 다시 시도해 주세요.");
    }
  }, [searchParams, router]);

  const getBrowserHWID = () => {
    let hwid = localStorage.getItem("mbam_hwid");
    if (!hwid) {
        hwid = "web-hwid-" + Math.random().toString(36).substring(2, 15);
        localStorage.setItem("mbam_hwid", hwid);
    }
    return hwid;
  };

  const handleLocalLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const hwid = getBrowserHWID();
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password, hwid }),
      });

      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("mbam_token", data.access_token);
        router.push(HOME_PATH);
      } else {
        const errorData = await res.json();
        setError(errorData.detail || "로그인에 실패했습니다.");
      }
    } catch (err) {
      setError("서버와 통신할 수 없습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = (provider) => {
    window.location.href = `/api/auth/login/${provider}`;
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#f8fafc" }}>
      <div style={{ width: "100%", maxWidth: "400px", padding: "2.5rem", backgroundColor: "white", borderRadius: "16px", boxShadow: "0 10px 25px rgba(0,0,0,0.05)" }}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <h1 style={{ fontSize: "1.8rem", fontWeight: "800", color: "#1e293b", marginBottom: "0.5rem" }}>마케팅 연구소</h1>
          <p style={{ color: "#64748b", fontSize: "0.95rem" }}>로그인하고 자동화 서비스를 시작하세요</p>
        </div>

        {error && (
          <div style={{ padding: "0.8rem", backgroundColor: "#fef2f2", color: "#ef4444", borderRadius: "8px", fontSize: "0.85rem", marginBottom: "1.5rem", textAlign: "center" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleLocalLogin} style={{ display: "flex", flexDirection: "column", gap: "1.2rem", marginBottom: "1.5rem" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>이메일</label>
            <input 
              type="text" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="example@naver.com"
              style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #e2e8f0", outline: "none", boxSizing: "border-box" }}
              required
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: "600", color: "#475569", marginBottom: "0.5rem" }}>비밀번호</label>
            <input 
              type="password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{ width: "100%", padding: "0.8rem 1rem", borderRadius: "8px", border: "1px solid #e2e8f0", outline: "none", boxSizing: "border-box" }}
              required
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            style={{ width: "100%", padding: "0.9rem", backgroundColor: "#3b82f6", color: "white", border: "none", borderRadius: "8px", fontWeight: "600", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1, marginTop: "0.5rem" }}
          >
            {loading ? "로그인 중..." : "이메일 로그인"}
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", margin: "1.5rem 0", color: "#94a3b8", fontSize: "0.8rem" }}>
          <div style={{ flex: 1, height: "1px", backgroundColor: "#e2e8f0" }}></div>
          <span style={{ padding: "0 10px" }}>또는 3초 만에 소셜 로그인</span>
          <div style={{ flex: 1, height: "1px", backgroundColor: "#e2e8f0" }}></div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.8rem" }}>
          <button 
            onClick={() => handleSocialLogin('kakao')}
            style={{ width: "100%", padding: "0.9rem", backgroundColor: "#FEE500", color: "#000000", border: "none", borderRadius: "8px", fontWeight: "600", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}
          >
            <img src="https://developers.kakao.com/assets/img/about/logos/kakaolink/kakaolink_btn_small.png" alt="kakao" style={{ width: "18px" }} />
            카카오 로그인
          </button>
          
          <button 
            onClick={() => handleSocialLogin('naver')}
            style={{ width: "100%", padding: "0.9rem", backgroundColor: "#03C75A", color: "#FFFFFF", border: "none", borderRadius: "8px", fontWeight: "600", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}
          >
            <div style={{ fontWeight: "900", fontSize: "1.1rem", fontFamily: "Arial" }}>N</div>
            네이버 로그인
          </button>
          
          <button 
            onClick={() => handleSocialLogin('google')}
            style={{ width: "100%", padding: "0.9rem", backgroundColor: "#FFFFFF", color: "#3c4043", border: "1px solid #dadce0", borderRadius: "8px", fontWeight: "600", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}
          >
            {/* 외부(위키미디어) 이미지 직접 링크는 차단돼 깨져 보였다 — 로고를 인라인 SVG 로 넣는다 */}
            <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/>
              <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/>
              <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/>
              <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/>
            </svg>
            구글 로그인
          </button>
        </div>

        <div style={{ textAlign: "center", marginTop: "2rem", fontSize: "0.9rem", color: "#64748b" }}>
          계정이 없으신가요? <Link href="/signup" style={{ color: "#3b82f6", fontWeight: "600", textDecoration: "none" }}>회원가입</Link>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <LoginContent />
    </Suspense>
  );
}
