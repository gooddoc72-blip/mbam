"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchWithAuth } from "../../utils/api";

// 토스 카드 등록 성공 후 돌아오는 페이지 — authKey 로 서버가 빌링키 발급 + 첫 결제를 한다.
function SuccessInner() {
  const params = useSearchParams();
  const [state, setState] = useState({ phase: "loading", message: "결제를 진행하고 있습니다. 창을 닫지 마세요..." });
  const sent = useRef(false); // 개발 모드에서 effect 가 두 번 돌아도 결제 요청은 한 번만

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    const authKey = params.get("authKey");
    const customerKey = params.get("customerKey");
    const plan = params.get("plan");
    if (!authKey || !customerKey || !plan) {
      setState({ phase: "error", message: "결제 정보가 올바르지 않습니다. 다시 시도해 주세요." });
      return;
    }
    fetchWithAuth("/api/billing/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auth_key: authKey, customer_key: customerKey, plan_id: plan }),
    })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        setState(res.ok
          ? { phase: "done", message: data.message || "결제가 완료되었습니다." }
          : { phase: "error", message: data.detail || "결제에 실패했습니다." });
      })
      .catch(() => setState({ phase: "error", message: "서버에 연결할 수 없습니다. 잠시 후 결제 내역을 확인해 주세요." }));
  }, [params]);

  const color = state.phase === "error" ? "#ef4444" : state.phase === "done" ? "#16a34a" : "#334155";
  return (
    <div style={{ maxWidth: 520, margin: "4rem auto", padding: "2rem", background: "white", borderRadius: 24, border: "1px solid #e2e8f0", textAlign: "center", fontFamily: "sans-serif" }}>
      <h1 style={{ fontSize: "1.4rem", fontWeight: 800, margin: "0 0 1rem 0" }}>
        {state.phase === "done" ? "결제 완료" : state.phase === "error" ? "결제 실패" : "결제 진행 중"}
      </h1>
      <p style={{ color, whiteSpace: "pre-line", margin: "0 0 1.5rem 0" }}>{state.message}</p>
      {state.phase !== "loading" && (
        <a href="/billing" style={{ display: "inline-block", padding: "0.7rem 1.6rem", background: "#0f172a", color: "white", borderRadius: 10, fontWeight: 700, textDecoration: "none" }}>
          결제 및 플랜 관리로 돌아가기
        </a>
      )}
    </div>
  );
}

export default function BillingSuccessPage() {
  return (
    <Suspense fallback={null}>
      <SuccessInner />
    </Suspense>
  );
}
