"use client";
import { useState, useEffect } from "react";
import { fetchWithAuth } from "../utils/api";
import { Check, AlertCircle, CreditCard, Zap, Crown, Star } from "lucide-react";

export default function BillingPage() {
  const [userInfo, setUserInfo] = useState(null);
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetchWithAuth('/api/auth/me').then(res => res.ok ? res.json() : null),
      fetch('/api/admin/plans').then(res => res.ok ? res.json() : [])
    ])
    .then(([userData, plansData]) => {
      setUserInfo(userData);
      setPlans(plansData);
    })
    .catch(err => console.error(err))
    .finally(() => setLoading(false));
  }, []);

  const handleUpgrade = (planName) => {
    alert(`[${planName}] 플랜 결제 모듈 연동 준비 중입니다. 관리자에게 문의해주세요.`);
  };

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
              {userInfo.plan_type === 'trial' ? '무료 체험판 (Trial)' : `유료 플랜 (${userInfo.plan_type})`}
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
          <p style={{ fontSize: "0.9rem", color: "#64748b", marginBottom: "1rem" }}>현재 등록된 결제 수단이 없습니다.</p>
          <button style={{ padding: "0.6rem 1.5rem", background: "#0f172a", color: "white", fontSize: "0.9rem", fontWeight: "700", borderRadius: "8px", border: "none", cursor: "pointer", boxShadow: "0 4px 6px rgba(0,0,0,0.1)" }}>
            결제 수단 등록
          </button>
        </div>
      </div>

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
              
              <button 
                onClick={() => handleUpgrade(plan.name)}
                style={{ width: "100%", padding: "1rem", borderRadius: "12px", fontWeight: "700", color: "white", background: colorTheme.btnBg, border: "none", cursor: "pointer", fontSize: "1rem", boxShadow: "0 4px 6px rgba(0,0,0,0.1)" }}
              >
                {plan.name} 선택하기
              </button>
            </div>
          )
        })}
      </div>
    </div>
  );
}
