"use client";
import { useState, useEffect } from "react";
import { fetchWithAuth } from "../utils/api";
import { Check, AlertCircle, CreditCard, Zap, Crown, Star } from "lucide-react";

export default function BillingPage() {
  const [userInfo, setUserInfo] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [billingCfg, setBillingCfg] = useState({ enabled: false });
  const [billing, setBilling] = useState({ subscription: null, payments: [] });
  const [busy, setBusy] = useState(false);

  const loadBilling = () =>
    fetchWithAuth('/api/billing/me').then(res => res.ok ? res.json() : null)
      .then(data => data && setBilling(data)).catch(() => {});

  useEffect(() => {
    Promise.all([
      fetchWithAuth('/api/auth/me').then(res => res.ok ? res.json() : null),
      fetch('/api/admin/plans').then(res => res.ok ? res.json() : []),
      fetchWithAuth('/api/billing/config').then(res => res.ok ? res.json() : { enabled: false }),
    ])
    .then(([userData, plansData, cfg]) => {
      setUserInfo(userData);
      setPlans(plansData);
      setBillingCfg(cfg || { enabled: false });
    })
    .catch(err => console.error(err))
    .finally(() => setLoading(false));
    loadBilling();
  }, []);

  const sub = billing.subscription;
  const subLive = sub && ["active", "past_due", "canceled"].includes(sub.status);

  // 토스페이먼츠 SDK(v2) — 결제 버튼을 누를 때 한 번만 불러온다
  const loadToss = () => new Promise((resolve, reject) => {
    if (window.TossPayments) return resolve(window.TossPayments);
    const s = document.createElement("script");
    s.src = "https://js.tosspayments.com/v2/standard";
    s.onload = () => resolve(window.TossPayments);
    s.onerror = () => reject(new Error("결제 모듈을 불러오지 못했습니다."));
    document.head.appendChild(s);
  });

  const handleUpgrade = async (plan) => {
    if (!billingCfg.enabled) {
      alert(`[${plan.name}] 플랜은 관리자에게 문의해 주세요.`);
      return;
    }
    if (subLive && sub.status !== "past_due" && !confirm(
      `${plan.name} 요금제로 변경할까요?\n카드를 다시 등록하면 다음 결제일부터 ₩${plan.price.toLocaleString()} 이 결제됩니다.`)) return;
    try {
      setBusy(true);
      const TossPayments = await loadToss();
      const payment = TossPayments(billingCfg.client_key).payment({ customerKey: billingCfg.customer_key });
      // 카드 등록창 → 성공 시 /billing/success 로 돌아와 서버가 첫 결제를 진행한다
      await payment.requestBillingAuth({
        method: "CARD",
        successUrl: `${window.location.origin}/billing/success?plan=${encodeURIComponent(plan.id)}`,
        failUrl: `${window.location.origin}/billing/fail`,
        customerEmail: billingCfg.email,
        customerName: billingCfg.name || billingCfg.email,
      });
    } catch (e) {
      // 사용자가 창을 닫은 경우(USER_CANCEL)는 조용히 넘긴다
      if (e?.code !== "USER_CANCEL") alert(e?.message || "결제창을 열지 못했습니다.");
    } finally {
      setBusy(false);
    }
  };

  const callBilling = async (path) => {
    setBusy(true);
    try {
      const res = await fetchWithAuth(`/api/billing/${path}`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      alert(data.message || data.detail || (res.ok ? "처리되었습니다." : "처리하지 못했습니다."));
      await loadBilling();
    } finally {
      setBusy(false);
    }
  };

  const fmtDate = (iso) => iso ? new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleDateString() : "-";
  const STATUS_KR = { active: "자동결제 중", canceled: "해지 예약", past_due: "결제 실패 · 재시도 중", ended: "종료" };

  if (loading) return <div style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>정보를 불러오는 중입니다...</div>;
  if (!userInfo) return <div style={{ padding: "2rem", textAlign: "center", color: "#ef4444" }}>사용자 정보를 불러올 수 없습니다.</div>;

  const quotaPercentage = userInfo.max_usage > 0 
    ? Math.min((userInfo.usage_count / userInfo.max_usage) * 100, 100).toFixed(1) 
    : 0;

  return (
    <div style={{ minHeight: "100vh", padding: "2rem", maxWidth: "1100px", margin: "0 auto", fontFamily: "sans-serif", color: "#1e293b" }}>
      <div style={{ textAlign: "center", marginBottom: "3rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: "800", letterSpacing: "-0.5px", margin: "0 0 0.5rem 0" }}>결제 및 플랜 관리</h1>
        <p style={{ color: "#64748b", margin: 0 }}>마케팅연구소의 강력한 기능들을 제한 없이 경험해 보세요.</p>
      </div>

      {/* 내 요금제 현황 */}
      <div style={{ background: "white", padding: "2rem", borderRadius: "24px", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.05)", border: "1px solid #e2e8f0", marginBottom: "3rem", display: "flex", flexWrap: "wrap", gap: "2rem", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ flex: "1 1 500px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.5rem" }}>
            <h2 style={{ fontSize: "1.3rem", fontWeight: "700", margin: 0 }}>현재 이용 중인 플랜:</h2>
            <span style={{ 
              padding: "0.3rem 1rem", borderRadius: "99px", fontSize: "0.9rem", fontWeight: "700",
              background: userInfo.plan_type === 'trial' ? "#fef3c7" : "#dcfce3",
              color: userInfo.plan_type === 'trial' ? "#d97706" : "#16a34a"
            }}>
              {userInfo.plan_type === 'trial' ? '무료 체험판 (Trial)'
                : userInfo.plan_type === 'expired' ? '이용 기간 종료'
                : `유료 플랜 (${userInfo.plan_type})`}
            </span>
          </div>
          <p style={{ color: "#64748b", fontSize: "0.95rem", marginBottom: "1.5rem" }}>
            {userInfo.plan_type === 'trial' && userInfo.trial_ends_at 
              ? `체험 기한: ${new Date(userInfo.trial_ends_at).toLocaleDateString()} 까지`
              : '제한 없이 이용 가능한 쿼터제입니다.'}
          </p>

          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.95rem", fontWeight: "700", color: "#334155", marginBottom: "0.5rem" }}>
            <span>이번 달 사용량</span>
            <span><span style={{ color: "#3b82f6", fontSize: "1.2rem" }}>{userInfo.usage_count}</span> / {userInfo.max_usage}회</span>
          </div>
          <div style={{ width: "100%", background: "#f1f5f9", borderRadius: "99px", height: "16px", overflow: "hidden", boxShadow: "inset 0 2px 4px rgba(0,0,0,0.05)" }}>
            <div style={{ 
              height: "100%", borderRadius: "99px", transition: "width 1s ease-out",
              background: quotaPercentage >= 90 ? "#ef4444" : quotaPercentage >= 70 ? "#f59e0b" : "linear-gradient(to right, #3b82f6, #2563eb)",
              width: `${quotaPercentage}%`
            }}></div>
          </div>
          {quotaPercentage >= 100 && (
            <div style={{ marginTop: "0.8rem", display: "flex", alignItems: "center", gap: "0.4rem", color: "#ef4444", fontSize: "0.9rem", fontWeight: "600" }}>
              <AlertCircle size={16} /> 쿼터를 모두 소진하였습니다. 원활한 이용을 위해 플랜을 업그레이드 해주세요.
            </div>
          )}
        </div>
        
        <div style={{ flex: "0 0 auto", minWidth: "250px", background: "#f8fafc", padding: "1.5rem", borderRadius: "16px", border: "1px solid #f1f5f9", textAlign: "center" }}>
          <CreditCard size={32} color="#94a3b8" style={{ margin: "0 auto 0.8rem auto" }} />
          {subLive ? (
            <>
              <p style={{ fontSize: "0.95rem", fontWeight: "700", margin: "0 0 0.3rem 0" }}>
                {sub.card_company || "카드"} {sub.card_number || ""}
              </p>
              <p style={{ fontSize: "0.85rem", color: sub.status === "active" ? "#16a34a" : "#d97706", fontWeight: "700", margin: "0 0 0.3rem 0" }}>
                {STATUS_KR[sub.status]}
              </p>
              <p style={{ fontSize: "0.85rem", color: "#64748b", margin: "0 0 1rem 0" }}>
                {sub.status === "canceled"
                  ? `${fmtDate(sub.current_period_end)} 까지 이용`
                  : `다음 결제일 ${fmtDate(sub.next_billing_at)} · ₩${(sub.amount || 0).toLocaleString()}`}
              </p>
              {sub.status === "past_due" && sub.last_error && (
                <p style={{ fontSize: "0.8rem", color: "#ef4444", margin: "0 0 1rem 0" }}>{sub.last_error}</p>
              )}
              {sub.status === "canceled" ? (
                <button disabled={busy} onClick={() => callBilling("resume")}
                  style={{ padding: "0.6rem 1.5rem", background: "#16a34a", color: "white", fontSize: "0.9rem", fontWeight: "700", borderRadius: "8px", border: "none", cursor: "pointer" }}>
                  구독 계속하기
                </button>
              ) : (
                <button disabled={busy} onClick={() => confirm("구독을 해지할까요?\n남은 기간까지는 계속 이용할 수 있습니다.") && callBilling("cancel")}
                  style={{ padding: "0.6rem 1.5rem", background: "white", color: "#ef4444", fontSize: "0.9rem", fontWeight: "700", borderRadius: "8px", border: "1px solid #fecaca", cursor: "pointer" }}>
                  구독 해지
                </button>
              )}
            </>
          ) : (
            <p style={{ fontSize: "0.9rem", color: "#64748b", margin: 0, whiteSpace: "pre-line" }}>
              {billingCfg.enabled ? "아래에서 요금제를 고르면\n카드 등록 후 매월 자동결제됩니다." : "현재 등록된 결제 수단이 없습니다."}
            </p>
          )}
        </div>
      </div>

      {billing.payments.length > 0 && (
        <div style={{ background: "white", padding: "1.5rem 2rem", borderRadius: "24px", border: "1px solid #e2e8f0", marginBottom: "3rem" }}>
          <h2 style={{ fontSize: "1.1rem", fontWeight: "700", margin: "0 0 1rem 0" }}>결제 내역</h2>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
              <thead>
                <tr style={{ color: "#64748b", textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                  <th style={{ padding: "0.5rem" }}>일자</th><th style={{ padding: "0.5rem" }}>요금제</th>
                  <th style={{ padding: "0.5rem" }}>금액</th><th style={{ padding: "0.5rem" }}>결과</th><th style={{ padding: "0.5rem" }}>영수증</th>
                </tr>
              </thead>
              <tbody>
                {billing.payments.map(p => (
                  <tr key={p.order_id} style={{ borderBottom: "1px solid #f1f5f9" }}>
                    <td style={{ padding: "0.5rem" }}>{fmtDate(p.created_at)}</td>
                    <td style={{ padding: "0.5rem" }}>{p.plan_id}</td>
                    <td style={{ padding: "0.5rem" }}>₩{(p.amount || 0).toLocaleString()}</td>
                    <td style={{ padding: "0.5rem", color: p.status === "DONE" ? "#16a34a" : "#ef4444" }} title={p.message || ""}>
                      {p.status === "DONE" ? "결제 완료" : "실패"}
                    </td>
                    <td style={{ padding: "0.5rem" }}>
                      {p.receipt_url ? <a href={p.receipt_url} target="_blank" rel="noreferrer" style={{ color: "#2563eb" }}>보기</a> : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 요금제 선택 */}
      <h2 style={{ fontSize: "1.6rem", fontWeight: "700", textAlign: "center", marginBottom: "2rem" }}>플랜 업그레이드</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "2rem" }}>
        {plans.map((plan, idx) => {
          const isPro = plan.id === "pro";
          const isEnterprise = plan.id === "enterprise";
          let Icon = Zap;
          let colorTheme = { bg: "#dbeafe", text: "#2563eb", border: "#e2e8f0", hoverBorder: "#93c5fd", btnBg: "#0f172a" };
          
          if (isPro) {
            Icon = Crown;
            colorTheme = { bg: "#f3e8ff", text: "#9333ea", border: "#a855f7", hoverBorder: "#a855f7", btnBg: "linear-gradient(to right, #9333ea, #4f46e5)" };
          } else if (isEnterprise) {
            Icon = Star;
            colorTheme = { bg: "#d1fae5", text: "#059669", border: "#e2e8f0", hoverBorder: "#6ee7b7", btnBg: "#0f172a" };
          }

          return (
            <div key={idx} style={{ 
              position: "relative", background: "white", borderRadius: "24px", padding: "2.5rem", 
              border: `2px solid ${colorTheme.border}`, transition: "all 0.3s ease",
              boxShadow: isPro ? "0 20px 25px -5px rgba(168, 85, 247, 0.15)" : "0 4px 6px -1px rgba(0,0,0,0.05)"
            }}
            onMouseOver={(e) => { if(!isPro) e.currentTarget.style.borderColor = colorTheme.hoverBorder; e.currentTarget.style.transform = "translateY(-5px)"; }}
            onMouseOut={(e) => { if(!isPro) e.currentTarget.style.borderColor = colorTheme.border; e.currentTarget.style.transform = "translateY(0)"; }}
            >
              {isPro && (
                <div style={{ position: "absolute", top: 0, left: "50%", transform: "translate(-50%, -50%)", background: "linear-gradient(to right, #9333ea, #4f46e5)", color: "white", padding: "0.3rem 1rem", borderRadius: "99px", fontSize: "0.75rem", fontWeight: "800", textTransform: "uppercase", letterSpacing: "1px" }}>
                  Most Popular
                </div>
              )}
              <div style={{ width: "60px", height: "60px", borderRadius: "16px", background: colorTheme.bg, color: colorTheme.text, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "1.5rem" }}>
                <Icon size={30} />
              </div>
              <h3 style={{ fontSize: "1.8rem", fontWeight: "800", margin: "0 0 0.5rem 0" }}>{plan.name}</h3>
              <p style={{ color: "#64748b", fontSize: "0.9rem", margin: "0 0 1.5rem 0", height: "40px" }}>{plan.desc}</p>
              <div style={{ marginBottom: "2rem" }}>
                <span style={{ fontSize: "2.5rem", fontWeight: "800" }}>₩{plan.price.toLocaleString()}</span>
                <span style={{ color: "#64748b", fontWeight: "600" }}>/월</span>
              </div>
              
              <ul style={{ listStyle: "none", padding: 0, margin: "0 0 2rem 0", display: "flex", flexDirection: "column", gap: "1rem" }}>
                {plan.features.map((feature, fIdx) => (
                  <li key={fIdx} style={{ display: "flex", alignItems: "flex-start", gap: "0.8rem" }}>
                    <div style={{ marginTop: "2px", background: "#dcfce3", color: "#16a34a", padding: "2px", borderRadius: "99px" }}><Check size={14} strokeWidth={3} /></div>
                    <span style={{ color: "#334155", fontSize: "0.95rem" }}>{feature}</span>
                  </li>
                ))}
              </ul>
              
              {(() => {
                const current = subLive && sub.status !== "canceled" && sub.plan_id === plan.id;
                return (
                  <button
                    onClick={() => handleUpgrade(plan)}
                    disabled={busy || current}
                    style={{ width: "100%", padding: "1rem", borderRadius: "12px", fontWeight: "700", color: "white", background: current ? "#94a3b8" : colorTheme.btnBg, border: "none", cursor: current ? "default" : "pointer", fontSize: "1rem", boxShadow: "0 4px 6px rgba(0,0,0,0.1)" }}
                  >
                    {current ? "이용 중" : subLive ? `${plan.name}로 변경` : `${plan.name} 선택하기`}
                  </button>
                );
              })()}
            </div>
          )
        })}
      </div>
    </div>
  );
}
