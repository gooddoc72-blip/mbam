"use client";
import { fetchWithAuth } from "../utils/api";
import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
    LayoutDashboard, FileText, TrendingUp, MapPin, 
    ShieldCheck, PenTool, Coffee, Search, MessageSquare, HeartHandshake, Zap
} from 'lucide-react';

export default function SaaS_Dashboard() {
  const [activeTab, setActiveTab] = useState("history_blog");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [userInfo, setUserInfo] = useState(null);

  const tabs = [
    { id: "history_blog", label: "블로그 자동화" },
    { id: "history_cafe", label: "카페 자동화" },
    { id: "scraped_trends", label: "쇼핑 트렌드" },
    { id: "place_rank_history", label: "플레이스 진단" },
    { id: "history_analysis", label: "정밀 분석 리포트" },
  ];

  const fetchHistory = async (tableName) => {
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/history/${tableName}`);
      if (res.status === 401) return;
      const json = await res.json();
      if (json.success) setData(json.data);
      else setData([]);
    } catch (err) {
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserInfo = async () => {
    try {
      const res = await fetchWithAuth('/api/auth/me');
      if (res.ok) {
        const json = await res.json();
        setUserInfo(json);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchUserInfo();
    fetchHistory(activeTab);
  }, [activeTab]);

  const quotaPercentage = userInfo && userInfo.max_usage > 0 
    ? Math.min((userInfo.usage_count / userInfo.max_usage) * 100, 100).toFixed(1) 
    : 0;
  
  const isTrial = userInfo?.plan_type === "trial";
  
  const MENU_CARDS = [
    { title: "SEO 정밀 분석", desc: "검색 상위 노출 벤치마킹", icon: TrendingUp, path: "/seo-analysis", bg: "linear-gradient(135deg, #3b82f6, #2563eb)" },
    { title: "플레이스 진단", desc: "N사 플레이스 순위 추적", icon: MapPin, path: "/place-seo", bg: "linear-gradient(135deg, #a855f7, #9333ea)" },
    { title: "쇼핑 순위 검색", desc: "상품 순위 트렌드 분석", icon: Search, path: "/shopping/rank", bg: "linear-gradient(135deg, #10b981, #059669)" },
    { title: "블로그 자동화", desc: "AI 기반 원고 자동 포스팅", icon: PenTool, path: "/blog-auto", bg: "linear-gradient(135deg, #f97316, #ea580c)" },
    { title: "카페 자동화", desc: "카페 자동 포스팅 및 소통", icon: Coffee, path: "/cafe-auto", bg: "linear-gradient(135deg, #f43f5e, #e11d48)" },
    { title: "멀티태스킹", desc: "통합 봇 동시 실행 관리", icon: Zap, path: "/multi-task", bg: "linear-gradient(135deg, #6366f1, #4f46e5)" }
  ];

  const renderRows = () => {
    if (data.length === 0) return <tr><td colSpan="3" style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>최근 기록이 없습니다.</td></tr>;
    return data.slice(0, 5).map((row, idx) => (
      <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9", transition: "background 0.2s" }} onMouseOver={e=>e.currentTarget.style.background="#f8fafc"} onMouseOut={e=>e.currentTarget.style.background="transparent"}>
        <td style={{ padding: "1rem", fontSize: "0.9rem", color: "#64748b" }}>{row.created_at}</td>
        <td style={{ padding: "1rem", color: "#1e293b", fontWeight: "600" }}>{row.target_keyword || row.cafe_name || row.place_name || row.keyword}</td>
        <td style={{ padding: "1rem" }}>
          <span style={{ 
            padding: "0.3rem 0.8rem", borderRadius: "99px", fontSize: "0.8rem", fontWeight: "700",
            background: row.status?.includes('성공') ? "#dcfce3" : "#dbeafe",
            color: row.status?.includes('성공') ? "#16a34a" : "#2563eb"
          }}>
            {row.status || '완료'}
          </span>
        </td>
      </tr>
    ));
  };

  return (
    <div style={{ minHeight: "100vh", padding: "2.5rem", maxWidth: "1200px", margin: "0 auto", fontFamily: "sans-serif", color: "#1e293b" }}>
      
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "2rem" }}>
        <div>
          <h1 style={{ fontSize: "2.2rem", fontWeight: "800", letterSpacing: "-1px", margin: "0 0 0.5rem 0" }}>대시보드</h1>
          <p style={{ color: "#64748b", margin: 0 }}>환영합니다! 마케팅 자동화 현황을 한눈에 확인하세요.</p>
        </div>
        {userInfo && (
          <div style={{ textAlign: "right" }}>
            <span style={{ 
              display: "inline-block", padding: "0.3rem 1rem", borderRadius: "99px", fontSize: "0.85rem", fontWeight: "800",
              background: isTrial ? "#fef3c7" : "#dcfce3", color: isTrial ? "#d97706" : "#16a34a"
            }}>
              {isTrial ? '무료 체험판 (Trial)' : `유료 플랜 (${userInfo.plan_type})`}
            </span>
          </div>
        )}
      </div>

      {/* 진행상황 (Progress Bar) */}
      {userInfo && userInfo.role !== "admin" && (
        <div style={{ background: "white", padding: "2rem", borderRadius: "24px", border: "1px solid #e2e8f0", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)", marginBottom: "3rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3 style={{ margin: 0, fontWeight: "700", fontSize: "1.1rem" }}>이번 달 쿼터 사용량</h3>
            <div style={{ fontSize: "1rem", fontWeight: "700", color: "#64748b" }}>
              <span style={{ color: "#3b82f6", fontSize: "1.3rem" }}>{userInfo.usage_count}</span> / {userInfo.max_usage} 회
            </div>
          </div>
          <div style={{ width: "100%", background: "#f1f5f9", borderRadius: "99px", height: "16px", marginBottom: "0.8rem", overflow: "hidden", boxShadow: "inset 0 2px 4px rgba(0,0,0,0.05)" }}>
            <div style={{ 
              height: "100%", borderRadius: "99px", transition: "width 1s ease",
              background: quotaPercentage >= 90 ? "#ef4444" : quotaPercentage >= 70 ? "#f59e0b" : "linear-gradient(to right, #3b82f6, #2563eb)", 
              width: `${quotaPercentage}%` 
            }}></div>
          </div>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8", textAlign: "right" }}>
            {isTrial && userInfo.trial_ends_at && `무료체험 만료일: ${new Date(userInfo.trial_ends_at).toLocaleDateString()}`}
          </p>
        </div>
      )}
      
      {/* 최고관리자 공지 */}
      {userInfo && userInfo.role === "admin" && (
        <div style={{ background: "#eff6ff", padding: "1.5rem 2rem", borderRadius: "16px", border: "1px solid #bfdbfe", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "3rem" }}>
          <div>
            <h3 style={{ margin: "0 0 0.3rem 0", fontWeight: "700", color: "#1e3a8a" }}>최고 관리자 계정 (Super Admin)</h3>
            <p style={{ margin: 0, fontSize: "0.9rem", color: "#1d4ed8" }}>모든 기능을 무제한으로 사용할 수 있습니다.</p>
          </div>
          <Link href="/admin" style={{ textDecoration: "none" }}>
            <button style={{ padding: "0.6rem 1.2rem", background: "#2563eb", color: "white", borderRadius: "8px", border: "none", fontWeight: "700", cursor: "pointer" }}>관리자 콘솔로 이동</button>
          </Link>
        </div>
      )}

      {/* 빠른 실행 메뉴 */}
      <div style={{ marginBottom: "4rem" }}>
        <h2 style={{ fontSize: "1.4rem", fontWeight: "800", marginBottom: "1.5rem" }}>빠른 실행 메뉴</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
          {MENU_CARDS.map((card, idx) => {
            const Icon = card.icon;
            return (
              <Link href={card.path} key={idx} style={{ textDecoration: "none", color: "inherit" }}>
                <div 
                  style={{ 
                    background: "white", padding: "1.5rem", borderRadius: "20px", border: "1px solid #f1f5f9",
                    display: "flex", alignItems: "center", gap: "1.2rem", cursor: "pointer",
                    boxShadow: "0 4px 6px -1px rgba(0,0,0,0.02)", transition: "all 0.3s ease"
                  }}
                  onMouseOver={(e) => { e.currentTarget.style.transform = "translateY(-5px)"; e.currentTarget.style.boxShadow = "0 10px 15px -3px rgba(0,0,0,0.1)"; }}
                  onMouseOut={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = "0 4px 6px -1px rgba(0,0,0,0.02)"; }}
                >
                  <div style={{ padding: "1rem", borderRadius: "16px", background: card.bg, color: "white", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "inset 0 2px 4px rgba(255,255,255,0.3)" }}>
                    <Icon size={26} />
                  </div>
                  <div>
                    <h3 style={{ margin: "0 0 0.3rem 0", fontSize: "1.1rem", fontWeight: "800" }}>{card.title}</h3>
                    <p style={{ margin: 0, fontSize: "0.9rem", color: "#64748b" }}>{card.desc}</p>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </div>

      {/* 최근 작업 내역 */}
      <div style={{ background: "white", borderRadius: "24px", border: "1px solid #e2e8f0", overflow: "hidden", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.02)" }}>
        <div style={{ padding: "1.5rem 2rem", borderBottom: "1px solid #f1f5f9" }}>
          <h2 style={{ fontSize: "1.4rem", fontWeight: "800", margin: "0 0 1rem 0" }}>최근 작업 내역</h2>
          <div style={{ display: "flex", gap: "0.8rem", overflowX: "auto", paddingBottom: "0.5rem" }}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{ 
                  padding: "0.5rem 1.2rem", borderRadius: "99px", fontSize: "0.9rem", fontWeight: "600", cursor: "pointer", border: "none",
                  background: activeTab === tab.id ? "#0f172a" : "#f1f5f9",
                  color: activeTab === tab.id ? "white" : "#475569",
                  transition: "all 0.2s"
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#f8fafc", color: "#64748b", fontSize: "0.9rem" }}>
                <th style={{ padding: "1rem 2rem", fontWeight: "600" }}>일시</th>
                <th style={{ padding: "1rem 2rem", fontWeight: "600" }}>대상 키워드 / 상호명</th>
                <th style={{ padding: "1rem 2rem", fontWeight: "600" }}>상태</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="3" style={{ textAlign: "center", padding: "3rem", color: "#94a3b8" }}>데이터를 불러오는 중입니다...</td></tr>
              ) : (
                renderRows()
              )}
            </tbody>
          </table>
          <div style={{ padding: "1rem", textAlign: "center", background: "#f8fafc", borderTop: "1px solid #f1f5f9" }}>
            <span style={{ fontSize: "0.9rem", color: "#3b82f6", fontWeight: "700", cursor: "pointer" }}>모든 내역 보기 &rarr;</span>
          </div>
        </div>
      </div>
      
    </div>
  );
}
