"use client";
import AccountManager from "../../components/AccountManager";

// 계정 관리는 설정 페이지(/settings)에 바로 노출됩니다.
// 이 경로(/settings/accounts)는 직접 접근 시에도 동일 화면을 보여줍니다.
export default function AccountManagePage() {
  return (
    <div style={{ padding: "1rem", maxWidth: "1000px", margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#1e293b" }}>👤 네이버 계정 관리</h1>
        <a href="/settings" style={{ color: "#64748b", textDecoration: "none", fontSize: "0.9rem" }}>← 설정으로</a>
      </div>
      <AccountManager />
    </div>
  );
}
