"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

// 토스 카드 등록 실패·취소 시 돌아오는 페이지 — 결제는 일어나지 않았다.
function FailInner() {
  const params = useSearchParams();
  const message = params.get("message") || "카드 등록이 취소되었습니다.";
  return (
    <div style={{ maxWidth: 520, margin: "4rem auto", padding: "2rem", background: "white", borderRadius: 24, border: "1px solid #e2e8f0", textAlign: "center", fontFamily: "sans-serif" }}>
      <h1 style={{ fontSize: "1.4rem", fontWeight: 800, margin: "0 0 1rem 0" }}>카드 등록 실패</h1>
      <p style={{ color: "#ef4444", margin: "0 0 0.5rem 0" }}>{message}</p>
      <p style={{ color: "#64748b", fontSize: "0.85rem", margin: "0 0 1.5rem 0" }}>결제는 진행되지 않았습니다.</p>
      <a href="/billing" style={{ display: "inline-block", padding: "0.7rem 1.6rem", background: "#0f172a", color: "white", borderRadius: 10, fontWeight: 700, textDecoration: "none" }}>
        다시 시도하기
      </a>
    </div>
  );
}

export default function BillingFailPage() {
  return (
    <Suspense fallback={null}>
      <FailInner />
    </Suspense>
  );
}
