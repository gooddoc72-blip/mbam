"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { IS_STANDALONE, BRAND_COLOR } from "../utils/product";

// 공개 라우트 (비로그인 접근 허용) — 실제 회원가입 경로는 /signup
const PUBLIC_PATHS = ["/login", "/register", "/signup", "/"];

export default function AuthGuard({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const isPublicPath = PUBLIC_PATHS.includes(pathname);
    const token = localStorage.getItem("mbam_token") || localStorage.getItem("access_token");

    // ── 설치형(카페·블로그 전용판): 회원가입·로그인 화면 없이 바로 사용 ──
    // 실행 전에 이미 '기기 승인'을 통과했으므로 여기서 또 로그인을 받을 이유가 없다.
    // 토큰이 없으면 이 PC 전용 세션을 자동으로 받아온다.
    if (IS_STANDALONE) {
      if (token) {
        setAuthorized(true);
        return;
      }
      let cancelled = false;
      (async () => {
        try {
          const res = await fetch("/api/auth/local-session", { method: "POST" });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          if (cancelled) return;
          localStorage.setItem("mbam_token", data.access_token);
          setAuthorized(true);
        } catch (e) {
          if (!cancelled) setAuthorized("error");
        }
      })();
      return () => { cancelled = true; };
    }

    if (!token && !isPublicPath) {
      // 인증되지 않은 사용자가 보호된 라우트에 접근할 경우
      setAuthorized(false);

      // 토큰 정리 (만약 이상한 토큰 찌꺼기가 남아있을 경우 대비)
      localStorage.removeItem("mbam_token");
      localStorage.removeItem("access_token");

      router.push("/login");
    } else {
      setAuthorized(true);
    }
  }, [pathname, router]);

  // 설치형에서 세션 발급이 실패한 경우 — 원인이 대부분 '백엔드 미기동'이라 그렇게 안내한다
  if (IS_STANDALONE && authorized === "error") {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", background: "#f8fafc" }}>
        <div style={{ textAlign: "center", maxWidth: "460px", padding: "2rem" }}>
          <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>⚠️</div>
          <h2 style={{ color: "#1e293b", marginBottom: "0.75rem" }}>프로그램을 준비하지 못했습니다</h2>
          <p style={{ color: "#64748b", lineHeight: 1.7, fontSize: "0.95rem" }}>
            내부 서버가 아직 켜지지 않았을 수 있습니다.<br />
            <strong>10초쯤 뒤에 이 페이지를 새로고침</strong>해 보세요.<br /><br />
            그래도 같으면 프로그램을 완전히 종료했다가 다시 실행해 주세요.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop: "1.5rem", padding: "0.7rem 1.6rem", background: BRAND_COLOR, color: "white", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.95rem", fontWeight: "bold" }}
          >
            새로고침
          </button>
        </div>
      </div>
    );
  }

  // 인증 전이거나 비인가 상태면 내용 숨김 (깜빡임 방지)
  if (!authorized && !PUBLIC_PATHS.includes(pathname)) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", background: "#f8fafc" }}>
        <div style={{ fontSize: "1.2rem", color: "#64748b" }}>
          {IS_STANDALONE ? "프로그램을 준비하는 중..." : "인증 정보를 확인하는 중..."}
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
