"use client";
import { Users } from "lucide-react";
import AccountManager from "../components/AccountManager";

// 멀티 실행(순차 실행) 기능은 블로그/카페 포스팅 페이지로 이동했고,
// 이 메뉴는 '계정관리'(중앙 네이버 계정 풀 관리)로 전환되었습니다.
export default function AccountManagementPage() {
  return (
    <div style={{ padding: "2rem", display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div>
        <h1 style={{ fontSize: "1.6rem", fontWeight: "bold", color: "#1e293b", margin: 0, marginBottom: "0.5rem" }}>계정관리</h1>
        <p style={{ color: "#64748b", margin: 0 }}>
          네이버 계정을 등록·수정·삭제하고 기기 인증/블로그 주소를 관리합니다.
          여기에 저장된 계정은 <b>블로그·카페 포스팅에서 선택</b>하여 다계정 순차 실행에 사용됩니다.
        </p>
      </div>

      {/* 네이버 계정 관리 — 리스트 바로 노출 */}
      <div style={{ background: "white", padding: "1.5rem", border: "1px solid #cbd5e1", borderRadius: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1.2rem", paddingBottom: "0.8rem", borderBottom: "1px solid #e2e8f0" }}>
          <Users size={22} color="#0284c7" />
          <div>
            <h2 style={{ fontSize: "1.15rem", fontWeight: "700", color: "#334155", margin: 0 }}>네이버 계정 관리</h2>
            <p style={{ margin: "0.2rem 0 0", color: "#64748b", fontSize: "0.85rem" }}>계정 저장·수정·삭제, 등록일·인증여부 확인, 블로그 주소 설정 (블로그/카페 포스팅에서 추가한 계정도 여기에 표시됩니다)</p>
          </div>
        </div>
        <AccountManager />
      </div>
    </div>
  );
}
