"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

// 공개 라우트 (비로그인 접근 허용) — 실제 회원가입 경로는 /signup
const PUBLIC_PATHS = ["/login", "/register", "/signup", "/"];

export default function AuthGuard({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const isPublicPath = PUBLIC_PATHS.includes(pathname);

    const token = localStorage.getItem("mbam_token") || localStorage.getItem("access_token");

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

  // 인증 전이거나 비인가 상태면 내용 숨김 (깜빡임 방지)
  if (!authorized && !PUBLIC_PATHS.includes(pathname)) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", background: "#f8fafc" }}>
        <div style={{ fontSize: "1.2rem", color: "#64748b" }}>인증 정보를 확인하는 중...</div>
      </div>
    );
  }

  return <>{children}</>;
}
